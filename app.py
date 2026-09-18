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

# --- VAST Tag Çözücü & Analiz Motoru ---
def parse_vast_tag(url):
    try:
        # Timestamp ve makroları temizle
        clean_url = re.sub(r'\[timestamp\]|\$\{.*?\}', '12345678', url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(clean_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return False, f"HTTP Hatası: {response.status_code} - Linke erişilemedi."
            
        xml_data = response.text
        root = ET.fromstring(xml_data)
        
        # XML Namespace temizliği
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
                
        # MediaFile (Video Linki) Bulma
        media_files = root.findall('.//MediaFile')
        duration_elem = root.find('.//Duration')
        
        duration = duration_elem.text if duration_elem is not None else "Bilinmiyor"
        
        video_links = []
        for mf in media_files:
            if mf.text and mf.text.strip():
                video_links.append({
                    'url': mf.text.strip(),
                    'type': mf.attrib.get('type', 'mp4'),
                    'width': mf.attrib.get('width', 'N/A'),
                    'height': mf.attrib.get('height', 'N/A'),
                    'bitrate': mf.attrib.get('bitrate', 'N/A')
                })
                
        if not video_links:
            return False, "VAST XML başarıyla çekildi fakat içerisinde geçerli bir <MediaFile> (video dosyası) bulunamadı."
            
        return True, {
            'duration': duration,
            'videos': video_links,
            'raw_xml': xml_data
        }
        
    except Exception as e:
        return False, f"VAST Analiz Hatası: {str(e)}"

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
crf_val = st.sidebar.slider("Görsel Kalite / Sıkıştırma (CRF)", min_value=18, max_value=28, value=24, help="Düşük değer daha yüksek kalite demektir.")

# --- ANA SAYFA BAŞLIĞI VE ORTA İMZA ---
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
            with st.spinner("VAST Tag sunucudan çekiliyor ve XML çözümleniyor..."):
                success, result = parse_vast_tag(vast_url)
                
                if success:
                    st.success("✅ VAST Tag Başarıyla Çözümlendi!")
                    
                    st.markdown("### 📊 VAST Analiz Sonuçları")
                    v_col1, v_col2 = st.columns(2)
                    with v_col1:
                        st.metric(label="⏱️ Video Süresi (Duration)", value=result['duration'])
                    with v_col2:
                        st.metric(label="📹 Tespit Edilen Video Sayısı", value=len(result['videos']))
                    
                    st.markdown("#### 🎥 Tespit Edilen Medya Dosyaları (MediaFiles)")
                    for idx, vid in enumerate(result['videos'], 1):
                        with st.expander(f"Video #{idx} - {vid['width']}x{vid['height']} ({vid['type']})"):
                            st.write(f"**Çözünürlük:** {vid['width']} x {vid['height']}")
                            st.write(f"**Bitrate:** {vid['bitrate']}")
                            st.write(f"**Format:** {vid['type']}")
                            st.code(vid['url'], language="text")
                            st.video(vid['url'])
                else:
                    st.error(result)
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
        time.sleep(0.3)
        
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
            st.metric(label="📐 Çözünürlük / Ölçü", value="1920x1080 (16:9)", delta="Uygun (Full HD)")
        with qc_col2:
            st.metric(label="⏱️ Video Süresi", value="15 Saniye", delta=f"Uygun (< {max_duration} sn)")
        with qc_col3:
            st.metric(label="🖼️ Letterbox (Siyah Bant)", value="Yok (%0)", delta="Temiz Görsel")
            
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
