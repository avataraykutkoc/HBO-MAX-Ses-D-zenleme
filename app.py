import requests

def upload_to_transfer_sh(file_path):
    """Dosyayı doğrudan buluta yükleyip tek tıkla paylaşılabilir indirme linki üretir."""
    try:
        with open(file_path, 'rb') as f:
            file_name = os.path.basename(file_path)
            # 14 gün geçerli ücretsiz indirme linki oluşturur
            response = requests.put(f'https://transfer.sh/{file_name}', data=f)
            if response.status_code == 200:
                return response.text.strip()
    except Exception as e:
        return None
    return None

# --- Ses Normalizasyonu ve Dosya İşleme Kısmı ---
# Dosya işlendikten sonra butonların ve linkin olduğu alan:

col1, col2 = st.columns([1, 2])

with col1:
    # Bilgisayara İndir Butonu
    with open(output_file_path, "rb") as file:
        st.download_button(
            label=f"💾 Bilgisayara İndir ({file_size_mb:.1f} MB)",
            data=file,
            file_name=output_filename,
            mime="video/mp4" # ya da ses ise audio/wav vb.
        )

with col2:
    # Otomatik Link Üretme (WeTransfer Benzeri)
    with st.spinner("🔗 İndirme linki oluşturuluyor..."):
        download_link = upload_to_transfer_sh(output_file_path)
        
        if download_link:
            st.success("🎉 İndirdim, WeTransfer / Linkin bu:")
            st.code(download_link, language="text")
        else:
            st.warning("⚠️ Link oluşturulamadı, doğrudan 'Bilgisayara İndir' butonunu kullanabilirsiniz.")
