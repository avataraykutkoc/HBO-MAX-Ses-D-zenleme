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
    st.title("🎁 HepsiAd - Video Portal")
with col_author:
    st.markdown("<b>Creator: Aykut Koç</b>", unsafe_allow_html=True)


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
            cw = int(crops[-1][0])
            ch = int(crops[-1][1])
            res_m = re.search(r"Video:.*?\s(\d{3,4})x(\d{3,4})", out)
            if res_m:
                ow = int(res_m.group(1))
                oh = int(res_m.group(2))
                if (ow - cw > 30) or (oh - ch > 30):
                    return True
        return False
    except Exception:
        return False


def run_ffmpeg_analysis(input_path):
    stats = {}
    stats["duration"] = "00:00:00"
    stats["resolution"] = "Bilinmiyor"
    stats["lufs"] = None
    stats["true_peak"] = None
    stats["has_black_borders"] = False

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
    if ("vpaid" in xl) or ("javascript" in xl):
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
                dim = str(w) + "x" + str(h) if w and h else "Bilinmiyor"
                found.append(
                    {"url": u, "dimension": dim, "width": w, "height": h}
                )
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
        s = xml_text.split("<VASTAdTagURI>")[1].split("</VASTAdTagURI>")[0]
        s = s.replace("<![CDATA[", "").replace("]]>", "").strip()
        return s.replace("&amp;", "&")
    return None


def resolve_vast_and_get_media(vast_input, is_xml=False, max_redirects=5):
    if is_xml:
        medias, has_vpaid = extract_vast_details(vast_input)
        s_val = "ok" if medias else "no_media"
        res_ok = {}
        res_ok["medias"] = medias
        res_ok["has_vpaid"] = has_vpaid
        res_ok["xml"] = vast_input
        res_ok["status"] = s_val
        return res_ok

    curr_url = vast_input.strip()
    headers = {}
    headers["User-Agent"] = "Mozilla/5.0"

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
        curr_url = curr_url.replace("${GDPR_CONSENT_755}", "1")
        curr_url = curr_url.replace("[BREAKPOSITION]", "1")
        curr_url = curr_url.replace("[APIFRAMEWORKS]", "1,2,7")
        curr_url = curr_url.replace("[OMIDPARTNER]", "1")

        try:
            res = requests.get(curr_url, headers=headers, timeout=12)
            if res.status_code != 200:
                res_err = {}
                res_err["status"] = "error"
                res_err["message"] = "HTTP Hata " + str(res.status_code)
                return res_err

            last_xml = res.text
            medias, has_vpaid = extract_vast_details(last_xml)

            if medias:
                res_m = {}
                res_m["medias"] = medias
                res_m["has_vpaid"] = has_vpaid
                res_m["xml"] = last_xml
                res_m["status"] = "ok"
                return res_m

            next_u = find_wrapper_url(last_xml)
            if next_u:
                curr_url = next_u
                continue
            break
        except Exception as e:
            res_ex = {}
            res_ex["status"] = "error"
            res_ex["message"] = str(e)
            return res_ex

    res_final = {}
    res_final["status"] = "no_media"
    res_final["xml"] = last_xml
    res_final["message"] = "MP4 bulunamadi."
    return res_final


tab1, tab2, tab3 = st.tabs([
    "📁 Otomatik Video Normalizasyonu",
    "📊 BigQuery Paneli",
    "🔗 VAST Tag Analizi",
])

# --- TAB 1 ---
with tab1:
    st.header("Otomatik Video Normalizasyon Araci")
    st.write("MP4 yukleyin.")

    up_file = st.file_uploader("Video Yukle (.mp4)", type=["mp4"])

    if up_file is not None:
        fb = up_file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tf:
            tf.write(fb)
            tp = tf.name

        st.subheader("1. Video Analizi")
        st.video(fb)

        with st.spinner("Analiz ediliyor..."):
            stats = run_ffmpeg_analysis(tp)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Cozunurluk", stats["resolution"])
        c2.metric("Sure", stats["duration"])
        c3.metric(
            "Ses",
            str(stats["lufs"]) + " LUFS" if stats["lufs"] is not None else "Yok",
        )
        c4.metric(
            "Peak",
            str(stats["true_peak"]) + " dB"
            if stats["true_peak"] is not None
            else "Yok",
        )
        c5.metric(
            "Siyah Kenarlik",
            "VAR" if stats["has_black_borders"] else "Yok",
        )

        st.markdown("---")
        st.subheader("2. Otomatik Normalizasyon (-24 LUFS)")

        out_tmp = tp.replace(".mp4", "_norm.mp4")
        with st.spinner("Ses seviyesi -24 LUFS yapiliyor..."):
            ok = normalize_video_ffmpeg(tp, out_tmp)

        if ok and os.path.exists(out_tmp):
            st.success("Ses seviyesi -24 LUFS yapildi.")
            with open(out_tmp, "rb") as f:
                nb = f.read()
            st.subheader("Standardize Edilmis Video (-24 LUFS)")
            st.video(nb)
            st.download_button(
                label="Videoyu Indir",
                data=nb,
                file_name="normalized_" + up_file.name,
                mime="video/mp4",
            )
        else:
            st.error("Hata olustu.")

# --- TAB 2 ---
with tab2:
    st.header("BigQuery Paneli")
    st.info("Merchant paneli.")

# --- TAB 3 ---
with tab3:
    st.header("VAST Tag Analizi")

    input_type = st.radio(
        "Girdi Tipi:", ["VAST URL", "VAST XML"], horizontal=True
