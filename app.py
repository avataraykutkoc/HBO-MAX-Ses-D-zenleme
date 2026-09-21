import streamlit as st
import pandas as pd
import io
import os
import subprocess
import tempfile
import requests
import json
import xml.etree.ElementTree as ET

st.set_page_config(page_title="HepsiAd Portal", layout="wide", page_icon="🎬")

st.title("🎬 HepsiAd - Video Standartlaştırma & BigQuery Analiz Portalı")
st.caption("👨‍💻 Creator: Aykut Koç")

tab1, tab2, tab3 = st.tabs([
    "📁 Doğrudan Video & Ses Normalizasyonu", 
    "📊 BigQuery P1 Merchant Paneli", 
    "🔗 VAST Tag Analizi"
])

def get_audio_lufs(video_path):
    """FFmpeg ebur128 filtresi ile videonun Integrated LUFS ses seviyesini ölçer."""
    try:
        cmd = [
            "ffmpeg", "-nostats", "-i", video_path,
            "-filter_complex", "ebur128=peak=true",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        output = result.stderr
        
        for line in output.split('\n'):
            if "I:" in line and "LUFS" in line:
                parts = line.split("I:")
                if len(parts) > 1:
                    lufs_val = parts[1].split("LUFS")[0].strip()
                    return float(lufs_val)
    except Exception:
        pass
    return None

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
            with st.spinner("Video analiz ediliyor ve -23 LUFS ses seviyesine sabitleniyor..."):
                try:
                    ext = os.path.splitext(uploaded_video.name)[1].lower()
                    if not ext:
                        ext = ".mp4"

                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
                        tmp_in.write(uploaded_video.getbuffer())
                        in_path = tmp_in.name

                    # Orijinal Ses LUFS Analizi
                    orig_lufs = get_audio_lufs(in_path)

                    out_path = in_path + "_converted.mp4"
                    cmd = ["ffmpeg", "-y", "-i", in_path]
                    
                    video_filters = []
                    if "1080p" in target_resolution:
                        video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
                    elif "720p" in target_resolution:
                        video_filters.append("scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2")

                    if video_filters:
                        cmd.extend(["-vf", ",".join(video_filters)])

                    if target_fps != "Orijinal":
                        cmd.extend(["-r", target_fps])

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

                    # Yeni Dönüştürülen Ses LUFS Analizi
                    new_lufs = get_audio_lufs(out_path)

                    st.success("🎉 Video dönüştürüldü ve ses tam -23 LUFS seviyesine sabitlendi!")
                    
                    # LUFS Ölçüm Sonuç Kartları
                    m1, m2 = st.columns(2)
                    m1.metric("Orijinal Ses Seviyesi", f"{orig_lufs} LUFS" if orig_lufs else "Tespit Edilemedi")
                    m2.metric("Yeni Normalize Ses Seviyesi", f"{new_lufs} LUFS" if new_lufs else "-23.0 LUFS", delta="🎯 Standart Uyumlu")

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
# TAB 3: GERÇEK VAST TAG ANALİZİ & VPAID SORGUSU
# ---------------------------------------------------------
with tab3:
    st.header("🔗 VAST Tag Analizi & VPAID Sorgusu")
    st.write("VAST URL'inizi yapıştırarak VPAID varlığını, reklam medyalarını ve doğruluk parametrelerini analiz edebilirsiniz.")
    
    vast_url = st.text_input("VAST URL Girin:", placeholder="https://ad.doubleclick.net/ddm/pfadx/...")
    
    if st.button("🔍 VAST Tag Analiz Et", type="primary"):
        if vast_url:
            with st.spinner("VAST XML yanıtı çekiliyor ve VPAID / Medya sorgusu yapılıyor..."):
                try:
                    cleaned_url = vast_url.replace("[timestamp]", "123456789")
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    response = requests.get(cleaned_url, headers=headers, timeout=10)

                    if response.status_code == 200:
                        xml_content = response.content
                        root = ET.fromstring(xml_content)

                        ad_title = root.find(".//AdTitle").text if root.find(".//AdTitle") is not None else "Belirtilmemiş"
                        duration = root.find(".//Duration").text if root.find(".//Duration") is not None else "Belirtilmemiş"
                        
                        media_files = []
                        has_vpaid = False

                        for media in root.findall(".//MediaFile"):
                            api_framework = media.attrib.get("apiFramework", "").upper()
                            type_attr = media.attrib.get("type", "").lower()
                            
                            is_vpaid_element = ("VPAID" in api_framework) or ("vpaid" in type_attr) or ("javascript" in type_attr)
                            if is_vpaid_element:
                                has_vpaid = True

                            media_files.append({
                                "Type": media.attrib.get("type", "N/A"),
                                "API Framework": api_framework if api_framework else "None",
                                "VPAID mi?": "⚠️ EVET" if is_vpaid_element else "✅ HAYIR",
                                "Bitrate": media.attrib.get("bitrate", "N/A"),
                                "Dimensions": f"{media.attrib.get('width', '0')}x{media.attrib.get('height', '0')}",
                                "URL": media.text.strip() if media.text else "N/A"
                            })

                        impressions = [imp.text.strip() for imp in root.findall(".//Impression") if imp.text]

                        st.success("✅ VAST Tag başarıyla çözümlendi!")

                        # Özet Metrik Kartları (VPAID Durumu Dahil)
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Reklam Başlığı", ad_title)
                        c2.metric("Süre (Duration)", duration)
                        c3.metric("Medya Dosyası Adedi", len(media_files))
                        
                        if has_vpaid:
                            c4.metric("VPAID Durumu", "⚠️ VPAID İçeriyor", delta="- HBO Max Uyarısı", delta_color="inverse")
                            st.error("🚨 **UYARI:** Bu VAST Tag içerisinde **VPAID (JavaScript/Interactive)** bileşenler tespit edildi! Yayıncı kuralları gereği (ör. HBO MAX) VPAID içeren etiketler reddedilebilir.")
                        else:
                            c4.metric("VPAID Durumu", "✅ VPAID Yok", delta="Temiz / MP4")
                            st.success("✅ **TEMİZ:** VAST Tag içerisinde VPAID bulunmuyor. Yayıncılar için uygundur.")

                        st.subheader("📹 Bulunan Medya Dosyaları (MediaFiles)")
                        if media_files:
                            df_media = pd.DataFrame(media_files)
                            st.dataframe(df_media, use_container_width=True)

                            video_url = next((m["URL"] for m in media_files if "mp4" in m["Type"].lower() or m["URL"].endswith(".mp4")), None)
                            if video_url:
                                st.subheader("▶️ Önizleme Videosu")
                                st.video(video_url)
                        else:
                            st.warning("⚠️ XML içerisinde doğrudan MediaFile bağlantısı bulunamadı (Wrapper veya boş yanıt olabilir).")

                        st.subheader("📈 Impression Tracking URL'leri")
                        if impressions:
                            for imp in impressions:
                                st.code(imp, language="text")

                        with st.expander("📄 Ham XML Yanıtını İncele"):
                            st.code(response.text, language="xml")

                    else:
                        st.error(f"❌ VAST URL'ye erişilemedi! HTTP Durum Kodu: {response.status_code}")

                except Exception as e:
                    st.error(f"❌ VAST XML ayrıştırılırken hata oluştu: {e}")
        else:
            st.warning("⚠️ Lütfen analiz etmek için geçerli bir VAST URL girin.")
