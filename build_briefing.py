"""
Box 3: LLM briefing layer.

The LLM's ONLY job is to turn the computed facts into a ranked, plain-language
briefing for a non-technical health officer. It makes no calculations and no
risk decisions: those are already fixed by the engine (Box 2) and the
redistribution matcher (Box 2.5). The LLM is handed finished facts and told,
explicitly, to use only those numbers.

Key handling: the API key is read from the environment (loaded from a local
.env file that is git-ignored). It is never written into the code or the repo.
"""
import os
import csv

# ---- Step 1: assemble the facts the model is allowed to see ------------------
def load_rows(path):
    with open(path) as f:
        return list(csv.DictReader(f))

def assemble_facts():
    risk = load_rows("risk_facts.csv")
    try:
        moves = load_rows("redistribution_suggestions.csv")
    except FileNotFoundError:
        moves = []

    lines = ["STOCK RISK FACTS (computed, do not change these numbers):"]
    for r in risk:
        if r["status"] == "OK":
            continue   # only brief on items that need attention
        lines.append(
            f"- {r['facility']} | {r['item_name']} ({r['item_code']}) | "
            f"status={r['status']} | stock={r['current_stock']} | "
            f"forecast_daily_use={r['forecast_rate']} | "
            f"days_cover={r['cover_forecast']} | lead_time_days={r['lead_time_days']} | "
            f"days_to_expiry={r['days_to_expiry']} | "
            f"units_expiring={r['units_expiring_unused']} | "
            f"wastage_value_kes={r['wastage_value_kes']} | why={r['reasons']}"
        )

    if moves:
        lines.append("\nREDISTRIBUTION OPPORTUNITIES (computed):")
        for m in moves:
            lines.append(
                f"- Move {m['move_units']} units of {m['item_name']} "
                f"({m['item_code']}) from {m['from_facility']} to {m['to_facility']}. "
                f"Recipient cover rises from {m['recipient_cover_before_days']} to "
                f"{m['recipient_cover_after_days']} days. "
                f"Donor keeps {m['donor_keeps']} units. "
                f"Avoids {m['wastage_avoided_units']} units of wastage."
            )
    return "\n".join(lines)

# ---- Step 2: the prompt ------------------------------------------------------
SYSTEM_PROMPT = """You are a supply-chain assistant for a network of health facilities.
You write short, clear stock briefings for facility officers who are NOT data analysts.

Strict rules:
- Use ONLY the numbers given in the facts. Do not invent, estimate, round differently,
  or infer any figure that is not stated.
- Do not perform your own calculations. The figures are already computed.
- Rank the issues by urgency: imminent stockouts of essential medicines first,
  then expiry/wastage. If a stockout can be solved by a redistribution that is listed,
  say so together with that stockout.
- For each item: say what the problem is, how urgent (use the days figures given),
  and the recommended action in one plain sentence.
- Be concise. No jargon. No preamble. Write for someone deciding what to do this morning."""

USER_TEMPLATE = """Here are today's computed stock facts across the facilities.
Write the briefing.

{facts}"""

def build_messages():
    facts = assemble_facts()
    return SYSTEM_PROMPT, USER_TEMPLATE.format(facts=facts)

# ---- Step 3: the real API call (runs on your laptop with your key) -----------
def generate_briefing():
    """
    Calls the model to turn the computed facts into a briefing.
    Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
    Returns the briefing text.
    """
    try:
        import anthropic
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install anthropic python-dotenv")

    # load .env if present (keeps the key out of the code and out of git)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "No API key found. Create a .env file with:\n"
            "  ANTHROPIC_API_KEY=sk-ant-your-key-here"
        )

    system, user = build_messages()
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-5-5",   # current Sonnet model on my account,   # change to any current model you have access to
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text

# ---- run everything (must stay LAST, after all functions are defined) --------
if __name__ == "__main__":
    briefing = generate_briefing()
    print(briefing)
    with open("briefing_output.txt", "w") as f:
        f.write(briefing)
    print("\n(Saved to briefing_output.txt)")