import json, csv, pathlib
from collections import defaultdict

SRC = "data/userRecord.cleaned.csv"
OUT = pathlib.Path("docs/api")
(OUT / "byCounty").mkdir(parents=True, exist_ok=True)

rows = []
with open(SRC, newline="") as f:
    rdr = csv.DictReader(f)
    for r in rdr:
        r["Latency"] = int(r["Latency"])
        r["County"] = (r["County"] or "").strip().upper()
        rows.append(r)

lat = [r["Latency"] for r in rows]
def q(p): 
    if not lat: return 0
    i = int(p * (len(lat)-1))
    return sorted(lat)[i]

# Summary
by_cnty = defaultdict(list)
for r in rows: by_cnty[r["County"]].append(r["Latency"])
summary = {
  "count": len(rows),
  "mean": (sum(lat)/len(lat)) if lat else 0,
  "p50": q(0.50), "p95": q(0.95), "p99": q(0.99),
  "byCountyAvg": {c: sum(v)/len(v) for c, v in by_cnty.items()}
}
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "summary.json", "w") as f: json.dump(summary, f, indent=2)

# Per-county full lists (sorted by highest latency)
from itertools import groupby
for county, group in groupby(sorted(rows, key=lambda r: r["County"]), key=lambda r: r["County"]):
    items = sorted(list(group), key=lambda r: r["Latency"], reverse=True)
    with open(OUT / "byCounty" / (county or "UNKNOWN") + ".json", "w") as f:
        json.dump(items, f, indent=2)
