#!/usr/bin/env python3
"""Generate an HTML list of Crystal Card partner venues with Google Maps links."""
from __future__ import annotations

import argparse
import json
import sqlite3
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "crystal_locations.db"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output" / "google_list.html"

# Navigation terms to filter out from menu items
NAVIGATION_TERMS = ["ana sayfa", "hakkımızda", "iletişim", "markalarımız"]


def load_locations(connection: sqlite3.Connection) -> list[dict]:
    query = (
        "SELECT brand, branch, address, phone, website, extra_info, "
        "resolved_address, resolved_phone, resolved_website, geocode_maps_url, menu_data, menu_source, menu_last_updated "
        "FROM locations ORDER BY brand COLLATE NOCASE, branch COLLATE NOCASE"
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
            "resolved_address": row[6],
            "resolved_phone": row[7],
            "resolved_website": row[8],
            "maps_url": row[9],
            "menu_data": row[10],
            "menu_source": row[11],
            "menu_last_updated": row[12],
        })
    return records


def fallback_maps_url(record: dict) -> str | None:
    display_address = record.get("resolved_address") or record.get("address")
    if not display_address:
        return None
    query_parts = [record.get("brand"), record.get("branch"), display_address]
    query = ", ".join(filter(None, query_parts))
    if not query:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def build_row_html(record: dict) -> str:
    from datetime import datetime
    
    brand = escape(record.get("brand") or "")
    branch = escape(record.get("branch") or "")
    display_address = escape((record.get("resolved_address") or record.get("address") or "").strip())
    display_phone = escape((record.get("resolved_phone") or record.get("phone") or "").strip())
    display_website = (record.get("resolved_website") or record.get("website") or "").strip()
    maps_url = (record.get("maps_url") or fallback_maps_url(record) or "").strip()
    extra_info = escape((record.get("extra_info") or "").strip())

    # Build enhanced menu display
    menu_html = ""
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
            
            menu_parts = []
            
            # Show menu items with prices
            if menu.get("sections"):
                total_items = 0
                items_with_prices = 0
                
                for section in menu["sections"]:
                    items = section.get("items", [])
                    # Filter meaningful items
                    meaningful_items = [
                        item for item in items 
                        if item.get("name") and (
                            item.get("price") or 
                            (len(item.get("name", "")) < 50 and 
                             not any(nav in item.get("name", "").lower() for nav in NAVIGATION_TERMS))
                        )
                    ]
                    total_items += len(meaningful_items)
                    items_with_prices += sum(1 for item in meaningful_items if item.get("price"))
                
                if total_items > 0:
                    menu_parts.append(f"<span class='menu-badge'>🍽️ {total_items} ürün</span>")
                if items_with_prices > 0:
                    menu_parts.append(f"<span class='menu-badge price-badge'>💰 {items_with_prices} fiyatlı</span>")
            
            # Add PDF menus
            if menu.get("pdf_menus"):
                menu_parts.append("<span class='menu-badge'>📄 PDF menü</span>")
            
            # Add image menus
            if menu.get("image_menus"):
                menu_parts.append("<span class='menu-badge'>🖼️ Menü görseli</span>")
            
            # Add date badge
            if date_str and menu_parts:
                menu_parts.append(f"<span class='menu-badge date-badge'>📅 {date_str}</span>")
            
            if menu_parts:
                menu_html = "<div class='menu-info'>" + " ".join(menu_parts) + "</div>"
        
        except (json.JSONDecodeError, TypeError):
            pass

    website_html = (
        f"<a href='{escape(display_website, quote=True)}' target='_blank' rel='noopener' class='action-link'>🌐 Web</a>"
        if display_website
        else ""
    )
    maps_html = (
        f"<a href='{escape(maps_url, quote=True)}' target='_blank' rel='noopener' class='action-link primary'>📍 Google Maps</a>"
        if maps_url
        else ""
    )

    info_parts = [display_address, display_phone, extra_info]
    info_parts = [part for part in info_parts if part]
    if menu_html:
        info_parts.append(menu_html)
    info_lines = "<br>".join(info_parts)

    actions = maps_html or ""
    if actions and website_html:
        actions = f"{actions}{website_html}"
    elif website_html:
        actions = website_html

    branch_line = f"<span class='branch-name'>{branch}</span>" if branch else ""

    return (
        "<tr>"
        f"<td class='name'><strong class='brand-name'>{brand}</strong>{branch_line}</td>"
        f"<td class='info'>{info_lines}</td>"
        f"<td class='actions'>{actions}</td>"
        "</tr>"
    )


def render_html(records: list[dict]) -> str:
    rows_html = "\n".join(build_row_html(record) for record in records)
    return f"""<!DOCTYPE html>
<html lang='tr'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Crystal Card Mekan Listesi</title>
<link rel='preconnect' href='https://fonts.googleapis.com'>
<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>
<link href='https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap' rel='stylesheet'>
<style>
:root {{
    --crystal-primary: #14b8a6;
    --crystal-primary-dark: #0d9488;
    --crystal-primary-light: #ccfbf1;
    --crystal-secondary: #ec4899;
    --crystal-secondary-dark: #db2777;
    --crystal-bg: #f8fafb;
    --crystal-card-bg: #ffffff;
    --crystal-text: #1e293b;
    --crystal-text-light: #475569;
    --crystal-muted: #64748b;
    --crystal-accent: #f59e0b;
    --crystal-accent-light: #fef3c7;
    --crystal-price: #059669;
    --crystal-price-bg: #d1fae5;
    --crystal-shadow: rgba(15, 23, 42, 0.06);
    --crystal-shadow-hover: rgba(15, 23, 42, 0.12);
    --crystal-glow: rgba(20, 184, 166, 0.15);
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{ 
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #f0fdfa 0%, #e0f2fe 100%);
    color: var(--crystal-text);
    line-height: 1.6;
    min-height: 100vh;
    padding: 0;
}}

.header {{
    background: linear-gradient(135deg, var(--crystal-primary) 0%, var(--crystal-primary-dark) 100%);
    color: white;
    padding: 3rem 2rem;
    box-shadow: 0 8px 32px rgba(20, 184, 166, 0.2);
    position: sticky;
    top: 0;
    z-index: 100;
    border-bottom: 3px solid rgba(255, 255, 255, 0.2);
}}

.header h1 {{ 
    margin: 0 0 0.75rem;
    font-size: 2.5rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}}

.header p.meta {{ 
    margin: 0;
    color: rgba(255, 255, 255, 0.95);
    font-size: 1.1rem;
    font-weight: 500;
    letter-spacing: -0.01em;
}}

.container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
}}

.search-container {{
    background: var(--crystal-card-bg);
    padding: 1.75rem;
    border-radius: 20px;
    box-shadow: 0 8px 32px var(--crystal-shadow), 0 0 0 1px rgba(255, 255, 255, 0.9);
    margin-bottom: 2rem;
    border: 1px solid rgba(20, 184, 166, 0.1);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
}}

input[type="search"] {{ 
    padding: 1rem 1.5rem;
    width: 100%;
    border-radius: 14px;
    border: 2px solid rgba(20, 184, 166, 0.2);
    font-size: 1.05rem;
    font-family: inherit;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    background: white;
    font-weight: 500;
}}

input[type="search"]:focus {{
    outline: none;
    border-color: var(--crystal-primary);
    box-shadow: 0 0 0 4px rgba(20, 184, 166, 0.12), 0 4px 16px rgba(20, 184, 166, 0.1);
}}

input[type="search"]::placeholder {{
    color: var(--crystal-muted);
    font-weight: 400;
}}

.table-container {{
    background: var(--crystal-card-bg);
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 8px 32px var(--crystal-shadow), 0 0 0 1px rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(20, 184, 166, 0.08);
}}

table {{ 
    width: 100%;
    border-collapse: collapse;
}}

thead {{
    background: linear-gradient(135deg, var(--crystal-primary-light) 0%, #d1fae5 100%);
}}

th {{ 
    padding: 1.5rem 1.75rem;
    text-align: left;
    color: var(--crystal-primary-dark);
    font-weight: 800;
    font-size: 0.95rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border-bottom: 3px solid var(--crystal-primary);
}}

td {{ 
    padding: 1.5rem 1.75rem;
    border-bottom: 1px solid rgba(20, 184, 166, 0.08);
    vertical-align: top;
}}

tr:last-child td {{
    border-bottom: none;
}}

tbody tr {{
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    background: white;
}}

tbody tr:hover {{ 
    background: linear-gradient(90deg, rgba(20, 184, 166, 0.04) 0%, rgba(240, 253, 250, 0.8) 100%);
    transform: translateX(6px);
    box-shadow: 0 4px 16px var(--crystal-shadow-hover);
}}

.brand-name {{
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--crystal-text);
    display: block;
    margin-bottom: 0.3rem;
    letter-spacing: -0.02em;
}}

.branch-name {{
    display: block;
    font-size: 0.95rem;
    color: var(--crystal-text-light);
    font-weight: 600;
    margin-top: 0.3rem;
}}

td.info {{
    color: var(--crystal-muted);
    font-size: 0.95rem;
    line-height: 1.8;
    font-weight: 500;
}}

.menu-info {{
    margin-top: 0.875rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.625rem;
}}

.menu-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: linear-gradient(135deg, var(--crystal-primary-light), #d1fae5);
    color: var(--crystal-primary-dark);
    padding: 0.5rem 0.875rem;
    border-radius: 999px;
    font-size: 0.87rem;
    font-weight: 700;
    border: 1.5px solid rgba(20, 184, 166, 0.2);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 2px 6px rgba(20, 184, 166, 0.08);
}}

.menu-badge:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(20, 184, 166, 0.15);
    border-color: rgba(20, 184, 166, 0.3);
}}

.menu-badge.price-badge {{
    background: linear-gradient(135deg, var(--crystal-price-bg), #a7f3d0);
    color: #065f46;
    border-color: rgba(5, 150, 105, 0.3);
}}

.menu-badge.date-badge {{
    background: linear-gradient(135deg, var(--crystal-accent-light), #fde68a);
    color: #92400e;
    border-color: rgba(245, 158, 11, 0.3);
}}

.action-link {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--crystal-primary-dark);
    text-decoration: none;
    font-weight: 700;
    font-size: 0.95rem;
    padding: 0.625rem 1.125rem;
    border-radius: 999px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    background: rgba(20, 184, 166, 0.08);
    border: 2px solid rgba(20, 184, 166, 0.15);
    margin-right: 0.625rem;
    letter-spacing: 0.01em;
}}

.action-link:hover {{
    background: linear-gradient(135deg, var(--crystal-primary), var(--crystal-primary-dark));
    color: white;
    transform: translateY(-3px);
    box-shadow: 0 6px 20px var(--crystal-glow);
    border-color: var(--crystal-primary-dark);
}}

.action-link.primary {{
    background: linear-gradient(135deg, var(--crystal-primary), var(--crystal-primary-dark));
    color: white;
    border-color: var(--crystal-primary-dark);
    box-shadow: 0 4px 16px var(--crystal-glow);
}}

.action-link.primary:hover {{
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 8px 24px var(--crystal-glow);
}}

.no-results {{ 
    display: none;
    text-align: center;
    padding: 3.5rem;
    color: var(--crystal-muted);
    font-size: 1.15rem;
    font-weight: 600;
    font-style: italic;
}}

.no-results.show {{
    display: block;
}}

@media (max-width: 768px) {{
    .header {{
        padding: 2rem 1.25rem;
    }}
    
    .header h1 {{
        font-size: 1.75rem;
    }}
    
    .header p.meta {{
        font-size: 0.95rem;
    }}
    
    .container {{
        padding: 1rem;
    }}
    
    th, td {{
        padding: 1rem 1.25rem;
    }}
    
    .brand-name {{
        font-size: 1.05rem;
    }}
    
    .action-link {{
        padding: 0.5rem 0.875rem;
        font-size: 0.87rem;
    }}
}}
</style>
<script>
document.addEventListener('DOMContentLoaded', function () {{
  const input = document.querySelector('#search');
  const rows = Array.from(document.querySelectorAll('tbody tr'));
  const emptyState = document.querySelector('.no-results');

  input.addEventListener('input', function () {{
    const term = input.value.trim().toLowerCase();
    let visibleCount = 0;
    rows.forEach(function (row) {{
      const text = row.textContent.toLowerCase();
      const match = !term || text.includes(term);
      row.style.display = match ? '' : 'none';
      if (match) visibleCount += 1;
    }});
    emptyState.classList.toggle('show', visibleCount === 0);
  }});
}});
</script>
</head>
<body>
<div class='header'>
  <div class='container'>
    <h1>✨ Crystal Card Mekan Listesi</h1>
    <p class='meta'>Tüm restoranları menü bilgileri ve güncel fiyatlarıyla keşfedin</p>
  </div>
</div>
<div class='container'>
  <div class='search-container'>
    <input id='search' type='search' placeholder='🔍 Mekan adı, şehir, semt veya adres ara...' aria-label='Mekan ara'>
  </div>
  <div class='table-container'>
    <table>
      <thead>
        <tr>
          <th>Mekan</th>
          <th>Bilgiler & Menü</th>
          <th>Bağlantılar</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>
  <p class='no-results'>🔍 Aramanızla eşleşen mekan bulunamadı. Başka bir terim deneyin.</p>
</div>
</body>
</html>
"""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an HTML list view with Google Maps links for Crystal Card venues"
    )
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
        help="Where to write the generated HTML list",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if not args.db.exists():
        raise SystemExit(f"Database {args.db} does not exist. Run scrape_crystal.py first.")

    connection = sqlite3.connect(args.db)
    records = load_locations(connection)
    connection.close()

    html = render_html(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")

    print(f"Created Google Maps list with {len(records)} locations at {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(main(sys.argv[1:]))
