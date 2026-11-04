"""
Runs the whole pipeline in order, one command instead of five.
The final step (build_briefing) needs your API key in a .env file.
"""
import subprocess, sys

steps = [
    ("Generating data",        "generate_data.py"),
    ("Forecasting demand",     "forecast.py"),
    ("Computing risk",         "risk_engine.py"),
    ("Finding redistribution", "redistribution.py"),
    ("Writing briefing (LLM)", "build_briefing.py"),
    ("Checking briefing",      "guardrail.py"),
]

for label, script in steps:
    print(f"\n{'='*55}\n{label}  ({script})\n{'='*55}")
    result = subprocess.run([sys.executable, script])
    if result.returncode != 0:
        print(f"\nStopped: {script} did not finish cleanly.")
        sys.exit(1)

print("\nAll steps complete. See briefing_output.txt")
