import os, re, glob, sqlite3, pandas as pd
RAW_DIR = "backend/data/ingres_raw"      # put official CSV/XLSX here
DB_PATH = "storage/neersetu.db"; TABLE = "gw_levels"
USE_POST_MONSOON = True
os.makedirs("storage", exist_ok=True); os.makedirs(RAW_DIR, exist_ok=True)

def canon(s): return re.sub(r'[^a-z0-9]+', '_', s.strip().lower())
def pick_level(cols):
    pre  = [c for c in cols if 'pre'  in canon(c) and 'monsoon' in canon(c)]
    post = [c for c in cols if 'post' in canon(c) and 'monsoon' in canon(c)]
    depth= [c for c in cols if 'depth' in canon(c) or 'level' in canon(c)]
    if USE_POST_MONSOON and post: return post[0]
    if not USE_POST_MONSOON and pre: return pre[0]
    if pre: return pre[0]
    if post: return post[0]
    return depth[0] if depth else None

def norm_stage(x):
    if not isinstance(x,str): return ""
    s = x.lower()
    if "over" in s: return "Over-exploited"
    if "semi" in s: return "Semi-critical"
    if "critical" in s and "semi" not in s: return "Critical"
    if "safe" in s: return "Safe"
    return x.strip()

def first_present(d, keys):
    for k in keys:
        if k in d: return k
    return None

files = glob.glob(os.path.join(RAW_DIR, "*.csv")) + glob.glob(os.path.join(RAW_DIR, "*.xlsx"))
if not files: print(f"Put official CSV/XLSX into {RAW_DIR} and re-run."); raise SystemExit(0)

frames=[]
for f in files:
    df = pd.read_excel(f) if f.endswith(".xlsx") else pd.read_csv(f)
    df_cols = {canon(c): c for c in df.columns}
    k_state = first_present(df_cols, ["state","state_name"])
    k_dist  = first_present(df_cols, ["district","district_name"])
    k_block = first_present(df_cols, ["block","assessment_unit","taluka","tehsil"])
    k_year  = first_present(df_cols, ["year","assessment_year"])
    k_stage = first_present(df_cols, ["stage","stage_of_extraction","category"])
    if not (k_state and k_dist and k_block and k_year):
        print(f"Skipping {os.path.basename(f)}: missing core columns"); continue
    level_col = pick_level(list(df.columns))
    if not level_col:
        print(f"Skipping {os.path.basename(f)}: no level column"); continue
    out = pd.DataFrame({
        "state":   df[df_cols[k_state]].astype(str).str.strip(),
        "district":df[df_cols[k_dist]].astype(str).str.strip(),
        "block":   df[df_cols[k_block]].astype(str).str.strip(),
        "year":    pd.to_numeric(df[df_cols[k_year]], errors="coerce").astype("Int64"),
        "level_m": pd.to_numeric(df[level_col], errors="coerce"),
        "stage":   df[df_cols[k_stage]].astype(str).map(norm_stage) if k_stage else ""
    }).dropna(subset=["year","level_m"])
    frames.append(out)

import pandas as pd
if not frames: print("No valid rows parsed."); raise SystemExit(0)
all_rows = pd.concat(frames, ignore_index=True)
for col in ["state","district","block","stage"]:
    if col in all_rows: all_rows[col] = all_rows[col].astype(str).str.strip()

conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
cur.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE}(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  state TEXT, district TEXT, block TEXT,
  year INTEGER, level_m REAL, stage TEXT
);""")
cur.execute(f"DELETE FROM {TABLE};")
all_rows.to_sql(TABLE, conn, if_exists="append", index=False)
conn.commit(); conn.close()
print(f"Ingested {len(all_rows)} rows → {DB_PATH}:{TABLE}")
