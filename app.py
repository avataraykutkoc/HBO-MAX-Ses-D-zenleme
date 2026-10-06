import io
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


def extract_media_urls_from_xml(xml_text):
    """XML içinden hem etiketlerden hem CDATA/Regex ile MP4 ve Medya URL'lerini
    süzer."""
    found_urls = []

    # 1. Yöntem: Standart XML Parse (MediaFile ve VASTAdTagURI)
    try:
        # Namespace temizliği (Örn: xmlns="http://www.iab.net/2011/vhb")
        xml_clean = re.sub(r'xmlns="[^"]+"', "", xml_text)
        root = ET.fromstring(xml_clean)

        for mf in root.findall(".//MediaFile"):
            if mf.text and mf.text.strip():
                found_urls.append(mf.text.strip())
    except Exception:
        pass

    # 2. Yöntem: CDATA ve VPAID JS içi dâhil tüm MP4/WebM URL'lerini Regex ile yakala
    regex_mp4 = re.findall(
        r"https?://[^\s\"'<>]+?\.(?:mp4|webm|m3u8)[^\s\"'<>]*",
        xml_text,
        re.IGNORECASE,
    )
    for url in regex_mp4:
        # Temizlik
        clean_url = (
            url.replace("<![CDATA[", "")
            .replace("]]>", "")
            .replace("&amp;", "&")
        )
        if clean_url not in found_urls:
            found_urls.append(clean_url)

    return found_urls


def resolve_vast_and_get_media(vast_input, is_xml=False, max_redirects=5):
    """VAST Tag veya XML girdisini çözer, yönlendirmeleri takip eder ve medya
    URL'lerini bulur."""
    if is_xml:
        media_urls = extract_media_urls_from_xml(vast_input)
        has_vpaid = "vpaid" in vast_input.lower()
        return {
            "media_files": media_urls,
            "has_vpaid": has_vpaid,
            "xml": vast_input,
            "status": "ok" if media_urls else "no_media",
        }

    current_url = vast_input.strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    last_xml = ""
    visited_urls = set()

    for depth in range(max_redirects):
        if current_url in visited_urls:
            break
        visited_urls.add(current_url)

        # Makro Parametrelerini Temizle / Rakam Yap
        timestamp_str = str(int(time.time()))
        current_url = (
            current_url.replace("[timestamp]", timestamp_str)
            .replace("ord=[timestamp]", f"ord={timestamp_str}")
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
                    "message": f"HTTP {res.status_code} yanıtı alındı.",
                }

            last_xml = res.text
            media_urls = extract_media_urls_from_xml(last_xml)
            has_vpaid = "vpaid" in last_xml.lower()

            # Eğer medya dosyası bulunduysa başarılı dön
            if media_urls:
                return {
                    "media_files": media_urls,
                    "has_vpaid": has_vpaid,
                    "xml": last_xml,
                    "status": "ok",
                }

            # Medya bulunamadıysa VAST Wrapper yönlendirmesi var mı bak
            wrapper_match = re.search(
                r"<VASTAdTagURI>\s*<!\[CDATA\[\s*(.*?)\s*\]\]>\s*</VASTAdTagURI>|<VASTAdTagURI>\s*(.*?)\s*</VASTAdTagURI>",
                last_xml,
                re.DOTALL | re.IGNORECASE,
            )
            if wrapper_match:
                next_url = wrapper_match.group(1) or wrapper_match.group(2)
                if next_url:
                    current_url = (
                        next_url.strip().replace("&amp;", "&").strip()
                    )
                    continue

            break

        except Exception as e:
            return {
                "status": "error",
                "message": f"Bağlantı/Parse Hatası: {str(e)}",
            }

    return {
        "status": "no_media",
        "xml": last_xml,
        "message": "XML veya takip edilen yönlendirmeler içerisinde doğrudan medya (.mp4) bağlantısı bulunamadı.",
    }


# Tab Menüleri
tab1, tab2, tab3 = st.tabs([
    "📁 Tam Otomatik Video Normalizasyonu",
    "📊 BigQuery P1 Merchant Paneli",
    "🔗 VAST Tag Analizi, VPAID & LUFS Sorgusu",
])

with tab1:
    st.header("Video & Ses Normalizasyon Aracı")
    st.info("MP4 video dosyalarınızı buraya yükleyebilirsiniz.")

with tab2:
    st.header("BigQuery Paneli")
    st.write("Merchant veri analizleri bu bölümde yer alır.")

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
            with st.spinner("VAST Zinciri Çözümleniyor ve Analiz Ediliyor..."):
                is_xml_input = input_type == "VAST XML"
                result = resolve_vast_and_get_media(
                    vast_input, is_xml=is_xml_input
                )

                if (
                    result["status"] == "ok"
                    and len(result.get("media_files", [])) > 0
                ):
                    st.success(
                        f"✅ Başarılı! {len(result['media_files'])} adet Medya Dosyası (MediaFile) bulundu."
                    )

                    if result["has_vpaid"]:
                        st.warning(
                            "⚠️ Dikkat: Bu VAST içerisinde VPAID bileşeni tespit edildi."
                        )
                    else:
                        st.info("ℹ️ Temiz: VPAID bulunmuyor.")

                    st.subheader("Bulunan Video Bağlantıları:")
                    for idx, url in enumerate(result["media_files"], 1):
                        st.write(f"**Video {idx}:** {url}")
                        st.video(url)

                else:
                    st.error(
                        "⚠️ XML veya takip edilen VAST yönlendirmelerinde doğrudan MediaFile (video) bağlantısı bulunamadı."
                    )
                    if result.get("has_vpaid"):
                        st.warning(
                            "Not: VAST içerisinde VPAID/JS tespit edildi ancak doğrudan MP4 videosuna ulaşılamadı."
                        )

                if "xml" in result and result["xml"]:
                    with st.expander("Ham XML Yanıtını İncele"):
                        st.code(result["xml"], language="xml")
