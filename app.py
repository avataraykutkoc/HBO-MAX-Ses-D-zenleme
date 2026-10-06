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
    """XML içinden Medya URL'leri, VPAID durumu ve Video Boyutlarını (Resolution) çeker."""
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
        visited.add(current_url)

        # Makro Parametrelerini Temizle
        ts = str(int(time.time()))
        current_url = (
            current_url.replace("[timestamp]", ts)
            .replace("ord=[timestamp]", f"ord={ts}")
            .replace("${GDPR}", "1")
            .replace("${GDPR_CONSENT_755}", "1")
            .replace("[BREAKPOSITION]", "1")
            .replace("[APIFRAMEWORKS]", "1,2,7")
            .replace("[OMIDPARTNER]", "1")
        )

        try:
            res = requests.get(current_url, headers=headers, timeout=12)
            if res.status_code != 200:
                return {
                    "status": "error",
                    "message": f"HTTP {res.status_code} Hatası",
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

            # Wrapper yönlendirmesini izle
            wrapper_match = re.search(
                r"<VASTAdTagURI>\s*<!\[CDATA\[\s*(.*?)\s*\]\]>\s*</VASTAdTagURI>|<VASTAdTagURI>\s*(.*?)\s*</VASTAdTagURI>",
                last_xml,
                re.DOTALL | re.IGNORECASE,
            )
            if wrapper_match:
                next_url = wrapper_match.group(1) or wrapper_match.group(2)
                if next_url:
                    current_url = next_url.strip().replace("&amp;", "&")
                    continue
            break
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {
        "status": "no_media",
        "xml": last_xml,
        "message": "Doğrudan MP4 videosu bulunamadı.",
    }


# Tab Menüleri
tab1, tab2, tab3 = st.tabs([
    "📁 Tam Otomatik Video Normalizasyonu",
    "📊 BigQuery P1 Merchant Paneli",
    "🔗 VAST Tag Analizi, VPAID & LUFS Sorgusu",
])

with tab1:
    st.header("Video & Ses Normalizasyon Aracı")

with tab2:
    st.header("BigQuery Paneli")

with tab3:
    st.header("VAST Tag ve Medya Analizi")

    input_type = st.radio(
        "Girdi Tipi:",
        ["VAST URL", "VAST XML"],
        horizontal=True,
    )
    vast_input = st.text_area(
        "VAST Kodunu veya Bağlantısını Yapıştırın:", height=100
    )

    if st.button("Test Et", type="primary"):
        if not vast_input.strip():
            st.warning("Lütfen geçerli bir VAST URL veya XML girin.")
        else:
            with st.spinner(
                "VAST Zinciri Çözümleniyor, VPAID ve Ses Analizi Yapılıyor..."
            ):
                result = resolve_vast_and_get_media(
                    vast_input, is_xml=(input_type == "VAST XML")
                )

                if result["status"] == "ok" and result.get("medias"):
                    st.success("✅ VAST Tag Başarıyla Analiz Edildi!")

                    col1, col2, col3 = st.columns(3)

                    # 1. KART: VPAID Kontrolü
                    with col1:
                        if result["has_vpaid"]:
                            st.error("⚠️ VPAID Bağımlılığı: **VAR**")
                            st.caption(
                                "Bu VAST etiketi VPAID/JS çalıştırmaktadır. CTV cihazlarında sorun çıkabilir."
                            )
                        else:
                            st.success("✅ VPAID Bağımlılığı: **YOK**")
                            st.caption(
                                "Saf MP4 video. Yayıncılar ve CTV için uygundur."
                            )

                    # 2. KART: Video Çözünürlükleri
                    with col2:
                        dimensions = list(
                            set([m["dimension"] for m in result["medias"]])
                        )
                        dim_str = ", ".join(dimensions)
                        st.info(f"📐 Bulunan Boyutlar: **{dim_str}**")
                        st.caption(
                            f"Toplam {len(result['medias'])} farklı kalitede MP4 dosyası tespit edildi."
                        )

                    # 3. KART: Ses Seviyesi (LUFS)
                    with col3:
                        sample_video_url = result["medias"][0]["url"]
                        lufs_val = analyze_audio_lufs(sample_video_url)

                        if lufs_val is not None:
                            if -26.0 <= lufs_val <= -22.0:
                                st.success(f"🔊 Ses Seviyesi: **{lufs_val} LUFS**")
                                st.caption(
                                    "✅ Ses seviyesi TV ve Dijital standartlarına uygun."
                                )
                            else:
                                st.warning(f"🔊 Ses Seviyesi: **{lufs_val} LUFS**")
                                st.caption(
                                    "⚠️ Uyarı: Hedef -24 LUFS seviyesinin
