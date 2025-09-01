import json, csv, pathlib
from collections import defaultdict
from itertools import groupby

SRC = "data/userRecord.cleaned.csv"
OUT = pathlib.Path("docs/api")
(OUT / "byCounty").mkdir(parents=True, exist_ok=True)

def to_latency(val):
    """Parse latency from messy strings like '5,983', '5983.0', ' 5983 '."""
    if val is None:
        return None
    s = str(val).strip().replace(",", "")
    if s == "" or s.upper() in {"NA", "NULL"}:
        return None
    try:
        return int(float(s))  # handle '5983.0' as well
    except ValueError:
        return None

rows = []
# utf-8-sig strips a possible BOM from the header
with open(SRC, newline="", encoding="utf-8-sig") as f:
    rdr = csv.DictReader(f)
    for rec in rdr:
        # normalize keys/values
        rec = { (k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in rec.items() }
        rec["Latency"] = to_latency(rec.get("Latency"))
        rec["County"]  = (rec.get("County") or "").strip().upper()
        if rec["Latency"] is None:
            continue
        rows.append(rec)

lat = [r["Latency"] for r in rows]
def q(p):
    if not lat: return 0
    i = int(p * (len(lat) - 1))
    return sorted(lat)[i]

# --- Summary ---
by_cnty = defaultdict(list)
for r in rows:
    by_cnty[r["County"]].append(r["Latency"])

summary = {
    "count": len(rows),
    "mean": (sum(lat) / len(lat)) if lat else 0,
    "p50": q(0.50),
    "p95": q(0.95),
    "p99": q(0.99),
    "byCountyAvg": {c: (sum(v) / len(v)) for c, v in by_cnty.items()},
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2))

# --- Per-county detail (sorted high→low latency) ---
rows_sorted = sorted(rows, key=lambda r: r["County"])
for county, group in groupby(rows_sorted, key=lambda r: r["County"]):
    items = sorted(list(group), key=lambda r: r["Latency"], reverse=True)
    (OUT / "byCounty" / (county or "UNKNOWN")).with_suffix(".json").write_text(json.dumps(items, indent=2))
