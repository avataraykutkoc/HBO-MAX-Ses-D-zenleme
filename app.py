import os
import tempfile
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import streamlit as st

# Sayfa Yapılandırması
st.set_page_config(page_title="HepsiAd Volume Normalizer", page_icon="🎙️", layout="centered")

st.title("🎙️ HepsiAd - Ses Seviyesi Düzenleyici (LUFS)")
st.markdown("Video veya ses dosyanızı yükleyin; hedef **-19 LUFS / -27 LUFS** yayın standartlarına otomatik getirilsin.")

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

uploaded_file = st.file_uploader("Ses Dosyası Yükle (WAV, FLAC, OGG)", type=["wav", "flac", "ogg"])

if uploaded_file is not None:
    st.info("📂 Dosya okundu, ses analizi yapılıyor...")
    
    # Geçici dosyaya kaydetme
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    try:
        # Sesi Yükle
        data, rate = sf.read(tmp_path)

        # LUFS Ölçümü
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)

        st.write(f"📊 **Mevcut Ses Seviyesi:** `{loudness:.2f} LUFS`")

        # LUFS Normalize İşlemi
        normalized_data = pyln.normalize.loudness(data, loudness, target_lufs)
        new_loudness = meter.integrated_loudness(normalized_data)

        # İşlenmiş Sesi Kaydet
        output_path = tempfile.mktemp(suffix=".wav")
        sf.write(output_path, normalized_data, rate)

        st.success(f"✅ Başarıyla Dönüştürüldü! Yeni Seviye: `{new_loudness:.2f} LUFS`")

        # İndirme ve Dinleme Arayüzü
        with open(output_path, "rb") as f:
            audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/wav")
            st.download_button(
                label="📥 Normalize Edilmiş Dosyayı İndir",
                data=audio_bytes,
                file_name=f"normalized_{uploaded_file.name}.wav",
                mime="audio/wav"
            )

    except Exception as e:
        st.error(f"İşlem sırasında bir hata oluştu: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
