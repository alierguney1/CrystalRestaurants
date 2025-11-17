#!/usr/bin/env python3
"""Generate an HTML list of Crystal Card partner venues with Google Maps links."""
from __future__ import annotations

import argparse
import sqlite3
from html import escape
from pathlib import Path
from urllib.parse import quote_plus

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "crystal_locations.db"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "output" / "google_list.html"


def load_locations(connection: sqlite3.Connection) -> list[dict]:
    query = (
        "SELECT brand, branch, address, phone, website, extra_info, "
        "resolved_address, resolved_phone, resolved_website, geocode_maps_url "
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
    brand = escape(record.get("brand") or "")
    branch = escape(record.get("branch") or "")
    display_address = escape((record.get("resolved_address") or record.get("address") or "").strip())
    display_phone = escape((record.get("resolved_phone") or record.get("phone") or "").strip())
    display_website = (record.get("resolved_website") or record.get("website") or "").strip()
    maps_url = (record.get("maps_url") or fallback_maps_url(record) or "").strip()
    extra_info = escape((record.get("extra_info") or "").strip())

    website_html = (
        f"<a href='{escape(display_website, quote=True)}' target='_blank' rel='noopener'>Web</a>"
        if display_website
        else ""
    )
    maps_html = (
        f"<a href='{escape(maps_url, quote=True)}' target='_blank' rel='noopener'>Google Maps</a>"
        if maps_url
        else ""
    )

    info_lines = "<br>".join(filter(None, [display_address, display_phone, extra_info]))

    actions = maps_html or ""
    if actions and website_html:
        actions = f"{actions} · {website_html}"
    elif website_html:
        actions = website_html

    branch_line = f"<br>{branch}" if branch else ""

    return (
        "<tr>"
        f"<td class='name'><strong>{brand}</strong>{branch_line}</td>"
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
<title>Crystal Card Mekan Listesi</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f7f7f7; color: #222; }}
h1 {{ margin-bottom: 0.5rem; }}
p.meta {{ margin-top: 0; color: #555; }}
input[type="search"] {{ padding: 0.5rem; width: 100%; max-width: 420px; margin-bottom: 1rem; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; }}
th, td {{ padding: 0.75rem; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
th {{ text-align: left; color: #555; font-weight: 600; }}
td.name strong {{ font-size: 1.05rem; }}
td.actions a {{ color: #1a73e8; text-decoration: none; }}
td.actions a:hover {{ text-decoration: underline; }}
tr:hover {{ background: #f0f6ff; }}
.no-results {{ display: none; margin-top: 1rem; color: #777; }}
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
    emptyState.style.display = visibleCount ? 'none' : '';
  }});
}});
</script>
</head>
<body>
<h1>Crystal Card Mekan Listesi</h1>
<p class='meta'>Google Maps bağlantılarıyla birlikte tüm kayıtları görüntüleyin. Üstteki arama kutusuyla filtreleyebilirsiniz.</p>
<input id='search' type='search' placeholder='İsim, adres veya şehir ara...'>
<table>
  <thead>
    <tr>
      <th>Mekan</th>
      <th>Bilgiler</th>
      <th>Bağlantılar</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
<p class='no-results'>Sonuca ulaşılamadı. Başka bir terim deneyin.</p>
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
