#!/usr/bin/env python3
"""Scrape restaurant menus from websites and Google Places."""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "crystal_locations.db"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"


def load_env_file(path: Path) -> None:
    """Load environment variables from .env file."""
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Warning: Unable to read {path}: {exc}", file=sys.stderr)
        return

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_menu_columns(connection: sqlite3.Connection) -> None:
    """Ensure menu-related columns exist in the database."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(locations)")}
    
    if "menu_data" not in columns:
        connection.execute("ALTER TABLE locations ADD COLUMN menu_data TEXT")
    if "menu_source" not in columns:
        connection.execute("ALTER TABLE locations ADD COLUMN menu_source TEXT")
    if "menu_last_updated" not in columns:
        connection.execute("ALTER TABLE locations ADD COLUMN menu_last_updated TEXT")
    
    connection.commit()


def extract_menu_from_html(html: str, url: str) -> dict[str, Any] | None:
    """
    Extract menu information from HTML content.
    
    This function looks for common menu patterns in restaurant websites:
    - Menu sections with items and prices
    - PDF menu links
    - Image galleries that might contain menus
    """
    soup = BeautifulSoup(html, "html.parser")
    menu_data: dict[str, Any] = {
        "items": [],
        "sections": [],
        "pdf_menus": [],
        "image_menus": [],
    }
    
    # Look for PDF menu links
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").lower()
        text = link.get_text(strip=True).lower()
        
        if ".pdf" in href or "menü" in text or "menu" in text:
            full_url = urljoin(url, link["href"])
            if full_url.lower().endswith(".pdf") or "menu" in full_url.lower() or "menü" in full_url.lower():
                menu_data["pdf_menus"].append({
                    "url": full_url,
                    "text": link.get_text(strip=True),
                })
    
    # Look for menu images
    for img in soup.find_all("img", src=True):
        alt_text = (img.get("alt") or "").lower()
        src = img.get("src", "").lower()
        
        if "menu" in alt_text or "menü" in alt_text or "menu" in src or "menü" in src:
            full_url = urljoin(url, img["src"])
            menu_data["image_menus"].append({
                "url": full_url,
                "alt": img.get("alt", ""),
            })
    
    # Look for structured menu sections
    # Common patterns: div.menu-section, div.menu-category, section with "menu" class
    menu_containers = soup.find_all(
        ["div", "section", "article"],
        class_=re.compile(r"menu|menü", re.IGNORECASE)
    )
    
    for container in menu_containers:
        section_name = None
        
        # Try to find section header
        header = container.find(["h2", "h3", "h4", "h5"])
        if header:
            section_name = header.get_text(strip=True)
        
        # Look for menu items within this section
        items = []
        
        # Pattern 1: Lists (ul/ol)
        for list_elem in container.find_all(["ul", "ol"]):
            for item_elem in list_elem.find_all("li"):
                item_text = item_elem.get_text(" ", strip=True)
                
                # Try to extract price
                price_match = re.search(r"(\d+[.,]\d+|\d+)\s*(?:₺|TL|tl)", item_text)
                price = None
                name = item_text
                
                if price_match:
                    price = price_match.group(0).strip()
                    name = item_text[:price_match.start()].strip()
                
                if name:
                    items.append({
                        "name": name,
                        "price": price,
                    })
        
        # Pattern 2: Divs with item class
        for item_elem in container.find_all("div", class_=re.compile(r"item|product", re.IGNORECASE)):
            name_elem = item_elem.find(["h4", "h5", "h6", "span", "p"], class_=re.compile(r"name|title", re.IGNORECASE))
            price_elem = item_elem.find(["span", "p", "div"], class_=re.compile(r"price|fiyat", re.IGNORECASE))
            
            name = name_elem.get_text(strip=True) if name_elem else None
            price = price_elem.get_text(strip=True) if price_elem else None
            
            if name:
                items.append({
                    "name": name,
                    "price": price,
                })
        
        if items:
            menu_data["sections"].append({
                "name": section_name or "Genel",
                "items": items,
            })
    
    # If we found any menu data, return it
    if menu_data["pdf_menus"] or menu_data["image_menus"] or menu_data["sections"]:
        return menu_data
    
    # Fallback: Look for any price patterns on the page
    text_content = soup.get_text()
    price_patterns = re.findall(r"([^\n]+?)\s+(\d+[.,]\d+|\d+)\s*(?:₺|TL|tl)", text_content)
    
    if len(price_patterns) >= 3:  # At least 3 items with prices suggests a menu
        fallback_items = []
        for name, price in price_patterns[:50]:  # Limit to first 50 items
            name = name.strip()
            if len(name) > 3 and len(name) < 100:  # Reasonable item name length
                fallback_items.append({
                    "name": name,
                    "price": f"{price} ₺",
                })
        
        if fallback_items:
            menu_data["items"] = fallback_items
            return menu_data
    
    return None


def fetch_menu_from_google_places(
    place_id: str,
    *,
    api_key: str,
    session: requests.Session,
    timeout: float = 30,
) -> dict[str, Any] | None:
    """
    Fetch menu information from Google Places API.
    
    Note: The Places API doesn't provide menu items directly, but it can provide
    menu photos and sometimes editorial summaries that mention food items.
    """
    if not place_id:
        return None
    
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "id,displayName,editorialSummary,photos",
    }
    
    try:
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"[google] Failed to fetch place details for {place_id}: {exc}", file=sys.stderr)
        return None
    
    menu_data: dict[str, Any] = {
        "photos": [],
        "summary": None,
    }
    
    # Extract editorial summary
    if "editorialSummary" in data:
        summary = data["editorialSummary"]
        if isinstance(summary, dict):
            menu_data["summary"] = summary.get("text")
        else:
            menu_data["summary"] = str(summary)
    
    # Extract photo references (these might include menu photos)
    if "photos" in data and isinstance(data["photos"], list):
        for photo in data["photos"][:10]:  # Limit to first 10 photos
            if isinstance(photo, dict) and "name" in photo:
                menu_data["photos"].append({
                    "name": photo["name"],
                })
    
    if menu_data["photos"] or menu_data["summary"]:
        return menu_data
    
    return None


def scrape_menu_for_location(
    record: dict,
    *,
    session: requests.Session,
    google_api_key: str | None,
    delay: float,
    timeout: float,
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Attempt to scrape menu for a single location.
    
    Returns:
        Tuple of (menu_data, source) where source indicates where the menu was found.
    """
    menu_data = None
    source = None
    
    # Strategy 1: Try resolved website first (from Google Places)
    website = record.get("resolved_website") or record.get("website")
    
    if website:
        try:
            print(f"  Fetching menu from {website}...")
            response = session.get(
                website,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
            
            menu_data = extract_menu_from_html(response.text, response.url)
            
            if menu_data:
                source = "website"
                print(f"  ✓ Found menu on website")
            
        except Exception as exc:
            print(f"  Failed to fetch website {website}: {exc}", file=sys.stderr)
    
    # Strategy 2: Try Google Places API if we have a place_id and API key
    if not menu_data and google_api_key:
        place_id = record.get("geocode_place_id")
        if place_id:
            try:
                print(f"  Fetching menu from Google Places...")
                google_menu = fetch_menu_from_google_places(
                    place_id,
                    api_key=google_api_key,
                    session=session,
                    timeout=timeout,
                )
                
                if google_menu:
                    menu_data = google_menu
                    source = "google_places"
                    print(f"  ✓ Found menu data from Google Places")
                
            except Exception as exc:
                print(f"  Failed to fetch from Google Places: {exc}", file=sys.stderr)
    
    if delay > 0:
        time.sleep(delay)
    
    return menu_data, source


def scrape_menus(
    connection: sqlite3.Connection,
    *,
    delay_seconds: float,
    timeout: float,
    force: bool,
    google_api_key: str | None,
    limit: int | None,
) -> int:
    """Scrape menus for all locations in the database."""
    ensure_menu_columns(connection)
    
    # Build query
    base_query = (
        "SELECT id, brand, branch, website, resolved_website, geocode_place_id, menu_data "
        "FROM locations"
    )

    conditions = []

    if not force:
        conditions.append("menu_data IS NULL")

    # Only attempt scraping for records with a website available
    conditions.append("(website IS NOT NULL OR resolved_website IS NOT NULL)")

    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)}"
    else:
        query = base_query
    
    if limit:
        query += f" LIMIT {limit}"
    
    rows = connection.execute(query).fetchall()
    
    if not rows:
        print("No locations to process", file=sys.stderr)
        return 0
    
    print(f"Processing {len(rows)} locations...")
    
    session = requests.Session()
    updated = 0
    
    try:
        for idx, row in enumerate(rows, start=1):
            row_id, brand, branch, website, resolved_website, place_id, existing_menu = row
            
            location_name = f"{brand} - {branch}" if branch else brand
            print(f"\n[{idx}/{len(rows)}] {location_name}")
            
            record = {
                "website": website,
                "resolved_website": resolved_website,
                "geocode_place_id": place_id,
            }
            
            menu_data, source = scrape_menu_for_location(
                record,
                session=session,
                google_api_key=google_api_key,
                delay=delay_seconds,
                timeout=timeout,
            )
            
            if menu_data:
                timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                menu_json = json.dumps(menu_data, ensure_ascii=False)
                
                connection.execute(
                    """
                    UPDATE locations
                    SET menu_data = ?,
                        menu_source = ?,
                        menu_last_updated = ?
                    WHERE id = ?
                    """,
                    (menu_json, source, timestamp, row_id),
                )
                updated += 1
                
                if updated % 10 == 0:  # Commit every 10 updates
                    connection.commit()
            else:
                print(f"  ✗ No menu found")
        
        connection.commit()
        
    except KeyboardInterrupt:
        print("\nMenu scraping interrupted by user", file=sys.stderr)
        connection.commit()
    finally:
        session.close()
    
    return updated


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape restaurant menus from websites and Google Places"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database path",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Delay between requests (default: 2.0 seconds)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape menus even if already scraped",
    )
    parser.add_argument(
        "--google-api-key",
        default=None,
        help="Google Places API key (or set GOOGLE_MAPS_API_KEY env var)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of locations to process (for testing)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Main entry point."""
    args = parse_args(argv)
    load_env_file(DEFAULT_ENV_PATH)
    
    if not args.db.exists():
        print(f"Database {args.db} does not exist. Run scrape_crystal.py first.", file=sys.stderr)
        return 1
    
    google_api_key = (args.google_api_key or os.getenv("GOOGLE_MAPS_API_KEY") or "").strip() or None
    
    connection = sqlite3.connect(args.db)
    
    try:
        updated = scrape_menus(
            connection,
            delay_seconds=args.delay,
            timeout=args.timeout,
            force=args.force,
            google_api_key=google_api_key,
            limit=args.limit,
        )
        print(f"\nSuccessfully scraped menus for {updated} locations")
    finally:
        connection.close()
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
