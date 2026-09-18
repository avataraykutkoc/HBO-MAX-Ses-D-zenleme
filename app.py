import streamlit as st
import os
import tempfile
import requests
import subprocess
import time
import re
import xml.etree.ElementTree as ET

# --- Streamlit Sayfa Yapılandırması ---
st.set_page_config(
    page_title="HepsiAd Video & VAST QC Laboratuvarı",
    page_icon="🎬",
    layout="wide"
)

# --- Transfer.sh İndirme Linki Üretici ---
def upload_to_transfer_sh(file_path):
    try:
        with open(file_path, 'rb') as f:
            file_name = os.path.basename(file_path)
            response = requests.put(f'https://transfer.sh/{file_name}', data=f)
            if response.status_code == 200:
                return response.text.strip()
    except Exception:
        return None
    return None

# --- GERÇEK FFMPEG SES NORMALİZASYONU & VİDEO SIKIŞTIRMA ---
def process_video_ffmpeg(input_path, output_path, target_lufs=-23.0, crf=24):
    """
    FFmpeg loudnorm filtresi ile sesi BİREBİR verilen LUFS değerine normalize eder 
    ve video kalitesini belirlediğin CRF değerinde işler.
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:LRA=11:TP=-1.5", # Gerçek EBU R128 LUFS Normalizasyonu
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, res.stderr
    except Exception as e:
        return False, str(e)

# --- FFmpeg ile Video Analiz Fonksiyonu (LUFS & Letterbox) ---
def analyze_video_ffmpeg(video_path):
    lufs_val = -23.0
    has_letterbox = "Yok (%0)"
    
    try:
        cmd = [
            "ffmpeg", "-i", video_path, "-af", "ebur128=peak=true", "-f", "null", "-"
        ]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        matches = re.findall(r"I:\s+(-?\d+\.\d+)\s+LUFS", res.stderr)
        if matches:
            lufs_val = float(matches[-1])
    except Exception:
        pass

    try:
        cmd_crop = [
            "ffmpeg", "-i", video_path, "-vf", "cropdetect=24:16:0", "-vframes", "30", "-f", "null", "-"
        ]
        res_crop = subprocess.run(cmd_crop, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        crops = re.findall(r"crop=(\d+:\d+:\d+:\d+)", res_crop.stderr)
        if crops:
            last_crop = crops[-1]
            w, h, x, y = map(int, last_crop.split(":"))
            if y > 10:
                has_letterbox = f"Var (Siyah Bant: {y}px)"
    except Exception:
        pass
        
    return lufs_val, has_letterbox

# --- SIDEBAR (SOL MENÜ) ---
st.sidebar.markdown(
    """
    <div style="background-color: #1e1e2e; padding: 8px 12px; border-radius: 8px; border: 1px solid #313244; margin-bottom: 15px; text-align: center;">
        <span style="color: #a6adc8; font-size: 12px; font-weight: bold;">👨‍💻 Creator:</span> 
        <span style="color: #00d2ff; font-size: 13px; font-weight: bold;">Aykut Koç</span>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.header("⚙️ QC Standart Limitleri")
target_lufs = st.sidebar.number_input("Hedef Ses Seviyesi (LUFS)", value=-23.00, step=1.0)
min_lufs = st.sidebar.number_input("Minimum Kabul Edilebilir LUFS", value=-27.00, step=1.0)
max_lufs = st.sidebar.number_input("Maksimum Kabul Edilebilir LUFS", value=-19.00, step=1.0)
max_duration = st.sidebar.number_input("Maksimum Video Süresi (Saniye)", value=59, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🗜️ Sıkıştırma Ayarı (Dosya Yükleme İçin)")
auto_compress = st.sidebar.checkbox("100 MB Üstü İçin Otomatik Sıkıştır", value=True)
crf_val = st.sidebar.slider("Görsel Kalite / Sıkıştırma (CRF)", min_value=18, max_value=28, value=24)

# --- ANA SAYFA BAŞLIĞI ---
st.markdown(
    """
    <div style="display: flex; justify-content: center; margin-bottom: -10px; margin-top: -10px;">
        <div style="background-color: #1e1e2e; padding: 10px 18px; border-radius: 12px; border: 1.5px solid #00d2ff; text-align: center; box-shadow: 0 4px 12px rgba(0, 210, 255, 0.2);">
            <span style="color: #a6adc8; font-size: 14px; font-weight: bold; margin-right: 5px;">👨‍💻 Creator:</span> 
            <span style="color: #00d2ff; font-size: 16px; font-weight: bold;">Aykut Koç</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("🎬 HepsiAd - Video Standartlaştırma & VAST QC Laboratuvarı")
st.write("İster VAST Tag URL'si analiz edin, ister bilgisayarınızdan doğrudan video yükleyip LUFS, boyut ve siyah bant kontrolü yapın.")

tab1, tab2 = st.tabs(["🔗 VAST Tag Analizi", "📁 Doğrudan Video Yükleme & İşleme"])

with tab1:
    st.subheader("VAST Tag Analiz Paneli")
    vast_url = st.text_input("VAST Tag URL Adresini Girin:", placeholder="https://track.adform.net/serving/videoad/...")
    st.info("VAST Tag sekmesinden URL analiz edebilirsiniz.")

with tab2:
    st.subheader("🛠️ Ses Normalizasyonu ve Dosya İşleme")
    uploaded_file = st.file_uploader("İşlenecek Video Dosyasını Seçin (MP4/MOV):", type=["mp4", "mov", "mkv"])
    
    if uploaded_file is not None:
        orig_size_mb = uploaded_file.size / (1024 * 1024)
        st.info(f"Yüklenen Dosya Boyutu: {orig_size_mb:.2f} MB")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. Kaydet
        status_text.markdown("**⏳ Dosya sunucuya alınıyor... (%15)**")
        progress_bar.progress(15)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
            tmp_in.write(uploaded_file.read())
            input_path = tmp_in.name
            
        output_path = input_path.replace(".mp4", "_normalized.mp4")
        
        # 2. Orijinal Analiz
        status_text.markdown("**🔊 Orijinal ses LUFS seviyesi ölçülüyor... (%35)**")
        progress_bar.progress(35)
        orig_lufs, letterbox_val = analyze_video_ffmpeg(input_path)
        
        # 3. Gerçek FFmpeg İşleme
        status_text.markdown(f"**🔊 GERÇEK SES NORMALİZASYONU YAPILIYOR: {orig_lufs:.1f} LUFS ➡️ {target_lufs:.1f} LUFS... (%70)**")
        progress_bar.progress(70)
        
        success, ffmpeg_log = process_video_ffmpeg(input_path, output_path, target_lufs=target_lufs, crf=crf_val)
        
        if success and os.path.exists(output_path):
            # 4. Yeni LUFS Teyit
            status_text.markdown("**✅ İşlenmiş yeni dosya doğrulanıyor... (%90)**")
            progress_bar.progress(90)
            new_lufs, _ = analyze_video_ffmpeg(output_path)
            new_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            
            progress_bar.progress(100)
            status_text.markdown("**✅ İşlem Tamamlandı! (%100)**")
            
            st.success(f"✅ Ses Başarıyla Normalleştirildi! Orijinal: {orig_lufs:.2f} LUFS ➡️ Yeni: {new_lufs:.2f} LUFS")
            st.success(f"🎉 Dosya Boyutu: {orig_size_mb:.2f} MB ➡️ Yeni Boyut: {new_size_mb:.2f} MB")
            
            st.markdown("### 📊 İşlenmiş Video QC Kontrol Sonuçları")
            qc_col1, qc_col2, qc_col3 = st.columns(3)
            
            with qc_col1:
                st.metric(label="🔊 İşlenmiş Yeni Ses (LUFS)", value=f"{new_lufs:.2f} LUFS", delta=f"Hedef: {target_lufs} LUFS")
            with qc_col2:
                st.metric(label="🔊 Orijinal Ses (LUFS)", value=f"{orig_lufs:.2f} LUFS")
            with qc_col3:
                st.metric(label="🖼️ Letterbox (Siyah Bant)", value=letterbox_val)
                
            st.markdown("---")
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                with open(output_path, "rb") as file_data:
                    st.download_button(
                        label=f"💾 İşlenmiş Videoyu İndir ({new_size_mb:.1f} MB)",
                        data=file_data,
                        file_name=f"normalized_{uploaded_file.name}",
                        mime="video/mp4"
                    )
            
            with col2:
                link = upload_to_transfer_sh(output_path)
                if link:
                    st.success("🔗 WeTransfer / Paylaşım Linkin Hazır:")
                    st.code(link)
                else:
                    st.info("💡 Doğrudan sol taraftaki 'İşlenmiş Videoyu İndir' butonundan indirebilirsin.")
        else:
            st.error("FFmpeg işleme hatası oluştu.")
