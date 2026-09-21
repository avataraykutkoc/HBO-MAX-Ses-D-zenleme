import streamlit as st
import requests
import xml.etree.ElementTree as ET

# Page configuration
st.set_page_config(
    page_title="HepsiAd - Video Standartlaştırma & BigQuery Analiz Portalı",
    page_icon="🎬",
    layout="wide"
)

# Header Section
st.title("🎬 HepsiAd - Video Standartlaştırma & BigQuery Analiz Portalı")

# Creator Badge
st.markdown(
    """
    <div style="display: flex; justify-content: center; margin-bottom: 20px;">
        <span style="background-color: #0e1117; border: 1px solid #1f2937; color: #38bdf8; padding: 6px 16px; border-radius: 20px; font-weight: 500;">
            👨‍💻 Creator: <strong>Aykut Koç</strong>
        </span>
    </div>
    """,
    unsafe_allow_allowed_html=True if hasattr(st, "raw_html") else True
)

# VAST Tag Analiz Modülü Fonksiyonu
def render_vast_tag_analizi():
    st.header("🔗 VAST Tag Analizi")
    st.write("VAST URL'sini girerek XML içeriğini, medya dosyalarını ve piksel takiplerini detaylıca analiz edebilirsiniz.")

    vast_url = st.text_input(
        "VAST Tag URL'sini Girin:", 
        placeholder="https://example.com/vast.xml"
    )

    if st.button("VAST Tag'i Analiz Et", type="primary"):
        if not vast_url.strip():
            st.warning("Lütfen geçerli bir VAST URL'si girin.")
            return

        with st.spinner("VAST XML çekiliyor ve analiz ediliyor..."):
            try:
                # 1. URL'den VAST XML'i çek
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                response = requests.get(vast_url.strip(), headers=headers, timeout=12)
                
                if response.status_code != 200:
                    st.error(f"URL'ye ulaşılamadı. Durum Kodu: {response.status_code}")
                    return

                # 2. XML Parsing
                xml_str = response.text
                root = ET.fromstring(response.content)

                st.success("✅ VAST XML Başarıyla Çekildi ve Analiz Edildi!")

                # Sonuç Sekmeleri
                tab1, tab2, tab3 = st.tabs(["📊 Genel Bilgiler & Medya", "🎯 Etkinlikler & Pikseller", "📄 Ham XML"])

                with tab1:
                    st.subheader("Medya & Süre Bilgileri")
                    
                    # Duration (Süre)
                    durations = root.findall(".//Duration")
                    if durations and durations[0].text:
                        st.info(f"⏱️ **Reklam Süresi:** `{durations[0].text.strip()}`")

                    # MediaFile (Video Dosyaları)
                    media_files = root.findall(".//MediaFile")
                    if media_files:
                        st.write(f"Toplam **{len(media_files)}** adet medya dosyası bulundu:")
                        for idx, media in enumerate(media_files, 1):
                            m_type = media.attrib.get('type', 'Bilinmiyor')
                            bitrate = media.attrib.get('bitrate', 'N/A')
                            width = media.attrib.get('width', '')
                            height = media.attrib.get('height', '')
                            res = f"{width}x{height}" if width and height else "Boyut Belirtilmemiş"
                            
                            media_url = media.text.strip() if media.text else ""
                            
                            st.markdown(f"**{idx}. Format:** `{m_type}` | **Çözünürlük:** `{res}` | **Bitrate:** `{bitrate} kbps`")
                            st.code(media_url, language="text")
                            
                            # MP4 formatındaysa doğrudan oynatıcı ekle
                            if "mp4" in m_type.lower() or media_url.endswith(".mp4"):
                                st.video(media_url)
                    else:
                        st.warning("Medya dosyası (<MediaFile>) bulunamadı.")

                with tab2:
                    st.subheader("Tracking Events & Clicks")
                    
                    # ClickThrough (Tıklama Linki)
                    clicks = root.findall(".//ClickThrough")
                    if clicks:
                        st.write("🔗 **Tıklama Adresi (ClickThrough):**")
                        for c in clicks:
                            if c.text:
                                st.code(c.text.strip(), language="text")

                    # Tracking Events (Takip Pikselleri)
                    trackings = root.findall(".//Tracking")
                    if trackings:
                        st.write(f"📌 **Takip Pikselleri ({len(trackings)} adet):**")
                        tracking_data = []
                        for t in trackings:
                            event = t.attrib.get('event', 'Bilinmiyor')
                            url = t.text.strip() if t.text else ""
                            tracking_data.append({"Etkinlik Türü": event, "Piksel URL": url})
                        
                        st.dataframe(tracking_data, use_container_width=True)
                    else:
                        st.info("Herhangi bir tracking eventi bulunamadı.")

                with tab3:
                    st.subheader("Ham XML Çıktısı")
                    st.code(xml_str, language="xml")

            except Exception as e:
                st.error(f"VAST Tag analiz edilirken bir hata oluştu: {str(e)}")

# Ana Navigasyon Sekmeleri (Image'daki ile birebir aynı isimler)
main_tab1, main_tab2, main_tab3 = st.tabs([
    "📁 Doğrudan Video Normalizasyonu", 
    "📊 BigQuery P1 Merchant Paneli", 
    "🔗 VAST Tag Analizi"
])

with main_tab1:
    st.header("📁 Doğrudan Video Normalizasyonu")
    st.write("Video dönüştürme ve standartlaştırma işlemlerinizi buradan yapabilirsiniz.")
    # Buraya video normalizasyon modülünün kodlarını ekleyebilirsin.

with main_tab2:
    st.header("📊 BigQuery P1 Merchant Paneli")
    st.write("Merchant analizleri ve BigQuery sorgulamalarınızı buradan yürütebilirsiniz.")
    # Buraya BigQuery panel modülünün kodlarını ekleyebilirsin.

with main_tab3:
    render_vast_tag_analizi()
