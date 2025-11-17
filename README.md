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
	- Restoran web sitelerinden ve Google Maps'ten menü bilgilerini otomatik olarak toplar.
	- Menüler `data/crystal_locations.db` veritabanında `menu_data` sütununda JSON formatında saklanır.
	- **Parametreler:**
		- `--delay SECONDS`: İstekler arasındaki bekleme süresi (varsayılan: 2.0 saniye)
		- `--limit N`: İşlenecek restoran sayısını sınırla (test için)
		- `--force`: Daha önce toplanmış menüleri yeniden topla
		- `--use-selenium`: JavaScript içeren siteler için Selenium kullan (chromedriver gerektirir)
	- **Özellikler:**
		- Web sitelerinden menü sayfalarını otomatik bulur ve takip eder
		- Çoklu menü çıkarma stratejileri kullanır (HTML yapısı, metin desenleri, yapılandırılmış veri)
		- Ürün adı, fiyat, açıklama ve kategori bilgilerini çıkarır
		- JSON-LD ve diğer yapılandırılmış verileri destekler
		- Selenium ile dinamik içeriği destekler (opsiyonel)
	- **Örnek kullanım:**
		- `python scripts/scrape_menus.py --limit 10`: 10 restoran için test et
		- `python scripts/scrape_menus.py --use-selenium`: Tüm restoranlar için Selenium ile çalıştır
		- `python scripts/scrape_menus.py --force --limit 5`: 5 restoranı yeniden topla

## Menü Verilerini Görüntüleme
- `python scripts/view_menus.py`
	- Toplanan menü verilerini görüntüler ve istatistikler sağlar.
	- **Parametreler:**
		- `--limit N`: Görüntülenecek menü sayısı (varsayılan: 10)
		- `--details`: Detaylı menü öğelerini göster
		- `--stats`: Sadece istatistikleri göster
	- **Örnek kullanım:**
		- `python scripts/view_menus.py --stats`: Menü toplama istatistikleri
		- `python scripts/view_menus.py --limit 5 --details`: 5 menüyü detaylı göster

## Harita Üretimi
- `python scripts/generate_map.py`
	- `output/crystal_map.html` dosyası üretir. Tarayıcıda açarak mekanların işaretlendiği interaktif haritayı görüntüleyin.
	- Harita pencereleri mevcutsa Google Maps bağlantısını, güncel adresi ve telefon bilgisini gösterir. Google Maps bağlantısı yoksa adres üzerinden otomatik arama linki oluşturulur.
	- **Menü bilgileri varsa** harita popup'larında menü öğe sayısı ve örnek ürünler gösterilir.
	- Modern görünümlü CartoDB tabanlı tema kullanır, katman menüsünden gece moduna geçebilir ve butonlar aracılığıyla Google Maps/Web bağlantılarına ulaşabilirsiniz.
	- Sol üstteki arama panelini açarak isim/adres filtreleyebilir, listedeki kayda tıkladığınızda harita ilgili mekana odaklanıp balonu otomatik açar.
	- Aynı marka/şube kombinasyonuna ait, aynı konumda yinelenen kayıtlar otomatik olarak elenir; avm gibi tek konumda farklı markalar ise korunur.

## Google Maps Liste Görünümü
- `python scripts/generate_google_list.py`
	- `output/google_list.html` dosyası üretir.
	- Her mekan için Google Maps bağlantısı, web sitesi, adres ve telefon bilgilerini tablo halinde listeler.
	- Üstteki arama kutusunu kullanarak metin bazlı filtreleme yapabilirsiniz.

## Menü Toplama Detayları

### Desteklenen Veri Kaynakları
1. **Restoran Web Siteleri**: Birçok farklı web sitesi yapısını destekler
2. **Google Maps** (Selenium ile): Dinamik içerik için JavaScript renderlaması

### Çıkarılan Bilgiler
- Ürün adları
- Fiyatlar (₺, $, €, £ desteklenir)
- Açıklamalar
- Kategoriler
- Yapılandırılmış veriler (JSON-LD, Schema.org)

### Menü Çıkarma Stratejileri
1. **HTML Yapısı Analizi**: Yaygın menü HTML desenlerini tanır
2. **Metin Deseni Eşleştirme**: "Ürün adı ... ₺100" gibi desenleri bulur
3. **Yapılandırılmış Veri**: JSON-LD ve microdata'dan menü bilgisi çıkarır
4. **Otomatik Menü Sayfası Keşfi**: Ana sayfadan menü sayfalarını bulur ve takip eder

### Teknik Notlar
- Web sitelerinin kullanım politikalarına saygı göstermek için istekler arasında gecikme kullanılır
- Menü verileri JSON formatında saklanır, kolay işleme ve görüntüleme imkanı sunar
- Dinamik web siteleri için Selenium desteği mevcuttur (opsiyonel)
- Hata toleransı yüksektir: Bir site başarısız olsa bile diğer siteler işlenmeye devam eder
