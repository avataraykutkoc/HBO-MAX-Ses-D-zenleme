# ----------------------------------------------------
# TAB 1: VAST TAG ANALİZİ (GÜNCELLENMİŞ)
# ----------------------------------------------------
with tab1:
    vast_url = st.text_input("VAST Tag URL Adresini Girin:", placeholder="https://example.com/vast.xml")
    if st.button("VAST Tag'i Analiz Et") and vast_url:
        try:
            with st.spinner("VAST XML çekiliyor ve VPAID / MediaFile taranıyor..."):
                # Bot engellerini aşmak için Browser Header ekliyoruz
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(vast_url, headers=headers, timeout=15)
                xml_data = response.text
                
                root = ET.fromstring(xml_data)
                
                has_vpaid = False
                media_files = []
                
                for elem in root.iter():
                    if elem.tag.endswith('MediaFile'):
                        api_framework = elem.attrib.get('apiFramework', '')
                        file_type = elem.attrib.get('type', '')
                        url = elem.text.strip() if elem.text else ''
                        
                        if api_framework.upper() == 'VPAID' or 'javascript' in file_type:
                            has_vpaid = True
                        
                        if url:
                            media_files.append((file_type, url))

            st.markdown("### 🔍 VAST Tespiti")
            if has_vpaid:
                st.error("🚨 **VPAID Tespiti Yapıldı!** (Bu tag interaktif JavaScript/VPAID kodları içeriyor)")
            else:
                st.success("✅ **VPAID Yok (Pure VAST / Standart MP4 Video)**")

            if media_files:
                selected_media = media_files[0][1]
                st.write(f"📦 **Çekilen Video Linki:**")
                st.code(selected_media, language="text")
                
                with st.spinner("VAST içerisindeki video indirilip QC analizine tabi tutuluyor..."):
                    vid_res = requests.get(selected_media, headers=headers, stream=True, timeout=30)
                    
                    if vid_res.status_code == 200:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_vid:
                            for chunk in vid_res.iter_content(chunk_size=1024*1024):
                                if chunk:
                                    tmp_vid.write(chunk)
                            tmp_vid_path = tmp_vid.name
                        
                        # Dosya boyutu kontrolü (boş veya çok küçük dosya mı?)
                        if os.path.getsize(tmp_vid_path) > 1000:
                            st.video(selected_media)
                            process_video_qc(tmp_vid_path)
                        else:
                            st.error("🚨 **Video Dosyası Boş/Bozuk İndi!** Link erişimini veya CDN izinlerini kontrol edin.")
                        
                        if os.path.exists(tmp_vid_path):
                            os.remove(tmp_vid_path)
                    else:
                        st.error(f"🚨 **Video İndirilemedi!** HTTP Sunucu Yanıtı: {vid_res.status_code}")
            else:
                st.warning("⚠️ VAST XML içerisinde oynatılabilir MediaFile bulunamadı.")

        except Exception as e:
            st.error(f"VAST Analiz Hatası: {e}")
