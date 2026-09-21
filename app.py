import streamlit as st
import pandas as pd
import os
import tempfile
import requests
import subprocess
import re

# --- Streamlit Sayfa Yapılandırması ---
st.set_page_config(
    page_title="HepsiAd Video QC & VAST Laboratuvarı",
    page_icon="🎬",
    layout="wide",
    st.set_page_config(
    page_title="HepsiAd Video QC & VAST Laboratuvarı",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Üst İmza / Geliştirici Bilgisi ---
st.caption("🚀 Developed with ❤️ by **Aykut Koç** | HepsiAd Video & VAST QC Tool")
st.title("🎬 HepsiAd Video & VAST Kontrol Merkezi")
st.markdown("Video dosyalarının ve VAST etiketlerinin kalite ve uyumluluk kontrollerini yapabilirsiniz.")

# --- Sol Yan Menü (Sidebar - Teknik Detaylar ve Kurallar) ---
with st.sidebar:
    st.header("📋 Teknik Kriterler & Standartlar")
    
    st.subheader("🎥 Video QC Standartları")
    st.markdown("""
    * **Format:** MP4, MOV, MKV
    * **Video Codec:** H.264 / AVC
    * **Çözünürlük:** Min. 1080p (1920x1080)
    * **Kare Hızı (FPS):** 25 fps veya 30 fps
    * **Maks. Dosya Boyutu:** 200 MB
    * **Ses (Audio):** AAC, 48kHz, Stereo (-24 LKFS nominal)
    """)
    
    st.divider()
    
    st.subheader("🔗 VAST Etiket Standartları")
    st.markdown("""
    * **Versiyon:** VAST 2.0 / 3.0 / 4.0 uyumlu
    * **Protokol:** HTTPS zorunlu
    * **Medya Türü:** Doğrudan MP4 / M4V `MediaFile` düğümü içermelidir.
    * **Yanıt Süresi:** < 1.5 saniye
    """)
    
    st.divider()
    st.info("💡 Herhangi bir sorun veya geliştirme talebi için **Aykut Koç** ile iletişime geçebilirsiniz.")

# --- Sekme Yapısı ---
tab_video, tab_vast = st.tabs(["🎥 Video Kontrolü (QC)", "🔗 VAST Kontrolü"])

# ==========================================
# 1. SEKME: VIDEO KONTROLÜ (QC)
# ==========================================
with tab_video:
    st.header("Video Kalite Kontrolü")
    uploaded_file = st.file_uploader("Bir video dosyası yükleyin (MP4, MOV, MKV)", type=["mp4", "mov", "mkv"])

    if uploaded_file is not None:
        st.video(uploaded_file)
        
        if st.button("Videoyu Analiz Et"):
            with st.spinner("Video özellikleri analiz ediliyor..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_path = tmp_file.name

                try:
                    # FFprobe ile video detaylarını alma
                    cmd = [
                        "ffprobe", "-v", "error", 
                        "-show_entries", "stream=width,height,r_frame_rate,codec_name,bit_rate,duration", 
                        "-of", "default=noprint_wrappers=1", tmp_path
                    ]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    
                    st.subheader("Video Özellikleri ve Detaylar")
                    st.code(result.stdout)
                    st.success("Analiz başarıyla tamamlandı!")
                except Exception as e:
                    st.error(f"FFprobe analizi sırasında bir hata oluştu: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

# ==========================================
# 2. SEKME: VAST KONTROLÜ
# ==========================================
with tab_vast:
    st.header("VAST URL / Etiket Kontrolü")
    vast_url = st.text_input("VAST Bağlantısını (URL) Girin:")

    if st.button("VAST Etiketini Doğrula"):
        if vast_url:
            with st.spinner("VAST yanıtı alınıyor ve doğrulanıyor..."):
                try:
                    response = requests.get(vast_url, timeout=10)
                    if response.status_code == 200:
                        st.success("VAST Yanıtı Başarıyla Alındı! (Status 200)")
                        
                        # XML İçeriği
                        with st.expander("Ham VAST XML Yanıtı"):
                            st.code(response.text, language="xml")
                            
                        # Medya Dosyası (MediaFile) Arama
                        media_files = re.findall(r'<MediaFile[^>]*>(.*?)</MediaFile>', response.text, re.DOTALL)
                        if media_files:
                            st.subheader("Tespit Edilen Medya Bağlantıları:")
                            for idx, media in enumerate(media_files, 1):
                                media_clean = media.strip()
                                st.write(f"**Medya {idx}:** {media_clean}")
                                if media_clean.endswith(('.mp4', '.m4v')):
                                    st.video(media_clean)
                        else:
                            st.warning("VAST yanıtı içinde doğrudan <MediaFile> etiketi bulunamadı.")
                    else:
                        st.error(f"VAST URL'sine ulaşılamadı. Durum Kodu: {response.status_code}")
                except Exception as e:
                    st.error(f"Sorgulama sırasında hata oluştu: {e}")
        else:
            st.warning("Lütfen geçerli bir VAST URL'si girin.")
