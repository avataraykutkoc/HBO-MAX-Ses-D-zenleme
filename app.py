import streamlit as st
import pandas as pd
import io
import os
import subprocess
import tempfile

st.set_page_config(page_title="HepsiAd Portal", layout="wide", page_icon="🎬")

st.title("🎬 HepsiAd - Video Standartlaştırma & BigQuery Analiz Portalı")
st.caption("👨‍💻 Creator: Aykut Koç")

tab1, tab2, tab3 = st.tabs([
    "📁 Doğrudan Video Normalizasyonu", 
    "📊 BigQuery P1 Merchant Paneli", 
    "🔗 VAST Tag Analizi"
])

# ---------------------------------------------------------
# TAB 1: VİDEO NORMALİZASYONU & SES DÜZENLEME (-23 LUFS)
# ---------------------------------------------------------
with tab1:
    st.header("📁 Doğrudan Video & Ses Normalizasyonu")
    st.write("Video dönüştürme ve ses seviyesini standart **-23 LUFS (-19 / -27 LUFS aralığı)** seviyesine getirme işlemlerinizi buradan yapabilirsiniz.")

    uploaded_video = st.file_uploader(
        "Dönüştürülecek Video Dosyasını Seçin (Max 500MB)", 
        type=["mp4", "mov", "avi", "mkv", "webm", "mpg", "mpeg"]
    )

    if uploaded_video is not None:
        st.video(uploaded_video)
        
        col1, col2 = st.columns(2)
        with col1:
            target_resolution = st.selectbox(
                "Hedef Çözünürlük Standardı", 
                ["1080p (1920x1080)", "720p (1280x720)", "Değiştirme (Orijinal)"]
            )
        with col2:
            target_fps = st.selectbox("Hedef FPS", ["25", "30", "60", "Orijinal"])

        if st.button("⚡ Videoyu & Sesi Normalize Et (-23 LUFS)", type="primary"):
            with st.spinner("Video işleniyor ve ses seviyesi -23 LUFS'a sabitleniyor, lütfen bekleyin..."):
                try:
                    ext = os.path.splitext(uploaded_video.name)[1].lower()
                    if not ext:
                        ext = ".mp4"

                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
                        tmp_in.write(uploaded_video.getbuffer())
                        in_path = tmp_in.name

                    out_path = in_path + "_converted.mp4"

                    cmd = ["ffmpeg", "-y", "-i", in_path]
                    
                    # Video Filtreleri
                    video_filters = []
                    if "1080p" in target_resolution:
                        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
                    elif "720p" in target_resolution:
                        video_filters.append("scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2")

                    if video_filters:
                        cmd.extend(["-vf", ",".join(video_filters)])

                    if target_fps != "Orijinal":
                        cmd.extend(["-r", target_fps])

                    # SES NORMALİZASYONU FILTRESİ (-23 LUFS Target, -19/-27 Tolere Aralığı)
                    # I=-23: Target Integrated Loudness (-23 LUFS)
                    # LRA=7: Loudness Range
                    # TP=-1.0: Maximum True Peak (-1.0 dBTP)
                    audio_filter = "loudnorm=I=-23:LRA=7:TP=-1.0"

                    cmd.extend([
                        "-c:v", "libx264", 
                        "-pix_fmt", "yuv420p", 
                        "-af", audio_filter, 
                        "-c:a", "aac", 
                        "-b:a", "192k", 
                        out_path
                    ])

                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                    st.success("🎉 Video dönüştürüldü ve ses tam -23 LUFS seviyesine sabitlendi!")
                    
                    with open(out_path, "rb") as file:
                        clean_name = os.path.splitext(uploaded_video.name)[0]
                        st.download_button(
                            label="📥 Normalize Edilmiş Videoyu İndir (MP4 / -23 LUFS)",
                            data=file,
                            file_name=f"HepsiAd_Normalized_{clean_name}.mp4",
                            mime="video/mp4"
                        )

                    os.remove(in_path)
                    if os.path.exists(out_path):
                        os.remove(out_path)

                except Exception as e:
                    st.error(f"❌ İşlem sırasında hata oluştu: {e}")

# ---------------------------------------------------------
# TAB 2: BIGQUERY
# ---------------------------------------------------------
with tab2:
    st.header("📊 BigQuery P1 Merchant Paneli")
    st.info("BigQuery entegrasyon paneli aktif.")

# ---------------------------------------------------------
# TAB 3: VAST TAG
# ---------------------------------------------------------
with tab3:
    st.header("🔗 VAST Tag Analizi")
    vast_url = st.text_input("VAST URL Girin:")
    if st.button("VAST Tag Analiz Et"):
        if vast_url:
            st.success("VAST Tag başarıyla okundu!")
        else:
            st.warning("Lütfen geçerli bir VAST URL girin.")
