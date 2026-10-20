# CrewKit

**Software, built by a crew you never manage.**

CrewKit is a **one-founder software studio** (SF Startup Challenge, Track 1). One human founder
runs a crew of AI agents in a Band room. Customers describe work in plain words through a
storefront that prices the crew honestly; the order lands in the room, where the crew plans,
builds, reviews, security-gates and ships it. The founder approves before anything deploys.

The crew's first shipped product is **[Lexis](https://github.com/patrickboxfordpartners/lexis)**,
a prompt-precision tool.

| Repo | What it is |
|---|---|
| [crewkit](https://github.com/patrickboxfordpartners/crewkit) | storefront, order intake, Snyk security gate (this repo) |
| [crewkit-memory](https://github.com/patrickboxfordpartners/crewkit-memory) | the crew's shared Cognee memory CLI |
| [lexis](https://github.com/patrickboxfordpartners/lexis) | product shipped by the crew |

## Architecture

```
storefront (server.py)  ── order ──▶  Band room (planner, builders, reviewer, security)
   │  credit gate + metering                 │  board: To-do → In progress → Review → Done
   ▼                                         │  founder approval before deploy
Flexprice wallet / events                    ▼
                                    scripts/snyk_gate.py  ── blocks item on high/critical
                                             │
                                             ▼
                                    Cognee memory (crewkit-memory, dataset "studio")
```

## The agent team

| Agent | Harness | Role | Hands off to |
|---|---|---|---|
| Planner | [harness placeholder] | recalls memory, writes the plan, creates board items | Builders |
| Builder (backend) | [harness placeholder] | implements API items | Reviewer |
| Builder (frontend) | [harness placeholder] | implements UI items | Reviewer |
| Reviewer | [harness placeholder] | code review against plan + past lessons from memory | Security |
| Security | [harness placeholder] | runs `scripts/snyk_gate.py`, posts findings, blocks the item | Founder |
| Founder (human) | Band | approves the item and the deploy | — |

## How each sponsor tool is used (true to the code)

- **Band**: `POST /api/order` posts the scoped order into the crew room with `band send <room> --body-file … --as patrick/planner`.
  The crew works the board in the Band room; the founder approves there.
- **Cognee**: agents call `crewkit-memory/memory.py remember|recall|improve|forget` on the `studio` dataset.
  The Snyk gate recalls past security findings before scanning, flags recurring ones, and stores every new finding.
- **Flexprice**: before an order is accepted the storefront reads the customer's wallet
  (`/v1/wallets/{id}`); if the balance is below the quote it returns **402 insufficient credits**.
  Accepted orders are metered as a `feature_shipped` event (`/v1/events`). Customer is currently hardcoded to `lexis` (demo).
- **Snyk**: `scripts/snyk_gate.py <repo>` runs `snyk test --json` and `snyk code test --json`, summarizes high/critical findings
  as Markdown for the room, and exits `1` (BLOCKED) until they're fixed.

### The quote

Interview answers (work type, surfaces, auth/payments, urgency) set the scoped token estimate; the tier
(MVP / Mid / Premium) sets model, review passes and multiplier. Price = agent compute cost × 2 margin + **$49 flat studio fee**
(shown as its own ledger line).

## Setup

```bash
# 1. Storefront
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env    # set FLEXPRICE_API_KEY (and BAND_BIN if band isn't on PATH)
set -a; . ./.env; set +a
.venv/bin/python server.py          # http://127.0.0.1:5000  (chapter cards at /cards)

# 2. Band CLI (jam): install and log in, see https://docs.band.ai/jam
band login                          # the storefront finds band via $BAND_BIN, PATH, ~/.local/bin, /opt/homebrew/bin

# 3. Memory: clone crewkit-memory next to this repo and follow its README
git clone https://github.com/patrickboxfordpartners/crewkit-memory ../crewkit-memory

# 4. Snyk
npm i -g snyk && snyk auth
python scripts/snyk_gate.py ../lexis --item "Export history API"
```

Errors from Flexprice or Band come back as JSON (`502`/`503`) with a clear message, so the storefront never shows a raw 500.

### Security agent instructions (paste into the Security agent's prompt)

> When a work item reaches Review, run `python scripts/snyk_gate.py <repo> --item "<item title>"`.
> Post the full output to the room. If the exit code is non-zero, keep the item blocked and assign the
> findings back to the builder. Re-run after the fix; only a PASS lets the item move to Done.

Built at the SF Startup Challenge. Band · Cognee · Snyk · Flexprice.
