#!/usr/bin/env python3
"""Scrape restaurant menus from websites and Google Maps."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "crystal_locations.db"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"


class MenuScraper:
    """Base class for menu scraping strategies."""

    def __init__(self, timeout: float = 30, user_agent: str = USER_AGENT, use_selenium: bool = False):
        self.timeout = timeout
        self.user_agent = user_agent
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.driver = None
        
        if self.use_selenium:
            self._init_selenium()

    def _init_selenium(self) -> None:
        """Initialize Selenium WebDriver."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={self.user_agent}")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.timeout)
        except Exception as exc:
            print(f"Failed to initialize Selenium: {exc}", file=sys.stderr)
            self.use_selenium = False
            self.driver = None

    def __del__(self):
        """Cleanup Selenium driver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def fetch_html(self, url: str, use_selenium: bool = False) -> str | None:
        """Fetch HTML content from a URL."""
        # Try Selenium first if requested and available
        if use_selenium and self.use_selenium and self.driver:
            try:
                self.driver.get(url)
                time.sleep(2)  # Wait for dynamic content
                return self.driver.page_source
            except Exception as exc:
                print(f"Selenium error for {url}: {exc}", file=sys.stderr)
                # Fall back to requests
        
        # Use requests
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            print(f"Error fetching {url}: {exc}", file=sys.stderr)
            return None

    def extract_menu_generic(self, html: str, url: str) -> dict[str, Any] | None:
        """Generic menu extraction using common patterns."""
        soup = BeautifulSoup(html, "html.parser")
        menu_data: dict[str, Any] = {
            "source": "website",
            "url": url,
            "items": [],
            "categories": [],
        }

        # Strategy 1: Look for menu-related sections by common class/id patterns
        menu_sections = soup.find_all(
            ["div", "section", "article"],
            class_=re.compile(r"menu|food|dish|meal|category", re.I),
        )
        menu_sections.extend(
            soup.find_all(
                ["div", "section", "article"],
                id=re.compile(r"menu|food|dish|meal|category", re.I),
            )
        )

        # Strategy 2: Look for structured menu items
        menu_items = soup.find_all(
            ["div", "li", "article"],
            class_=re.compile(r"menu-item|food-item|dish|product", re.I),
        )

        if menu_items:
            for item in menu_items[:100]:  # Limit to avoid overwhelming data
                item_data = self._extract_item_details(item)
                if item_data and item_data.get("name"):
                    menu_data["items"].append(item_data)

        # Strategy 3: Look for price patterns in text
        if not menu_data["items"]:
            menu_data["items"] = self._extract_from_text(soup)

        # Strategy 4: Look for structured data (JSON-LD, microdata)
        structured = self._extract_structured_data(soup)
        if structured:
            menu_data["structured_data"] = structured

        # Extract categories
        categories = self._extract_categories(soup, menu_sections)
        if categories:
            menu_data["categories"] = categories

        return menu_data if menu_data["items"] or menu_data.get("structured_data") else None

    def _extract_item_details(self, element: Any) -> dict[str, Any] | None:
        """Extract details from a menu item element."""
        item: dict[str, Any] = {}

        # Try to find item name
        name_elem = (
            element.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            or element.find(class_=re.compile(r"name|title|heading", re.I))
            or element.find(["strong", "b"])
        )
        if name_elem:
            item["name"] = name_elem.get_text(strip=True)

        # Try to find price
        price_elem = element.find(class_=re.compile(r"price|cost|amount", re.I)) or element.find(
            "span", string=re.compile(r"[₺$€£]\s*\d+|^\d+\s*[₺$€£]", re.I)
        )
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            item["price"] = price_text
        else:
            # Search in text for price patterns
            text = element.get_text()
            price_match = re.search(r"([₺$€£]\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*[₺$€£])", text)
            if price_match:
                item["price"] = price_match.group(1)

        # Try to find description
        desc_elem = element.find(class_=re.compile(r"description|desc|detail|info", re.I)) or element.find(
            "p"
        )
        if desc_elem and desc_elem != name_elem:
            desc_text = desc_elem.get_text(strip=True)
            if desc_text and len(desc_text) > 10:
                item["description"] = desc_text[:500]  # Limit description length

        # Try to find category
        category_elem = element.find_parent(class_=re.compile(r"category|section", re.I))
        if category_elem:
            cat_heading = category_elem.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if cat_heading:
                item["category"] = cat_heading.get_text(strip=True)

        return item if item.get("name") else None

    def _extract_from_text(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract menu items from plain text patterns."""
        items: list[dict[str, Any]] = []
        
        # Look for lines that match "item name ... price" pattern
        text_elements = soup.find_all(["p", "li", "div"])
        for elem in text_elements[:200]:
            text = elem.get_text(strip=True)
            if not text or len(text) > 200:
                continue

            # Pattern: "Item Name ₺100" or "Item Name ... ₺100"
            match = re.match(
                r"^(.+?)\s*[.\-\s]{2,}\s*([₺$€£]\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*[₺$€£])$",
                text,
            )
            if match:
                name, price = match.groups()
                items.append({"name": name.strip(), "price": price.strip()})

        return items

    def _extract_structured_data(self, soup: BeautifulSoup) -> dict[str, Any] | None:
        """Extract structured data (JSON-LD, microdata) for menu information."""
        structured_data: dict[str, Any] = {}

        # Look for JSON-LD
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Check if it's a Restaurant or Menu schema
                    schema_type = data.get("@type", "")
                    if isinstance(schema_type, str) and any(
                        t in schema_type.lower() for t in ["restaurant", "menu", "foodestablishment"]
                    ):
                        structured_data["json_ld"] = data
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and any(
                            t in item.get("@type", "").lower()
                            for t in ["restaurant", "menu", "foodestablishment"]
                        ):
                            structured_data["json_ld"] = item
                            break
            except (json.JSONDecodeError, AttributeError):
                continue

        return structured_data if structured_data else None

    def _extract_categories(
        self, soup: BeautifulSoup, menu_sections: list[Any]
    ) -> list[str]:
        """Extract menu categories."""
        categories: set[str] = set()

        # From menu sections
        for section in menu_sections:
            heading = section.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if heading:
                cat_text = heading.get_text(strip=True)
                if cat_text and len(cat_text) < 100:
                    categories.add(cat_text)

        # From navigation/tabs
        nav_items = soup.find_all(["a", "button"], class_=re.compile(r"tab|nav|category", re.I))
        for nav in nav_items[:20]:
            text = nav.get_text(strip=True)
            if text and len(text) < 50 and any(
                keyword in text.lower()
                for keyword in ["menu", "food", "ana", "başlangıç", "tatlı", "içecek", "çorba"]
            ):
                categories.add(text)

        return sorted(categories)

    def scrape_google_maps(self, maps_url: str) -> dict[str, Any] | None:
        """Scrape menu information from Google Maps URL."""
        if not self.use_selenium or not self.driver:
            print(
                f"Google Maps scraping requires Selenium. Install selenium and chromedriver. Skipping: {maps_url}",
                file=sys.stderr,
            )
            return None
        
        try:
            self.driver.get(maps_url)
            time.sleep(3)  # Wait for content to load
            
            menu_data: dict[str, Any] = {
                "source": "google_maps",
                "url": maps_url,
                "items": [],
                "categories": [],
            }
            
            # Try to find and click the menu tab
            try:
                # Look for menu button/tab
                menu_buttons = self.driver.find_elements(By.XPATH, "//button[contains(translate(., 'MENU', 'menu'), 'menu')]")
                if menu_buttons:
                    menu_buttons[0].click()
                    time.sleep(2)
            except Exception:
                pass
            
            # Get page source after loading
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            # Look for menu items in Google Maps
            # Google Maps uses dynamic class names, so we search by structure
            menu_items = soup.find_all("div", class_=re.compile(r"fontBodyMedium|fontBodySmall"))
            
            seen_items: set[str] = set()
            for item in menu_items[:50]:
                text = item.get_text(strip=True)
                if not text or len(text) < 3 or len(text) > 200:
                    continue
                
                # Look for price patterns
                if re.search(r"[₺$€£]\s*\d+", text):
                    item_name = re.sub(r"\s*[₺$€£]\s*\d+.*$", "", text).strip()
                    price_match = re.search(r"([₺$€£]\s*\d+(?:[.,]\d{2})?)", text)
                    
                    if item_name and price_match and item_name not in seen_items:
                        menu_data["items"].append({
                            "name": item_name,
                            "price": price_match.group(1),
                        })
                        seen_items.add(item_name)
            
            return menu_data if menu_data["items"] else None
            
        except Exception as exc:
            print(f"Error scraping Google Maps {maps_url}: {exc}", file=sys.stderr)
            return None

    def scrape_website(self, url: str) -> dict[str, Any] | None:
        """Scrape menu from a restaurant website."""
        if not url or not url.startswith(("http://", "https://")):
            return None

        # Try with regular requests first
        html = self.fetch_html(url, use_selenium=False)
        
        # If that fails and selenium is available, try with selenium
        if not html and self.use_selenium:
            html = self.fetch_html(url, use_selenium=True)
        
        if not html:
            return None

        # Try to find menu page if we're on homepage
        soup = BeautifulSoup(html, "html.parser")
        menu_links = soup.find_all(
            "a",
            href=True,
            string=re.compile(r"menu|menü|yemek|food", re.I),
        )
        if not menu_links:
            menu_links = soup.find_all(
                "a",
                href=re.compile(r"menu|menü|food|yemek", re.I),
            )

        menu_data = self.extract_menu_generic(html, url)

        # If we found a specific menu page link, try that too
        if menu_links and not menu_data:
            menu_link = menu_links[0].get("href")
            if menu_link:
                # Resolve relative URLs
                from urllib.parse import urljoin

                menu_url = urljoin(url, menu_link)
                print(f"  Following menu link: {menu_url}", file=sys.stderr)
                menu_html = self.fetch_html(menu_url, use_selenium=False)
                if menu_html:
                    menu_data = self.extract_menu_generic(menu_html, menu_url)

        return menu_data


def ensure_menu_columns(connection: sqlite3.Connection) -> None:
    """Add menu-related columns to the locations table if they don't exist."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(locations)")}
    
    if "menu_data" not in columns:
        connection.execute("ALTER TABLE locations ADD COLUMN menu_data TEXT")
    
    if "menu_last_scraped" not in columns:
        connection.execute("ALTER TABLE locations ADD COLUMN menu_last_scraped TEXT")
    
    if "menu_source" not in columns:
        connection.execute("ALTER TABLE locations ADD COLUMN menu_source TEXT")
    
    connection.commit()


def scrape_menus(
    connection: sqlite3.Connection,
    *,
    delay_seconds: float,
    force: bool,
    limit: int | None = None,
    use_selenium: bool = False,
) -> dict[str, int]:
    """Scrape menus for all restaurants in the database."""
    scraper = MenuScraper(use_selenium=use_selenium)
    
    # Get restaurants to scrape
    if force:
        query = """
            SELECT id, brand, branch, website, geocode_maps_url 
            FROM locations 
            WHERE (website IS NOT NULL AND website != '') 
               OR (geocode_maps_url IS NOT NULL AND geocode_maps_url != '')
        """
    else:
        query = """
            SELECT id, brand, branch, website, geocode_maps_url 
            FROM locations 
            WHERE ((website IS NOT NULL AND website != '') 
                   OR (geocode_maps_url IS NOT NULL AND geocode_maps_url != ''))
              AND (menu_data IS NULL OR menu_data = '')
        """
    
    if limit:
        query += f" LIMIT {limit}"
    
    rows = connection.execute(query).fetchall()
    
    stats = {
        "total": len(rows),
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }
    
    for idx, row in enumerate(rows, start=1):
        row_id, brand, branch, website, maps_url = row
        location_name = f"{brand} ({branch or 'Genel'})"
        
        print(f"[{idx}/{stats['total']}] Processing {location_name}...")
        
        menu_data = None
        source = None
        
        # Try website first
        if website:
            print(f"  Scraping website: {website}")
            menu_data = scraper.scrape_website(website)
            if menu_data:
                source = "website"
        
        # Try Google Maps if website scraping failed
        if not menu_data and maps_url:
            print(f"  Trying Google Maps: {maps_url}")
            menu_data = scraper.scrape_google_maps(maps_url)
            if menu_data:
                source = "google_maps"
        
        # Update database
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        
        if menu_data:
            menu_json = json.dumps(menu_data, ensure_ascii=False)
            connection.execute(
                """
                UPDATE locations 
                SET menu_data = ?, menu_last_scraped = ?, menu_source = ?
                WHERE id = ?
                """,
                (menu_json, timestamp, source, row_id),
            )
            stats["success"] += 1
            item_count = len(menu_data.get("items", []))
            print(f"  ✓ Found menu with {item_count} items from {source}")
        else:
            # Still update timestamp to mark as attempted
            connection.execute(
                """
                UPDATE locations 
                SET menu_last_scraped = ?
                WHERE id = ?
                """,
                (timestamp, row_id),
            )
            stats["failed"] += 1
            print(f"  ✗ No menu data found")
        
        connection.commit()
        
        # Rate limiting
        if delay_seconds > 0 and idx < stats["total"]:
            time.sleep(delay_seconds)
    
    return stats


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape restaurant menus from websites")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Target SQLite database path",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Delay between requests (default: 2.0 seconds)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape menus even if already scraped",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of restaurants to process (for testing)",
    )
    parser.add_argument(
        "--use-selenium",
        action="store_true",
        help="Use Selenium for JavaScript-rendered websites (requires chromedriver)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    
    if not args.db.exists():
        print(f"Database {args.db} does not exist. Run scrape_crystal.py first.", file=sys.stderr)
        return 1
    
    connection = sqlite3.connect(args.db)
    ensure_menu_columns(connection)
    
    print("Starting menu scraping...")
    if args.use_selenium and not SELENIUM_AVAILABLE:
        print("Warning: Selenium requested but not available. Install selenium package.", file=sys.stderr)
    
    stats = scrape_menus(
        connection,
        delay_seconds=args.delay,
        force=args.force,
        limit=args.limit,
        use_selenium=args.use_selenium,
    )
    
    connection.close()
    
    print("\n" + "=" * 60)
    print(f"Menu scraping completed:")
    print(f"  Total processed: {stats['total']}")
    print(f"  Successfully scraped: {stats['success']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Success rate: {stats['success'] / max(stats['total'], 1) * 100:.1f}%")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
