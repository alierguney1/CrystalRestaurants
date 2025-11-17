#!/usr/bin/env python3
"""Scrape Crystal Card partner venues and persist them into a SQLite database."""
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
from typing import Callable, Iterable, Optional, Sequence

import requests
from bs4 import BeautifulSoup

try:
    from geopy.geocoders import ArcGIS, Nominatim, Photon
except ImportError:  # pragma: no cover - geopy is optional at runtime
    ArcGIS = None  # type: ignore
    Nominatim = None  # type: ignore
    Photon = None  # type: ignore

SOURCE_URL = "https://www.crystalcard.com.tr/crystal-dunyasi/yurtici-anlasmali-otel-and-restoran-indirimleri"
SUPPORTED_GEOCODERS = {"nominatim", "arcgis", "photon", "google"}
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "crystal_locations.db"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"


class SimpleLocation:
    """Lightweight stand-in for geopy Location objects."""

    def __init__(self, latitude: float, longitude: float, *, address: str | None = None, raw: dict | None = None):
        self.latitude = latitude
        self.longitude = longitude
        self.address = address
        self.raw = raw or {}


class LocationRecord(dict):
    """Dictionary subclass so mypy understands well-known keys."""

    brand: str
    branch: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    extra_info: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    geocode_provider: Optional[str]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - informative warning only
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


def fetch_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


def parse_locations(html: str) -> list[LocationRecord]:
    soup = BeautifulSoup(html, "html.parser")
    locations: list[LocationRecord] = []

    for gallery_item in soup.select("div.gallery-item"):
        brand_tag = gallery_item.select_one(".gallery-right h3")
        if not brand_tag:
            continue
        brand = brand_tag.get_text(strip=True)

        info_items = gallery_item.select(".gallery-information-item")
        if not info_items:
            locations.append(
                LocationRecord(
                    brand=brand,
                    branch=None,
                    address=None,
                    phone=None,
                    website=None,
                    extra_info=None,
                    latitude=None,
                    longitude=None,
                    geocode_provider=None,
                )
            )
            continue

        for info_item in info_items:
            branch_tag = info_item.find("h4")
            branch_text = branch_tag.get_text(strip=True) if branch_tag else None

            paragraphs = [p.get_text(" ", strip=True) for p in info_item.find_all("p")]
            paragraphs = [p for p in paragraphs if p]

            address = paragraphs[0] if paragraphs else None
            phone = paragraphs[1] if len(paragraphs) > 1 else None
            extra_lines = paragraphs[2:] if len(paragraphs) > 2 else []
            extra_info = " | ".join(extra_lines) if extra_lines else None

            website = None
            for link in info_item.find_all("a", href=True):
                href = link["href"].strip()
                if not href or href.lower().startswith("javascript:"):
                    continue
                website = requests.compat.urljoin(SOURCE_URL, href)
                break

            locations.append(
                LocationRecord(
                    brand=brand,
                    branch=branch_text or None,
                    address=address,
                    phone=phone,
                    website=website,
                    extra_info=extra_info,
                    latitude=None,
                    longitude=None,
                    geocode_provider=None,
                )
            )

    return locations


def initialise_database(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_key TEXT UNIQUE NOT NULL,
            brand TEXT NOT NULL,
            branch TEXT,
            address TEXT,
            phone TEXT,
            website TEXT,
            extra_info TEXT,
            latitude REAL,
            longitude REAL,
            geocode_provider TEXT,
            raw_payload TEXT,
            last_updated TEXT NOT NULL
        )
        """
    )
    ensure_column(connection, "geocode_provider", "TEXT")
    ensure_column(connection, "resolved_address", "TEXT")
    ensure_column(connection, "resolved_phone", "TEXT")
    ensure_column(connection, "resolved_website", "TEXT")
    ensure_column(connection, "geocode_place_id", "TEXT")
    ensure_column(connection, "geocode_maps_url", "TEXT")
    return connection


def ensure_column(connection: sqlite3.Connection, name: str, definition: str) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(locations)")}
    if name not in columns:
        connection.execute(f"ALTER TABLE locations ADD COLUMN {name} {definition}")
        connection.commit()


def upsert_locations(
    connection: sqlite3.Connection,
    records: Iterable[LocationRecord],
) -> int:
    cursor = connection.cursor()
    stored = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for record in records:
        unique_key = json.dumps([
            record.get("brand"),
            record.get("branch"),
            record.get("address"),
        ], ensure_ascii=False)

        payload = json.dumps(record, ensure_ascii=False)
        cursor.execute(
            """
            INSERT INTO locations (
                unique_key, brand, branch, address, phone, website, extra_info,
                latitude, longitude, raw_payload, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(unique_key) DO UPDATE SET
                brand=excluded.brand,
                branch=excluded.branch,
                address=excluded.address,
                phone=excluded.phone,
                website=excluded.website,
                extra_info=excluded.extra_info,
                raw_payload=excluded.raw_payload,
                last_updated=excluded.last_updated
            """,
            (
                unique_key,
                record.get("brand"),
                record.get("branch"),
                record.get("address"),
                record.get("phone"),
                record.get("website"),
                record.get("extra_info"),
                record.get("latitude"),
                record.get("longitude"),
                payload,
                now,
            ),
        )
        stored += 1

    connection.commit()
    return stored


def normalise_address(address: str | None) -> str | None:
    if not address:
        return None
    cleaned = address.strip()
    cleaned = re.sub(r"^(adres|address)\s*[:=]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" / ", ", ")
    cleaned = cleaned.replace(" - ", ", ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(",; ")
    return cleaned or None


def build_geocoders(
    names: Sequence[str],
    *,
    timeout: float,
    language: str,
    nominatim_email: str | None,
    google_api_key: str | None,
) -> list[tuple[str, Callable[[str], object]]]:
    geocoders: list[tuple[str, Callable[[str], object]]] = []

    for name in names:
        key = name.strip().lower()
        if not key:
            continue
        if key not in SUPPORTED_GEOCODERS:
            print(f"Unknown geocoder '{name}'. Supported: {', '.join(sorted(SUPPORTED_GEOCODERS))}", file=sys.stderr)
            continue

        if key == "nominatim":
            if Nominatim is None:
                print("geopy[geocoders] missing Nominatim support. Install geopy to enable.", file=sys.stderr)
                continue
            user_agent = "CrystalRestaurants/1.0"
            if nominatim_email:
                user_agent += f" ({nominatim_email})"
            geolocator = Nominatim(user_agent=user_agent, timeout=timeout)

            def geocode_nominatim(query: str, *, _geo=geolocator) -> object:
                return _geo.geocode(query, exactly_one=True, language=language)

            geocoders.append((key, geocode_nominatim))
            continue

        if key == "arcgis":
            if ArcGIS is None:
                print("geopy missing ArcGIS support. Install geopy to enable.", file=sys.stderr)
                continue
            geolocator = ArcGIS(timeout=timeout)

            def geocode_arcgis(query: str, *, _geo=geolocator) -> object:
                return _geo.geocode(query, exactly_one=True)

            geocoders.append((key, geocode_arcgis))
            continue

        if key == "photon":
            if Photon is None:
                print("geopy missing Photon support. Install geopy to enable.", file=sys.stderr)
                continue
            geolocator = Photon(timeout=timeout)

            def geocode_photon(query: str, *, _geo=geolocator) -> object:
                return _geo.geocode(query, exactly_one=True, language=language)

            geocoders.append((key, geocode_photon))
            continue

        if key == "google":
            if not google_api_key:
                print(
                    "Google geocoder requested but no API key provided. Set --google-api-key or the GOOGLE_MAPS_API_KEY environment variable.",
                    file=sys.stderr,
                )
                continue

            session = requests.Session()
            def geocode_google(query: str, *, _session=session, _api_key=google_api_key) -> object:
                return geocode_with_google_places(
                    query,
                    session=_session,
                    api_key=_api_key,
                    language=language,
                    timeout=timeout,
                )

            geocoders.append((key, geocode_google))

    return geocoders


def geocode_with_google_places(
    query: str,
    *,
    session: requests.Session,
    api_key: str,
    language: str,
    timeout: float,
) -> SimpleLocation | None:
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.internationalPhoneNumber,places.nationalPhoneNumber,places.websiteUri,places.googleMapsUri",
    }
    payload = {
        "textQuery": query,
        "languageCode": language,
        "pageSize": 1,
    }

    try:
        response = session.post(search_url, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:
        print(f"[google] HTTP error for '{query}': {exc}", file=sys.stderr)
        return None

    if response.status_code != 200:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text}}
        message = error_payload.get("error", {}).get("message") or error_payload
        print(f"[google] status {response.status_code} for '{query}': {message}", file=sys.stderr)
        return None

    try:
        payload = response.json()
    except ValueError as exc:
        print(f"[google] Invalid JSON for '{query}': {exc}", file=sys.stderr)
        return None

    places = payload.get("places") or []
    if not places:
        if "error" in payload:
            message = payload.get("error", {}).get("message")
            print(f"[google] error for '{query}': {message}", file=sys.stderr)
        return None

    place = places[0]
    location = place.get("location") or {}
    lat = location.get("latitude")
    lng = location.get("longitude")
    if lat is None or lng is None:
        return None

    resolved_address = place.get("formattedAddress")
    resolved_phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
    resolved_website = place.get("websiteUri")
    place_id = place.get("id")
    maps_url = place.get("googleMapsUri")

    raw = {
        "resolved_address": resolved_address,
        "resolved_phone": resolved_phone,
        "resolved_website": resolved_website,
        "place_id": place_id,
        "maps_url": maps_url,
        "name": (place.get("displayName") or {}).get("text") if isinstance(place.get("displayName"), dict) else place.get("displayName"),
    }

    return SimpleLocation(lat, lng, address=resolved_address, raw=raw)


def geocode_records(
    connection: sqlite3.Connection,
    *,
    delay_seconds: float,
    force: bool,
    geocoders: list[tuple[str, Callable[[str], object]]],
) -> int:
    if not geocoders:
        print("No geocoders configured; skipping geocoding", file=sys.stderr)
        return 0

    query = "SELECT id, brand, branch, address, latitude, longitude FROM locations"
    rows = connection.execute(query).fetchall()

    delay = max(delay_seconds, 0.5)
    requires_one_second = any(name == "nominatim" for name, _ in geocoders)
    if requires_one_second and delay < 1.0:
        print("Nominatim selected. Increasing delay to 1 second to respect usage policy.", file=sys.stderr)
        delay = 1.0

    updated = 0
    failures: list[str] = []

    try:
        for idx, row in enumerate(rows, start=1):
            row_id, brand, branch, address, latitude, longitude = row
            if not address:
                continue
            if latitude is not None and longitude is not None and not force:
                continue

            cleaned_address = normalise_address(address)
            if not cleaned_address:
                continue

            search_parts = [brand]
            if branch and branch.lower() not in {"genel", brand.lower()}:
                search_parts.append(branch)
            search_parts.append(cleaned_address)
            search_text = ", ".join(
                dict.fromkeys(part.strip() for part in search_parts if part and part.strip())
            )
            if not search_text:
                continue
            if "Türkiye" not in search_text and "Turkey" not in search_text:
                search_text = f"{search_text}, Türkiye"

            location = None
            provider_used: Optional[str] = None

            for name, geocode_func in geocoders:
                try:
                    result = geocode_func(search_text)
                except Exception as exc:  # pragma: no cover - best effort logging
                    print(f"[{name}] failed for '{search_text}': {exc}", file=sys.stderr)
                    result = None

                if result:
                    provider_used = name
                    location = result
                    if delay > 0:
                        time.sleep(delay)
                    break

                if delay > 0:
                    time.sleep(delay)

            if not location:
                failures.append(search_text)
                print(f"No geocode result for '{search_text}'", file=sys.stderr)
                continue

            raw_data = {}
            if hasattr(location, "raw"):
                raw_candidate = getattr(location, "raw") or {}
                if isinstance(raw_candidate, dict):
                    raw_data = raw_candidate

            resolved_address = raw_data.get("resolved_address") or getattr(location, "address", None)
            resolved_phone = raw_data.get("resolved_phone")
            resolved_website = raw_data.get("resolved_website")
            place_id = raw_data.get("place_id")
            maps_url = raw_data.get("maps_url")

            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

            connection.execute(
                """
                UPDATE locations SET
                    latitude=?,
                    longitude=?,
                    geocode_provider=?,
                    resolved_address=?,
                    resolved_phone=?,
                    resolved_website=?,
                    geocode_place_id=?,
                    geocode_maps_url=?,
                    last_updated=?
                WHERE id=?
                """,
                (
                    location.latitude,
                    location.longitude,
                    provider_used,
                    resolved_address,
                    resolved_phone,
                    resolved_website,
                    place_id,
                    maps_url,
                    timestamp,
                    row_id,
                ),
            )
            updated += 1
            print(
                f"Geocoded {brand} ({branch or 'Genel'}): {location.latitude:.5f}, {location.longitude:.5f} [{provider_used}]"
            )

        connection.commit()
    except KeyboardInterrupt:  # pragma: no cover - allow graceful stop
        print("Geocoding interrupted by user", file=sys.stderr)
        connection.commit()

    if failures:
        print(f"Failed to geocode {len(failures)} locations. Last sample: {failures[-1]}", file=sys.stderr)

    return updated


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Crystal Card partner venues")
    parser.add_argument("--url", default=SOURCE_URL, help="Crystal Card listing URL to scrape")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Target SQLite database path",
    )
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Attempt to geocode addresses with the configured providers",
    )
    parser.add_argument(
        "--geocoder-list",
        dest="geocoders",
        default="nominatim,arcgis",
        help="Comma-separated list of geocoders to try (supported: nominatim, arcgis, photon, google)",
    )
    parser.add_argument(
        "--geocode-delay",
        type=float,
        default=1.5,
        metavar="SECONDS",
        help="Delay between geocoding requests (default: 1.5; Nominatim requires >= 1.0)",
    )
    parser.add_argument(
        "--geocode-timeout",
        type=float,
        default=15.0,
        help="Per-request timeout in seconds for each geocoder",
    )
    parser.add_argument(
        "--geocode-language",
        default="tr",
        help="Preferred language hint for geocoders that support it (default: tr)",
    )
    parser.add_argument(
        "--nominatim-email",
        default=None,
        help="Contact email to include in the Nominatim user agent (recommended)",
    )
    parser.add_argument(
        "--google-api-key",
        default=None,
        help="Google Maps Places API key for the 'google' geocoder (or set GOOGLE_MAPS_API_KEY)",
    )
    parser.add_argument(
        "--force-geocode",
        action="store_true",
        help="Re-run geocoding even if coordinates already exist",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    load_env_file(DEFAULT_ENV_PATH)
    html = fetch_html(args.url)
    records = parse_locations(html)

    if not records:
        print("No locations found in the provided HTML", file=sys.stderr)
        return 1

    connection = initialise_database(args.db)
    stored = upsert_locations(connection, records)
    print(f"Stored {stored} location rows in {args.db}")

    if args.geocode:
        google_api_key = (args.google_api_key or os.getenv("GOOGLE_MAPS_API_KEY") or "").strip() or None
        geocoder_names = [part.strip() for part in args.geocoders.split(",") if part.strip()]
        geocoders = build_geocoders(
            geocoder_names,
            timeout=args.geocode_timeout,
            language=args.geocode_language,
            nominatim_email=args.nominatim_email,
            google_api_key=google_api_key,
        )
        updated = geocode_records(
            connection,
            delay_seconds=args.geocode_delay,
            force=args.force_geocode,
            geocoders=geocoders,
        )
        print(f"Geocoded {updated} locations")

    connection.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
