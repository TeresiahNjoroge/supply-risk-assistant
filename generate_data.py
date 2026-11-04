"""
Box 1: Synthetic essential-medicines dataset (180 days of history).

Patterns deliberately built in so the forecast layer has something real to find:
  1. A mild weekly cycle on every item (busier early week, quiet weekends).
  2. A seasonal rise on the antimalarial (AL) into the rainy season.
  3. A recent outbreak ramp on ORS at Thika (demand climbing over the last ~4 weeks).

Everything is deterministic (no random seed) so results reproduce exactly.
"""
import csv
import math
from datetime import date, timedelta

TODAY = date(2026, 11, 3)
HISTORY_DAYS = 180

MEDICINES = {
    "AMOX-250": {"name": "Amoxicillin 250mg suspension", "category": "Antibiotic",   "unit_cost": 45},
    "AL-ACT":   {"name": "Artemether-Lumefantrine (AL)",  "category": "Antimalarial", "unit_cost": 120},
    "ORS-SACH": {"name": "Oral Rehydration Salts sachet", "category": "Diarrhoea",    "unit_cost": 15},
    "ZINC-20":  {"name": "Zinc Sulfate 20mg tablet",      "category": "Diarrhoea",    "unit_cost": 8},
    "RUTF-BAR": {"name": "Ready-to-Use Therapeutic Food", "category": "Nutrition",    "unit_cost": 95},
}

# (facility, item, current_stock, base_daily, reorder_level, lead_time, days_to_expiry, flags)
# base_daily is the baseline consumption; patterns are applied on top per day.
RECORDS = [
    ("Thika Dispensary",      "ORS-SACH",  80,  16,  150, 7,  240, {"outbreak": True}),
    ("Kiambu District Store", "AL-ACT",    900, 12,  200, 5,  20,  {"malaria_season": True}),
    ("Ruiru Health Centre",   "AL-ACT",    40,  15,  120, 6,  300, {"malaria_season": True}),
    ("Kiambu District Store", "AMOX-250",  420, 18,  200, 5,  180, {}),
    ("Ruiru Health Centre",   "AMOX-250",  260, 16,  150, 6,  160, {}),
    ("Thika Dispensary",      "AMOX-250",  190, 14,  120, 7,  150, {}),
    ("Kiambu District Store", "ORS-SACH",  600, 20,  200, 5,  220, {}),
    ("Ruiru Health Centre",   "ORS-SACH",  300, 18,  150, 6,  210, {}),
    ("Kiambu District Store", "ZINC-20",   500, 19,  200, 5,  200, {}),
    ("Ruiru Health Centre",   "ZINC-20",   240, 15,  150, 6,  190, {}),
    ("Thika Dispensary",      "ZINC-20",   170, 13,  120, 7,  185, {}),
    ("Kiambu District Store", "RUTF-BAR",  350, 10,  150, 5,  120, {}),
    ("Ruiru Health Centre",   "RUTF-BAR",  180, 9,   100, 6,  110, {}),
    ("Thika Dispensary",      "RUTF-BAR",  60,  11,  100, 7,  95,  {}),
    ("Thika Dispensary",      "AL-ACT",    210, 13,  120, 7,  170, {"malaria_season": True}),
]

def weekly_factor(d):
    # Mon=0 .. Sun=6 : busier Mon-Wed, quieter weekend
    wd = d.weekday()
    return {0:1.10, 1:1.12, 2:1.08, 3:1.00, 4:0.95, 5:0.80, 6:0.78}[wd]

def seasonal_factor(d, on):
    # Smooth rise toward Nov (rainy season). Peak ~ now, trough ~6 months ago.
    if not on:
        return 1.0
    # days_ago 0 (today) -> peak; 180 -> trough
    days_ago = (TODAY - d).days
    # cosine curve from 0.8 (trough) to 1.35 (peak)
    phase = (days_ago / 180.0) * math.pi          # 0..pi
    return 0.8 + (1.35 - 0.8) * (math.cos(phase) + 1) / 2 * 0 + (1.35 - (1.35-0.8)*(days_ago/180.0))

def outbreak_factor(d, on):
    # Flat for most of the window, then a ramp over the last 28 days.
    if not on:
        return 1.0
    days_ago = (TODAY - d).days
    if days_ago > 28:
        return 1.0
    # ramp from 1.0 (28 days ago) up to ~2.2x (today)
    return 1.0 + (1.2) * (28 - days_ago) / 28.0

def daily_qty(base, d, flags):
    q = base
    q *= weekly_factor(d)
    q *= seasonal_factor(d, flags.get("malaria_season", False))
    q *= outbreak_factor(d, flags.get("outbreak", False))
    # small deterministic wobble so it isn't suspiciously smooth
    wob = ((d.toordinal() * 7) % 11 - 5) / 50.0    # ~ +/-10%
    q *= (1 + wob)
    return max(0, round(q))

stock_path = "stock_snapshot.csv"
hist_path  = "consumption_history.csv"

with open(stock_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["facility","item_code","item_name","category","current_stock",
                "reorder_level","lead_time_days","expiry_date","unit_cost_kes"])
    for (fac,item,stock,base,reorder,lead,dte,flags) in RECORDS:
        med = MEDICINES[item]
        expiry = (TODAY + timedelta(days=dte)).isoformat()
        w.writerow([fac,item,med["name"],med["category"],stock,reorder,lead,expiry,med["unit_cost"]])

rows_written = 0
with open(hist_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["facility","item_code","date","units_dispensed"])
    for (fac,item,stock,base,reorder,lead,dte,flags) in RECORDS:
        for n in range(HISTORY_DAYS, 0, -1):
            d = TODAY - timedelta(days=n)
            w.writerow([fac,item,d.isoformat(),daily_qty(base,d,flags)])
            rows_written += 1

print(f"Stock records: {len(RECORDS)}")
print(f"History rows : {rows_written}  ({len(RECORDS)} x {HISTORY_DAYS} days)")
