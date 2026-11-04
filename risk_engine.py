"""
Box 2: Risk engine. NO AI here, pure testable arithmetic.

Now consumes the forecast layer (Box 2.4): days-of-cover is computed against
FORECAST demand, not the flat average, so stockout timing reflects where demand
is heading. We keep the flat average alongside, for transparency and comparison.

Two stockout rules, and we record which fired:
  reorder rule : current_stock < reorder_level     (static floor)
  cover rule   : days_of_cover < lead_time_days     (demand-aware, on forecast)
Expiry rule    : units that expire unused before expiry_date, and their KES value.
"""
import csv
from datetime import date
from collections import defaultdict

TODAY = date(2026, 11, 3)

# ---- flat average from history (kept for comparison) -------------------------
daily = defaultdict(list)
with open("consumption_history.csv") as f:
    for r in csv.DictReader(f):
        daily[(r["facility"], r["item_code"])].append(int(r["units_dispensed"]))
flat_avg = {k: sum(v)/len(v) for k, v in daily.items()}

# ---- forecast rate from Box 2.4 ----------------------------------------------
forecast = {}
with open("demand_forecast.csv") as f:
    for r in csv.DictReader(f):
        forecast[(r["facility"], r["item_code"])] = float(r["forecast_rate"])

# ---- walk the snapshot, compute signals on FORECAST demand -------------------
facts = []
with open("stock_snapshot.csv") as f:
    for r in csv.DictReader(f):
        key = (r["facility"], r["item_code"])
        stock     = int(r["current_stock"])
        reorder   = int(r["reorder_level"])
        lead      = int(r["lead_time_days"])
        unit_cost = int(r["unit_cost_kes"])
        expiry    = date.fromisoformat(r["expiry_date"])

        rate_flat = flat_avg.get(key, 0)
        rate_fc   = forecast.get(key, rate_flat)   # fall back to flat if missing

        cover_flat = round(stock / rate_flat, 1) if rate_flat > 0 else None
        cover_fc   = round(stock / rate_fc, 1)     if rate_fc   > 0 else None
        days_to_expiry = (expiry - TODAY).days

        reorder_fired = stock < reorder
        cover_fired   = (cover_fc is not None) and (cover_fc < lead)

        # expiry uses forecast rate too (how much we'll really use before expiry)
        usable = rate_fc * days_to_expiry if rate_fc > 0 else 0
        units_expiring = max(0, round(stock - usable))
        wastage_value  = units_expiring * unit_cost

        reasons = []
        if reorder_fired: reasons.append("below reorder level")
        if cover_fired:   reasons.append(f"{cover_fc}d forecast cover vs {lead}d lead")
        if units_expiring > 0: reasons.append(f"{units_expiring} units expire unused")

        if reorder_fired or cover_fired:   status = "STOCKOUT_RISK"
        elif units_expiring > 0:           status = "EXPIRY_RISK"
        else:                              status = "OK"

        rule = ("both" if reorder_fired and cover_fired else
                "reorder" if reorder_fired else
                "cover" if cover_fired else "none")

        facts.append({
            "facility": r["facility"], "item_code": r["item_code"],
            "item_name": r["item_name"], "current_stock": stock,
            "flat_avg": round(rate_flat,1), "forecast_rate": round(rate_fc,1),
            "cover_flat": cover_flat if cover_flat is not None else "n/a",
            "cover_forecast": cover_fc if cover_fc is not None else "n/a",
            "reorder_level": reorder, "lead_time_days": lead,
            "days_to_expiry": days_to_expiry,
            "units_expiring_unused": units_expiring,
            "wastage_value_kes": wastage_value,
            "stockout_rule_fired": rule, "status": status,
            "reasons": "; ".join(reasons) if reasons else "healthy",
        })

with open("risk_facts.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(facts[0].keys()))
    w.writeheader(); w.writerows(facts)

# ---- show it, flagged first, with flat-vs-forecast cover side by side ---------
order = {"STOCKOUT_RISK":0, "EXPIRY_RISK":1, "OK":2}
facts.sort(key=lambda x:(order[x["status"]], -x["wastage_value_kes"]))
print("RISK FACTS (cover now computed on FORECAST demand)\n")
print(f"{'facility':22} {'item':9} {'stock':>5} {'cover_flat':>10} {'cover_fcst':>10} "
      f"{'waste KES':>9} {'rule':>7}  status")
print("-"*95)
for x in facts:
    print(f"{x['facility'][:22]:22} {x['item_code']:9} {x['current_stock']:>5} "
          f"{str(x['cover_flat']):>10} {str(x['cover_forecast']):>10} "
          f"{x['wastage_value_kes']:>9} {x['stockout_rule_fired']:>7}  {x['status']}")
