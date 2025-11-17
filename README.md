# CrystalRestaurants

Haritadaki Crystal Card anlaşmalı restoranları otomatik olarak derlemek ve görselleştirmek için yardımcı betikler.

## Kurulum
- İsteğe bağlı sanal ortam oluşturun ve etkinleştirin.
- Gereksinimleri kurun: `pip install -r requirements.txt`

## Veri Toplama
- `python scripts/scrape_crystal.py --geocode`
	- Çalıştırdıktan sonra `data/crystal_locations.db` dosyası oluşur veya güncellenir.
	- Varsayılan olarak Nominatim ve ArcGIS sırasıyla denenir. Kendi tercihlerinizi `--geocoder-list nominatim,arcgis,photon` gibi parametreyle belirleyebilirsiniz.
	- Nominatim kullanırken erişim politikasına uygun şekilde gecikme süresini (`--geocode-delay`) en az 1 sn tutun ve mümkünse `--nominatim-email example@mail.com` ile iletişim bilgisi ekleyin.
	- Google Maps Places API kullanmak için `--geocoder-list google` (veya listeye ekleyin) ile çalıştırın. API anahtarınızı `--google-api-key YOUR_KEY` parametresiyle ya da `GOOGLE_MAPS_API_KEY` ortam değişkeni üzerinden sağlayın. Google politikalarına ve kota limitlerine uyduğunuzdan emin olun.
	- Depo kökünde `.env` dosyası bulunuyorsa otomatik olarak yüklenir. Örneğin `GOOGLE_MAPS_API_KEY="XXXXXXXX"` satırı ekleyebilirsiniz.
	- Geri dönen koordinatlar `geocode_provider` alanında hangi servisle bulunduğu bilgisiyle saklanır.
	- Google sonuçlarında adres, telefon, web sitesi ve Google Maps bağlantısı gibi ek alanlar `resolved_*` sütunlarına kaydedilir.

## Harita Üretimi
- `python scripts/generate_map.py`
	- `output/crystal_map.html` dosyası üretir. Tarayıcıda açarak mekanların işaretlendiği interaktif haritayı görüntüleyin.
	- Harita pencereleri mevcutsa Google Maps bağlantısını, güncel adresi ve telefon bilgisini gösterir. Google Maps bağlantısı yoksa adres üzerinden otomatik arama linki oluşturulur.
	- Modern görünümlü CartoDB tabanlı tema kullanır, katman menüsünden gece moduna geçebilir ve butonlar aracılığıyla Google Maps/Web bağlantılarına ulaşabilirsiniz.
	- Sol üstteki arama panelini açarak isim/adres filtreleyebilir, listedeki kayda tıkladığınızda harita ilgili mekana odaklanıp balonu otomatik açar.
	- Aynı marka/şube kombinasyonuna ait, aynı konumda yinelenen kayıtlar otomatik olarak elenir; avm gibi tek konumda farklı markalar ise korunur.

## Google Maps Liste Görünümü
- `python scripts/generate_google_list.py`
	- `output/google_list.html` dosyası üretir.
	- Her mekan için Google Maps bağlantısı, web sitesi, adres ve telefon bilgilerini tablo halinde listeler.
	- Üstteki arama kutusunu kullanarak metin bazlı filtreleme yapabilirsiniz.
