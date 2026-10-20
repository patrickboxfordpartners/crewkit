#!/usr/bin/env python3
"""Snyk security gate for the CrewKit security-reviewer agent.

Usage:
  python scripts/snyk_gate.py <target-repo-path> [--item "<work item>"] [--severity high]
                              [--no-memory] [--no-cognify]

What it does (in order):
  1. Recalls earlier security findings from Cognee (crewkit-memory, dataset "studio").
  2. Runs `snyk test --json` (dependencies) and `snyk code test --json` (SAST) on the target.
  3. Summarizes high/critical findings as Markdown the agent can post to the Band room.
  4. Flags findings that RECUR (already in memory) so the crew sees repeat mistakes.
  5. Stores each new finding in Cognee via `memory.py remember security-reviewer finding ...`.
  6. Exits 1 if any finding at/above --severity exists (the work item stays BLOCKED), 0 if clean,
     2 if Snyk itself could not run.

Env: SNYK_TOKEN (or `snyk auth`), CREWKIT_MEMORY_DIR (default ../crewkit-memory),
     MEMORY_PYTHON (default: <memory dir>/.venv/bin/python, else `uv run python`).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

SEV_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SARIF_LEVEL = {"error": "high", "warning": "medium", "note": "low"}
HERE = os.path.dirname(os.path.abspath(__file__))


def memory_cmd():
    mdir = os.path.abspath(os.environ.get("CREWKIT_MEMORY_DIR", os.path.join(HERE, "..", "..", "crewkit-memory")))
    script = os.path.join(mdir, "memory.py")
    if not os.path.isfile(script):
        return None, mdir
    py = os.environ.get("MEMORY_PYTHON") or os.path.join(mdir, ".venv", "bin", "python")
    if os.path.isfile(py):
        return [py, script], mdir
    if shutil.which("uv"):
        return ["uv", "run", "--project", mdir, "python", script], mdir
    return [sys.executable, script], mdir


def run_memory(args, timeout=300):
    cmd, mdir = memory_cmd()
    if not cmd:
        return None
    try:
        r = subprocess.run(cmd + args, cwd=mdir, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def run_snyk(args, target):
    snyk = shutil.which("snyk")
    if not snyk:
        raise RuntimeError("snyk CLI not found (npm i -g snyk && snyk auth)")
    r = subprocess.run([snyk] + args + ["--json"], cwd=target, capture_output=True, text=True, timeout=900)
    # Snyk exit codes: 0 clean, 1 issues found, 2/3 errors
    if r.returncode not in (0, 1):
        try:
            msg = json.loads(r.stdout).get("error") or r.stderr
        except Exception:
            msg = (r.stderr or r.stdout)[:300]
        raise RuntimeError(f"snyk {' '.join(args)} failed: {str(msg).strip()[:300]}")
    try:
        return json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        raise RuntimeError(f"snyk {' '.join(args)} returned non-JSON output")


def parse_deps(data):
    out = []
    for proj in data if isinstance(data, list) else [data]:
        seen = set()
        for v in proj.get("vulnerabilities", []):
            key = (v.get("id"), v.get("packageName"))
            if key in seen:
                continue
            seen.add(key)
            fix = ", ".join(v.get("fixedIn") or []) or "no fix available"
            out.append({"kind": "dependency", "severity": v.get("severity", "low"), "id": v.get("id", "?"),
                        "title": v.get("title", "?"), "where": f"{v.get('packageName')}@{v.get('version')}",
                        "fix": f"upgrade to {fix}"})
    return out


def parse_code(data):
    out = []
    for run in data.get("runs", []):
        for res in run.get("results", []):
            loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
            path = loc.get("artifactLocation", {}).get("uri", "?")
            line = loc.get("region", {}).get("startLine", "?")
            out.append({"kind": "code", "severity": SARIF_LEVEL.get(res.get("level"), "low"),
                        "id": res.get("ruleId", "?"), "title": res.get("message", {}).get("text", "?")[:160],
                        "where": f"{path}:{line}", "fix": "see Snyk Code rule guidance"})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--item", default="", help="Band work item this scan gates")
    ap.add_argument("--severity", default="high", choices=list(SEV_ORDER))
    ap.add_argument("--no-memory", action="store_true", help="skip Cognee recall/remember")
    ap.add_argument("--no-cognify", action="store_true", help="store findings without rebuilding the graph each time")
    a = ap.parse_args()
    target = os.path.abspath(a.target)
    repo = os.path.basename(target)
    item = f" for work item '{a.item}'" if a.item else ""

    print(f"## Snyk security gate: `{repo}`{item}\n")

    past = ""
    if not a.no_memory:
        past = run_memory(["recall", f"What security findings has Snyk reported before for {repo}?"]) or ""
        print("### Recalled from studio memory (Cognee)")
        print((past or "_no earlier security findings recalled_") + "\n")

    try:
        findings = parse_deps(run_snyk(["test"], target)) + parse_code(run_snyk(["code", "test"], target))
    except Exception as e:
        print(f"**GATE ERROR**: {e}\nWork item stays BLOCKED until the scan can run.")
        sys.exit(2)

    floor = SEV_ORDER[a.severity]
    blocking = [f for f in findings if SEV_ORDER.get(f["severity"], 0) >= floor]
    blocking.sort(key=lambda f: -SEV_ORDER.get(f["severity"], 0))
    past_l = past.lower()
    recurring = [f for f in blocking if past_l and (f["id"].lower() in past_l or f["where"].split("@")[0].lower() in past_l)]

    print(f"### Findings at or above {a.severity}: {len(blocking)} (of {len(findings)} total)")
    for f in blocking:
        tag = " **(RECURRING)**" if f in recurring else ""
        print(f"- [{f['severity'].upper()}] {f['kind']} `{f['id']}`: {f['title']} @ `{f['where']}`, fix: {f['fix']}{tag}")
    if recurring:
        print(f"\n**{len(recurring)} recurring issue(s)**: the crew has shipped these before. Builder must fix at the root.")

    if not a.no_memory:
        stored = 0
        for i, f in enumerate(blocking):
            last = i == len(blocking) - 1
            args = ["remember", "security-reviewer", "finding",
                    f"[security] Snyk {f['kind']} {f['severity']} in {repo}: {f['id']} {f['title']} at {f['where']}; {f['fix']}"
                    + (" (recurring)" if f in recurring else "")]
            if a.no_cognify or not last:
                args.insert(1, "--no-cognify")  # build the graph once, after the last finding
            if run_memory(args) is not None:
                stored += 1
        print(f"\nStored {stored}/{len(blocking)} finding(s) in Cognee dataset `studio`.")

    if blocking:
        print(f"\n**VERDICT: BLOCKED**. Work item{item} cannot move to Done until these are fixed and the gate re-runs clean.")
        sys.exit(1)
    print("\n**VERDICT: PASS**. No high/critical findings. Work item may move to Done.")


if __name__ == "__main__":
    main()
