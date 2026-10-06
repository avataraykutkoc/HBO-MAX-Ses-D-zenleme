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

st.set_page_config(
    page_title="HepsiAd Portal", layout="wide", page_icon="🎁"
)

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


def check_black_borders(video_path_or_url):
    """FFmpeg cropdetect ile videoda siyah kenarlık (letterbox/pillarbox)
    olup olmadığını kontrol eder."""
    try:
        cmd = [
            "ffmpeg",
            "-ss",
            "00:00:02",
            "-i",
            video_path_or_url,
            "-vframes",
            "10",
            "-vf",
            "cropdetect=24:16:0",
            "-f",
            "null",
            "-",
        ]
        res = subprocess.run(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        out = res.stderr

        crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", out)
        if crops:
            w_crop, h_crop = int(crops[-1][0]), int(crops[-1][1])

            # Orijinal Çözünürlüğü Yakala
            res_m = re.search(r"Video:.*?\s(\d{3,4})x(\d{3,4})", out)
            if res_m:
                orig_w, orig_h = int(res_m.group(1)), int(res_m.group(2))

                # Tolerans Payı (30 piksel)
                if (orig_w - w_crop > 30) or (orig_h - h_crop > 30):
                    return True  # Siyah Kenarlık Var!

        return False  # Siyah Kenarlık Yok / Temiz
    except Exception:
        return False


def run_ffmpeg_analysis(input_path):
    stats = {
        "duration": "00:00:00",
        "resolution": "Bilinmiyor",
        "lufs": None,
        "true_peak": None,
        "has_black_borders": False,
    }
    try:
        cmd = [
            "ffmpeg",
            "-i",
            input_path,
            "-af",
            "ebur128=framelog=verbose",
            "-f",
            "null",
            "-",
        ]
        res = subprocess.run(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        out = res.stderr

        res_m = re.search(r"Video:.*?\s(\d{3,4}x\d{3,4})", out)
        if res_m:
            stats["resolution"] = res_m.group(1)

        dur_m = re.search(r"Duration:\s(\d{2}:\d{2}:\d{2})", out)
        if dur_m:
            stats["duration"] = dur_m.group(1)

        lufs_m = re.search(r"I:\s+([-\d.]+)\s+LUFS", out)
        if lufs_m:
            stats["lufs"] = float(lufs_m.group(1))

        tp_m = re.search(r"Peak:\s+([-\d.]+)\s+dBFS", out)
        if tp_m:
            stats["true_peak"] = float(tp_m.group(1))

        stats["has_black_borders"] = check_black_borders(input_path)

    except Exception:
        pass
    return stats


def normalize_video_ffmpeg(input_path, output_path):
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-af",
            "loudnorm=I=-24:LRA=11:TP=-2",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_path,
        ]
        subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        return True
    except Exception:
        return False


def analyze_audio_lufs(video_url):
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
        res = subprocess.run(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        out = res.stderr
        m = re.search(r"I:\s+([-\d.]+)\s+LUFS", out)
        if m:
            return float(m.group(1))
        return None
    except Exception:
        return None


def extract_vast_details(xml_text):
    found_medias = []
    has_vpaid = False
    xml_lower = xml_text.lower()

    if "vpaid" in xml_lower or "application/x-javascript" in xml_lower:
        has_vpaid = True

    try:
        xml_clean = re.sub(r'xmlns="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)
        for mf in root.findall(".//MediaFile"):
            url = mf.text.strip() if mf.text else ""
            w = mf.get("width")
            h = mf.get("height")
            m_type = mf.get("type", "")
            if "vpaid" in mf.get("apiFramework", "").lower() or ".js" in url:
                has_vpaid = True
            if url and (
                ".mp4" in url.lower() or "video" in m_type.lower()
            ):
                dim = str(w) + "x" + str(h) if w and h else "Belirtilmemiş"
                found_medias.append(
                    {"url": url, "dimension": dim, "width": w, "height": h}
                )
    except Exception:
        pass

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
            found_medias.append({
                "url": clean_url,
                "dimension": "Bilinmiyor",
                "width": 0,
                "height": 0,
            })

    return found_medias, has_vpaid


def resolve_vast_and_get_media(vast_input, is_xml=False, max_redirects=5):
    if is_xml:
        medias, has_vpaid = extract_vast_details(vast_input)
        status = "ok" if medias else "no_media"
        return {
            "medias": medias,
            "has_vpaid": has_vpaid,
            "xml": vast_input,
            "status": status,
        }

    curr_url = vast_input.strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    last_xml = ""
    visited = set()
    step = 0

    while step < max_redirects:
        step += 1
        if curr_url in visited:
            break
        visited.add(curr_url)

        ts = str(int(time.time()))
        replacements = {
            "[timestamp]": ts,
            "${GDPR}": "1",
            "${GDPR_CONSENT_755}": "1",
            "[BREAKPOSITION]": "1",
            "[APIFRAMEWORKS]": "1,2,7",
            "[OMIDPARTNER]": "1",
        }
        for old_val, new_val in replacements.items():
            curr_url = curr_url.replace(old_val, new_val)

        try:
            res = requests.get(curr_url, headers=headers, timeout=12)
            if res.status_code != 200:
                return {
                    "status": "error",
                    "message": "HTTP " + str(res.status_code) + " Hatası",
                }

            last_xml = res.text
            medias, has_vpaid = extract_vast_details(last_xml)

            if medias:
                return {
