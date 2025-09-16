import sqlite3
from typing import List, Tuple

DB_PATH = "storage/neersetu.db"

def _fetch_rows(block: str, start_year: int, end_year: int) -> List[Tuple]:
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("""
        SELECT year, level_m, stage
        FROM gw_levels
        WHERE lower(block)=lower(?) AND year BETWEEN ? AND ?
        ORDER BY year ASC
    """, (block, start_year, end_year))
    rows = cur.fetchall(); conn.close()
    return rows

def get_trend(block: str, start_year: int, end_year: int) -> dict:
    rows = _fetch_rows(block, start_year, end_year)
    if not rows:
        return {"ok": False, "msg": f"insufficient data for {block} {start_year}-{end_year}"}
    first, last = rows[0][1], rows[-1][1]
    years = max(1, rows[-1][0] - rows[0][0])
    slope = (last - first) / years
    last5 = rows[-5:]
    tiny_table = [{"year": y, "level_m": float(lvl)} for (y,lvl,_) in last5]
    latest_stage = rows[-1][2]
    return {
        "ok": True, "block": block, "start": rows[0][0], "end": rows[-1][0],
        "slope_per_year": slope, "latest_stage": latest_stage,
        "tiny_table": tiny_table, "source": "SQLite gw_levels"
    }

def get_stage(block: str, year: int) -> dict:
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("""
        SELECT stage, level_m FROM gw_levels
        WHERE lower(block)=lower(?) AND year=?
    """, (block, year))
    row = cur.fetchone(); conn.close()
    if not row: return {"ok": False, "msg": f"insufficient data for {block} {year}"}
    stage, lvl = row
    return {"ok": True, "block": block, "year": year, "stage": stage,
            "level_m": float(lvl), "source": "SQLite gw_levels"}

def get_level(block: str, year: int) -> dict:
    """Return only the level (m) for a given year (used for comparisons)."""
    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    cur.execute("""
        SELECT level_m FROM gw_levels
        WHERE lower(block)=lower(?) AND year=?
    """, (block, year))
    row = cur.fetchone(); conn.close()
    if not row: return {"ok": False, "msg": f"insufficient data for {block} {year}"}
    (lvl,) = row
    return {"ok": True, "block": block, "year": year, "level_m": float(lvl), "source": "SQLite gw_levels"}
