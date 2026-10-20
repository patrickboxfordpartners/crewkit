# CrewKit demo: 2:45 shot list

Prep: storefront running (`python server.py`), Band desktop open on the crew room, all agent sessions running,
Snyk authed, crewkit-memory `.env` set, Lexis live at [LEXIS_URL]. Seed one known-vulnerable dependency on a Lexis branch.
Pre-record a backup take of each segment in case a live call is slow.

| Time | Shot | What's on screen | Voiceover |
|---|---|---|---|
| 0:00–0:15 | Hook | Lexis live, rough prompt → precision prompt | "This app was shipped by a crew of AI agents. I'm the only human. This is CrewKit." |
| 0:15–0:40 | Storefront intake | Answer 4 questions, pick Mid tier, quote ledger with tokens, cost, margin, $49 fee | "Customers describe work in plain words; the quote is the crew's real cost plus margin." |
| 0:40–0:55 | **Flexprice credit gate** | Dispatch with a low wallet → "insufficient credits" badge + top-up; top up; dispatch → DISPATCHED stamp, balance drops | "Credits gate the work. No credits, no crew." |
| 0:55–1:20 | **Band room + board** | Order message lands from Planner; Planner recalls memory, creates board items; builders claim them; cost per agent visible | "Planner, two builders, reviewer, security, on Claude Code, Codex and Copilot. The cost view shows what each agent spent." |
| 1:20–1:45 | **Snyk block** | Security agent runs `snyk_gate.py ../lexis --item …`; posts high finding; VERDICT: BLOCKED; item stays in Review | "Nothing reaches Done dirty. The finding is stored in Cognee." |
| 1:45–2:15 | **Restart → Cognee recall changes behavior** | Kill all agent sessions, restart. Builder opens a new item that re-adds the same package; Reviewer runs `memory.py recall` → past finding returned; Reviewer rejects / gate shows **RECURRING** | "New session, different agent, same memory. It caught the mistake before Snyk even ran." |
| 2:15–2:30 | **Human approval → Done** | Fix lands, gate PASS, founder clicks approve in Band, card moves to Done | "I approve once. The crew does the rest." |
| 2:30–2:45 | Close | Lexis live with the shipped change; repo links | "CrewKit: Band, Cognee, Flexprice, Snyk. A software studio with one founder." |
