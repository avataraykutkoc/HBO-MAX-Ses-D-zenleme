import streamlit as st
import pandas as pd
import os
import tempfile
import requests
import subprocess
import re

# --- Streamlit Sayfa Yapılandırması (Sol Menü Her Zaman Açık) ---
st.set_page_config(
    page_title="HepsiAd Video QC & VAST Laboratuvarı",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Sol Menünün Kapatılmasını Tamamen Engelleyen CSS ---
st.markdown(
    """
    <style>
        /* Sol menünün kapalı başlama ihtimalini ve kapatma butonunu engeller */
        [data-testid="stSidebarCollapseButton"] {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Üst İmza / Geliştirici Bilgisi ---
st.caption("🚀 Developed with ❤️ by **Aykut Koç** | HepsiAd Video & VAST QC Tool")
st.title("🎬 HepsiAd Video & VAST Kontrol Merkezi")
st.markdown("Video dosyalarının ve VAST etiketlerinin kalite ve uyumluluk kontrollerini yapabilirsiniz.")

# --- Sol Yan Menü (Sidebar - Teknik Detaylar ve Kurallar) ---
with st.sidebar:
    st.header("📋 Teknik Kriterler & Standartlar")
    st.subheader("🎥 Video QC Standartları")
