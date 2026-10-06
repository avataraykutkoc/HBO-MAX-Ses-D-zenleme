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

st.set_page_config(page_title="HepsiAd Portal", layout="wide", page_icon="🎁")

col_title, col_author = st.columns([3, 1])
with col_title:
    st.title("🎁 HepsiAd - Video Portal")
with col_author:
    st.markdown(
        """
        <div style="background: rgba(255, 255, 255, 0.05); padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.1); text-align: right; float: right;">
            <span style="font-size: 11px; color: #94A3B8;">Creator</span>
            <span style="font-size: 12px; font-weight: 600; color: #38BDF8; margin-left: 5px;">👨‍💻 Aykut Koç</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

page = st.radio(
    "Mod Secin:",
    ["📁 Otomatik Video Normalizasyonu", "📊 BigQuery Paneli", "🔗 VAST Tag Analizi"],
    horizontal=True,
)

st.markdown("---")


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
        crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", res.stderr)
        if crops:
            cw, ch = int(crops[-1][0]), int(crops[-1][1])
            res_m = re.search(r"Video:.*?\s(\d{3,4})x(\d{3,4})", res.stderr)
            if res_m:
                ow, oh = int(res_m.group(1)), int(res_m.group(2))
                if (ow - cw > 30) or (oh - ch > 30):
                    return True
        return False
    except Exception:
        return False


def get_fast_lufs(input_path_or_url):
    try:
        cmd = [
            "ffmpeg",
            "-i",
            input_path_or_url,
            "-af",
            "ebur128=metadata=1",
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
    except Exception:
        pass
    return None


def run_ffmpeg_analysis(input_path_or_url):
    stats = {
        "duration": "00:00:00",
        "duration_sec": 0,
        "resolution": "Bilinmiyor",
        "lufs": None,
        "has_black_borders": False,
        "size_mb": 0,
    }
    try:
        if os.path.exists(input_path_or_url):
            stats["size_mb"] = round(
                os.path.getsize(input_path_or_url) / (1024 * 1024), 2
            )

        cmd = ["ffmpeg", "-i", input_path_or_url, "-f", "null", "-"]
        res = subprocess.run(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        out = res.stderr

        rm = re.search(r"Video:.*?\s(\d{3,4}x\d{3,4})", out)
        if rm:
            stats["resolution"] = rm.group(1)

        dm = re.search(r"Duration:\s(\d{2}):(\d{2}):(\d{2}\.\d+)", out)
        if dm:
            h, m, s = float(dm.group(1)), float(dm.group(2)), float(dm.group(3))
            stats["duration_sec"] = h * 3600 + m * 60 + s
            stats["duration"] = (
                str(int(h)).zfill(2)
                + ":"
                + str(int(m)).zfill(2)
                + ":"
                + str(int(s)).zfill(2)
            )

        stats["lufs"] = get_fast_lufs(input_path_or_url)
        stats["has_black_borders"] = check_black_borders(input_path_or_url)
    except Exception:
        pass
    return stats


def normalize_video_ffmpeg(input_path, output_path, duration_sec, file_size_mb):
    try:
        if file_size_mb > 100 and duration_sec > 0:
            target_size_mb = 98.0
            target_total_bitrate = (target_size_mb * 8192) / duration_sec
            audio_bitrate = 128
            video_bitrate = max(int(target_total_bitrate - audio_bitrate), 500)

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                input_path,
                "-af",
                "loudnorm=I=-24:LRA=11:TP=-2",
                "-c:v",
                "libx264",
                "-b:v",
                str(video_bitrate) + "k",
                "-c:a",
                "aac",
                "-b:a",
                str(audio_bitrate) + "k",
                output_path,
            ]
        else:
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


def extract_vast_details(xml_text):
    found = []
    has_vpaid = False

    try:
        xml_clean = re.sub(r'xmlns="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)

        for mf in root.findall(".//MediaFile"):
            u = mf.text.strip() if mf.text else ""
            w = mf.get("width")
            h = mf.get("height")
            mt = mf.get("type", "").lower()
            api_fw = mf.get("apiFramework", "").lower()

            if "vpaid" in api_fw or "javascript" in mt or u.lower().endswith(".js"):
                has_vpaid = True

            if u and (".mp4" in u.lower() or "video/" in mt):
                dim = str(w) + "x" + str(h) if w and h else "Bilinmiyor"
                found.append({"url": u, "dimension": dim, "width": w, "height": h})

        for res_tag in root.findall(".//HTMLResource") + root.findall(".//JavaScriptResource"):
            if res_tag.text and "vpaid" in res_tag.text.lower():
                has_vpaid = True

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
            found.append({"url": clean_u, "dimension": "Bilinmiyor", "width": 0, "height": 0})

    return found, has_vpaid


def find_wrapper_url(xml_text):
    try:
        xml_clean = re.sub(r'xmlns="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)
        uri_tag = root.find(".//VASTAdTagURI")
        if uri_tag is not None and uri_tag.text:
            return uri_tag.text.strip().replace("&amp;", "&")
    except Exception:
        pass

    if "<VASTAdTagURI>" in xml_text:
        try:
            s = xml_text.split("<VASTAdTagURI>")[1].split("</VASTAdTagURI>")[0]
            s = s.replace("<![CDATA[", "").replace("]]>", "").strip()
            return s.replace("&amp;", "&")
        except Exception:
            pass
    return None


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
    headers = {"User-Agent": "Mozilla/5.0"}
    last_xml = ""
    visited = set()
    step = 0

    while step < max_redirects:
        step += 1
        if curr_url in visited:
            break
        visited.add(curr_url)
        ts = str(int(time.time()))

        curr_url = curr_url.replace("[timestamp]", ts)
        curr_url = curr_url.replace("${GDPR}", "1")
        curr_url = curr_url.replace("${GDPR_CONSENT_50}", "1")
        curr_url = curr_url.replace("${GDPR_CONSENT_755}", "1")
        curr_url = curr_url.replace("[BREAKPOSITION]", "1")
        curr_url = curr_url.replace("[APIFRAMEWORKS]", "1,2,7")
        curr_url = curr_url.replace("[OMIDPARTNER]", "1")

        try:
            res = requests.get(curr_url, headers=headers, timeout=12)
            if res.status_code != 200:
                return {
                    "status": "error",
                    "message": "HTTP Hata " + str(res.status_code),
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

            next_u = find_wrapper_url(last_xml)
            if next_u:
                curr_url = next_u
                continue
            break
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {
        "status": "no_media",
        "xml": last_xml,
        "message": "MP4 bulunamadi.",
    }


# --- SAYFA 1 ---
if page == "📁 Otomatik Video Normalizasyonu":
    st.header("Otomatik Video Normalizasyon Araci")
    st.write("MP4 yukleyin.")

    up
