import os
import tempfile
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import streamlit as st
from moviepy import VideoFileClip, AudioFileClip

# Sayfa Yapılandırması
st.set_page_config(page_title="HepsiAd Volume, Size & QC Optimizer", page_icon="🎬", layout="centered")

st.title("🎬 HepsiAd - Video Standartlaştırma & Ses Düzenleyici")
st.markdown("Video/Ses dosyanızı yükleyin; **LUFS ses seviyesi**, **1920x1080 Full HD standart ölçü**, **Alt/Üst Siyah Bant Temizleme** ve **Sıkıştırma** otomatik yapılsın.")

# Sol Panel Ayarları
st.sidebar.header("⚙️ Ayarlar")

target_lufs = st.sidebar.slider(
    "Hedef Ses Seviyesi (LUFS)",
    min_value=-27.0,
    max_value=-19.0,
    value=-23.0,
    step=0.5,
    help="TV/Dijital yayın standartları için önerilen değer: -23 LUFS"
)

st.sidebar.markdown("---")
st.sidebar.header("📐 Çözünürlük & Siyah Bant Ayarları")

remove_letterbox = st.sidebar.checkbox("Alt ve Üst Siyah Bantları (Letterbox) Tamamen Temizle", value=True)

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
            st.write("🎞️ Video algılandı, çözünürlük ve ses analizi yapılıyor...")
            video_clip = VideoFileClip(tmp_path)
            
            width, height = video_clip.w, video_clip.h
            st.write(f"📐 **Orijinal Çözünürlük:** `{width}x{height}`")

            video_clip.audio.write_audiofile(extracted_audio_path, logger=None)
        else:
            extracted_audio_path = tmp_path

        # Ses Analizi & LUFS Ölçümü
        data, rate = sf.read(extracted_audio_path)
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)

        st.write(f"📊 **Mevcut Ses Seviyesi:** `{loudness:.2f} LUFS`")

        # LUFS Normalize
        normalized_data = pyln.normalize.loudness(data, loudness, target_lufs)
        new_loudness = meter.integrated_loudness(normalized_data)

        norm_audio_path = tempfile.mktemp(suffix=".wav")
        sf.write(norm_audio_path, normalized_data, rate)

        st.success(f"✅ Ses Başarıyla Normalize Edildi! Yeni Seviye: `{new_loudness:.2f} LUFS`")

        if is_video:
            st.write("🎬 Görüntü ve ses birleştiriliyor, alt/üst siyah bantlar temizleniyor...")
            new_audio_clip = AudioFileClip(norm_audio_path)
            
            if hasattr(video_clip, 'with_audio'):
                final_video = video_clip.with_audio(new_audio_clip)
            else:
                final_video = video_clip.set_audio(new_audio_clip)
            
            output_video_path = tempfile.mktemp(suffix=".mp4")

            # FFmpeg Filtre Yapılandırması
            ffmpeg_params = []
            video_filters = []

            if remove_letterbox:
                # 1. Otomatik siyah bant tespiti yap
                # 2. Siyah alanları kes ve görüntüyü tam 1920x1080 kadrajına oranlayarak oturt
                vf_chain = "cropdetect=limit=24:round=2,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
                video_filters.append(vf_chain)
            else:
                video_filters.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black")

            if video_filters:
                ffmpeg_params.extend(["-vf", ",".join(video_filters)])

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
            st.success(f"🎉 İşlem Tamamlandı! Çıktı Çözünürlüğü: **1920x1080 Full HD (Siyah Bantlar Temizlendi)** | Yeni Boyut: **{output_size_mb:.2f} MB**")

            with open(output_video_path, "rb") as f:
                video_bytes = f.read()
                st.video(video_bytes)
                st.download_button(
                    label=f"📥 1920x1080 Standart Videoyu İndir ({output_size_mb:.1f} MB)",
                    data=video_bytes,
                    file_name=f"clean_1080p_{uploaded_file.name}",
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
