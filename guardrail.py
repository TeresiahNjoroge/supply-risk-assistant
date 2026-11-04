"""
Box 4: Output guardrail (hallucination check). NO AI.

The LLM briefing (Box 3) is only allowed to repeat numbers that the engine
computed. This module checks that it did: it extracts every number from the
briefing text and confirms each one appears in the source facts. Any number in
the briefing that is NOT in the facts is flagged as a possible hallucination.

This is a safety net, not a guarantee. It catches invented or mis-stated
figures, which is the most common and most dangerous LLM failure for a tool
that drives real stock decisions.
"""
import re
import csv

def numbers_in(text):
    """Pull out all numbers (ints and decimals) from a block of text."""
    # matches 40, 1.3, 48000, 48,000 -> normalised without commas
    raw = re.findall(r"\d[\d,]*\.?\d*", text)
    out = set()
    for r in raw:
        r = r.replace(",", "")
        try:
            f = float(r)
            out.add(f)
        except ValueError:
            pass
    return out

def facts_numbers():
    """Collect every number that legitimately appears in the computed facts."""
    nums = set()
    for path in ("risk_facts.csv", "redistribution_suggestions.csv"):
        try:
            with open(path) as f:
                for row in csv.DictReader(f):
                    for v in row.values():
                        for n in numbers_in(str(v)):
                            nums.add(n)
        except FileNotFoundError:
            pass
    return nums

def check(briefing_text):
    allowed = facts_numbers()
    used = numbers_in(briefing_text)

    # a briefing number is OK if it matches a fact number (allow tiny rounding)
    def is_supported(n):
        if n in allowed:
            return True
        # allow a value that rounds to / from a fact value within 0.1
        return any(abs(n - a) <= 0.1 for a in allowed)

    # ignore bare small integers used as list labels (1, 2, 3) and dates
    suspicious = []
    for n in used:
        if n in (1, 2, 3, 4, 5):      # list numbering / "1 sentence" etc.
            continue
        if 2024 <= n <= 2030:          # a year
            continue
        if not is_supported(n):
            suspicious.append(n)

    return sorted(suspicious)

if __name__ == "__main__":
    try:
        briefing = open("briefing_output.txt").read()
    except FileNotFoundError:
        raise SystemExit("No briefing_output.txt yet. Run build_briefing.py first.")

    flagged = check(briefing)
    print("GUARDRAIL CHECK")
    print("-"*40)
    print(f"Numbers in briefing : checked")
    if not flagged:
        print("PASS: every figure in the briefing traces back to the computed facts.")
    else:
        print(f"WARNING: {len(flagged)} figure(s) not found in the facts:")
        for n in flagged:
            print(f"  - {n}  (not in computed facts, possible hallucination)")
        print("\nReview these before trusting the briefing.")
