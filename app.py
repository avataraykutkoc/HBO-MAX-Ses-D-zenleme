import streamlit as st
import pandas as pd
import os
import tempfile
import requests
import subprocess
import re

# --- Streamlit Sayfa Yapılandırması (Sol Menüyü Açık Başlatır) ---
st.set_page_config(
    page_title="HepsiAd Video QC & VAST Laboratuvarı",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Üst İmza / Geliştirici Bilgisi ---
st.caption("🚀 Developed with ❤️ by **Aykut Koç** | HepsiAd Video & VAST QC Tool")
st.title("🎬 HepsiAd Video & VAST Kontrol Merkezi")
st.markdown("Video dosyalarının ve VAST etiketlerinin kalite ve uyumluluk kontrollerini yapabilirsiniz.")

# --- Sol Yan Menü (Sidebar - Teknik Detaylar ve Kurallar) ---
with st.sidebar:
    st.header("📋 Teknik Kriterler & Standartlar")
    st.subheader("🎥 Video QC Standartları")
