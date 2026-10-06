import io
import os
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


# VAST & Wrapper Çözümleme Fonksiyonu
def resolve_vast_and_get_media(vast_input, is_xml=False, max_redirects=5):
    """VAST Tag veya XML girdisini çözer.

    Wrapper (yönlendirme) varsa derinlemesine takip eder ve MediaFile'ları
    bulur.
    """
    if is_xml:
        try:
            root = ET.fromstring(vast_input)
            media_files = root.findall(".//MediaFile")
            media_urls = [
                mf.text.strip() for mf in media_files if mf and mf.text
            ]
            has_vpaid = any(
                "vpaid" in (mf.get("apiFramework", "").lower())
                or "vpaid" in (mf.text or "").lower()
                for mf in media_files
            )
            return {
                "media_files": media_urls,
                "has_vpaid": has_vpaid,
                "xml": vast_input,
                "status": "ok" if media_urls else "no_media",
            }
        except Exception as e:
            return {"status": "error", "message": f"XML Parse Hatası: {str(e)}"}

    # URL İşleme Mantığı
    current_url = vast_input.strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    last_xml = ""
    for depth in range(max_redirects):
        # Makro parametreleri temizle / doldur
        current_url = current_url.replace("[timestamp]", str(int(time.time())))
        current_url = current_url.replace(
            "ord=[timestamp]", f"ord={int(time.time())}"
        )
        current_url = current_url.replace("${GDPR}", "1")
        current_url = current_url.replace("${GDPR_CONSENT_755}", "1")
        current_url = current_url.replace("[BREAKPOSITION]", "1")

        try:
            res = requests.get(current_url, headers=headers, timeout=12)
            if res.status_code != 200:
                return {
                    "status": "error",
                    "message": f"HTTP {res.status_code} Hatası alındı.",
                }

            last_xml = res.text
            root = ET.fromstring(last_xml)

            # 1. Doğrudan MediaFile var mı?
            media_files = root.findall(".//MediaFile")
            if media_files:
                media_urls = [
                    mf.text.strip() for mf in media_files if mf and mf.text
                ]
                has_vpaid = any(
                    "vpaid" in (mf.get("apiFramework", "").lower())
                    or "vpaid" in (mf.text or "").lower()
                    for mf in media_files
                )
                return {
                    "media_files": media_urls,
                    "has_vpaid": has_vpaid,
                    "xml": last_xml,
                    "status": "ok",
                }

            # 2. Wrapper / Yönlendirme Var mı?
            wrapper_tag = root.find(".//VASTAdTagURI")
            if wrapper_tag is not None and wrapper_tag.text:
                current_url = wrapper_tag.text.strip()
            else:
                break
        except Exception as e:
            return {
                "status": "error",
                "message": f"Bağlantı/Parse Hatası: {str(e)}",
            }

    return {
        "status": "no_media",
        "xml": last_xml,
        "message": "XML veya yönlendirmeler içerisinde doğrudan MediaFile (video) bağlantısı bulunamadı.",
    }


# Tab Menüleri
tab1, tab2, tab3 = st.tabs([
    "📁 Tam Otomatik Video Normalizasyonu",
    "📊 BigQuery P1 Merchant Paneli",
    "🔗 VAST Tag Analizi, VPAID & LUFS Sorgusu",
])

# TAB 1: Video Normalizasyonu
with tab1:
    st.header("Video & Ses Normalizasyon Aracı")
    st.info(
        "Buraya MP4 video dosyalarınızı yükleyerek standartlaştırma işlemlerini gerçekleştirebilirsiniz."
    )

# TAB 2: BigQuery
with tab2:
    st.header("BigQuery Paneli")
    st.write("Merchant veri analizleri bu bölümde yer alır.")

# TAB 3: VAST Tag Analizi
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

                if result["status"] == "ok":
                    st.success(
                        f"✅ Başarılı! {len(result['media_files'])} adet Medya Dosyası (MediaFile) bulundu."
                    )

                    if result["has_vpaid"]:
                        st.warning(
                            "⚠️ Dikkat: Bu VAST içerisinde VPAID bileşeni tespit edildi."
                        )
                    else:
                        st.info("ℹ️ Temiz: VPAID tespit edilmedi.")

                    st.subheader("Bulunan Video Bağlantıları:")
                    for idx, url in enumerate(result["media_files"], 1):
                        st.write(f"**Video {idx}:** {url}")
                        st.video(url)

                elif result["status"] == "no_media":
                    st.error(
                        "⚠️ XML içerisinde veya takip edilen VAST yönlendirmelerinde doğrudan MediaFile bağlantısı bulunamadı."
                    )
                else:
                    st.error(f"Hata: {result.get('message')}")

                if "xml" in result and result["xml"]:
                    with st.expander("Ham XML Yanıtını İncele"):
                        st.code(result["xml"], language="xml")
