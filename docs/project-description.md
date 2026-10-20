# CrewKit: a one-founder software studio run by an AI crew

**Track 1: One-founder software studio** · Demo: storefront at http://localhost:5000 · lexis live at [LEXIS_URL] · Video: [video link placeholder]
Repos: [crewkit](https://github.com/patrickboxfordpartners/crewkit) · [crewkit-memory](https://github.com/patrickboxfordpartners/crewkit-memory) · [lexis](https://github.com/patrickboxfordpartners/lexis)

## Problem
Solo founders and small businesses need software shipped, but hiring an agency is slow and opaque, and
"just use an AI agent" means babysitting one agent that forgets everything between sessions and ships
insecure code. CrewKit is a studio where one human founder runs a crew of AI agents that plans, builds,
reviews, security-gates and ships customer work, priced honestly from real agent cost.

## How it works
1. A customer answers a 4-question intake on the CrewKit storefront and picks a tier (MVP / Mid / Premium / Flagship).
   The quote is derived from the answers: estimated agent tokens × model cost × review passes × 2 margin + $49 flat fee.
2. **Flexprice** gates the order: if the customer's wallet balance is below the quote, the order is refused (402).
   Accepted orders are metered as a `feature_shipped` event.
3. The order is posted into the crew's **Band** room. The Planner recalls memory, writes the plan and creates board items.
4. Builders implement; the Reviewer reviews; the Security agent runs the **Snyk** gate.
   High/critical findings block the item. The founder approves in Band before deploy.
5. Every decision, finding and lesson goes into **Cognee**, so the next session and the next agent start smarter.

The crew's first shipped product is **Lexis**, a prompt-precision tool (React + Vercel + Neon + Clerk + xAI).

## The agent team
| Agent | Harness | Role | Handoff |
|---|---|---|---|
| Planner | Claude Code | recall memory, plan, create board items | → Builders |
| Backend builder | Codex (OpenAI) | API work items | → Reviewer |
| Frontend builder | Copilot (GitHub) | UI work items | → Reviewer |
| Reviewer | Claude Code | code review against plan and past lessons | → Security |
| Security reviewer | Claude Code | Snyk gate, posts findings, blocks item | → Founder |
| Founder (human) | Band | approves item + deploy | → Done |

Handoffs happen on the Band board (To-do → In progress → Review → Done) with @mentions in the room.

## How Cognee is used
- `crewkit-memory/memory.py` is the crew's shared memory CLI over one Cognee dataset, `studio`:
  `remember <agent> <kind> "<text>"`, `recall "<question>"` (graph completion), `improve`, `forget`.
- Memory persists across restarts and is shared across agents. Demo: the Security agent stores a Snyk finding;
  after every session is restarted, a different agent recalls it and changes its behavior (it blocks the PR that
  reintroduces the issue).
- The Snyk gate recalls past security findings *before* scanning and labels repeat issues **RECURRING**.
- `--no-cognify` batches writes; the graph is rebuilt once per batch. Neo4j can be configured as the graph backend (optional) [placeholder: confirm whether used in demo].

## How Flexprice is used
- Wallet balance read before each order (`/v1/wallets/{id}`); orders over balance are rejected with a top-up link.
- Each accepted order is metered (`/v1/events`, `feature_shipped`, with tier, price and scoped tokens).
- The storefront shows the live wallet balance next to the quote.

## How Snyk is used
- `crewkit/scripts/snyk_gate.py <repo> --item "<work item>"` runs `snyk test --json` (dependencies) and
  `snyk code test --json` (SAST), summarizes high/critical findings as Markdown for the Band room, stores each in
  Cognee tagged `[security]`, and exits non-zero so the work item stays blocked until a clean re-run.

## Startup viability
Agencies charge by the hour and hide their cost; CrewKit shows the factory's real cost and charges a transparent
margin. Credits-based billing (Flexprice) means prepaid revenue and no collections. One founder can run many
crews; memory compounds, so every job makes the studio faster and safer.

## What's next
Per-customer wallets (the demo bills one customer, `lexis`), deploy automation behind founder approval, and a
customer-facing live view of the board.
