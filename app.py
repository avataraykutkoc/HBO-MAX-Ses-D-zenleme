import io
import json
import os
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import streamlit as st

# Streamlit Sayfa Yapılandırması
st.set_page_config(
    page_title="HepsiAd Portal", layout="wide", page_icon="🎁"
)

# Başlık Bölümü
col_title, col_author = st.columns([3, 1])
with col_title:
    st.title("🎁 HepsiAd - Otomatik Video & Ses Standartlaştırma Portalı")
with col_author:
    st.markdown(
        """
        <div style="background-color: #1E293B; padding: 10px; border-radius: 10px; border: 1px solid #3B82F6; text-align: center;">
            <p style="margin: 0; font-size: 11px; color: #94A3B8;">HepsiAd Tech Portal</p>
            <p style="margin: 0; font-weight: bold; color: #38BDF8;">👨‍💻 Creator: Aykut Koç</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def analyze_audio_lufs(video_url):
    """FFmpeg kullanarak verilen video URL'sinin LUFS ses seviyesini ölçer."""
    try:
        cmd = [
            "ffmpeg",
            "-i",
            video_url,
            "-af",
            "ebur128=framelog=verbose",
            "-f",
            "null",
            "-",
        ]
        result = subprocess.run(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        output = result.stderr

        # Integrated Loudness (LUFS) Yakala
        lufs_match = re.search(r"I:\s+([-\d.]+)\s+LUFS", output)
        integrated_lufs = float(lufs_match.group(1)) if lufs_match else None

        return integrated_lufs
    except Exception:
        return None


def extract_vast_details(xml_text):
    """XML içinden Medya URL'leri, VPAID durumu ve Video Boyutlarını çeker."""
    found_medias = []
    has_vpaid = False

    # VPAID Kontrolü
    if (
        "vpaid" in xml_text.lower()
        or "application/x-javascript" in xml_text.lower()
    ):
        has_vpaid = True

    try:
        xml_clean = re.sub(r'xmlns="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)

        for mf in root.findall(".//MediaFile"):
            url = mf.text.strip() if mf.text else ""
            width = mf.get("width")
            height = mf.get("height")
            media_type = mf.get("type", "")

            if "vpaid" in mf.get("apiFramework", "").lower() or ".js" in url:
                has_vpaid = True

            if url and (
                ".mp4" in url.lower() or "video" in media_type.lower()
            ):
                dim = f"{width}x{height}" if width and height else "Belirtilmemiş"
                found_medias.append({"url": url, "dimension": dim})
    except Exception:
        pass

    # Regex ile MP4 linklerini yedek olarak tara
    if not found_medias:
        regex_mp4 = re.findall(
            r"https?://[^\s\"'<>]+?\.(?:mp4)[^\s\"'<>]*", xml_text, re.IGNORECASE
        )
        for url in regex_mp4:
            clean_url = (
                url.replace("<![CDATA[", "")
                .replace("]]>", "")
                .replace("&amp;", "&")
            )
            found_medias.append({"url": clean_url, "dimension": "Bilinmiyor"})

    return found_medias, has_vpaid


def resolve_vast_and_get_media(vast_input, is_xml=False, max_redirects=5):
    """VAST zincirini takip eder."""
    if is_xml:
        medias, has_vpaid = extract_vast_details(vast_input)
        return {
            "medias": medias,
            "has_vpaid": has_vpaid,
            "xml": vast_input,
            "status": "ok" if medias else "no_media",
        }

    current_url = vast_input.strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    last_xml = ""
    visited = set()

    for _ in range(max_redirects):
        if current_url in visited:
            break
        visited.add(current_
