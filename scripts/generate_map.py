#!/usr/bin/env python3
"""Generate an interactive HTML map of Crystal Card partner venues."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from urllib.parse import quote_plus

import folium
from folium import Element
from folium.plugins import BeautifyIcon, Fullscreen, MarkerCluster

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "crystal_locations.db"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output" / "crystal_map.html"

MAP_STYLES = """
<style>
:root {
    --crystal-primary: #2a9d8f;
    --crystal-primary-dark: #1f7a6d;
    --crystal-bg: #ffffff;
    --crystal-text: #24303f;
    --crystal-muted: #6b7280;
}

.leaflet-container {
    font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
    background: #f4f6fb;
}

.leaflet-control-layers {
    background: rgba(255, 255, 255, 0.9);
    border-radius: 14px;
    border: none;
    box-shadow: 0 12px 32px rgba(36, 48, 63, 0.18);
    padding: 0.75rem 0.85rem;
    color: var(--crystal-text);
}

.leaflet-control-layers-toggle {
    width: auto;
    height: auto;
    padding: 0.35rem 0.65rem;
    background: var(--crystal-primary);
    color: #fff;
    border-radius: 999px;
    font-size: 0.85rem;
    box-shadow: 0 12px 32px rgba(42, 157, 143, 0.25);
}

.leaflet-popup-content-wrapper {
    border-radius: 18px;
    box-shadow: 0 22px 38px rgba(36, 48, 63, 0.24);
    background: linear-gradient(165deg, #ffffff 0%, #f5f7fb 100%);
    border: none;
}

.leaflet-popup-tip {
    background: linear-gradient(165deg, #ffffff 0%, #f5f7fb 100%);
}

.crystal-popup {
    min-width: 240px;
    color: var(--crystal-text);
}

.crystal-popup h3 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
}

.crystal-popup p.branch {
    margin: 0.2rem 0 0;
    font-size: 0.9rem;
    color: var(--crystal-muted);
}

.crystal-popup ul.details {
    list-style: none;
    margin: 0.75rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
}

.crystal-popup ul.details li {
    display: grid;
    grid-template-columns: minmax(60px, auto) 1fr;
    gap: 0.6rem;
    font-size: 0.92rem;
}

.crystal-popup ul.details span.label {
    font-weight: 600;
    color: var(--crystal-muted);
}

.crystal-popup .extra {
    margin-top: 0.65rem;
    font-size: 0.9rem;
    color: var(--crystal-muted);
}

.crystal-popup .actions {
    margin-top: 0.9rem;
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.crystal-popup .actions a {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--crystal-primary);
    color: #fff;
    text-decoration: none;
    font-size: 0.88rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    transition: background 0.2s ease, transform 0.2s ease;
}

.crystal-popup .actions .icon {
    font-size: 1.05rem;
    line-height: 1;
}

.crystal-popup .actions a:hover {
    background: var(--crystal-primary-dark);
    transform: translateY(-1px);
}

.crystal-popup .actions a.secondary {
    background: rgba(255, 255, 255, 0.95);
    color: var(--crystal-primary);
    border: 1px solid rgba(42, 157, 143, 0.35);
}

.crystal-popup .actions a.secondary:hover {
    background: rgba(42, 157, 143, 0.12);
    color: var(--crystal-primary-dark);
}

.custom-cluster {
    background: var(--crystal-primary);
    border-radius: 50%;
    color: #fff;
    font-weight: 600;
    font-size: 0.95rem;
    box-shadow: 0 18px 36px rgba(36, 48, 63, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 3px solid rgba(255, 255, 255, 0.8);
    width: 44px;
    height: 44px;
    background-image: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.35), rgba(42,157,143,0.9));
}

.custom-cluster span {
    transform: translateY(-1px);
}

.crystal-popup .extra.source {
    font-size: 0.8rem;
    color: var(--crystal-muted);
}

.leaflet-control-fullscreen a {
    border-radius: 999px;
    box-shadow: 0 12px 24px rgba(36, 48, 63, 0.18);
    background: #fff;
}

.leaflet-bar a { border: none; }
.leaflet-bar a:hover { background: rgba(36, 48, 63, 0.08); }
</style>
"""

CLUSTER_ICON_FUNCTION = """
function(cluster) {
    const count = cluster.getChildCount();
    return L.divIcon({
        html: `<div class="custom-cluster"><span>${count}</span></div>`,
        className: 'marker-cluster',
        iconSize: [46, 46]
    });
}
"""


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def record_quality(record: dict) -> float:
    score = 0.0
    if record.get("maps_url"):
        score += 5.0
    if record.get("resolved_address"):
        score += 2.0
    if record.get("resolved_phone"):
        score += 1.5
    if record.get("resolved_website"):
        score += 1.0
    if record.get("extra_info"):
        score += 0.5
    if (record.get("geocode_provider") or "").lower() == "google":
        score += 0.5
    return score


def dedupe_key(record: dict) -> tuple:
    brand_key = normalize_text(record.get("brand"))
    branch_key = normalize_text(record.get("branch"))
    addr_key = normalize_text(record.get("resolved_address") or record.get("address"))
    phone_key = normalize_text(record.get("resolved_phone") or record.get("phone"))
    lat = record.get("latitude")
    lon = record.get("longitude")
    coord_key = (round(lat, 6), round(lon, 6)) if lat is not None and lon is not None else None

    if branch_key:
        return ("branch", brand_key, branch_key, coord_key, addr_key)
    if coord_key and addr_key:
        return ("coord_addr", brand_key, coord_key, addr_key)
    if coord_key:
        return ("coord", brand_key, coord_key, phone_key)
    return ("fallback", brand_key, addr_key, phone_key)


def deduplicate_records(records: list[dict]) -> list[dict]:
    unique: dict[tuple, dict] = {}
    for record in records:
        key = dedupe_key(record)
        existing = unique.get(key)
        if existing is None or record_quality(record) > record_quality(existing):
            unique[key] = record
    return list(unique.values())


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
    parts = ["<div class='crystal-popup'>", "<header>", f"<h3>{brand}</h3>"]
    if branch:
        parts.append(f"<p class='branch'>{branch}</p>")
    parts.append("</header>")

    detail_rows: list[str] = []
    if display_address:
        detail_rows.append(f"<li><span class='label'>Adres</span><span>{display_address}</span></li>")
    if display_phone:
        detail_rows.append(f"<li><span class='label'>Telefon</span><span>{display_phone}</span></li>")
    if detail_rows:
        parts.append("<ul class='details'>" + "".join(detail_rows) + "</ul>")

    if record.get("extra_info"):
        parts.append(f"<div class='extra'>{record['extra_info']}</div>")

    actions: list[str] = []
    if maps_url:
        actions.append(
            f"<a href='{maps_url}' target='_blank' rel='noopener'><span class='icon'>📍</span>Google Maps</a>"
        )
    if display_website:
        actions.append(
            f"<a class='secondary' href='{display_website}' target='_blank' rel='noopener'>Web Sitesi</a>"
        )
    if actions:
        parts.append("<div class='actions'>" + "".join(actions) + "</div>")

    if record.get("geocode_provider"):
        provider = record["geocode_provider"].title()
        parts.append(f"<div class='extra source'>Konum kaynağı: {provider}</div>")

    parts.append("</div>")
    return "".join(parts)


def generate_map(records: list[dict], output_path: Path) -> int:
    if not records:
        raise SystemExit("No geocoded locations found. Run scrape_crystal.py with --geocode first.")

    records = deduplicate_records(records)
    if not records:
        raise SystemExit("No unique locations available after deduplication.")

    latitudes = [rec["latitude"] for rec in records if rec["latitude"] is not None]
    longitudes = [rec["longitude"] for rec in records if rec["longitude"] is not None]
    center_lat = sum(latitudes) / len(latitudes)
    center_lon = sum(longitudes) / len(longitudes)

    base_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles=None,
        control_scale=True,
        zoom_control=True,
    )

    folium.TileLayer("CartoDB Positron", name="Açık Tema", control=False).add_to(base_map)
    folium.TileLayer("CartoDB Dark_Matter", name="Gece Modu").add_to(base_map)

    base_map.get_root().html.add_child(Element(MAP_STYLES))
    Fullscreen(position="topright", title="Tam ekran", title_cancel="Kapat").add_to(base_map)

    cluster = MarkerCluster(
        name="Restoranlar",
        icon_create_function=CLUSTER_ICON_FUNCTION,
        disableClusteringAtZoom=12,
        maxClusterRadius=36,
    )

    for record in records:
        popup_html = build_popup(record)
        icon = BeautifyIcon(
            icon="cutlery",
            prefix="fa",
            icon_shape="marker",
            background_color="#2a9d8f",
            border_color="#1f7a6d",
            text_color="#ffffff",
            border_width=2,
            inner_icon_style="font-size:16px;padding-top:2px;",
        )
        marker = folium.Marker(
            location=[record["latitude"], record["longitude"]],
            tooltip=record["brand"],
            popup=folium.Popup(popup_html, max_width=360),
            icon=icon,
        )
        cluster.add_child(marker)

    cluster.add_to(base_map)
    folium.LayerControl(position="topright").add_to(base_map)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_map.save(str(output_path))
    return len(records)


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

    location_count = generate_map(records, args.output)
    print(f"Created map with {location_count} locations at {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
