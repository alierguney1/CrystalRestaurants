#!/usr/bin/env python3
"""View scraped menu data from the database."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "crystal_locations.db"


def view_menus(db_path: Path, limit: int = 10, show_details: bool = False) -> None:
    """View menu data from the database."""
    connection = sqlite3.connect(db_path)
    
    query = """
        SELECT brand, branch, menu_source, menu_data, menu_last_scraped
        FROM locations
        WHERE menu_data IS NOT NULL AND menu_data != ''
        ORDER BY menu_last_scraped DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    rows = connection.execute(query).fetchall()
    connection.close()
    
    if not rows:
        print("No menu data found in database.")
        return
    
    print(f"\nFound {len(rows)} restaurants with menu data:\n")
    print("=" * 80)
    
    for idx, row in enumerate(rows, start=1):
        brand, branch, source, menu_json, last_scraped = row
        
        try:
            menu_data = json.loads(menu_json)
        except json.JSONDecodeError:
            continue
        
        location_name = f"{brand} ({branch or 'Genel'})"
        print(f"\n{idx}. {location_name}")
        print(f"   Source: {source or 'unknown'}")
        print(f"   Last scraped: {last_scraped}")
        print(f"   Items found: {len(menu_data.get('items', []))}")
        
        if menu_data.get("categories"):
            print(f"   Categories: {', '.join(menu_data['categories'][:5])}")
        
        if show_details and menu_data.get("items"):
            print("\n   Sample items:")
            for item in menu_data["items"][:5]:
                name = item.get("name", "N/A")
                price = item.get("price", "")
                desc = item.get("description", "")[:50]
                category = item.get("category", "")
                
                print(f"     - {name} {price}")
                if category:
                    print(f"       Category: {category}")
                if desc:
                    print(f"       {desc}...")
        
        print("-" * 80)


def get_stats(db_path: Path) -> None:
    """Get statistics about menu scraping."""
    connection = sqlite3.connect(db_path)
    
    total = connection.execute("SELECT COUNT(*) FROM locations").fetchone()[0]
    with_websites = connection.execute(
        "SELECT COUNT(*) FROM locations WHERE website IS NOT NULL AND website != ''"
    ).fetchone()[0]
    with_maps = connection.execute(
        "SELECT COUNT(*) FROM locations WHERE geocode_maps_url IS NOT NULL AND geocode_maps_url != ''"
    ).fetchone()[0]
    with_menus = connection.execute(
        "SELECT COUNT(*) FROM locations WHERE menu_data IS NOT NULL AND menu_data != ''"
    ).fetchone()[0]
    attempted = connection.execute(
        "SELECT COUNT(*) FROM locations WHERE menu_last_scraped IS NOT NULL"
    ).fetchone()[0]
    
    connection.close()
    
    print("\nMenu Scraping Statistics:")
    print("=" * 60)
    print(f"Total restaurants: {total}")
    print(f"Restaurants with websites: {with_websites}")
    print(f"Restaurants with Google Maps URLs: {with_maps}")
    print(f"Menu scraping attempted: {attempted}")
    print(f"Menus successfully scraped: {with_menus}")
    if attempted > 0:
        print(f"Success rate: {with_menus / attempted * 100:.1f}%")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="View scraped menu data")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit number of menus to display (0 for all)",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Show detailed menu items",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    
    if not args.db.exists():
        print(f"Database {args.db} does not exist.", file=sys.stderr)
        return 1
    
    if args.stats:
        get_stats(args.db)
    else:
        view_menus(args.db, limit=args.limit, show_details=args.details)
        print()
        get_stats(args.db)
    
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
