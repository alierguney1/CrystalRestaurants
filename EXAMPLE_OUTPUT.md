# Menu Scraping Feature - Example Output

## Running the Demo

```bash
$ python scripts/demo_menu_scraping.py
```

Output:
```
======================================================================
Menu Scraping Demo & Testing Script
======================================================================

This script demonstrates the menu scraping functionality.

Usage:
  python scripts/demo_menu_scraping.py

What this does:
  - Adds sample menu data to a few restaurants in the database
  - Demonstrates the JSON structure used for menu storage
  - Shows how menu data appears in the map interface

After running this script, you can:
  1. View the sample menus:
     python scripts/view_menus.py --details

  2. Generate the map with menu data:
     python scripts/generate_map.py
     (Open output/crystal_map.html in a browser)

  3. Try real menu scraping (requires working websites):
     python scripts/scrape_menus.py --limit 5

  4. With Selenium for dynamic sites:
     python scripts/scrape_menus.py --use-selenium --limit 3
======================================================================

Adding sample menu data...

Added sample menu data to 3 restaurants

Sample menu data has been added. You can now:
  1. View menus: python scripts/view_menus.py --details
  2. Generate map: python scripts/generate_map.py
  3. Open output/crystal_map.html to see menu info in popups
```

## Viewing Menus

```bash
$ python scripts/view_menus.py --details
```

Output:
```
Found 3 restaurants with menu data:

================================================================================

1. 29 (Genel)
   Source: google_maps
   Last scraped: 2025-11-17 12:28:50
   Items found: 4

   Sample items:
     - Izgara Köfte ₺125
     - Tavuk Şiş ₺115
     - Patlıcan Kebap ₺135
     - Mevsim Salatası ₺50
--------------------------------------------------------------------------------

2. Ali Ocakbaşı (Ali Ocakbaşı-Suadiye)
   Source: website
   Last scraped: 2025-11-17 12:28:50
   Items found: 6
   Categories: Ana Yemekler, Çorbalar, Salatalar, İçecekler

   Sample items:
     - Adana Kebap ₺150
       Category: Ana Yemekler
     - Urfa Kebap ₺145
       Category: Ana Yemekler
     - Kuzu Şiş ₺160
       Category: Ana Yemekler
     - Mercimek Çorbası ₺35
       Category: Çorbalar
     - Çoban Salata ₺45
       Category: Salatalar
--------------------------------------------------------------------------------

3. Chinese & Sushi Express (Chinese & Sushi Express Altunizade)
   Source: website
   Last scraped: 2025-11-17 12:28:50
   Items found: 6
   Categories: Sushi, Noodles, Main Dishes, Appetizers

   Sample items:
     - California Roll ₺95
       Category: Sushi
     - Salmon Sashimi ₺120
       Category: Sushi
     - Dragon Roll ₺110
       Category: Sushi
     - Chicken Noodles ₺85
       Category: Noodles
     - Sweet & Sour Chicken ₺90
       Category: Main Dishes
--------------------------------------------------------------------------------
```

## Statistics

```bash
$ python scripts/view_menus.py --stats
```

Output:
```
Menu Scraping Statistics:
============================================================
Total restaurants: 517
Restaurants with websites: 67
Restaurants with Google Maps URLs: 507
Menu scraping attempted: 5
Menus successfully scraped: 3
Success rate: 60.0%
============================================================
```

## Map Generation

```bash
$ python scripts/generate_map.py
```

Output:
```
Created map with 515 locations at /home/runner/work/CrystalRestaurants/CrystalRestaurants/output/crystal_map.html
```

The generated map includes menu information in popups:

### Example Popup Content (Ali Ocakbaşı):

```
Ali Ocakbaşı
Ali Ocakbaşı-Suadiye

Adres: Suadiye, Kazım Özalp Sk. NO: 60 C Kat:4, 34740 Kadıköy/İstanbul, Türkiye
Telefon: +90 531 665 17 77

📋 Menü: 6 ürün

Örnek ürünler:
• Adana Kebap ₺150
• Urfa Kebap ₺145
• Kuzu Şiş ₺160

[Google Maps] [Web Sitesi]

Konum kaynağı: Google
```

## JSON Data Structure

Each menu is stored as JSON in the database:

```json
{
  "source": "website",
  "url": "https://example.com/menu",
  "items": [
    {
      "name": "Adana Kebap",
      "price": "₺150",
      "category": "Ana Yemekler"
    },
    {
      "name": "Urfa Kebap",
      "price": "₺145",
      "category": "Ana Yemekler"
    },
    {
      "name": "Kuzu Şiş",
      "price": "₺160",
      "category": "Ana Yemekler"
    },
    {
      "name": "Mercimek Çorbası",
      "price": "₺35",
      "category": "Çorbalar"
    },
    {
      "name": "Çoban Salata",
      "price": "₺45",
      "category": "Salatalar"
    },
    {
      "name": "Ayran",
      "price": "₺15",
      "category": "İçecekler"
    }
  ],
  "categories": [
    "Ana Yemekler",
    "Çorbalar",
    "Salatalar",
    "İçecekler"
  ]
}
```

## Real Menu Scraping Example

```bash
$ python scripts/scrape_menus.py --limit 3 --delay 1.0
```

Output:
```
Starting menu scraping...
[1/3] Processing Ahali Teşvikiye (Genel)...
  Trying Google Maps: https://maps.google.com/...
  Google Maps scraping requires Selenium. Install selenium and chromedriver. Skipping
  ✗ No menu data found

[2/3] Processing Akıntı Burnu (Genel)...
  Trying Google Maps: https://maps.google.com/...
  Google Maps scraping requires Selenium. Install selenium and chromedriver. Skipping
  ✗ No menu data found

[3/3] Processing Ali Ocakbaşı (Ali Ocakbaşı-Suadiye)...
  Scraping website: https://aliocakbasi.com/
  Error fetching https://aliocakbasi.com/: [Connection error]
  Trying Google Maps: https://maps.google.com/...
  Google Maps scraping requires Selenium. Install selenium and chromedriver. Skipping
  ✗ No menu data found

============================================================
Menu scraping completed:
  Total processed: 3
  Successfully scraped: 0
  Failed: 3
  Success rate: 0.0%
============================================================
```

Note: Real scraping success depends on website accessibility and structure. The demo data provides a working example of the feature.
