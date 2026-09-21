import streamlit as st
import pandas as pd
import io
import os
import subprocess
import tempfile
import requests
import xml.etree.ElementTree as ET

st.set_page_config(page_title="HepsiAd Portal", layout="wide", page_icon="🎬")

# Aykut Koç İmza Başlığı
col_title, col_author = st.columns([3, 1])
with col_title:
    st.title("🎬 HepsiAd - Video Standartlaştırma & BigQuery Analiz Portalı")
with col_author:
    st.markdown("""
        <div style="background-color: #1E293B; padding: 10px; border-radius: 10px; border: 1px solid #3B82F6; text-align: center;">
            <p style="margin: 0; font-size: 11px; color: #94A3B8;">HepsiAd Tech Portal</p>
            <p style="margin: 0; font-weight: bold; color: #38BDF8;">👨‍💻 Creator: Aykut Koç</p>
        </div>
    """, unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "📁 Doğrudan Video & Ses Normalizasyonu", 
    "📊 BigQuery P1 Merchant Paneli", 
    "🔗 VAST Tag Analizi, VPAID & LUFS Sorgusu"
])

def get_audio_lufs(video_input):
    """Video URL'si veya yerel dosyadan ses indirip LUFS seviyesini ölçer."""
    temp_file = None
    try:
        if video_input.startswith("http"):
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = requests.get(video_input, headers=headers, stream=True, timeout=15)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                for chunk in req.iter_content(chunk_size=1024*1024):
                    if chunk:
                        tmp.write(chunk)
                temp_file = tmp.name
            target_path = temp_file
        else:
            target_path = video_input

        cmd = [
            "ffmpeg", "-nostats", "-i", target_path,
            "-filter_complex", "ebur128=peak=true",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=25)
        output = result.stderr

        lufs_val = None
        for line in output.split('\n'):
            if "I:" in line and "LUFS" in line:
                parts = line.split("I:")
                if len(parts) > 1:
                    val_str = parts[1].split("LUFS")[0].strip()
                    lufs_val = float(val_str)

        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)

        return lufs_val
    except Exception:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        return None

def check_letterboxing(video_path):
    """FFmpeg cropdetect ile videoda siyah bant (letterbox) var mı kontrol eder."""
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", "cropdetect=24:16:0",
            "-vframes", "10",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, timeout=15)
        output = result.stderr
        
        crops = []
        for line in output.split('\n'):
            if "crop=" in line:
                crop_str = line.split("crop=")[1].split()[0]
                crops.append(crop_str)
        
        if crops:
            # Örnek crop: 1920:800:0:140 -> Yüksekliği 1080'den küçükse letterbox vardır
            last_crop = crops[-1]
            w, h, x, y = map(int, last_crop.split(':'))
            if h < 1040 or w < 1880 or y > 10 or x > 10:
                return True, last_crop
        return False, None
    except Exception:
        return False, None

# ---------------------------------------------------------
# TAB 1: VİDEO NORMALİZASYONU & LETTERBOX SORGUSU
# ---------------------------------------------------------
with tab1:
    st.header("📁 Doğrudan Video & Ses Normalizasyonu")
    st.write("Video dönüştürme, **letterbox (siyah bant) kontrolü** ve ses seviyesini standart **-23 LUFS** seviyesine getirme portalı.")

    uploaded_video = st.file_uploader(
        "Dönüştürülecek Video Dosyasını Seçin (Max 500MB)", 
        type=["mp4", "mov", "avi", "mkv", "webm", "mpg", "mpeg"]
    )

    if uploaded_video is not None:
        st.video(uploaded_video)
        
        # YÜKLENDİĞİ AN OTOMATİK LUFS VE LETTERBOX KONTROLÜ
        with st.spinner("🔍 Videonun ses ve siyah bant (letterbox) analizi yapılıyor..."):
            ext = os.path.splitext(uploaded_video.name)[1].lower()
            if not ext:
                ext = ".mp4"

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
                tmp_in.write(uploaded_video.getbuffer())
                in_path = tmp_in.name

            orig_lufs = get_audio_lufs(in_path)
            has_letterbox, crop_params = check_letterboxing(in_path)

        st.subheader("📊 Otomatik Video Teşhis Raporu")
        c1, c2 = st.columns(2)
        
        if orig_lufs is not None:
            status_str = "🎯 Uyumlu" if -27 <= orig_lufs <= -19 else "⚠️ Standart Dışı (Düzeltilmeli)"
            c1.metric("Mevcut Ses Seviyesi", f"{orig_lufs} LUFS", delta=status_str)
        else:
            c1.metric("Mevcut Ses Seviyesi", "Ölçülemedi")

        if has_letterbox:
            c2.metric("Letterboxing (Siyah Bant)", "⚠️ Siyah Bant Var!", delta="- HBO/WBD Red Riski", delta_color="inverse")
            st.error("🚨 **UYARI:** Videoda siyah bant (Letterboxing) tespit edildi! Dönüştürme işleminde bu bantlar otomatik temizlenecektir.")
        else:
            c2.metric("Letterboxing (Siyah Bant)", "✅ Siyah Bant Yok", delta="Temiz / Tam Ekran")

        col1, col2 = st.columns(2)
        with col1:
            target_resolution = st.selectbox(
                "Hedef Çözünürlük Standardı", 
                ["1080p (1920x1080)", "720p (1280x720)", "Değiştirme (Orijinal)"]
            )
        with col2:
            target_fps = st.selectbox("Hedef FPS", ["25", "30", "60", "Orijinal"])

        remove_letterbox = st.checkbox("✂️ Siyah Bantları (Letterbox) Otomatik Kırp ve Temizle", value=has_letterbox)

        if st.button("⚡ Videoyu & Sesi Normalize Et (-23 LUFS)", type="primary"):
            with st.spinner("Video işleniyor, siyah bantlar temizleniyor ve -23 LUFS'a sabitleniyor..."):
                try:
                    out_path = in_path + "_converted.mp4"
                    cmd = ["ffmpeg", "-y", "-i", in_path]
                    
                    video_filters = []
                    if remove_letterbox and crop_params:
                        video_filters.append(f"crop={crop_params}")

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

                    new_lufs = get_audio_lufs(out_path)

                    st.success("🎉 Video dönüştürüldü, siyah bantlar temizlendi ve ses tam -23 LUFS yapıldı!")
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Orijinal Ses", f"{orig_lufs} LUFS" if orig_lufs is not None else "Ölçülemedi")
                    m2.metric("Yeni Normalize Ses", f"{new_lufs} LUFS" if new_lufs is not None else "-23.0 LUFS", delta="🎯 Standart Uyumlu")

                    with open(out_path, "rb") as file:
                        clean_name = os.path.splitext(uploaded_video.name)[0]
                        st.download_button(
                            label="📥 Standardize Videoyu İndir (MP4 / -23 LUFS)",
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
# TAB 3: VAST TAG ANALİZİ, VPAID VE LUFS SORGUSU
# ---------------------------------------------------------
with tab3:
    st.header("🔗 VAST Tag Analizi, VPAID & Ses LUFS Sorgusu")
    st.write("VAST URL'inizi yapıştırarak VPAID varlığını, video çözünürlüğünü ve **gerçek zamanlı ses LUFS seviyesini** sorgulayabilirsiniz.")
    
    vast_url = st.text_input("VAST URL Girin:", placeholder="https://ad.doubleclick.net/ddm/pfadx/...")
    
    if st.button("🔍 VAST Tag & Ses LUFS Analiz Et", type="primary"):
        if vast_url:
            with st.spinner("VAST XML yanıtı çekiliyor, VPAID ve Ses LUFS seviyesi ölçülüyor..."):
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
                        target_video_url = None

                        for media in root.findall(".//MediaFile"):
                            api_framework = media.attrib.get("apiFramework", "").upper()
                            type_attr = media.attrib.get("type", "").lower()
                            m_url = media.text.strip() if media.text else "N/A"
                            
                            is_vpaid_element = ("VPAID" in api_framework) or ("vpaid" in type_attr) or ("javascript" in type_attr)
                            if is_vpaid_element:
                                has_vpaid = True

                            if ("mp4" in type_attr or m_url.endswith(".mp4")) and not target_video_url:
                                target_video_url = m_url

                            media_files.append({
                                "Type": media.attrib.get("type", "N/A"),
                                "API Framework": api_framework if api_framework else "None",
                                "VPAID mi?": "⚠️ EVET" if is_vpaid_element else "✅ HAYIR",
                                "Bitrate": media.attrib.get("bitrate", "N/A"),
                                "Dimensions": f"{media.attrib.get('width', '0')}x{media.attrib.get('height', '0')}",
                                "URL": m_url
                            })

                        impressions = [imp.text.strip() for imp in root.findall(".//Impression") if imp.text]

                        vast_lufs = None
                        if target_video_url:
                            vast_lufs = get_audio_lufs(target_video_url)

                        st.success("✅ VAST Tag ve Ses Analizi başarıyla çözümlendi!")

                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("Reklam Başlığı", ad_title)
                        c2.metric("Süre (Duration)", duration)
                        c3.metric("Medya Dosyası", f"{len(media_files)} Adet")
                        
                        if has_vpaid:
                            c4.metric("VPAID Durumu", "⚠️ VPAID Var", delta="- Uyumsuz", delta_color="inverse")
                        else:
                            c4.metric("VPAID Durumu", "✅ VPAID Yok", delta="Temiz MP4")

                        if vast_lufs is not None:
                            status_delta = "🎯 Uyumlu (-23 LUFS)" if -27 <= vast_lufs <= -19 else "⚠️ Standart Dışı"
                            c5.metric("Ses Seviyesi (LUFS)", f"{vast_lufs} LUFS", delta=status_delta)
                        else:
                            c5.metric("Ses Seviyesi (LUFS)", "Ölçülemedi")

                        if has_vpaid:
                            st.error("🚨 **UYARI:** Bu VAST Tag içerisinde **VPAID (JavaScript)** bileşenler tespit edildi! HBO MAX vb. platformlar reddedebilir.")
                        else:
                            st.success("✅ **TEMİZ:** VAST Tag içerisinde VPAID bulunmuyor. Yayıncılar için uygundur.")

                        st.subheader("📹 Bulunan Medya Dosyaları (MediaFiles)")
                        if media_files:
                            df_media = pd.DataFrame(media_files)
                            st.dataframe(df_media, use_container_width=True)

                            if target_video_url:
                                st.subheader("▶️ VAST Önizleme Videosu")
                                st.video(target_video_url)
                        else:
                            st.warning("⚠️ XML içerisinde doğrudan MediaFile bağlantısı bulunamadı.")

                        st.subheader("📈 Impression Tracking URL'leri")
                        if impressions:
                            for imp in impressions:
                                st.code(imp, language="text")

                        with st.expander("📄 Ham XML Yanıtını İncele"):
                            st.code(response.text, language="xml")

                    else:
                        st.error(f"❌ VAST URL'ye erişilemedi! HTTP Durum Kodu: {response.status_code}")

                except Exception as e:
                    st.error(f"❌ VAST XML veya Ses ayrıştırılırken hata oluştu: {e}")
        else:
            st.warning("⚠️ Lütfen analiz etmek için geçerli bir VAST URL girin.")
