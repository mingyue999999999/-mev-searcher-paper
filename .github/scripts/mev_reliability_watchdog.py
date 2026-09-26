import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

THRESHOLD_MINUTES = 55.0
POLL_SECONDS = 5
RUN_TIMEOUT_SECONDS = 900

token = os.environ["GITHUB_TOKEN"]
repo = os.environ["GITHUB_REPOSITORY"]

def api_request(url, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    retryable_statuses = {429, 502, 503, 504}

    for attempt in range(4):
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if exc.code not in retryable_statuses or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise

        time.sleep(2 ** attempt)

def runs():
    url = f"https://api.github.com/repos/{repo}/actions/workflows/mev-searcher.yml/runs?per_page=20"
    return api_request(url).get("workflow_runs", [])

def parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

current = runs()
active = any(r.get("status") in {"queued", "in_progress", "waiting", "requested", "pending"} for r in current)

freshness = None
for r in current:
    if r.get("status") == "completed" and r.get("conclusion") == "success":
        freshness = parse_ts(r.get("updated_at") or r.get("run_started_at") or r.get("created_at"))
        break

now = datetime.now(timezone.utc)
age = float("inf") if freshness is None else max(0.0, (now - freshness).total_seconds() / 60.0)
stale = age > THRESHOLD_MINUTES

print(json.dumps({
    "now": now.isoformat(),
    "age_minutes": None if age == float("inf") else round(age, 1),
    "active": active,
    "stale": stale,
}, ensure_ascii=False))

if not stale or active:
    raise SystemExit(0)

before = {r["id"] for r in current}
started = datetime.now(timezone.utc)
url = f"https://api.github.com/repos/{repo}/actions/workflows/mev-searcher.yml/dispatches"
api_request(url, method="POST", payload={"ref": "main"})
print("dispatched MEV recovery")

deadline = time.time() + RUN_TIMEOUT_SECONDS
run_id = None
while time.time() < deadline:
    fresh = [
        r for r in runs()
        if r.get("id") not in before
        and r.get("event") == "workflow_dispatch"
        and parse_ts(r.get("created_at")) is not None
        and parse_ts(r.get("created_at")) >= started
    ]
    if fresh:
        fresh.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        run = fresh[0]
        run_id = run["id"]
        if run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise SystemExit(f"MEV recovery run {run_id} ended as {run.get('conclusion')}")
            print(f"MEV recovered successfully in run {run_id}")
            raise SystemExit(0)
    time.sleep(POLL_SECONDS)

raise SystemExit(f"MEV recovery timed out; run_id={run_id}")
