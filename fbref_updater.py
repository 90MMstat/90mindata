"""
fbref_updater.py  —  Auto-hämtar Allsvenskan-statistik från FBRef
och uppdaterar data.json utan manuellt arbete.

Kör:  cd "C:\\Users\\vikto\\OneDrive\\Skrivbord\\blavitttest"
      python fbref_updater.py
      python fbref_updater.py --season 2025
      python fbref_updater.py --dry-run   (hämtar men sparar ej)

Kräver: pip install requests beautifulsoup4 lxml openpyxl

FBRef-regler:
  - Vänta minst 3 sekunder mellan anrop (respektera servern)
  - Kör inte mer än en gång per dag per säsong
  - Källan är FBRef.com — ange detta om du delar data
"""

import requests, time, json, os, sys, argparse, re, datetime
from bs4 import BeautifulSoup
import openpyxl
from io import BytesIO

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
FBREF_BASE  = "https://fbref.com"
ALLSV_ID    = "29"           # FBRef comp ID for Allsvenskan
DELAY_SEC   = 4.0            # seconds between requests (be polite)
CACHE_DIR   = os.path.join(BASE_DIR, ".fbref_cache")

SEASON_IDS = {
    # FBRef season slug → our year label
    # These are filled automatically by scanning FBRef
    # but you can hardcode known ones here:
    "2025": None,  # filled at runtime
    "2024": None,
    "2023": None,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Referer":         "https://fbref.com/en/comps/29/Allsvenskan-Stats",
    "Connection":      "keep-alive",
}

# Stat pages to fetch — (slug, table_id, descriptive name)
STAT_PAGES = [
    ("stats",       "stats_standard",    "Standard Stats"),
    ("shooting",    "stats_shooting",    "Shooting"),
    ("goalkeeping", "stats_keeper",      "Goalkeeping"),
    ("misc",        "stats_misc",        "Miscellaneous"),
    ("passing",     "stats_passing",     "Passing"),      # includes xA
    ("gca",         "stats_gca",         "GCA"),          # goal-creating actions
]

# ── Helpers ───────────────────────────────────────────────────────────────────
os.makedirs(CACHE_DIR, exist_ok=True)

session = requests.Session()
session.headers.update(HEADERS)

def fetch(url: str, cache_key: str = None, force: bool = False) -> str:
    """Fetch URL with caching. Returns HTML string."""
    if cache_key:
        cache_path = os.path.join(CACHE_DIR, cache_key + ".html")
        if not force and os.path.exists(cache_path):
            # Use cache if it's less than 6 hours old
            age = time.time() - os.path.getmtime(cache_path)
            if age < 6 * 3600:
                print(f"  [cache] {cache_key}")
                with open(cache_path, encoding="utf-8") as f:
                    return f.read()

    print(f"  [fetch] {url}")
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text

    if cache_key:
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(html)

    time.sleep(DELAY_SEC)
    return html


def parse_fbref_table(html: str, table_id: str) -> list[dict]:
    """Parse a FBRef HTML stats table into list of dicts."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": table_id})
    if not table:
        print(f"    ⚠ Table '{table_id}' not found")
        return []

    # FBRef has two header rows — use the second (index 1) for column names
    headers_rows = table.find("thead").find_all("tr")
    if len(headers_rows) < 2:
        header_row = headers_rows[0]
    else:
        header_row = headers_rows[-1]

    raw_cols = []
    for th in header_row.find_all("th"):
        stat = th.get("data-stat", th.get_text(strip=True))
        raw_cols.append(stat)

    # Deduplicate columns
    seen = {}
    cols = []
    for c in raw_cols:
        cnt = seen.get(c, 0) + 1
        seen[c] = cnt
        cols.append(f"{c}_{cnt}" if cnt > 1 else c)

    rows = []
    tbody = table.find("tbody")
    if not tbody:
        return []

    for tr in tbody.find_all("tr"):
        if "thead" in tr.get("class", []):
            continue  # skip mid-table header repeats
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row = {}
        for i, cell in enumerate(cells):
            if i >= len(cols):
                break
            stat_name = cell.get("data-stat", cols[i])
            # Use data-stat as key if available (more reliable)
            row[stat_name] = cell.get_text(strip=True)
            # Also store links (e.g. player profile URLs)
            a = cell.find("a")
            if a and "href" in a.attrs:
                row[stat_name + "_url"] = a["href"]

        player = row.get("player", "")
        squad  = row.get("squad", "")
        if not player or player in ("Player", ""):
            continue
        rows.append(row)

    print(f"    ✓ {len(rows)} rows from '{table_id}'")
    return rows


def get_season_url(year_label: str) -> str | None:
    """Find the FBRef URL for a given Allsvenskan season."""
    # Try current season first
    current_url = f"{FBREF_BASE}/en/comps/{ALLSV_ID}/Allsvenskan-Stats"
    html = fetch(current_url, cache_key=f"allsv_home_{year_label}")
    soup = BeautifulSoup(html, "lxml")

    # Look for season links in the page
    season_links = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Pattern: /en/comps/67/YYYY-YYYY/Allsvenskan-Stats
        m = re.search(r"/en/comps/29/(\d{4}(?:-\d{4})?)/Allsvenskan-Stats", href)
        if m:
            slug = m.group(1)
            # Map to year
            yr = slug.split("-")[-1] if "-" in slug else slug
            season_links[yr] = f"{FBREF_BASE}{href}"

    # Also check if current page IS the year we want
    title = soup.find("h1")
    if title:
        m = re.search(r"(\d{4})", title.get_text())
        if m:
            season_links[m.group(1)] = current_url

    return season_links.get(year_label)


def fetch_season_stats(year_label: str, stat_slug: str, table_id: str) -> list[dict]:
    """Fetch one stat page for one season."""
    # Build URL
    if year_label == str(datetime.date.today().year):
        # Current season
        url = f"{FBREF_BASE}/en/comps/{ALLSV_ID}/{stat_slug}/Allsvenskan-Stats"
    else:
        url = f"{FBREF_BASE}/en/comps/{ALLSV_ID}/{year_label}/{stat_slug}/{year_label}-Allsvenskan-Stats"

    cache_key = f"allsv_{year_label}_{stat_slug}"
    try:
        html = fetch(url, cache_key=cache_key)
        return parse_fbref_table(html, table_id)
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            # Try alternate URL format
            url2 = f"{FBREF_BASE}/en/comps/{ALLSV_ID}/{year_label}-{int(year_label)+1}/{stat_slug}/{year_label}-{int(year_label)+1}-Allsvenskan-Stats"
            try:
                html2 = fetch(url2, cache_key=cache_key + "_alt")
                return parse_fbref_table(html2, table_id)
            except Exception:
                pass
        print(f"    ⚠ HTTP {e.response.status_code} for {url}")
        return []
    except Exception as e:
        print(f"    ⚠ Error: {e}")
        return []


# ── Transform FBRef row → clean stats dict ────────────────────────────────────
def safe_float(v):
    if not v or v in ("", "—", "-", "N/A"): return 0.0
    try: return float(v.replace(",", "."))
    except: return 0.0

def safe_int(v): return int(safe_float(v))

def fix_min(v):
    """FBRef stores minutes without thousands separator in HTML scraping."""
    return safe_int(v)

def transform_scraped_row(std=None, sh=None, misc=None, gk=None, pas=None, gca=None):
    """Merge multiple stat rows into one clean player dict."""
    src = std or sh or misc or gk or {}
    p = {
        "name":   src.get("player", "").strip(),
        "nation": src.get("nationality", src.get("nation", "")).strip()[-3:].upper(),
        "pos":    src.get("position",   src.get("pos", "")).strip(),
        "squad":  src.get("squad", "").strip(),
        "age":    safe_int(src.get("age", "0").split("-")[0]),  # FBRef: "23-145" format
        "competition": "allsvenskan",
    }
    if not p["name"]: return None

    # Clean nation — FBRef format: "se SWE" → "SWE"
    nat_raw = src.get("nationality", src.get("nation", ""))
    parts   = nat_raw.strip().split()
    p["nation"] = parts[-1].upper() if parts else ""

    if std:
        p["mp"]       = safe_int(std.get("games", std.get("matches_played", 0)))
        p["starts"]   = safe_int(std.get("games_starts", 0))
        p["min"]      = fix_min(std.get("minutes", 0))
        p["nineties"] = safe_float(std.get("minutes_90s", 0))
        p["gls"]      = safe_int(std.get("goals", 0))
        p["ast"]      = safe_int(std.get("assists", 0))
        p["gPluA"]    = safe_int(std.get("goals_assists", 0))
        p["pk"]       = safe_int(std.get("pens_made", 0))
        p["crdY"]     = safe_int(std.get("cards_yellow", 0))
        p["crdR"]     = safe_int(std.get("cards_red", 0))
        # Per-90 cols in FBRef standard table
        p["glsPer90"] = safe_float(std.get("goals_per90", 0))
        p["astPer90"] = safe_float(std.get("assists_per90", 0))
        # xG in standard stats
        p["xG"]       = safe_float(std.get("xg", std.get("expected_goals", 0)))
        p["xA"]       = safe_float(std.get("xg_assist", std.get("expected_assists", 0)))
        p["npxG"]     = safe_float(std.get("npxg", 0))
        p["xGpx"]     = safe_float(std.get("xg_per90", 0))
        p["xApx"]     = safe_float(std.get("xg_assist_per90", 0))

    if sh:
        p["sh"]       = safe_int(sh.get("shots", 0))
        p["sot"]      = safe_int(sh.get("shots_on_target", 0))
        p["sotPct"]   = safe_float(sh.get("shots_on_target_pct", 0))
        p["shPer90"]  = safe_float(sh.get("shots_per90", 0))
        p["sotPer90"] = safe_float(sh.get("shots_on_target_per90", 0))
        p["gPerSh"]   = safe_float(sh.get("goals_per_shot", 0))
        p["gPerSoT"]  = safe_float(sh.get("goals_per_shot_on_target", 0))

    if misc:
        p["fls"]    = safe_int(misc.get("fouls", 0))
        p["fld"]    = safe_int(misc.get("fouled", 0))
        p["off"]    = safe_int(misc.get("offsides", 0))
        p["crs"]    = safe_int(misc.get("crosses", 0))
        p["int"]    = safe_int(misc.get("interceptions", 0))
        p["tklW"]   = safe_int(misc.get("tackles_won", 0))
        p["pkWon"]  = safe_int(misc.get("pens_won", 0))
        p["pkCon"]  = safe_int(misc.get("pens_conceded", 0))
        p["og"]     = safe_int(misc.get("own_goals", 0))

    if gk:
        p["gkGA"]      = safe_int(gk.get("gk_goals_against", 0))
        p["gkGA90"]    = safe_float(gk.get("gk_goals_against_per90", 0))
        p["gkSoTA"]    = safe_int(gk.get("gk_shots_on_target_against", 0))
        p["gkSaves"]   = safe_int(gk.get("gk_saves", 0))
        p["gkSavePct"] = safe_float(gk.get("gk_save_pct", 0))
        p["gkW"]       = safe_int(gk.get("gk_wins", 0))
        p["gkD"]       = safe_int(gk.get("gk_ties", 0))
        p["gkL"]       = safe_int(gk.get("gk_losses", 0))
        p["gkCS"]      = safe_int(gk.get("gk_clean_sheets", 0))
        p["gkCSPct"]   = safe_float(gk.get("gk_clean_sheets_pct", 0))

    if pas:
        # xA and xP from advanced passing table
        p["xA"]   = p.get("xA") or safe_float(pas.get("xg_assist", 0))
        p["xP"]   = safe_float(pas.get("pass_xa", pas.get("xa", 0)))

    # Compute per-90 fields
    n90 = max(p.get("nineties", 0), 0.1)
    for raw, per in [("fls","flsPer90"),("fld","fldPer90"),("int","intPer90"),
                     ("tklW","tklWPer90"),("crs","crsPer90"),("xA","xApx"),("xP","xPpx")]:
        if raw in p and per not in p:
            p[per] = round(p[raw] / n90, 3)
    if "xG" in p and not p.get("xGpx"):
        p["xGpx"] = round(p["xG"] / n90, 3)
    if p.get("xG") and p.get("gls"):
        p["gMinusXG"] = round(p["gls"] - p["xG"], 2)

    # Clean squad name
    sq_norm = {"Göteborg": "IFK Göteborg"}
    p["squad"] = sq_norm.get(p["squad"], p["squad"])

    return p


# ── Main update function ───────────────────────────────────────────────────────
def update_season(year_label: str, dry_run: bool = False) -> list[dict]:
    """Fetch all stat pages for a season and return merged player list."""
    print(f"\n  Hämtar {year_label} från FBRef…")

    all_rows = {}  # name → merged row
    for slug, table_id, name in STAT_PAGES:
        print(f"  → {name}…")
        rows = fetch_season_stats(year_label, slug, table_id)
        for row in rows:
            player_name = row.get("player", "").strip()
            if not player_name: continue
            if player_name not in all_rows:
                all_rows[player_name] = {}
            all_rows[player_name][slug] = row

    # Merge
    players = []
    for name, data in all_rows.items():
        p = transform_scraped_row(
            std  = data.get("stats"),
            sh   = data.get("shooting"),
            misc = data.get("misc"),
            gk   = data.get("goalkeeping"),
            pas  = data.get("passing"),
            gca  = data.get("gca"),
        )
        if p and p.get("name") and p.get("squad"):
            players.append(p)

    print(f"  ✓ {len(players)} spelare samlade för {year_label}")
    return players


def run(years: list[str], dry_run: bool = False, force: bool = False):
    print("=" * 60)
    print("FBRef Allsvenskan Auto-Updater")
    print(f"Säsonger: {', '.join(years)}")
    print(f"Tid: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if dry_run: print("DRY RUN — sparar ej")
    print("=" * 60)

    # Load existing data.json
    data_path = os.path.join(BASE_DIR, "data.json")
    if os.path.exists(data_path):
        with open(data_path, encoding="utf-8") as f:
            DB = json.load(f)
        print(f"\nLäste befintlig data.json ({len(DB.get('seasons',{}))} säsonger)")
    else:
        DB = {"seasons": {}, "generated": ""}

    # Import process_data helpers for percentiles
    sys.path.insert(0, BASE_DIR)
    try:
        from process_data import add_percentiles, compute_league_averages
        has_process = True
        print("✓ Importerade percentil-beräkning från process_data.py")
    except ImportError:
        has_process = False
        print("⚠ process_data.py ej tillgänglig — inga percentiler beräknas")

    for year in years:
        players = update_season(year, dry_run)
        if not players:
            print(f"  ⚠ Inga spelare hämtade för {year}")
            continue

        if has_process:
            players = add_percentiles(players)
            avgs    = compute_league_averages(players)
        else:
            avgs = {}

        # Preserve existing squads and nationalities
        existing = DB["seasons"].get(year, {})
        DB["seasons"][year] = {
            "players":         players,
            "squads":          existing.get("squads", []),
            "league_averages": avgs,
            "nationalities":   existing.get("nationalities", []),
            "updated":         datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source":          "FBRef auto-scrape",
        }
        print(f"  ✓ {year}: {len(players)} spelare redo")

    DB["generated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not dry_run:
        # Backup old file
        if os.path.exists(data_path):
            backup = data_path.replace(".json", f"_backup_{datetime.date.today()}.json")
            import shutil
            shutil.copy(data_path, backup)
            print(f"\nBackup sparad: {os.path.basename(backup)}")

        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(DB, f, ensure_ascii=False, separators=(",", ":"))
        kb = os.path.getsize(data_path) // 1024
        print(f"✓ data.json uppdaterad ({kb} KB)")
    else:
        print("\n[DRY RUN] Ingen fil sparad.")

    print("\n✓ Klart!")
    total_p = sum(len(DB["seasons"][y].get("players",[])) for y in years)
    print(f"  {total_p} spelare uppdaterade")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FBRef Allsvenskan Auto-Updater")
    parser.add_argument("--season", nargs="+",
                        default=[str(datetime.date.today().year)],
                        help="Säsong(er) att uppdatera, t.ex. --season 2025 2024")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Hämta men spara ej")
    parser.add_argument("--force",    action="store_true",
                        help="Ignorera cache, hämta alltid färsk data")
    args = parser.parse_args()
    run(years=args.season, dry_run=args.dry_run, force=args.force)
