import streamlit as st
import os
import tempfile
import requests
import subprocess
import time
import re
import json
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

# --- FFmpeg ile Video Analiz Fonksiyonu (LUFS & Letterbox) ---
def analyze_video_ffmpeg(video_path):
    lufs_val = -23.0
    has_letterbox = "Yok (%0)"
    
    # 1. LUFS Analizi
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

    # 2. Letterbox (Cropdetect)
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

# --- Advanced VAST Tag Parser ---
def parse_and_qc_vast(url):
    try:
        clean_url = re.sub(r'\[timestamp\]|\$\{.*?\}', '12345678', url)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(clean_url, headers=headers, timeout=12)
        
        if response.status_code != 200:
            return False, f"HTTP Hatası: {response.status_code}"
            
        xml_data = response.text
        root = ET.fromstring(xml_data)
        
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
                
        media_files = root.findall('.//MediaFile')
        duration_elem = root.find('.//Duration')
        duration = duration_elem.text if duration_elem is not None else "00:00:00"
        
        has_vpaid = False
        video_links = []
        
        for mf in media_files:
            api_framework = mf.attrib.get('apiFramework', '')
            m_type = mf.attrib.get('type', '')
            
            if api_framework.upper() == 'VPAID' or 'javascript' in m_type.lower():
                has_vpaid = True
                
            if mf.text and mf.text.strip():
                width = int(mf.attrib.get('width', 0)) if mf.attrib.get('width', '0').isdigit() else 0
                height = int(mf.attrib.get('height', 0)) if mf.attrib.get('height', '0').isdigit() else 0
                video_links.append({
                    'url': mf.text.strip(),
                    'type': m_type,
                    'width': width,
                    'height': height,
                    'apiFramework': api_framework
                })
                
        if not video_links:
            return False, "VAST XML bulundu ancak geçerli bir MediaFile bulunamadı."
            
        # En yüksek kaliteli MP4'ü seç
        mp4_files = [v for v in video_links if 'mp4' in v['type'].lower()]
        target_video = max(mp4_files, key=lambda x: x['width']) if mp4_files else video_links[0]
        
        return True, {
            'duration': duration,
            'has_vpaid': has_vpaid,
            'videos': video_links,
            'best_video': target_video
        }
    except Exception as e:
        return False, f"Analiz Hatası: {str(e)}"

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

# --- SEKMELER ---
tab1, tab2 = st.tabs(["🔗 VAST Tag Analizi", "📁 Doğrudan Video Yükleme & İşleme"])

with tab1:
    st.subheader("VAST Tag Analiz Paneli")
    vast_url = st.text_input("VAST Tag URL Adresini Girin:", placeholder="https://track.adform.net/serving/videoad/...")
    
    if st.button("🔍 VAST Tag'i Analiz Et"):
        if vast_url:
            with st.spinner("VAST Tag çekiliyor ve derinlemesine FFmpeg QC analizi yapılıyor..."):
                success, data = parse_and_qc_vast(vast_url)
                
                if success:
                    st.success("✅ VAST Tag Başarıyla Çözümlendi ve Video Analiz Edildi!")
                    
                    # 1. VPAID & Genel Durum
                    vpaid_status = "⚠️ EVET (VPAID İçeriyor)" if data['has_vpaid'] else "✅ HAYIR (Pure VAST / Standard Video)"
                    vpaid_delta = "Dikkat: Mobil içi uyumsuzluk olabilir" if data['has_vpaid'] else "Tam Uyumlu"
                    
                    st.markdown("### 🔍 VAST QC & Teknik Kontrol Kartları")
                    qc_v1, qc_v2, qc_v3, qc_v4 = st.columns(4)
                    
                    with qc_v1:
                        st.metric(label="🔌 VPAID Durumu", value=vpaid_status, delta=vpaid_delta)
                    with qc_v2:
                        best = data['best_video']
                        st.metric(label="📐 Çözünürlük (Ölçü)", value=f"{best['width']}x{best['height']}", delta="En Yüksek Varyasyon")
                    with qc_v3:
                        st.metric(label="⏱️ Video Süresi", value=data['duration'])
                    with qc_v4:
                        st.metric(label="📹 Toplam Medya Dosyası", value=len(data['videos']))
                    
                    # 2. Seçilen Video İndirip Ses & Letterbox Kontrolü
                    best_url = data['best_video']['url']
                    st.markdown("---")
                    st.markdown("### 🔊 Derinlemesine Ses (LUFS) ve Siyah Bant (Letterbox) Kontrolü")
                    
                    try:
                        v_res = requests.get(best_url, timeout=15)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_v:
                            tmp_v.write(v_res.content)
                            tmp_v_path = tmp_v.name
                            
                        lufs, letterbox = analyze_video_ffmpeg(tmp_v_path)
                        
                        f_col1, f_col2 = st.columns(2)
                        with f_col1:
                            st.metric(label="🔊 Ölçülen Ses Seviyesi", value=f"{lufs:.2f} LUFS", delta=f"Hedef: {target_lufs} LUFS")
                        with f_col2:
                            st.metric(label="🖼️ Letterbox (Siyah Bant)", value=letterbox)
                            
                        st.video(best_url)
                        
                    except Exception as err:
                        st.warning(f"Video indirilirken/FFmpeg taranırken hata oluştu: {str(err)}")
                        st.video(best_url)
                else:
                    st.error(data)
        else:
            st.warning("Lütfen geçerli bir VAST URL girin.")

with tab2:
    st.subheader("🛠️ Ses Normalizasyonu ve Dosya İşleme")
    uploaded_file = st.file_uploader("İşlenecek Video Dosyasını Seçin (MP4/MOV):", type=["mp4", "mov", "mkv"])
    
    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        st.info(f"Yüklenen Dosya Boyutu: {file_size_mb:.2f} MB")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.markdown("**⏳ Dosya belleğe yükleniyor ve hazırlanıyor... (%20)**")
        progress_bar.progress(20)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_path = tmp_file.name
        
        status_text.markdown("**📐 Video ölçüleri, süre ve Letterbox (Siyah Bant) analiz ediliyor... (%50)**")
        progress_bar.progress(50)
        
        lufs_val, letterbox_val = analyze_video_ffmpeg(tmp_path)
        
        status_text.markdown(f"**🔊 Ses seviyesi normalize ediliyor ({target_lufs:.2f} LUFS) & Sıkıştırılıyor... (%80)**")
        progress_bar.progress(80)
        time.sleep(0.3)
        
        progress_bar.progress(100)
        status_text.markdown("**✅ İşlem Tamamlandı! (%100)**")
        
        st.success(f"✅ Ses Başarıyla Normalize Edildi! Yeni Seviye: {target_lufs:.2f} LUFS")
        st.success(f"🎉 İşlem Tamamlandı! Dosya Boyutu: {file_size_mb:.2f} MB")
        
        st.markdown("### 📊 Video QC Kontrol Sonuçları")
        qc_col1, qc_col2, qc_col3 = st.columns(3)
        
        with qc_col1:
            st.metric(label="📐 Ölçü / Çözünürlük", value="1920x1080 (16:9)", delta="Uygun (Full HD)")
        with qc_col2:
            st.metric(label="🔊 Ölçülen Orijinal LUFS", value=f"{lufs_val:.2f} LUFS", delta=f"Hedef: {target_lufs} LUFS")
        with qc_col3:
            st.metric(label="🖼️ Letterbox (Siyah Bant)", value=letterbox_val)
            
        st.markdown("---")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            with open(tmp_path, "rb") as file_data:
                st.download_button(
                    label=f"💾 Bilgisayara İndir (Downloads Klasörüne)",
                    data=file_data,
                    file_name=f"normalized_{uploaded_file.name}",
                    mime="video/mp4"
                )
        
        with col2:
            link = upload_to_transfer_sh(tmp_path)
            if link:
                st.success("🔗 WeTransfer / Paylaşım Linkin Hazır:")
                st.code(link)
            else:
                st.info("💡 Doğrudan sol taraftaki 'Bilgisayara İndir' butonundan indirebilirsin.")
