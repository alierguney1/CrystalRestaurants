#!/usr/bin/env python3
"""Generate an interactive HTML map of Crystal Card partner venues."""
from __future__ import annotations

import argparse
import json
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --crystal-primary: #2a9d8f;
    --crystal-primary-dark: #1f7a6d;
    --crystal-primary-light: #e0f5f2;
    --crystal-bg: #ffffff;
    --crystal-text: #24303f;
    --crystal-muted: #6b7280;
    --crystal-accent: #f59e0b;
    --crystal-price: #10b981;
    --crystal-shadow: rgba(36, 48, 63, 0.24);
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
    border-radius: 20px;
    box-shadow: 0 25px 50px var(--crystal-shadow);
    background: linear-gradient(165deg, #ffffff 0%, #f8fafb 100%);
    border: none;
    overflow: hidden;
}

.leaflet-popup-tip {
    background: linear-gradient(165deg, #ffffff 0%, #f8fafb 100%);
}

.crystal-popup {
    min-width: 280px;
    max-width: 400px;
    color: var(--crystal-text);
}

.crystal-popup h3 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--crystal-primary), var(--crystal-primary-dark));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.crystal-popup p.branch {
    margin: 0.3rem 0 0;
    font-size: 0.95rem;
    color: var(--crystal-muted);
    font-weight: 500;
}

.crystal-popup ul.details {
    list-style: none;
    margin: 0.85rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.45rem;
}

.crystal-popup ul.details li {
    display: grid;
    grid-template-columns: minmax(70px, auto) 1fr;
    gap: 0.7rem;
    font-size: 0.92rem;
    line-height: 1.5;
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

/* Modern Menu Styles */
.menu-section {
    margin-top: 1rem;
    background: linear-gradient(145deg, var(--crystal-primary-light), #f0fdf9);
    border-radius: 16px;
    padding: 1rem;
    border: 2px solid rgba(42, 157, 143, 0.2);
    position: relative;
    overflow: hidden;
}

.menu-section::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--crystal-primary), var(--crystal-accent));
}

.menu-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0 0 0.75rem;
}

.menu-header h4 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--crystal-primary);
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.menu-date-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: rgba(255, 255, 255, 0.9);
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--crystal-muted);
    border: 1px solid rgba(42, 157, 143, 0.25);
}

.menu-category {
    margin-bottom: 0.85rem;
}

.menu-category:last-child {
    margin-bottom: 0;
}

.menu-category-name {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--crystal-text);
    margin-bottom: 0.5rem;
    padding-bottom: 0.3rem;
    border-bottom: 2px solid rgba(42, 157, 143, 0.2);
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

.menu-items {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.4rem;
}

.menu-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.6rem;
    background: rgba(255, 255, 255, 0.8);
    border-radius: 10px;
    transition: all 0.2s ease;
    border: 1px solid rgba(42, 157, 143, 0.1);
}

.menu-item:hover {
    background: rgba(255, 255, 255, 1);
    transform: translateX(3px);
    box-shadow: 0 2px 8px rgba(42, 157, 143, 0.15);
}

.menu-item-name {
    font-size: 0.88rem;
    color: var(--crystal-text);
    font-weight: 500;
    flex: 1;
    margin-right: 0.5rem;
}

.menu-item-price {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--crystal-price);
    background: linear-gradient(135deg, #d1fae5, #a7f3d0);
    padding: 0.25rem 0.6rem;
    border-radius: 999px;
    white-space: nowrap;
    box-shadow: 0 2px 4px rgba(16, 185, 129, 0.15);
}

.menu-more {
    font-style: italic;
    color: var(--crystal-muted);
    font-size: 0.82rem;
    text-align: center;
    margin-top: 0.5rem;
    padding: 0.4rem;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 8px;
}

.menu-pdf-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: var(--crystal-primary);
    font-size: 0.9rem;
    font-weight: 600;
    text-decoration: none;
    padding: 0.5rem 0.75rem;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 10px;
    margin-bottom: 0.4rem;
    transition: all 0.2s ease;
    border: 1px solid rgba(42, 157, 143, 0.2);
}

.menu-pdf-link:hover {
    background: rgba(255, 255, 255, 1);
    transform: translateX(3px);
    box-shadow: 0 2px 8px rgba(42, 157, 143, 0.2);
}

.crystal-popup .actions {
    margin-top: 1rem;
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
    font-weight: 600;
    padding: 0.5rem 0.9rem;
    border-radius: 999px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(42, 157, 143, 0.3);
}

.crystal-popup .actions .icon {
    font-size: 1.05rem;
    line-height: 1;
}

.crystal-popup .actions a:hover {
    background: var(--crystal-primary-dark);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(42, 157, 143, 0.4);
}

.crystal-popup .actions a.secondary {
    background: rgba(255, 255, 255, 0.95);
    color: var(--crystal-primary);
    border: 2px solid rgba(42, 157, 143, 0.4);
}

.crystal-popup .actions a.secondary:hover {
    background: rgba(42, 157, 143, 0.12);
    color: var(--crystal-primary-dark);
    border-color: var(--crystal-primary);
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

#crystal-search-panel {
    position: absolute;
    top: 92px;
    left: 24px;
    width: 320px;
    max-width: 80vw;
    z-index: 999;
    transition: transform 0.25s ease, opacity 0.25s ease;
    font-family: 'Inter', 'Segoe UI', Roboto, sans-serif;
}

#crystal-search-panel.collapsed .panel-body {
    display: none;
}

#crystal-search-panel.collapsed {
    transform: translateX(-4px);
    opacity: 0.88;
}

#crystal-search-panel .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--crystal-primary);
    border: none;
    color: #fff;
    padding: 0.55rem 0.95rem;
    border-radius: 16px;
    box-shadow: 0 15px 30px rgba(36, 48, 63, 0.22);
    cursor: pointer;
    font-size: 0.92rem;
}

#crystal-search-panel .toggle:hover {
    background: var(--crystal-primary-dark);
}

#crystal-search-panel .panel-body {
    margin-top: 0.75rem;
    background: rgba(255, 255, 255, 0.96);
    border-radius: 18px;
    box-shadow: 0 22px 44px rgba(36, 48, 63, 0.18);
    padding: 0.95rem;
    backdrop-filter: blur(6px);
}

#crystal-search-panel input[type="search"] {
    width: 100%;
    padding: 0.55rem 0.75rem;
    border-radius: 12px;
    border: 1px solid rgba(36, 48, 63, 0.18);
    font-size: 0.92rem;
    outline: none;
}

#crystal-search-panel input[type="search"]:focus {
    border-color: var(--crystal-primary);
    box-shadow: 0 0 0 3px rgba(42, 157, 143, 0.18);
}

#crystal-search-results {
    list-style: none;
    margin: 0.85rem 0 0;
    padding: 0;
    max-height: 320px;
    overflow-y: auto;
    display: grid;
    gap: 0.6rem;
}

#crystal-search-results li {
    background: #f6f8fc;
    border-radius: 14px;
    padding: 0.65rem 0.75rem;
    box-shadow: inset 0 0 0 1px rgba(36, 48, 63, 0.05);
    cursor: pointer;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

#crystal-search-results li:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(36, 48, 63, 0.18);
    background: #fff;
}

#crystal-search-results li strong {
    display: block;
    font-weight: 600;
    color: var(--crystal-text);
}

#crystal-search-results li span {
    display: block;
    color: var(--crystal-muted);
    font-size: 0.85rem;
    margin-top: 0.2rem;
}

#crystal-search-results li p {
    margin: 0.35rem 0 0;
    font-size: 0.85rem;
    color: var(--crystal-muted);
}

#crystal-search-panel .empty-state {
    display: none;
    margin-top: 0.75rem;
    font-size: 0.85rem;
    color: var(--crystal-muted);
    text-align: center;
}

@media (max-width: 640px) {
    #crystal-search-panel {
        top: auto;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        width: calc(100% - 32px);
        max-width: 420px;
    }

    #crystal-search-panel.collapsed {
        transform: translate(-50%, 0);
    }
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
        html: `<div class=\"custom-cluster\"><span>${count}</span></div>`,
        className: 'marker-cluster',
        iconSize: [46, 46]
    });
}
"""

SEARCH_PANEL_HTML = """
<div id='crystal-search-panel' class='collapsed'>
    <button type='button' class='toggle'>🔍 Mekan Ara</button>
    <div class='panel-body'>
        <input id='crystal-search-input' type='search' placeholder='İsim, semt veya adres ara...'>
        <ul id='crystal-search-results'></ul>
        <div class='empty-state'>Eşleşen kayıt bulunamadı.</div>
    </div>
</div>
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


def resolve_display_fields(record: dict) -> dict[str, str | None]:
    display_address = record.get("resolved_address") or record.get("address")
    display_phone = record.get("resolved_phone") or record.get("phone")
    display_website = record.get("resolved_website") or record.get("website")
    maps_url = record.get("maps_url")
    if not maps_url and display_address:
        query = ", ".join(filter(None, [record.get("brand"), record.get("branch"), display_address]))
        maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
    return {
        "address": display_address,
        "phone": display_phone,
        "website": display_website,
        "maps_url": maps_url,
    }


def load_locations(connection: sqlite3.Connection) -> list[dict]:
    query = (
        "SELECT brand, branch, address, phone, website, extra_info, latitude, longitude, geocode_provider, "
        "resolved_address, resolved_phone, resolved_website, geocode_maps_url, menu_data, menu_source, menu_last_updated "
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
            "menu_data": row[13],
            "menu_source": row[14],
            "menu_last_updated": row[15],
        })
    return records


def build_popup(record: dict, display: dict[str, str | None]) -> str:
    from datetime import datetime
    from html import escape
    
    brand = escape(record["brand"])
    branch = escape(record.get("branch") or "") if record.get("branch") else None
    display_address = escape(display.get("address") or "") if display.get("address") else None
    display_phone = escape(display.get("phone") or "") if display.get("phone") else None
    display_website = display.get("website")
    maps_url = display.get("maps_url")

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
        parts.append(f"<div class='extra'>{escape(record['extra_info'])}</div>")

    # Add menu information if available with modern design
    menu_data = record.get("menu_data")
    menu_last_updated = record.get("menu_last_updated")
    
    if menu_data:
        try:
            menu = json.loads(menu_data) if isinstance(menu_data, str) else menu_data
            
            # Format the date nicely
            date_str = ""
            if menu_last_updated:
                try:
                    dt = datetime.fromisoformat(menu_last_updated.replace('Z', '+00:00'))
                    date_str = dt.strftime("%d.%m.%Y")
                except (ValueError, AttributeError):
                    pass
            
            # Show menu sections with prices
            if menu.get("sections"):
                has_prices = any(
                    item.get("price") 
                    for section in menu["sections"] 
                    for item in section.get("items", [])
                )
                
                parts.append("<div class='menu-section'>")
                parts.append("<div class='menu-header'>")
                parts.append("<h4><span>🍽️</span> Menü</h4>")
                if date_str:
                    parts.append(f"<span class='menu-date-badge'>📅 {date_str}</span>")
                parts.append("</div>")
                
                sections_shown = 0
                for section in menu["sections"]:
                    if sections_shown >= 2:  # Show max 2 sections
                        break
                        
                    section_name = section.get("name", "")
                    items = section.get("items", [])
                    
                    # Filter out navigation items and only show items with meaningful content
                    meaningful_items = [
                        item for item in items 
                        if item.get("name") and (
                            item.get("price") or 
                            (len(item.get("name", "")) < 50 and 
                             not any(nav in item.get("name", "").lower() for nav in ["ana sayfa", "hakkımızda", "iletişim", "markalarımız"]))
                        )
                    ]
                    
                    if meaningful_items:
                        sections_shown += 1
                        parts.append("<div class='menu-category'>")
                        if section_name and section_name.lower() not in ["genel", "general"]:
                            parts.append(f"<div class='menu-category-name'>✨ {escape(section_name)}</div>")
                        parts.append("<ul class='menu-items'>")
                        
                        for item in meaningful_items[:4]:  # Show first 4 items per section
                            item_name = escape(item.get("name", ""))
                            item_price = escape(item.get("price", "")) if item.get("price") else ""
                            
                            if item_name:
                                parts.append("<li class='menu-item'>")
                                parts.append(f"<span class='menu-item-name'>{item_name}</span>")
                                if item_price:
                                    parts.append(f"<span class='menu-item-price'>{item_price}</span>")
                                parts.append("</li>")
                        
                        if len(meaningful_items) > 4:
                            parts.append(f"<li class='menu-more'>+{len(meaningful_items) - 4} ürün daha</li>")
                        
                        parts.append("</ul></div>")
                
                total_sections = len([s for s in menu.get("sections", []) if s.get("items")])
                if total_sections > sections_shown:
                    parts.append(f"<div class='menu-more'>+{total_sections - sections_shown} kategori daha</div>")
                
                parts.append("</div>")
            
            # Show PDF menu links with modern design
            elif menu.get("pdf_menus"):
                parts.append("<div class='menu-section'>")
                parts.append("<div class='menu-header'>")
                parts.append("<h4><span>🍽️</span> Menü</h4>")
                if date_str:
                    parts.append(f"<span class='menu-date-badge'>📅 {date_str}</span>")
                parts.append("</div>")
                
                for pdf in menu["pdf_menus"][:2]:
                    pdf_url = pdf.get("url", "")
                    pdf_text = escape(pdf.get("text", "PDF Menü"))
                    if pdf_url:
                        parts.append(f"<a href='{escape(pdf_url, quote=True)}' target='_blank' class='menu-pdf-link'>📄 {pdf_text}</a>")
                parts.append("</div>")
        
        except (json.JSONDecodeError, TypeError):
            pass  # Ignore invalid menu data

    actions: list[str] = []
    if maps_url:
        actions.append(
            f"<a href='{escape(maps_url, quote=True)}' target='_blank' rel='noopener'><span class='icon'>📍</span>Google Maps</a>"
        )
    if display_website:
        actions.append(
            f"<a class='secondary' href='{escape(display_website, quote=True)}' target='_blank' rel='noopener'>🌐 Web Sitesi</a>"
        )
    if actions:
        parts.append("<div class='actions'>" + "".join(actions) + "</div>")

    if record.get("geocode_provider"):
        provider = escape(record["geocode_provider"].title())
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

    search_payload: list[dict[str, object]] = []

    for index, record in enumerate(records):
        display = resolve_display_fields(record)
        popup_html = build_popup(record, display)
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

        search_payload.append({
            "id": index,
            "markerName": marker.get_name(),
            "brand": record.get("brand") or "",
            "branch": record.get("branch") or "",
            "address": display.get("address") or "",
            "latitude": record.get("latitude"),
            "longitude": record.get("longitude"),
            "mapsUrl": display.get("maps_url") or "",
        })

    cluster.add_to(base_map)
    folium.LayerControl(position="topright").add_to(base_map)
    base_map.get_root().html.add_child(Element(SEARCH_PANEL_HTML))

    search_script = f"""<script>
(function() {{
    const panel = document.getElementById('crystal-search-panel');
    if (!panel) return;

    const searchData = {json.dumps(search_payload, ensure_ascii=False)};

    const escapeHtml = (value) => value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    searchData.forEach(loc => {{
        const parts = [loc.brand, loc.branch, loc.address].filter(Boolean);
        loc.searchText = parts.join(' ').toLowerCase();
    }});

    const initialise = () => {{
        const mapObject = window["{base_map.get_name()}"];
        const clusterGroup = window["{cluster.get_name()}"];
        if (!mapObject || !clusterGroup) {{
            window.setTimeout(initialise, 120);
            return;
        }}

        const toggleBtn = panel.querySelector('.toggle');
        const input = panel.querySelector('#crystal-search-input');
        const list = panel.querySelector('#crystal-search-results');
        const emptyState = panel.querySelector('.empty-state');

        const focusLocation = (loc) => {{
            const marker = window[loc.markerName];
            if (!marker) return;
            const currentZoom = mapObject.getZoom();
            const targetZoom = currentZoom < 15 ? 15 : currentZoom;
            const targetLatLng = [loc.latitude, loc.longitude];

            const openPopup = () => {{
                if (clusterGroup && clusterGroup.zoomToShowLayer) {{
                    clusterGroup.zoomToShowLayer(marker, () => {{
                        if (marker.openPopup) marker.openPopup();
                    }});
                }} else if (marker.openPopup) {{
                    marker.openPopup();
                }}
            }};

            mapObject.once('moveend', openPopup);
            mapObject.flyTo(targetLatLng, targetZoom, {{ duration: 0.6 }});
            panel.classList.add('collapsed');
        }};

        const render = (items) => {{
            list.innerHTML = '';
            if (!items.length) {{
                emptyState.style.display = 'block';
                return;
            }}
            emptyState.style.display = 'none';
            items.slice(0, 40).forEach(loc => {{
                const li = document.createElement('li');
                const branch = loc.branch ? `<span>${{escapeHtml(loc.branch)}}</span>` : '';
                const address = loc.address ? `<p>${{escapeHtml(loc.address)}}</p>` : '';
                li.innerHTML = `<strong>${{escapeHtml(loc.brand)}}</strong>${{branch}}${{address}}`;
                li.addEventListener('click', () => focusLocation(loc));
                list.appendChild(li);
            }});
        }};

        toggleBtn.addEventListener('click', () => {{
            panel.classList.toggle('collapsed');
            if (!panel.classList.contains('collapsed')) {{
                window.setTimeout(() => input && input.focus(), 180);
            }}
        }});

        input.addEventListener('input', () => {{
            const term = input.value.trim().toLowerCase();
            if (!term) {{
                render(searchData);
                return;
            }}
            const filtered = searchData.filter(loc => loc.searchText.includes(term));
            render(filtered);
        }});

        render(searchData);
    }};

    initialise();
}})();
</script>"""

    base_map.get_root().html.add_child(Element(search_script))

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
