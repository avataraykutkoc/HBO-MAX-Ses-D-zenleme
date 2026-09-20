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
    layout="wide"
)

st.title("🎬 HepsiAd Video & VAST Kontrol Merkezi")
st.markdown("Video dosyalarının ve VAST etiketlerinin kalite ve uyumluluk kontrollerini yapabilirsiniz.")

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
                    
                    st.subheader("Video Özellikleri")
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
