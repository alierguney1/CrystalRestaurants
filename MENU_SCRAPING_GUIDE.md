# Menu Scraping Feature - Usage Guide

## Overview
This feature enables automatic scraping of restaurant menus from their websites and Google Maps pages. The scraped menu data is stored in the database and displayed on the interactive map.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Add Sample Menu Data (for testing)
```bash
python scripts/demo_menu_scraping.py
```

### 3. View Scraped Menus
```bash
python scripts/view_menus.py --details
```

### 4. Generate Map with Menu Data
```bash
python scripts/generate_map.py
```
Then open `output/crystal_map.html` in a browser.

## Detailed Usage

### Scraping Menus from Real Websites

#### Basic Usage (without Selenium)
```bash
# Scrape menus from all restaurants with websites
python scripts/scrape_menus.py

# Test with a limited number of restaurants
python scripts/scrape_menus.py --limit 10

# Re-scrape menus that were previously scraped
python scripts/scrape_menus.py --force
```

#### Advanced Usage (with Selenium for dynamic websites)
```bash
# Install Selenium and ChromeDriver first
pip install selenium

# Use Selenium for JavaScript-rendered websites
python scripts/scrape_menus.py --use-selenium --limit 5

# Adjust delay between requests (in seconds)
python scripts/scrape_menus.py --delay 3.0
```

### Viewing Menu Data

```bash
# Show statistics only
python scripts/view_menus.py --stats

# Show 10 most recent menus
python scripts/view_menus.py

# Show 20 menus with details
python scripts/view_menus.py --limit 20 --details

# Show all menus
python scripts/view_menus.py --limit 0
```

## Features

### Menu Extraction Strategies

The scraper uses multiple strategies to extract menu data:

1. **HTML Structure Analysis**: Recognizes common menu HTML patterns
   - Looks for elements with class/id containing "menu", "food", "dish"
   - Extracts item names, prices, descriptions, and categories

2. **Text Pattern Matching**: Finds menu items in plain text
   - Pattern: "Item Name .... ₺100"
   - Handles various price formats (₺, $, €, £)

3. **Structured Data Extraction**: Parses JSON-LD and Schema.org data
   - Restaurant and Menu schemas
   - FoodEstablishment types

4. **Automatic Menu Page Discovery**: Follows links to dedicated menu pages
   - Searches for links with "menu", "menü", "food", "yemek"

### Supported Data Sources

- **Restaurant Websites**: Most static and dynamic websites
- **Google Maps** (with Selenium): Extracts menu information from Maps listings

### Data Storage

Menus are stored in the SQLite database with these columns:

- `menu_data`: JSON string containing menu items, categories, prices
- `menu_source`: Source of the menu (website, google_maps)
- `menu_last_scraped`: Timestamp of last scraping attempt

### Menu Data Structure

```json
{
  "source": "website",
  "url": "https://example.com/menu",
  "items": [
    {
      "name": "Adana Kebap",
      "price": "₺150",
      "category": "Ana Yemekler",
      "description": "Geleneksel Adana usulü kebap"
    }
  ],
  "categories": ["Ana Yemekler", "Çorbalar", "Salatalar"],
  "structured_data": {
    "json_ld": { ... }
  }
}
```

## Map Integration

When you generate the map, restaurants with menu data will show:

- **📋 Menü: X ürün** - Number of menu items available
- **Sample menu items** - Shows first 3 items with prices
- Enhanced popup styling for menu information

## Troubleshooting

### No menus found?

1. **Check if restaurants have websites**:
   ```bash
   sqlite3 data/crystal_locations.db "SELECT COUNT(*) FROM locations WHERE website IS NOT NULL"
   ```

2. **View failed attempts**:
   ```bash
   python scripts/view_menus.py --stats
   ```

3. **Try with Selenium** for JavaScript-heavy sites:
   ```bash
   python scripts/scrape_menus.py --use-selenium --limit 5
   ```

### Selenium not working?

1. **Install ChromeDriver**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install chromium-chromedriver
   
   # macOS
   brew install chromedriver
   ```

2. **Install Selenium**:
   ```bash
   pip install selenium
   ```

### Websites blocking requests?

- Increase delay between requests:
  ```bash
  python scripts/scrape_menus.py --delay 5.0
  ```

- Some websites may have anti-scraping measures
- Respect robots.txt and website terms of service

## Rate Limiting and Ethics

- Default delay: 2 seconds between requests
- Adjustable with `--delay` parameter
- Always respect website policies
- Consider using `--limit` for testing

## Statistics

View comprehensive statistics:

```bash
python scripts/view_menus.py --stats
```

Output includes:
- Total restaurants
- Restaurants with websites
- Restaurants with Google Maps URLs
- Scraping attempts
- Successful scrapes
- Success rate

## Example Workflow

```bash
# 1. Add sample data for demonstration
python scripts/demo_menu_scraping.py

# 2. View the sample menus
python scripts/view_menus.py --details

# 3. Generate map with menu data
python scripts/generate_map.py

# 4. Open the map
# Open output/crystal_map.html in your browser

# 5. Try scraping real menus (test with 5 restaurants)
python scripts/scrape_menus.py --limit 5

# 6. View results
python scripts/view_menus.py --stats
python scripts/view_menus.py --details

# 7. Regenerate map with new data
python scripts/generate_map.py
```

## Advanced: Database Queries

Query menus directly from SQLite:

```bash
# Count menus
sqlite3 data/crystal_locations.db "SELECT COUNT(*) FROM locations WHERE menu_data IS NOT NULL"

# View a specific menu
sqlite3 data/crystal_locations.db "SELECT brand, menu_data FROM locations WHERE brand LIKE '%Ali%' LIMIT 1"

# Export menus to JSON
sqlite3 data/crystal_locations.db -json "SELECT brand, branch, menu_data FROM locations WHERE menu_data IS NOT NULL" > menus.json
```

## Notes

- Menu scraping respects website structure and may not work for all sites
- Success rate depends on website design and accessibility
- Some websites require JavaScript rendering (use --use-selenium)
- Menus are stored as structured JSON for easy processing
- The feature is designed to be extensible for future improvements
