# ----------------------------------------------------
# TAB 1: VAST TAG ANALİZİ (FFMPEG DESTEKLİ NİHAİ SÜRÜM)
# ----------------------------------------------------
with tab1:
    vast_url = st.text_input("VAST Tag URL Adresini Girin:", placeholder="https://example.com/vast.xml")
    if st.button("VAST Tag'i Analiz Et") and vast_url:
        try:
            with st.spinner("VAST XML çekiliyor ve VPAID / MediaFile taranıyor..."):
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                response = requests.get(vast_url, headers=headers, timeout=15, allow_redirects=True)
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
                
                with st.spinner("Video FFmpeg ile güvenli şekilde indiriliyor ve analiz ediliyor..."):
                    tmp_vid_path = tempfile.mktemp(suffix=".mp4")
                    
                    # Videoyu doğrudan FFmpeg ile indirip MP4 olarak paketliyoruz (HLS / Redirect korumalı)
                    ffmpeg_download_cmd = [
                        "ffmpeg", "-y",
                        "-user_agent", headers["User-Agent"],
                        "-i", selected_media,
                        "-c", "copy",
                        tmp_vid_path
                    ]
                    
                    dl_result = subprocess.run(ffmpeg_download_cmd, stderr=subprocess.PIPE, text=True)
                    
                    if os.path.exists(tmp_vid_path) and os.path.getsize(tmp_vid_path) > 1000:
                        st.video(selected_media)
                        process_video_qc(tmp_vid_path)
                    else:
                        st.error("🚨 **Video Çekilemedi!** Link erişim kısıtlamalı, geçersiz veya desteklenmeyen bir akış formatında.")
                    
                    if os.path.exists(tmp_vid_path):
                        os.remove(tmp_vid_path)
            else:
                st.warning("⚠️ VAST XML içerisinde oynatılabilir MediaFile bulunamadı.")

        except Exception as e:
            st.error(f"VAST Analiz Hatası: {e}")
