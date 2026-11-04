"""
Box 2.5: Redistribution matcher. NO AI, pure logic.

Finds cases where the SAME item has a surplus at one facility (expiring unused)
and a shortage at another (stockout risk), and proposes a transfer that:
  - moves units from donor (surplus) to recipient (shortage)
  - leaves the donor enough to cover its OWN forecast demand over a buffer period
  - sends only what the recipient needs to reach a safe cover level
  - reports the wastage avoided (units that would have expired, now used)

Reads risk_facts.csv (from the engine). Writes redistribution_suggestions.csv.
"""
import csv
from collections import defaultdict

# how many days of its own cover a donor must retain before giving units away
DONOR_SELF_COVER_DAYS = 21
# target days of cover we want to lift a short recipient up to
RECIPIENT_TARGET_COVER_DAYS = 14

facts = []
with open("risk_facts.csv") as f:
    for r in csv.DictReader(f):
        facts.append(r)

# group facts by item so we only ever match like-for-like
by_item = defaultdict(list)
for x in facts:
    by_item[x["item_code"]].append(x)

def num(v):
    try: return float(v)
    except: return 0.0

suggestions = []
for item, rows in by_item.items():
    donors    = [x for x in rows if x["status"] == "EXPIRY_RISK"]
    recipients = [x for x in rows if x["status"] == "STOCKOUT_RISK"]
    if not donors or not recipients:
        continue

    for d in donors:
        d_stock = num(d["current_stock"])
        d_rate  = num(d["forecast_rate"])
        # units the donor must keep for itself
        d_keep  = d_rate * DONOR_SELF_COVER_DAYS
        d_spare = max(0, d_stock - d_keep)
        if d_spare <= 0:
            continue

        for r in recipients:
            r_stock = num(r["current_stock"])
            r_rate  = num(r["forecast_rate"])
            # units needed to lift recipient to target cover
            r_target = r_rate * RECIPIENT_TARGET_COVER_DAYS
            r_need   = max(0, r_target - r_stock)
            if r_need <= 0:
                continue

            move = round(min(d_spare, r_need))
            if move <= 0:
                continue

            # benefit: units that would have expired at donor, now used
            would_expire = num(d["units_expiring_unused"])
            wastage_avoided_units = min(move, would_expire)
            # recipient cover after the move
            new_r_cover = round((r_stock + move) / r_rate, 1) if r_rate > 0 else None

            suggestions.append({
                "item_code": item,
                "item_name": d["item_name"],
                "from_facility": d["facility"],
                "to_facility": r["facility"],
                "move_units": move,
                "donor_keeps": round(d_keep),
                "recipient_cover_before_days": r["cover_forecast"],
                "recipient_cover_after_days": new_r_cover,
                "wastage_avoided_units": round(wastage_avoided_units),
            })

if suggestions:
    with open("redistribution_suggestions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(suggestions[0].keys()))
        w.writeheader(); w.writerows(suggestions)

print(f"Redistribution opportunities found: {len(suggestions)}\n")
for s in suggestions:
    print(f"MOVE {s['move_units']} units of {s['item_code']} "
          f"({s['item_name']})")
    print(f"   from {s['from_facility']}  ->  {s['to_facility']}")
    print(f"   recipient cover: {s['recipient_cover_before_days']}d  ->  {s['recipient_cover_after_days']}d")
    print(f"   donor retains {s['donor_keeps']} units for its own demand")
    print(f"   wastage avoided: {s['wastage_avoided_units']} units")
    print()
