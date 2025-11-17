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

## Menü Toplama
- `python scripts/scrape_menus.py`
	- Restoran menülerini web sitelerinden ve Google Places API'den toplar.
	- Yalnızca web sitesi bilgisi olan mekanlar için çalışır.
	- Birden fazla strateji kullanır:
		- **Web Sitesi Kazıma**: Restoran web sitesinden menü bölümlerini, ürünleri ve fiyatları otomatik çıkarır.
		- **PDF/Görsel Menüler**: PDF menü linklerini ve menü görsellerini tespit eder.
		- **Google Places API**: `place_id` ve API anahtarı varsa Google'dan ek bilgi toplar.
	- Toplanan menü bilgileri `menu_data` (JSON), `menu_source` ve `menu_last_updated` sütunlarında saklanır.
	- Örnekler:
		- `python scripts/scrape_menus.py --limit 10`: İlk 10 mekanın menüsünü toplar (test için)
		- `python scripts/scrape_menus.py --delay 3`: İstekler arasında 3 saniye bekler
		- `python scripts/scrape_menus.py --force`: Daha önce toplanmış menüleri yeniden toplar
		- `python scripts/scrape_menus.py --google-api-key YOUR_KEY`: Google Places API kullanır

## Harita Üretimi
- `python scripts/generate_map.py`
	- `output/crystal_map.html` dosyası üretir. Tarayıcıda açarak mekanların işaretlendiği interaktif haritayı görüntüleyin.
	- Harita pencereleri mevcutsa Google Maps bağlantısını, güncel adresi ve telefon bilgisini gösterir. Google Maps bağlantısı yoksa adres üzerinden otomatik arama linki oluşturulur.
	- **Menü bilgileri varsa, popup penceresinde menü kategorileri ve ürünler görüntülenir.**
	- Modern görünümlü CartoDB tabanlı tema kullanır, katman menüsünden gece moduna geçebilir ve butonlar aracılığıyla Google Maps/Web bağlantılarına ulaşabilirsiniz.
	- Sol üstteki arama panelini açarak isim/adres filtreleyebilir, listedeki kayda tıkladığınızda harita ilgili mekana odaklanıp balonu otomatik açar.
	- Aynı marka/şube kombinasyonuna ait, aynı konumda yinelenen kayıtlar otomatik olarak elenir; avm gibi tek konumda farklı markalar ise korunur.

## Google Maps Liste Görünümü
- `python scripts/generate_google_list.py`
	- `output/google_list.html` dosyası üretir.
	- Her mekan için Google Maps bağlantısı, web sitesi, adres ve telefon bilgilerini tablo halinde listeler.
	- **Menü bilgileri varsa, her mekan için menü özeti gösterilir (örn: "🍽️ 24 menü ürünü · 📄 PDF menü mevcut").**
	- Üstteki arama kutusunu kullanarak metin bazlı filtreleme yapabilirsiniz.
