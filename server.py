"""CrewKit storefront API.

Endpoints:
  GET  /                 storefront page
  GET  /api/quote?tier=  price quote (agent cost x margin, by tier)
  GET  /api/credits      lexis wallet balance from Flexprice
  POST /api/order        submit feature brief -> Band crew room
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

from flask import Flask, request, jsonify, send_file

FP_HOST = "https://us.api.flexprice.io"
FP_KEY = os.environ.get("FLEXPRICE_API_KEY", "")
WALLET_ID = "wallet_01M5DD2GD2AJM50FC33ZNZ8SVS"
ROOM_ID = "cc69d7ea-6b1b-4c91-9b01-91cbe7ab385d"
CUSTOMER = "lexis"
FLAT_FEE_USD = 49  # flat studio fee per order, shown as its own ledger line

# Extra places `band` is commonly installed (pipx/uv and Homebrew on Apple Silicon).
EXTRA_PATHS = [os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]


def band_env() -> dict:
    path = os.pathsep.join([os.environ.get("PATH", "")] + EXTRA_PATHS)
    return {**os.environ, "PATH": path}


def find_band():
    """Locate the band CLI: $BAND_BIN, then PATH plus common install dirs."""
    explicit = os.environ.get("BAND_BIN")
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    return shutil.which("band", path=band_env()["PATH"])

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
    price = round(agent_cost * t["margin"] + FLAT_FEE_USD, 2)
    return {
        "tier": t["label"], "model": t["model"], "reviews": t["reviews"],
        "scoped_tokens": int(scoped), "est_tokens": int(tokens),
        "est_agent_cost_usd": round(agent_cost, 2), "flat_fee_usd": FLAT_FEE_USD, "price_usd": price,
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
    data = request.get_json(silent=True) or {}
    brief = str(data.get("brief", "")).strip()
    tier = data.get("tier", "mid")
    answers = {
        "work": data.get("work", "feature"),
        "surface": data.get("surface", "both"),
        "gate": data.get("gate", "no_gate"),
        "rush": data.get("rush", "standard"),
    }
    if not brief or tier not in TIERS or any(a not in SCOPE for a in answers.values()):
        return jsonify({"error": "brief, scope answers and valid tier required"}), 400
    est = estimate(answers, tier)
    price = est["price_usd"]

    # Credit gate: wallet must have at least the quote price
    if not FP_KEY:
        return jsonify({"error": "billing is not configured (FLEXPRICE_API_KEY missing)"}), 503
    try:
        w = fp_get(f"/v1/wallets/{WALLET_ID}")
        balance = float(w.get("credit_balance", 0))
    except Exception as e:
        app.logger.error("flexprice wallet check failed: %s", e)
        return jsonify({"error": "could not check credits with Flexprice, please retry"}), 502
    if balance < price:
        return jsonify({"error": "insufficient credits", "balance": balance, "needed": price,
                        "top_up_at": "https://us.flexprice.io"}), 402

    band = find_band()
    if not band:
        return jsonify({"error": "crew room unavailable: band CLI not found (set BAND_BIN)"}), 503

    # Meter the order intake
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        fp_post("/v1/events", {"event_name": "feature_shipped", "external_customer_id": CUSTOMER,
                               "properties": {"order": "new", "tier": tier, "stage": "intake",
                                              "price_usd": price, "scoped_tokens": est["scoped_tokens"]},
                               "timestamp": ts})
    except Exception as e:
        app.logger.error("flexprice event post failed: %s", e)
        return jsonify({"error": "could not meter the order with Flexprice, please retry"}), 502

    # Submit into the crew room as Planner — the interview answers ride along
    msg = (f"Storefront order ({est['tier']} tier): {brief}\n"
           f"Scoping from the intake interview: {est['work_label']}; {est['surface_label']}; "
           f"auth/payments: {est['gate_label']}; {est['rush_label']}.\n"
           f"Quote: ${price} (incl. ${FLAT_FEE_USD} flat studio fee) — est {est['est_tokens']:,} agent tokens "
           f"({est['scoped_tokens']:,} scoped × tier), {est['reviews']} review passes, {est['model']}.\n"
           f"@patrick/scout process this order.")
    body_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(msg)
            body_path = f.name
        r = subprocess.run([band, "send", ROOM_ID, "--body-file", body_path,
                            "--as", "patrick/planner", "--session", "lexis-planner"],
                           capture_output=True, text=True, timeout=60, env=band_env())
    except Exception as e:
        app.logger.error("band send crashed: %s", e)
        return jsonify({"error": "could not reach the crew room, please retry"}), 502
    finally:
        if body_path and os.path.exists(body_path):
            os.unlink(body_path)
    if r.returncode != 0:
        app.logger.error("band send failed: %s", r.stderr[:500])
        return jsonify({"error": "crew room rejected the order (band send failed)",
                        "detail": r.stderr.strip()[:200]}), 502
    return jsonify({"ok": True, "tier": est["tier"], "price_usd": price, "brief": brief,
                    "scope": f"{est['work_label']}, {est['surface_label']}, {est['rush_label'].lower()}"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
