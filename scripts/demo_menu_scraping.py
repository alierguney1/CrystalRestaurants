#!/usr/bin/env python3
"""
Demo script to test menu scraping with mock data and real examples.
This script demonstrates the menu scraping functionality without making actual web requests.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "crystal_locations.db"


def add_sample_menu_data() -> None:
    """Add sample menu data to demonstrate the feature."""
    
    sample_menus = [
        {
            "brand": "Ali Ocakbaşı",
            "menu_data": {
                "source": "website",
                "url": "https://example.com/menu",
                "items": [
                    {"name": "Adana Kebap", "price": "₺150", "category": "Ana Yemekler"},
                    {"name": "Urfa Kebap", "price": "₺145", "category": "Ana Yemekler"},
                    {"name": "Kuzu Şiş", "price": "₺160", "category": "Ana Yemekler"},
                    {"name": "Mercimek Çorbası", "price": "₺35", "category": "Çorbalar"},
                    {"name": "Çoban Salata", "price": "₺45", "category": "Salatalar"},
                    {"name": "Ayran", "price": "₺15", "category": "İçecekler"},
                ],
                "categories": ["Ana Yemekler", "Çorbalar", "Salatalar", "İçecekler"],
            },
            "menu_source": "website",
        },
        {
            "brand": "Chinese & Sushi Express",
            "menu_data": {
                "source": "website",
                "url": "https://example.com/menu",
                "items": [
                    {"name": "California Roll", "price": "₺95", "category": "Sushi"},
                    {"name": "Salmon Sashimi", "price": "₺120", "category": "Sushi"},
                    {"name": "Dragon Roll", "price": "₺110", "category": "Sushi"},
                    {"name": "Chicken Noodles", "price": "₺85", "category": "Noodles"},
                    {"name": "Sweet & Sour Chicken", "price": "₺90", "category": "Main Dishes"},
                    {"name": "Spring Rolls", "price": "₺55", "category": "Appetizers"},
                ],
                "categories": ["Sushi", "Noodles", "Main Dishes", "Appetizers"],
            },
            "menu_source": "website",
        },
        {
            "brand": "29",
            "menu_data": {
                "source": "google_maps",
                "url": "https://maps.google.com/example",
                "items": [
                    {"name": "Izgara Köfte", "price": "₺125"},
                    {"name": "Tavuk Şiş", "price": "₺115"},
                    {"name": "Patlıcan Kebap", "price": "₺135"},
                    {"name": "Mevsim Salatası", "price": "₺50"},
                ],
                "categories": [],
            },
            "menu_source": "google_maps",
        },
    ]
    
    connection = sqlite3.connect(DB_PATH)
    
    for menu_item in sample_menus:
        brand = menu_item["brand"]
        menu_json = json.dumps(menu_item["menu_data"], ensure_ascii=False)
        source = menu_item["menu_source"]
        
        # Update first restaurant with matching brand
        connection.execute(
            """
            UPDATE locations 
            SET menu_data = ?, menu_source = ?, menu_last_scraped = datetime('now')
            WHERE brand = ? AND (menu_data IS NULL OR menu_data = '')
            LIMIT 1
            """,
            (menu_json, source, brand),
        )
    
    connection.commit()
    rows_updated = connection.total_changes
    connection.close()
    
    print(f"Added sample menu data to {rows_updated} restaurants")
    print("\nSample menu data has been added. You can now:")
    print("  1. View menus: python scripts/view_menus.py --details")
    print("  2. Generate map: python scripts/generate_map.py")
    print("  3. Open output/crystal_map.html to see menu info in popups")


def show_usage() -> None:
    """Show usage examples."""
    print("=" * 70)
    print("Menu Scraping Demo & Testing Script")
    print("=" * 70)
    print("\nThis script demonstrates the menu scraping functionality.")
    print("\nUsage:")
    print("  python scripts/demo_menu_scraping.py")
    print("\nWhat this does:")
    print("  - Adds sample menu data to a few restaurants in the database")
    print("  - Demonstrates the JSON structure used for menu storage")
    print("  - Shows how menu data appears in the map interface")
    print("\nAfter running this script, you can:")
    print("  1. View the sample menus:")
    print("     python scripts/view_menus.py --details")
    print("\n  2. Generate the map with menu data:")
    print("     python scripts/generate_map.py")
    print("     (Open output/crystal_map.html in a browser)")
    print("\n  3. Try real menu scraping (requires working websites):")
    print("     python scripts/scrape_menus.py --limit 5")
    print("\n  4. With Selenium for dynamic sites:")
    print("     python scripts/scrape_menus.py --use-selenium --limit 3")
    print("=" * 70)


def main() -> int:
    if "--help" in sys.argv or "-h" in sys.argv:
        show_usage()
        return 0
    
    if not DB_PATH.exists():
        print(f"Error: Database {DB_PATH} not found.", file=sys.stderr)
        print("Run: python scripts/scrape_crystal.py --geocode", file=sys.stderr)
        return 1
    
    show_usage()
    print("\nAdding sample menu data...\n")
    add_sample_menu_data()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
