# Supply Risk Assistant

A small decision-support prototype for health-commodity supply chains. It looks
at stock levels across several facilities, works out which medicines are heading
for a stockout or about to expire unused, finds cases where stock can be moved
between facilities instead of wasted, and writes a short plain-language briefing
a facility officer can act on.

I built this to practise putting a language model to work on a real supply-chain
problem, in a way where the model does not get to make up numbers. I come from a
supply-chain and logistics background, so the stockout and expiry dynamics are
familiar ground. The health-commodity setting is a stand-in; the same logic fits
any perishable, lead-time-driven inventory.

## The problem

Facilities run out of essential items while, at the same time, other facilities
sit on stock of the same item that is about to expire. Both failures are
avoidable with better visibility. The hard part is not the maths, it is turning
the maths into something a busy, non-technical person will read and act on.

## How it works

The project is deliberately split so that the language model never touches the
numbers. All the risk logic is plain, testable arithmetic. The model only turns
finished facts into readable guidance.

```
data  ->  forecast  ->  risk engine  ->  redistribution  ->  LLM briefing  ->  guardrail
```

1. **Data (`generate_data.py`)** Synthetic stock and 180 days of daily
   consumption for 5 medicines across 3 facilities. Patterns are built in on
   purpose: a weekly cycle, a seasonal rise on the malaria drug, and a recent
   demand spike on ORS at one facility, so the forecast has something real to find.

2. **Forecast (`forecast.py`)** Estimates forward daily demand from the recent
   trend, not just a flat average, so a rising demand shows up before it causes a
   stockout. The projection is capped so a short sharp spike cannot extrapolate to
   silly numbers. It is a simple, transparent method, chosen so I can explain and
   check every step.

3. **Risk engine (`risk_engine.py`)** For each item at each facility it computes
   days of cover against forecast demand, applies two stockout rules (below reorder
   level, and cover shorter than resupply lead time) and records which one fired,
   and works out how many units will expire unused and what that is worth. No AI
   here. Same input always gives the same output.

4. **Redistribution (`redistribution.py`)** Finds the same item sitting in surplus
   at one facility and short at another, and proposes a transfer. It only moves what
   the short facility needs, and only what the surplus facility can spare after
   covering its own demand, so it never fixes one stockout by causing another.

5. **Briefing (`build_briefing.py`)** Sends the computed facts to a language model
   with strict instructions: use only these numbers, do not calculate, rank by
   urgency, and tie a stockout to its redistribution fix. The model writes the
   briefing. It is given the finished facts only, never the raw data, so it has
   nothing to miscalculate.

6. **Guardrail (`guardrail.py`)** Reads the briefing back, pulls out every number,
   and checks each one against the source facts. Anything the model invented or
   mis-stated is flagged. This is the automatic honesty check on the model's output.

## Why the language model is boxed in like this

Language models are good at language and unreliable at arithmetic. So I gave the
arithmetic to code, where it is exact and auditable, and gave the model the one job
it is actually good at: turning a table of facts into clear, prioritised writing for
a non-technical reader. The model makes no risk decision and sees no raw data, and
its output is checked. If someone asks "how do you know the AI isn't making things
up", the answer is the guardrail, and I can show it catching a planted fake number.

## Running it

You need Python 3 and an Anthropic API key.

```
# 1. install dependencies
pip install -r requirements.txt

# 2. add your API key
copy .env.example .env        # Windows   (use: cp .env.example .env  on Mac/Linux)
# then open .env and paste your key after ANTHROPIC_API_KEY=

# 3. run the whole pipeline
python run.py
```

The briefing is printed and saved to `briefing_output.txt`. Only the briefing step
uses the API key and it costs a fraction of a cent per run. If you get a
"model not found" error, open `build_briefing.py` and change the model name to one
your account can use.

The key lives only in `.env`, which is listed in `.gitignore` and is never committed.

## What I would do next

- **Seasonality.** The trend forecast catches sudden shocks well but underweights
  slow seasonal drift. A seasonal model (such as Holt-Winters) would forecast weeks
  to months ahead for procurement planning, which is a different job from the
  short-horizon stockout alert this does now.
- **Transport cost in redistribution.** Right now a transfer is judged only on stock,
  not on what it costs or how long it takes to move goods between facilities. A real
  version would weigh waste avoided against the cost to redistribute.
- **Guardrail on actions, not just numbers.** The check validates figures, not the
  named medicine or action. It would catch "12 units" when the fact says 80, but not
  a wrong drug name with no wrong number. Validating the claims too is the next step.
- **Real data.** The dataset is synthetic. The point was to build and test the logic;
  the next step is to run it against a real facility dataset.

## Files

| File | What it does |
|------|--------------|
| `generate_data.py` | builds the synthetic stock + consumption data |
| `forecast.py` | forward demand forecast with a cap |
| `risk_engine.py` | stockout and expiry risk, pure arithmetic |
| `redistribution.py` | matches surplus to shortage across facilities |
| `build_briefing.py` | sends facts to the model, gets the briefing |
| `guardrail.py` | checks the briefing invents no numbers |
| `run.py` | runs the whole pipeline in order |
