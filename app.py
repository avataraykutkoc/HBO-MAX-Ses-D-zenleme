import os
import tempfile
import requests
import subprocess
import xml.etree.ElementTree as ET
import soundfile as sf
import pyloudnorm as pyln
import streamlit as st
from moviepy import VideoFileClip

# Sayfa Ayarları
st.set_page_config(page_title="HepsiAd Volume, Size & VAST QC Optimizer", page_icon="🎬", layout="wide")

st.title("🎬 HepsiAd - Video Standartlaştırma & VAST QC Laboratuvarı")
st.markdown("İster **VAST Tag URL**'si analiz edin, ister bilgisayarınızdan **Doğrudan Video** yükleyip LUFS, boyut ve siyah bant kontrolü yapın.")

# Sol Panel Ayarları
st.sidebar.header("⚙️ QC Standart Limitleri")

target_lufs = st.sidebar.number_input("Hedef Ses Seviyesi (LUFS)", value=-23.0, step=0.5)
lufs_tolerance = st.sidebar.number_input("LUFS Toleransı (±)", value=1.0, step=0.5)
max_duration = st.sidebar.number_input("Maksimum Video Süresi (Saniye)", value=30, step=1)

st.sidebar.markdown("---")
st.sidebar.header("🗜️ Sıkıştırma Ayarı (Dosya Yükleme İçin)")

auto_compress = st.sidebar.checkbox("100 MB Üstü İçin Otomatik Sıkıştır", value=True)

crf_val = st.sidebar.slider(
    "Görsel Kalite / Sıkıştırma (CRF)",
    min_value=18,
    max_value=32,
    value=24,
    step=1,
    help="Düşük CRF (18-20): Yüksek Kalite / Büyük Boyut\nYüksek CRF (28-32): Küçük Boyut"
)

# Sekme Yapısı
tab1, tab2 = st.tabs(["🔗 VAST Tag Analizi", "📁 Doğrudan Video Yükleme & İşleme"])

def detect_black_borders(video_path):
    """FFmpeg cropdetect ile siyah bant tespiti"""
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", "cropdetect=limit=24:round=2",
            "-vframes", "30", "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        crops = [line for line in result.stderr.split('\n') if "crop=" in line]
        if crops:
            last_crop = crops[-1].split("crop=")[1].split()[0]
            w, h, x, y = map(int, last_crop.split(':'))
            return w, h, x, y
    except Exception:
        pass
    return None

def process_video_qc(video_path):
    """Videoda Yayın Standartları / QC Analizi Yapar"""
    st.markdown("### 📊 Medya QC Sonuçları")
    col1, col2, col3 = st.columns(3)
    
    clip = VideoFileClip(video_path)
    width, height = clip.w, clip.h
    duration = clip.duration
    
    with col1:
        st.subheader("📐 Ölçü & Çerçeve")
        st.write(f"**Çözünürlük:** `{width}x{height}`")
        if width == 1920 and height == 1080:
            st.success("✅ **1920x1080 Full HD Standart**")
        else:
            st.error("⚠️ **1920x1080 Değil!**")
            
        crop_info = detect_black_borders(video_path)
        if crop_info:
            cw, ch, cx, cy = crop_info
            if (height - ch) > 20:
                st.warning("⚠️ **Letterboxing Tespiti:** Alt/Üst Siyah Bant var!")
            elif (width - cw) > 20:
                st.warning("⚠️ **Pillarboxing Tespiti:** Sağ/Sol Siyah Bant var!")
            else:
                st.success("✅ **Temiz Kadraj (Siyah Bant Yok)**")

    with col2:
        st.subheader("⏱️ Süre Kontrolü")
        st.write(f"**Video Süresi:** `{duration:.2f} saniye`")
        if duration <= max_duration:
            st.success(f"✅ Maksimum {max_duration}s sınırına uygun.")
        else:
            st.error(f"🚨 **Süre Aşımı!** (Sınır: {max_duration}s)")

    with col3:
        st.subheader("🔊 Ses (LUFS) Seviyesi")
        try:
            audio_path = tempfile.mktemp(suffix=".wav")
            clip.audio.write_audiofile(audio_path, logger=None)
            
            data, rate = sf.read(audio_path)
            meter = pyln.Meter(rate)
            loudness = meter.integrated_loudness(data)
            
            st.write(f"**Mevcut Ses:** `{loudness:.2f} LUFS`")
            min_lufs = target_lufs - lufs_tolerance
            max_lufs = target_lufs + lufs_tolerance
            
            if min_lufs <= loudness <= max_lufs:
                st.success(f"✅ Standart İdeal ({target_lufs} ±{lufs_tolerance} LUFS)")
            else:
                st.error(f"⚠️ **Ses Uyumsuz!** (Hedef: {target_lufs} LUFS)")
                
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            st.info("ℹ️ Videoda ses kanalı taranamadı.")

    clip.close()

# ----------------------------------------------------
# TAB 1: VAST TAG ANALİZİ
# ----------------------------------------------------
with tab1:
    vast_url = st.text_input("VAST Tag URL Adresini Girin:", placeholder="https://example.com/vast.xml")
    if st.button("VAST Tag'i Analiz Et") and vast_url:
        try:
            with st.spinner("VAST XML çekiliyor ve VPAID / MediaFile taranıyor..."):
                response = requests.get(vast_url, timeout=10)
                xml_data = response.text
                
                root = ET.fromstring(xml_data)
                
                has_vpaid = False
                media_files = []
                
                for elem in root.iter():
                    if elem.tag.endswith('MediaFile'):
                        api_framework = elem.attrib.get('apiFramework', '')
                        file_type = elem.attrib.get('type', '')
                        url = elem.text.strip() if elem.text else ''
                        
                        if api_framework.upper() == 'VPAID' or 'javascript' in file_type:
                            has_vpaid = True
                        
                        if url:
                            media_files.append((file_type, url))

            st.markdown("### 🔍 VAST Tespiti")
            if has_vpaid:
                st.error("🚨 **VPAID Tespiti Yapıldı!** (Bu tag interaktif JavaScript/VPAID kodları içeriyor)")
            else:
                st.success("✅ **VPAID Yok (Pure VAST / Standart MP4 Video)**")

            if media_files:
                selected_media = media_files[0][1]
                st.write(f"📦 **Çekilen Video Linki:**")
                st.code(selected_media, language="text")
                
                with st.spinner("VAST içerisindeki video indirilip QC analizine tabi tutuluyor..."):
                    vid_res = requests.get(selected_media, stream=True)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_vid:
                        for chunk in vid_res.iter_content(chunk_size=1024*1024):
                            if chunk:
                                tmp_vid.write(chunk)
                        tmp_vid_path = tmp_vid.name
                    
                    st.video(selected_media)
                    process_video_qc(tmp_vid_path)
                    
                    if os.path.exists(tmp_vid_path):
                        os.remove(tmp_vid_path)
            else:
                st.warning("⚠️ VAST XML içerisinde oynatılabilir MediaFile bulunamadı.")

        except Exception as e:
            st.error(f"VAST Analiz Hatası: {e}")

# ----------------------------------------------------
# TAB 2: DOĞRUDAN VİDEO YÜKLEME & İŞLEME
# ----------------------------------------------------
with tab2:
    uploaded_file = st.file_uploader(
        "Video veya Ses Dosyası Yükle (MP4, MOV, AVI, WAV, MP3)", 
        type=["mp4", "mov", "avi", "wav", "mp3", "flac"]
    )

    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.info(f"📂 Dosya Okundu: **{uploaded_file.name}** ({file_size_mb:.2f} MB)")
        
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_path = tmp_file.name

        try:
            extracted_audio_path = tempfile.mktemp(suffix=".wav")
            is_video = file_ext in [".mp4", ".mov", ".avi"]

            if is_video:
                st.video(tmp_path)
                process_video_qc(tmp_path)
                
                video_clip = VideoFileClip(tmp_path)
                video_clip.audio.write_audiofile(extracted_audio_path, logger=None)
            else:
                extracted_audio_path = tmp_path

            # Ses Normalizasyonu ve Sıkıştırma İşlemi
            st.markdown("---")
            st.markdown("### 🛠️ Ses Normalizasyonu ve Dosya İşleme")
            
            data, rate = sf.read(extracted_audio_path)
            meter = pyln.Meter(rate)
            loudness = meter.integrated_loudness(data)

            normalized_data = pyln.normalize.loudness(data, loudness, target_lufs)
            new_loudness = meter.integrated_loudness(normalized_data)

            norm_audio_path = tempfile.mktemp(suffix=".wav")
            sf.write(norm_audio_path, normalized_data, rate)

            st.success(f"✅ Ses Başarıyla Normalize Edildi! Yeni Seviye: `{new_loudness:.2f} LUFS`")

            if is_video:
                new_audio_clip = VideoFileClip(tmp_path).audio
                final_video = video_clip.set_audio(AudioFileClip(norm_audio_path))
                
                output_video_path = tempfile.mktemp(suffix=".mp4")
                ffmpeg_params = []
                selected_crf = str(crf_val)

                if (auto_compress and file_size_mb > 100) or not auto_compress:
                    ffmpeg_params.extend(["-crf", selected_crf, "-preset", "medium"])

                final_video.write_videofile(
                    output_video_path, 
                    codec="libx264", 
                    audio_codec="aac", 
                    ffmpeg_params=ffmpeg_params if ffmpeg_params else None,
                    logger=None
                )

                output_size_mb = os.path.getsize(output_video_path) / (1024 * 1024)

                st.balloons()
                st.success(f"🎉 İşlem Tamamlandı! Yeni Dosya Boyutu: **{output_size_mb:.2f} MB**")

                with open(output_video_path, "rb") as f:
                    video_bytes = f.read()
                    st.download_button(
                        label=f"📥 Normalize Edilmiş Videoyu İndir ({output_size_mb:.1f} MB)",
                        data=video_bytes,
                        file_name=f"opt_{uploaded_file.name}",
                        mime="video/mp4"
                    )
                
                video_clip.close()
            else:
                with open(norm_audio_path, "rb") as f:
                    audio_bytes = f.read()
                    st.audio(audio_bytes, format="audio/wav")
                    st.download_button(
                        label="📥 Normalize Edilmiş Sesi İndir (WAV)",
                        data=audio_bytes,
                        file_name=f"normalized_{uploaded_file.name}.wav",
                        mime="audio/wav"
                    )

        except Exception as e:
            st.error(f"İşlem sırasında bir hata oluştu: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
