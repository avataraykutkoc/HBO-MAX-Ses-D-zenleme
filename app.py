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


def check_black_borders(v_src):
    try:
        cmd = [
            "ffmpeg",
            "-ss",
            "00:00:02",
            "-i",
            v_src,
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
            cw, ch = int(crops[-1][0]), int(crops[-1][1])
            res_m = re.search(r"Video:.*?\s(\d{3,4})x(\d{3,4})", out)
            if res_m:
                ow, oh = int(res_m.group(1)), int(res_m.group(2))
                if (ow - cw > 30) or (oh - ch > 30):
                    return True
        return False
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
        rm = re.search(r"Video:.*?\s(\d{3,4}x\d{3,4})", out)
        if rm:
            stats["resolution"] = rm.group(1)
        dm = re.search(r"Duration:\s(\d{2}:\d{2}:\d{2})", out)
        if dm:
            stats["duration"] = dm.group(1)
        lm = re.search(r"I:\s+([-\d.]+)\s+LUFS", out)
        if lm:
            stats["lufs"] = float(lm.group(1))
        tm = re.search(r"Peak:\s+([-\d.]+)\s+dBFS", out)
        if tm:
            stats["true_peak"] = float(tm.group(1))
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
        m = re.search(r"I:\s+([-\d.]+)\s+LUFS", res.stderr)
        if m:
            return float(m.group(1))
        return None
    except Exception:
        return None


def extract_vast_details(xml_text):
    found = []
    has_vpaid = False
    xl = xml_text.lower()
    if ("vpaid" in xl) or ("application/x-javascript" in xl):
        has_vpaid = True
    try:
        xml_clean = re.sub(r'xmlns="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)
        for mf in root.findall(".//MediaFile"):
            u = mf.text.strip() if mf.text else ""
            w = mf.get("width")
            h = mf.get("height")
            mt = mf.get("type", "")
            if ("vpaid" in mf.get("apiFramework", "").lower()) or (".js" in u):
                has_vpaid = True
            if u and ((".mp4" in u.lower()) or ("video" in mt.lower())):
                dim = str(w) + "x" + str(h) if w and h else "Belirtilmemiş"
                found.append({"url": u, "dimension": dim, "width": w, "height": h})
    except Exception:
        pass

    if not found:
        mp4_list = re.findall(
            r"https?://[^\s\"'<>]+?\.(?:mp4)[^\s\"'<>]*", xml_text, re.IGNORECASE
        )
        for target_url in mp4_list:
            clean_u = (
                target_url.replace("<![CDATA[", "")
                .replace("]]>", "")
                .replace("&amp;", "&")
            )
            found.append(
                {"url": clean_u, "dimension": "Bilinmiyor", "width": 0, "height": 0}
            )

    return found, has_vpaid


def resolve_vast_and_get_media(vast_input, is_xml=False, max_redirects=5):
    if is_xml:
        medias, has_vpaid = extract_vast_details(vast_input)
        s_val = "ok" if medias else "no_media"
        return {
            "medias": medias,
            "has_vpaid": has_vpaid,
            "xml": vast_input,
            "status": s_val,
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
        reps = {
            "[timestamp]": ts,
            "${GDPR}": "1",
            "${GDPR_CONSENT_755}": "1",
            "[BREAKPOSITION]": "1",
            "[APIFRAMEWORKS]": "1,2,7",
            "[OMIDPARTNER]": "1",
        }
        for k, v in reps.items():
            curr_url = curr_url.replace(k, v)

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
                    "medias": medias,
                    "has_vpaid": has_vpaid,
                    "xml": last_xml,
                    "status": "ok",
                }

            wm = re.search(
                r"<VASTAdTagURI>\s*<!\[CDATA\[\s*(.*?)\s*\]\]>\s*</VASTAdTagURI>|<VASTAdTagURI>\s*(.*?)\s*</VASTAdTagURI>",
                last_xml,
                re.DOTALL | re.IGNORECASE,
            )
            if wm:
                next_url = wm.group(1) or wm.group(2)
