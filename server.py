"""CrewKit storefront API.

Endpoints:
  GET  /                 storefront page
  GET  /api/quote?tier=  price quote (agent cost x margin, by tier)
  GET  /api/credits      lexis wallet balance from Flexprice
  POST /api/order        submit feature brief -> Band crew room
"""
import json
import os
import subprocess
import time
import urllib.request

from flask import Flask, request, jsonify, send_file

FP_HOST = "https://us.api.flexprice.io"
FP_KEY = os.environ.get("FLEXPRICE_API_KEY", "")
WALLET_ID = "wallet_01M5DD2GD2AJM50FC33ZNZ8SVS"
ROOM_ID = "cc69d7ea-6b1b-4c91-9b01-91cbe7ab385d"
CUSTOMER = "lexis"

# Tier -> (model class, est. tokens multiplier, review passes, margin, base model cost per 1k tokens USD)
TIERS = {
    "mvp": {"label": "MVP", "model": "Grok-3-mini", "token_mult": 1.0, "reviews": 1, "margin": 2.0, "per_1k": 0.0006},
    "mid": {"label": "Mid-tier", "model": "Claude Sonnet", "token_mult": 2.5, "reviews": 2, "margin": 2.0, "per_1k": 0.009},
    "premium": {"label": "Premium", "model": "Claude Opus + extended thinking", "token_mult": 5.0, "reviews": 3, "margin": 2.0, "per_1k": 0.045},
    "flagship": {"label": "Flagship", "model": "Fable — the frontier model", "token_mult": 8.0, "reviews": 4, "margin": 2.0, "per_1k": 0.075},
}

# Interview scoping: each answer sets a multiplier on the base estimate.
SCOPE = {
    # work type -> (label, base tokens)
    "polish": {"label": "Polish an existing feature", "base": 80_000},
    "feature": {"label": "New feature in an existing app", "base": 150_000},
    "integration": {"label": "New integration (auth, payments, external API)", "base": 300_000},
    "app": {"label": "A whole new app", "base": 600_000},
    # surface -> multiplier
    "ui": {"label": "UI only", "mult": 1.0},
    "api": {"label": "API only", "mult": 1.2},
    "both": {"label": "UI and API", "mult": 1.6},
    # complexity gate
    "no_gate": {"label": "No", "mult": 1.0},
    "gate": {"label": "Yes — auth or payments", "mult": 1.5},
    # urgency
    "standard": {"label": "Standard queue", "mult": 1.0},
    "rush": {"label": "Rush — priority queue", "mult": 1.3},
}


def estimate(answers: dict, tier_key: str) -> dict:
    """Derive the quote from the interview answers + chosen tier."""
    t = TIERS[tier_key]
    wt = SCOPE[answers["work"]]["base"]
    surface = SCOPE[answers["surface"]]["mult"]
    gate = SCOPE[answers["gate"]]["mult"]
    rush = SCOPE[answers["rush"]]["mult"]
    scoped = wt * surface * gate * rush
    tokens = scoped * t["token_mult"]
    agent_cost = tokens / 1000 * t["per_1k"] * t["reviews"]
    price = round(agent_cost * t["margin"] + 49, 2)
    return {
        "tier": t["label"], "model": t["model"], "reviews": t["reviews"],
        "scoped_tokens": int(scoped), "est_tokens": int(tokens),
        "est_agent_cost_usd": round(agent_cost, 2), "price_usd": price,
        "work_label": SCOPE[answers["work"]]["label"],
        "surface_label": SCOPE[answers["surface"]]["label"],
        "gate_label": SCOPE[answers["gate"]]["label"],
        "rush_label": SCOPE[answers["rush"]]["label"],
    }

app = Flask(__name__)


def fp_get(path: str):
    req = urllib.request.Request(f"{FP_HOST}{path}", headers={"x-api-key": FP_KEY, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def fp_post(path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{FP_HOST}{path}", data=data,
                                 headers={"x-api-key": FP_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


@app.get("/")
def index():
    return send_file("index.html")


@app.get("/cards")
def cards():
    return send_file("cards.html")


@app.get("/api/quote")
def quote():
    tier = request.args.get("tier", "mid")
    if tier not in TIERS:
        return jsonify({"error": "unknown tier"}), 400
    answers = {
        "work": request.args.get("work", "feature"),
        "surface": request.args.get("surface", "both"),
        "gate": request.args.get("gate", "no_gate"),
        "rush": request.args.get("rush", "standard"),
    }
    if any(a not in SCOPE for a in answers.values()):
        return jsonify({"error": "invalid scope answer"}), 400
    return jsonify(estimate(answers, tier))


@app.get("/api/credits")
def credits():
    try:
        w = fp_get(f"/v1/wallets/{WALLET_ID}")
        return jsonify({"balance": float(w.get("credit_balance", 0)), "currency": w.get("currency", "usd")})
    except Exception as e:
        return jsonify({"error": str(e)[:100]}), 502


@app.post("/api/order")
def order():
    brief = request.json.get("brief", "").strip()
    tier = request.json.get("tier", "mid")
    answers = {
        "work": request.json.get("work", "feature"),
        "surface": request.json.get("surface", "both"),
        "gate": request.json.get("gate", "no_gate"),
        "rush": request.json.get("rush", "standard"),
    }
    if not brief or tier not in TIERS or any(a not in SCOPE for a in answers.values()):
        return jsonify({"error": "brief, scope answers and valid tier required"}), 400
    est = estimate(answers, tier)
    price = est["price_usd"]

    # Credit gate: wallet must have at least the quote price
    w = fp_get(f"/v1/wallets/{WALLET_ID}")
    balance = float(w.get("credit_balance", 0))
    if balance < price:
        return jsonify({"error": "insufficient credits", "balance": balance, "needed": price,
                        "top_up_at": "https://us.flexprice.io"}), 402

    # Meter the order intake
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fp_post("/v1/events", {"event_name": "feature_shipped", "external_customer_id": CUSTOMER,
                           "properties": {"order": "new", "tier": tier, "stage": "intake",
                                          "price_usd": price, "scoped_tokens": est["scoped_tokens"]},
                           "timestamp": ts})

    # Submit into the crew room as Planner — the interview answers ride along
    msg = (f"Storefront order ({est['tier']} tier): {brief}\n"
           f"Scoping from the intake interview: {est['work_label']}; {est['surface_label']}; "
           f"auth/payments: {est['gate_label']}; {est['rush_label']}.\n"
           f"Quote: ${price} — est {est['est_tokens']:,} agent tokens "
           f"({est['scoped_tokens']:,} scoped × tier), {est['reviews']} review passes, {est['model']}.\n"
           f"@patrick/scout process this order.")
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(msg)
        body_path = f.name
    r = subprocess.run(["band", "send", ROOM_ID, "--body-file", body_path,
                        "--as", "patrick/planner", "--session", "lexis-planner"],
                       capture_output=True, text=True,
                       env={**os.environ, "PATH": "/usr/local/bin:/usr/bin:/bin"})
    os.unlink(body_path)
    if r.returncode != 0:
        return jsonify({"error": f"band send failed: {r.stderr[:200]}"}), 502
    return jsonify({"ok": True, "tier": est["tier"], "price_usd": price, "brief": brief,
                     "scope": f"{est['work_label']}, {est['surface_label']}, {est['rush_label'].lower()}"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
