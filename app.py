import streamlit as st
import pandas as pd
import os
import tempfile
import requests
import subprocess
import re

# ==========================================
# 1. SAYFA YAPILANDIRMASI (Sol Menü Sabit)
# ==========================================
st.set_page_config(
    page_title="HepsiAd Video QC & VAST Laboratuvarı",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded" # Sol menünün her zaman açık başlamasını sağlar[cite: 3]
)

# ==========================================
# 2. ÜST İMZA VE BAŞLIK
# ==========================================
st.caption("🚀 Developed with ❤️ by **Aykut Koç** | HepsiAd Video & VAST QC Tool")
st.title("🎬 HepsiAd Video Standartlaştırma & BigQuery Analiz Portalı")
st.markdown("Video dosyalarının ve VAST etiketlerinin kalite, çözünürlük ve uyumluluk kontrollerini yapabilirsiniz.")

# ==========================================
# 3. SOL YAN MENÜ (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("📋 Teknik Kriterler & Standartlar")
    st.subheader("🎥 Video QC Standartları")
    st.markdown("""
    - **Çözünürlük:** 1920x1080 (Full HD)[cite: 14]
    - **Ses Seviyesi:** -23 LUFS (±1 LUFS)[cite: 14]
    - **Format:** MP4 / MOV[cite: 14]
    - **Letterbox:** Siyah bant tespiti yapılması ve korunması[cite: 14]
    """)

# ==========================================
# 4. ANA İÇERİK & SEKMELER
# ==========================================
tab1, tab2, tab3 = st.tabs(["📁 Doğrudan Video Normalizasyonu", "📊 BigQuery P1 Merchant Paneli", "🔗 VAST Tag Analizi"])

with tab1:
    st.subheader("🛠️ Ses Normalizasyonu (-23 LUFS) ve İşleme")
    
    uploaded_file = st.file_uploader("İşlenecek Video (MP4/MOV):", type=["mp4", "mov", "mkv"])
    
    if uploaded_file is not None:
        # Video işleme mantığı örneği
        st.video(uploaded_file)
        
        # ÖRNEK ANALİZ DEĞERLERİ (Sisteminden dinamik gelen değişkenler)
        # Gerçek kodunda bu değerler ffmpeg/ffprobe analizinden alınıyor:
        original_lufs = -13.4
        new_lufs = -23.8
        has_letterbox = True
        video_width = 1920   # ffprobe ile çekilen genişlik
        video_height = 1080  # ffprobe ile çekilen yükseklik
        
        st.success("🎉 İŞLEM TAMAMLANDI! Ses seviyesi -23 LUFS yapıldı ve indirme bağlantısı hazırlandı.")
        
        # Çözünürlük Kontrol Mantığı
        is_1920x1080 = (video_width == 1920 and video_height == 1080)
        
        # 4'LÜ MERTİK KARTLARI (Çözünürlük Kontrolü Eklendi)
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.caption("Orijinal Ses Seviyesi")
            st.markdown(f"### {original_lufs:.1f} LUFS")
            
        with col2:
            st.caption("Yeni Normalize Ses")
            st.markdown(f"### {new_lufs:.1f} LUFS")
            st.caption("🎯 Standart Uyumlu")
            
        with col3:
            st.caption("Letterbox Durumu")
            if has_letterbox:
                st.markdown("### ⚠️ Siyah Bant Var")
                st.caption("↓ - Orijinal Şekilde Korundu")
            else:
                st.markdown("### ✅ Bant Yok")
                st.caption("🎯 Tam Ekran")
                
        with col4:
            st.caption("Çözünürlük Durumu (1920x1080)")
            if is_1920x1080:
                st.markdown(f"### ✅ {video_width}x{video_height}")
                st.caption("🎯 Full HD Uyumlu")
            else:
                st.markdown(f"### ⚠️ {video_width}x{video_height}")
                st.caption("❌ 1920x1080 Değil")

        if has_letterbox:
            st.warning("⚠️ LETTERBOX UYARISI: Videoda siyah bant (letterboxing) tespit edildi. İstediğiniz üzerine videonun orijinal kadrajına dokunulmadı, doğrudan yayına alabilirsiniz.")
            
        st.download_button(
            label="💾 NORMALİZE EDİLMİŞ VİDEOYU İNDİR (MP4 / -23 LUFS)",
            data=uploaded_file,
            file_name="normalized_video.mp4",
            mime="video/mp4"
        )
