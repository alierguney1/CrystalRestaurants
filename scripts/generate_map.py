#!/usr/bin/env python3
"""Generate an interactive HTML map of Crystal Card partner venues."""
from __future__ import annotations

import argparse
import sqlite3
from urllib.parse import quote_plus
from pathlib import Path

import folium
from folium.plugins import MarkerCluster

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "crystal_locations.db"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output" / "crystal_map.html"


def load_locations(connection: sqlite3.Connection) -> list[dict]:
    query = (
        "SELECT brand, branch, address, phone, website, extra_info, latitude, longitude, geocode_provider, "
        "resolved_address, resolved_phone, resolved_website, geocode_maps_url "
        "FROM locations WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
        " ORDER BY brand COLLATE NOCASE, branch COLLATE NOCASE"
    )
    rows = connection.execute(query).fetchall()
    records: list[dict] = []
    for row in rows:
        records.append({
            "brand": row[0],
            "branch": row[1],
            "address": row[2],
            "phone": row[3],
            "website": row[4],
            "extra_info": row[5],
            "latitude": row[6],
            "longitude": row[7],
            "geocode_provider": row[8],
            "resolved_address": row[9],
            "resolved_phone": row[10],
            "resolved_website": row[11],
            "maps_url": row[12],
        })
    return records


def build_popup(record: dict) -> str:
    brand = record["brand"]
    branch = record.get("branch")
    display_address = record.get("resolved_address") or record.get("address")
    display_phone = record.get("resolved_phone") or record.get("phone")
    display_website = record.get("resolved_website") or record.get("website")
    maps_url = record.get("maps_url")
    if not maps_url and display_address:
        query = ", ".join(filter(None, [brand, branch, display_address]))
        maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
    parts = [f"<strong>{brand}</strong>"]
    if branch:
        parts.append(f"<div><em>{branch}</em></div>")
    if display_address:
        parts.append(f"<div>{display_address}</div>")
    if display_phone:
        parts.append(f"<div>Telefon: {display_phone}</div>")
    if display_website:
        parts.append(f"<div><a href='{display_website}' target='_blank' rel='noopener'>Web Sitesi</a></div>")
    if record.get("extra_info"):
        parts.append(f"<div>{record['extra_info']}</div>")
    if maps_url:
        parts.append(
            f"<div><a href='{maps_url}' target='_blank' rel='noopener'>Google Maps</a></div>"
        )
    if record.get("geocode_provider"):
        parts.append(f"<div style='font-size: 0.85em; color: #555;'>Konum kaynağı: {record['geocode_provider'].title()}</div>")
    return "".join(parts)


def generate_map(records: list[dict], output_path: Path) -> None:
    if not records:
        raise SystemExit("No geocoded locations found. Run scrape_crystal.py with --geocode first.")

    latitudes = [rec["latitude"] for rec in records if rec["latitude"] is not None]
    longitudes = [rec["longitude"] for rec in records if rec["longitude"] is not None]
    center_lat = sum(latitudes) / len(latitudes)
    center_lon = sum(longitudes) / len(longitudes)

    base_map = folium.Map(location=[center_lat, center_lon], zoom_start=6)
    cluster = MarkerCluster(name="Restoranlar")

    for record in records:
        popup_html = build_popup(record)
        marker = folium.Marker(
            location=[record["latitude"], record["longitude"]],
            tooltip=record["brand"],
            popup=folium.Popup(popup_html, max_width=320),
        )
        cluster.add_child(marker)

    cluster.add_to(base_map)
    folium.LayerControl().add_to(base_map)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_map.save(str(output_path))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an interactive map from stored Crystal Card venues")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database produced by scrape_crystal.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the generated HTML map",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f"Database {args.db} does not exist. Run scrape_crystal.py first.")

    connection = sqlite3.connect(args.db)
    records = load_locations(connection)
    connection.close()

    generate_map(records, args.output)
    print(f"Created map with {len(records)} locations at {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
