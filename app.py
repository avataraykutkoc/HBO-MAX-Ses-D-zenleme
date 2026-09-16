import os
import tempfile
import subprocess
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import streamlit as st
from moviepy import VideoFileClip, AudioFileClip

# Sayfa Yapılandırması
st.set_page_config(page_title="HepsiAd Volume & Size Optimizer", page_icon="🎬", layout="centered")

st.title("🎬 HepsiAd - Video Sıkıştırma & Ses Düzenleyici")
st.markdown("Video/Ses dosyanızı yükleyin; **LUFS ses seviyesi** düzenlensin, **100 MB üstü videolar** otomatik optimize edilsin.")

# Sol Panel Ayarları & QC Paneli
st.sidebar.header("⚙️ Ses & Sıkıştırma Ayarları")

target_lufs = st.sidebar.slider(
    "Hedef Ses Seviyesi (LUFS)",
    min_value=-27.0,
    max_value=-19.0,
    value=-23.0,
    step=0.5,
    help="TV/Dijital yayın standartları için önerilen değer: -23 LUFS"
)

st.sidebar.markdown("---")
st.sidebar.header("🗜️ Sıkıştırma Ayarı")

auto_compress = st.sidebar.checkbox("100 MB Üstü İçin Otomatik Sıkıştır", value=True)

crf_val = st.sidebar.slider(
    "Görsel Kalite / Sıkıştırma (CRF)",
    min_value=18,
    max_value=32,
    value=24,
    step=1,
    help="Düşük CRF (18-20): Yüksek Kalite / Büyük Boyut\nYüksek CRF (28-32): Küçük Boyut"
)

def detect_black_borders(video_path):
    """FFmpeg cropdetect filtresi ile piksel seviyesinde siyah bant tespiti yapar."""
    try:
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", "cropdetect=limit=24:round=2",
            "-vframes", "30", "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        lines = result.stderr.split('\n')
        crops = [line for line in lines if "crop=" in line]
        
        if crops:
            last_crop = crops[-1].split("crop=")[1].split()[0]
            w, h, x, y = map(int, last_crop.split(':'))
            return w, h, x, y
    except Exception:
        pass
    return None

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

        # ----------------------------------------------------
        # SOL PANEL KALİTE KONTROL (QC) TESPİTİ
        # ----------------------------------------------------
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Video Format Kontrolü (QC)")

        if is_video:
            st.write("🎞️ Video algılandı, çözünürlük ve ses analizi yapılıyor...")
            video_clip = VideoFileClip(tmp_path)
            
            width, height = video_clip.w, video_clip.h
            st.sidebar.write(f"📐 **Çözünürlük:** `{width}x{height}`")

            if width == 1920 and height == 1080:
                st.sidebar.success("✅ **Çözünürlük Uygun:** 1920x1080")
            else:
                st.sidebar.error("⚠️ **Hatalı Çözünürlük:** Video 1920x1080 değil!")

            # PIKSEL SEVİYESİNDE SIYAH BANT DETEKTÖRÜ
            crop_info = detect_black_borders(tmp_path)
            if crop_info:
                crop_w, crop_h, crop_x, crop_y = crop_info
                
                # Toleranslı Kontrol (Piksel kaymaları için)
                has_letterbox = (height - crop_h) > 20
                has_pillarbox = (width - crop_w) > 20

                if has_letterbox:
                    st.sidebar.warning("⚠️ **Letterboxing Tespiti:** Videoda Alt/Üst Siyah Bant var!")
                if has_pillarbox:
                    st.sidebar.warning("⚠️ **Pillarboxing Tespiti:** Videoda Sağ/Sol Siyah Bant var!")
                if not has_letterbox and not has_pillarbox:
                    st.sidebar.success("✅ **Temiz Kadraj:** Siyah bant tespit edilmedi.")
            
            video_clip.audio.write_audiofile(extracted_audio_path, logger=None)
        else:
            st.sidebar.info("🎵 Yüklenen dosya Ses Formatında.")
            extracted_audio_path = tmp_path

        # ----------------------------------------------------
        # SES ANALİZİ & LUFS DÜZENLEME
        # ----------------------------------------------------
        data, rate = sf.read(extracted_audio_path)
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)

        st.write(f"📊 **Mevcut Ses Seviyesi:** `{loudness:.2f} LUFS`")

        normalized_data = pyln.normalize.loudness(data, loudness, target_lufs)
        new_loudness = meter.integrated_loudness(normalized_data)

        norm_audio_path = tempfile.mktemp(suffix=".wav")
        sf.write(norm_audio_path, normalized_data, rate)

        st.success(f"✅ Ses Başarıyla Normalize Edildi! Yeni Seviye: `{new_loudness:.2f} LUFS`")

        # ----------------------------------------------------
        # VİDEO İŞLEME & SIKIŞTIRMA (GÖRÜNTÜYE MÜDAHALE ETMEDEN)
        # ----------------------------------------------------
        if is_video:
            st.write("🎬 Görüntü orijinal haliyle korunup normalize edilmiş ses ekleniyor...")
            new_audio_clip = AudioFileClip(norm_audio_path)
            
            if hasattr(video_clip, 'with_audio'):
                final_video = video_clip.with_audio(new_audio_clip)
            else:
                final_video = video_clip.set_audio(new_audio_clip)
            
            output_video_path = tempfile.mktemp(suffix=".mp4")

            # 100 MB Üstü & CRF Sıkıştırma Parametreleri
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
            st.success(f"🎉 İşlem Tamamlandı! Yeni Dosya Boyutu: **{output_size_mb:.2f} MB** (Orijinal: {file_size_mb:.2f} MB)")

            with open(output_video_path, "rb") as f:
                video_bytes = f.read()
                st.video(video_bytes)
                st.download_button(
                    label=f"📥 Optimize Edilmiş Videoyu İndir ({output_size_mb:.1f} MB)",
                    data=video_bytes,
                    file_name=f"opt_{uploaded_file.name}",
                    mime="video/mp4"
                )
            
            video_clip.close()
            new_audio_clip.close()
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
