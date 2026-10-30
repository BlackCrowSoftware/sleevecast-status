#!/usr/bin/env python3
"""Checks Sleevecast's public endpoints and keeps data.json: each check's current state, when it last changed and
hourly uptime for 90 days. Run every 5 minutes by GitHub Actions; the workflow commits only when this script says
so (a state changed, or a new hour began), which keeps the history small. Prints COMMIT when data.json should be
committed."""
import base64
import datetime as dt
import http.client
import json
import os
import ssl
import time

CHECKS = [
    {"id": "app", "name": "Console", "url": "https://app.sleevecast.com/", "expect": [200, 302]},
    {"id": "api", "name": "API", "url": "https://api.sleevecast.com/healthz", "expect": [200]},
    {"id": "connect", "name": "Dock connections", "url": "https://connect.sleevecast.com/", "websocket": True},
    {"id": "auth", "name": "Sign-in", "url": "https://auth.sleevecast.com/realms/sleevecast/.well-known/openid-configuration", "expect": [200]},
    {"id": "get", "name": "Dock installers", "url": "https://get.sleevecast.com/dock.sh", "expect": [200]},
    {"id": "site", "name": "Website and docs", "url": "https://sleevecast.com/", "expect": [200]},
]
HOURS = 90 * 24


def probe(check: dict) -> tuple[bool, str, int]:
    host = check["url"].split("/")[2]
    path = "/" + check["url"].split("/", 3)[3] if check["url"].count("/") > 2 else "/"
    started = time.monotonic()
    try:
        conn = http.client.HTTPSConnection(host, 443, timeout=15, context=ssl.create_default_context())
        headers = {"User-Agent": "sleevecast-status/1"}
        if check.get("websocket"):
            headers.update({"Connection": "Upgrade", "Upgrade": "websocket", "Sec-WebSocket-Version": "13",
                            "Sec-WebSocket-Key": base64.b64encode(os.urandom(16)).decode()})
        conn.request("GET", path, headers=headers)
        status = conn.getresponse().status
        conn.close()
        ms = int((time.monotonic() - started) * 1000)
        ok = status == 101 if check.get("websocket") else status in check["expect"]
        return ok, f"HTTP {status}", ms
    except Exception as e:  # network errors are the outage we want to see
        return False, type(e).__name__, int((time.monotonic() - started) * 1000)


def main() -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    hour = now.strftime("%Y-%m-%dT%H:00Z")
    try:
        data = json.load(open("data.json"))
    except FileNotFoundError:
        data = {"checks": {}}
    commit = data.get("hour") != hour
    for c in CHECKS:
        ok, detail, ms = probe(c)
        if not ok:  # one retry before calling it down
            time.sleep(10)
            ok, detail, ms = probe(c)
        state = data["checks"].setdefault(c["id"], {"history": []})
        state["name"] = c["name"]
        new_status = "up" if ok else "down"
        if state.get("status") != new_status:
            state["status"], state["since"] = new_status, now.isoformat()
            commit = True
        state["detail"], state["ms"] = detail, ms
        hist = state["history"]
        if not hist or hist[-1]["hour"] != hour:
            hist.append({"hour": hour, "up": 0, "total": 0})
        hist[-1]["total"] += 1
        hist[-1]["up"] += 1 if ok else 0
        del hist[:-HOURS]
    data["hour"], data["checked"] = hour, now.isoformat()
    json.dump(data, open("data.json", "w"), indent=1)
    print("COMMIT" if commit else "no change")


if __name__ == "__main__":
    main()
