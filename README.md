# CrewKit

**Software, built by a crew you never manage.**

CrewKit is a one-founder software studio where a team of AI agents — a planner, builders, a
security reviewer and a deployer — ships customer orders from a shared plan. Customers describe
the work in plain words through a storefront that prices the crew honestly; the order lands in
a Band room where the crew plans, claims, reviews, gates and ships it.

## The architecture

```
storefront (this repo)  ──order──▶  Band room (9 agents, 3 harnesses)
      │                                    │
      ▼                                    ├── Claude Code (planner, security, scout,
Flexprice                                    │   tester, deployer, cashier)
meters + credits                             ├── Codex (backend builder)
gate the intake                              └── Copilot (frontend builder)
                                             │
                                             ▼
                                      Cognee memory (crewkit-memory)
                                      knowledge graph on Neon pgvector
                                             │
                                             ▼
                                      Snyk gates every work item
```

- **Storefront** (`server.py` + `index.html`): a four-slide work order — intake interview,
  crew configuration (MVP / Mid / Premium / Flagship), an honest-math quote ledger
  (estimated agent tokens × model cost × margin), and dispatch. Credits gate the intake
  through the customer's Flexprice wallet.
- **The quote is derived, not displayed**: interview answers (work type, surfaces, auth/payments,
  urgency) set the scoped token estimate; the tier sets the model, reviews and multiplier.
- **Every order** is metered to Flexprice (`agent_tokens`, `feature_shipped`) and posted to the
  crew's Band room with its scoping, so the planner quotes the crew to the same numbers.

## The crew

9 agents in one Band room, across three harnesses:

| Agent | Harness | Role |
|---|---|---|
| Planner | Claude Code | recalls memory, writes the plan, assigns board items |
| Scout | Claude Code | storefront liaison — every order starts with a memory recall |
| Backend | Codex | implements API items |
| Frontend | Copilot | implements UI items |
| Security | Claude Code | Snyk gate — no item reaches Done dirty |
| Tester | Claude Code | runs the suite on every item |
| Deployer | Claude Code | ships only after founder approval in Band |
| Cashier | Claude Code | owns Stripe + Flexprice work |

Memory: every agent writes decisions, findings and lessons to Cognee (see
[crewkit-memory](https://github.com/patrickboxfordpartners/crewkit-memory)) and recalls
before acting — across sessions, restarts and agents.

## Run

```
uv venv && uv pip install flask
export FLEXPRICE_API_KEY=...   # us.api.flexprice.io
.venv/bin/python server.py     # storefront at :5000, chapter cards at /cards
```

Built at the SF Startup Challenge. Band · Cognee · Snyk · Flexprice.
