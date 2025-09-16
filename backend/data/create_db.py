import sqlite3, csv, os
os.makedirs("storage", exist_ok=True)
db_path = "storage/neersetu.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS gw_levels(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  state TEXT, district TEXT, block TEXT,
  year INTEGER, level_m REAL, stage TEXT
);
""")
cur.execute("DELETE FROM gw_levels;")
with open("backend/data/sample_levels.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        cur.execute("""INSERT INTO gw_levels(state,district,block,year,level_m,stage)
                       VALUES(?,?,?,?,?,?)""",
                    (row["state"], row["district"], row["block"],
                     int(row["year"]), float(row["level_m"]), row["stage"]))
conn.commit()
conn.close()
print("Seeded SQLite at storage/neersetu.db")
