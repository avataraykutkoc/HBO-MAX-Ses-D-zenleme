import os
import tempfile
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import streamlit as st
from moviepy import VideoFileClip, AudioFileClip

# Sayfa Yapılandırması
st.set_page_config(page_title="HepsiAd Volume Normalizer", page_icon="🎬", layout="centered")

st.title("🎬 HepsiAd - Video & Ses Seviyesi Düzenleyici (LUFS)")
st.markdown("MP4/Video veya ses dosyanızı yükleyin; hedef **-19 LUFS / -27 LUFS** yayın standartlarına otomatik getirilsin.")

# Sol Panel Ayarları
st.sidebar.header("⚙️ Ayarlar")
target_lufs = st.sidebar.slider(
    "Hedef Ses Seviyesi (LUFS)",
    min_value=-27.0,
    max_value=-19.0,
    value=-23.0,
    step=0.5,
    help="TV/Dijital yayın standartları için önerilen değer: -23 LUFS (-19 ile -27 arası)"
)

uploaded_file = st.file_uploader(
    "Video veya Ses Dosyası Yükle (MP4, MOV, AVI, WAV, MP3)", 
    type=["mp4", "mov", "avi", "wav", "mp3", "flac"]
)

if uploaded_file is not None:
    st.info("📂 Dosya okundu, işlem başlatılıyor...")
    
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    
    # Geçici girdi dosyası
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    try:
        extracted_audio_path = tempfile.mktemp(suffix=".wav")
        is_video = file_ext in [".mp4", ".mov", ".avi"]

        # Video ise sesini sök
        if is_video:
            st.write("🎞️ Video algılandı, ses izi ayrıştırılıyor...")
            video_clip = VideoFileClip(tmp_path)
            video_clip.audio.write_audiofile(extracted_audio_path, logger=None)
        else:
            extracted_audio_path = tmp_path

        # Ses Analizi & LUFS Ölçümü
        data, rate = sf.read(extracted_audio_path)
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)

        st.write(f"📊 **Mevcut Ses Seviyesi:** `{loudness:.2f} LUFS`")

        # LUFS Normalize İşlemi
        normalized_data = pyln.normalize.loudness(data, loudness, target_lufs)
        new_loudness = meter.integrated_loudness(normalized_data)

        # Temp Normalize WAV
        norm_audio_path = tempfile.mktemp(suffix=".wav")
        sf.write(norm_audio_path, normalized_data, rate)

        st.success(f"✅ Ses Başarıyla Normalize Edildi! Yeni Seviye: `{new_loudness:.2f} LUFS`")

        # Video Çıktısı Hazırlama
        if is_video:
            st.write("🎬 Normalize edilmiş ses videoyla birleştiriliyor...")
            new_audio_clip = AudioFileClip(norm_audio_path)
            final_video = video_clip.set_audio(new_audio_clip)
            
            output_video_path = tempfile.mktemp(suffix=".mp4")
            final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", logger=None)

            with open(output_video_path, "rb") as f:
                video_bytes = f.read()
                st.video(video_bytes)
                st.download_button(
                    label="📥 Normalize Edilmiş Videoyu İndir (MP4)",
                    data=video_bytes,
                    file_name=f"normalized_{uploaded_file.name}",
                    mime="video/mp4"
                )
            
            # Kapatma işlemleri
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
