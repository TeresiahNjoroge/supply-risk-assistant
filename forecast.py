"""
Box 2.4: Demand forecast layer.

Purpose: estimate the forward daily consumption rate for each record, so the
risk engine can judge stockouts against where demand is HEADING, not just its
long-run average. This is the 'predictive analytics layer' the problem calls for.

Method (deliberately simple and transparent, so it can be explained and audited):
  1. Baseline rate  = mean of days 45-15 ago   (a settled, pre-recent window)
  2. Recent rate    = mean of the last 14 days  (where demand is now)
  3. Daily slope    = (recent - baseline) / gap_in_days_between_window_midpoints
  4. Forecast rate  = recent + slope * (lead_time / 2)
                      i.e. project the trend forward across the resupply window,
                      evaluated at its midpoint so we get an average-over-period rate.
  5. CAP: forecast is bounded to <= 1.5x the item's own recent peak day, so a steep
     short-term ramp cannot extrapolate to implausible demand. (Known weakness of
     naive trend projection; the cap is the guardrail.)

No ML library, no training. Just windowed means and a bounded linear projection.
"""
import csv
from datetime import date, timedelta
from collections import defaultdict

TODAY = date(2026, 11, 3)

# ---- load history, grouped and date-sorted per (facility, item) --------------
series = defaultdict(list)
with open("consumption_history.csv") as f:
    for r in csv.DictReader(f):
        series[(r["facility"], r["item_code"])].append(
            (date.fromisoformat(r["date"]), int(r["units_dispensed"]))
        )
for k in series:
    series[k].sort()

def window_mean(s, start_days_ago, end_days_ago):
    """Mean units/day for days whose age is within [end, start] days ago."""
    lo = TODAY - timedelta(days=start_days_ago)
    hi = TODAY - timedelta(days=end_days_ago)
    vals = [q for (d, q) in s if lo <= d <= hi]
    return sum(vals) / len(vals) if vals else 0.0

def recent_peak(s, days=14):
    cutoff = TODAY - timedelta(days=days)
    vals = [q for (d, q) in s if d >= cutoff]
    return max(vals) if vals else 0

def forecast_rate(s, lead_time_days):
    baseline = window_mean(s, 45, 15)     # settled window
    recent   = window_mean(s, 14, 0)      # current window
    # midpoints of the two windows are ~30 and ~7 days ago -> ~23 days apart
    gap_days = 23
    slope = (recent - baseline) / gap_days          # units/day change per day
    projected = recent + slope * (lead_time_days / 2.0)
    # --- the cap ---
    ceiling = 1.5 * recent_peak(s)
    capped = min(projected, ceiling) if ceiling > 0 else projected
    capped = max(0.0, capped)                        # never negative
    return {
        "baseline_rate": round(baseline, 1),
        "recent_rate": round(recent, 1),
        "slope_per_day": round(slope, 2),
        "forecast_rate": round(capped, 1),
        "was_capped": capped < projected - 0.05,
    }

# ---- produce a forecast per stock record -------------------------------------
out_rows = []
with open("stock_snapshot.csv") as f:
    for r in csv.DictReader(f):
        key = (r["facility"], r["item_code"])
        lead = int(r["lead_time_days"])
        fc = forecast_rate(series[key], lead)
        out_rows.append({"facility": r["facility"], "item_code": r["item_code"], **fc})

with open("demand_forecast.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
    w.writeheader()
    w.writerows(out_rows)

# ---- show before/after: flat average vs forecast -----------------------------
print("DEMAND FORECAST vs FLAT AVERAGE\n")
print(f"{'facility':22} {'item':9} {'baseline':>8} {'recent':>7} {'slope':>6} "
      f"{'forecast':>8} {'capped?':>7}")
print("-"*80)
for x in out_rows:
    print(f"{x['facility'][:22]:22} {x['item_code']:9} "
          f"{x['baseline_rate']:>8} {x['recent_rate']:>7} {x['slope_per_day']:>6} "
          f"{x['forecast_rate']:>8} {'yes' if x['was_capped'] else '-':>7}")
