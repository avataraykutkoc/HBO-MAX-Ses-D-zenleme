import time
import requests
import xml.etree.ElementTree as ET


def fetch_vast_and_find_media(url, max_redirects=5):
    """VAST Tag/URL'sini çözer, Wrapper varsa alt seviyelere inerek asıl MediaFile'ı bulur."""
    current_url = url

    # VAST URL içindeki makro parametrelerini dinamik değerlerle doldur/temizle
    current_url = current_url.replace("[timestamp]", str(int(time.time())))
    current_url = current_url.replace(
        "${GDPR}", "1"
    )  # İhtiyaca göre düzenleyebilirsiniz

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for _ in range(max_redirects):
        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            if response.status_code != 200:
                break

            # Dönen yanıtı parse et
            root = ET.fromstring(response.text)

            # 1. Öncelik: Doğrudan MediaFile var mı?
            media_files = root.findall(".//MediaFile")
            if media_files:
                media_urls = [
                    mf.text.strip() for mf in media_files if mf.text
                ]
                return {
                    "status": "success",
                    "media_files": media_urls,
                    "xml": response.text,
                }

            # 2. Öncelik: MediaFile yoksa VASTAdTagURI (Wrapper/Yönlendirme) var mı?
            wrapper_tag = root.find(".//VASTAdTagURI")
            if wrapper_tag is not None and wrapper_tag.text:
                # Yeni URL'ye geçip döngüyü devam ettir (Recursive Redirect)
                current_url = wrapper_tag.text.strip()
            else:
                # Ne MediaFile var ne de yönlendirme etiketi
                break

        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {
        "status": "not_found",
        "message": "XML içerisinde doğrudan MediaFile bulunamadı ve yönlendirmeler çözülemedi.",
    }
