"""Lightweight in-memory usage tracking.

Counts unique visitors (by session id) and when the app is used. This lives in
memory only, so it resets when the app restarts, sleeps (free tier) or redeploys.
For durable, cumulative numbers this would need a database.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from html import escape

IST = timezone(timedelta(hours=5, minutes=30))
STARTED = time.time()

# session_id -> {"first": ts, "last": ts, "messages": int}
SESSIONS: dict[str, dict] = {}
# bounded event log of (ts, session_id, kind)
EVENTS: list[tuple[float, str, str]] = []
MAX_EVENTS = 10000


def record(session_id: str, kind: str) -> None:
    """kind is 'visit' (page load / __start__) or 'message' (a real user message)."""
    if not session_id:
        return
    now = time.time()
    s = SESSIONS.get(session_id)
    if s is None:
        SESSIONS[session_id] = s = {"first": now, "last": now, "messages": 0}
    s["last"] = now
    if kind == "message":
        s["messages"] += 1
    EVENTS.append((now, session_id, kind))
    if len(EVENTS) > MAX_EVENTS:
        del EVENTS[: len(EVENTS) - MAX_EVENTS]


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts, IST).strftime("%d %b, %H:%M")


def stats() -> dict:
    now = time.time()
    people = len(SESSIONS)
    visits = sum(1 for _, _, k in EVENTS if k == "visit")
    messages = sum(s["messages"] for s in SESSIONS.values())
    active_1h = sum(1 for s in SESSIONS.values() if now - s["last"] <= 3600)
    active_24h = sum(1 for s in SESSIONS.values() if now - s["last"] <= 86400)

    # Hourly activity for the last 24 hours (events per hour, IST-labelled).
    buckets: list[dict] = []
    for h in range(23, -1, -1):
        start = now - (h + 1) * 3600
        end = now - h * 3600
        count = sum(1 for ts, _, _ in EVENTS if start < ts <= end)
        label = datetime.fromtimestamp(end, IST).strftime("%H:00")
        buckets.append({"label": label, "count": count})

    recent = sorted(SESSIONS.items(), key=lambda kv: kv[1]["last"], reverse=True)[:12]
    recent_rows = [
        {
            "id": sid.replace("s_", "")[:8],
            "first": _fmt(s["first"]),
            "last": _fmt(s["last"]),
            "messages": s["messages"],
        }
        for sid, s in recent
    ]

    return {
        "people": people,
        "visits": visits,
        "messages": messages,
        "active_1h": active_1h,
        "active_24h": active_24h,
        "since": _fmt(STARTED),
        "hourly": buckets,
        "recent": recent_rows,
    }


def render_html() -> str:
    d = stats()
    peak = max((b["count"] for b in d["hourly"]), default=0) or 1
    bars = "".join(
        f'<div class="bar"><div class="fill" style="height:{int(b["count"] / peak * 100)}%" '
        f'title="{b["count"]} events"></div><span>{escape(b["label"])}</span></div>'
        for b in d["hourly"]
    )
    rows = "".join(
        f"<tr><td>…{escape(r['id'])}</td><td>{escape(r['first'])}</td>"
        f"<td>{escape(r['last'])}</td><td>{r['messages']}</td></tr>"
        for r in d["recent"]
    ) or '<tr><td colspan="4" class="empty">No visitors yet.</td></tr>'

    def card(value, label):
        return f'<div class="card"><div class="num">{value}</div><div class="lbl">{label}</div></div>'

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>Grocery Compare — Usage</title>
<style>
  :root {{ --teal:#075e54; --green:#25d366; --ink:#111b21; --sub:#667781; --bg:#f0f2f5; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
          background:var(--bg); color:var(--ink); }}
  header {{ background:var(--teal); color:#fff; padding:18px 20px; }}
  header h1 {{ margin:0; font-size:19px; }}
  header p {{ margin:4px 0 0; font-size:13px; opacity:.85; }}
  main {{ max-width:860px; margin:0 auto; padding:18px 16px 40px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; }}
  .card {{ background:#fff; border-radius:12px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  .num {{ font-size:30px; font-weight:700; color:var(--teal); }}
  .lbl {{ font-size:12.5px; color:var(--sub); margin-top:2px; }}
  .panel {{ background:#fff; border-radius:12px; padding:16px; margin-top:16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  .panel h2 {{ font-size:14px; margin:0 0 12px; color:var(--ink); }}
  .chart {{ display:flex; align-items:flex-end; gap:3px; height:120px; }}
  .bar {{ flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; }}
  .bar .fill {{ width:70%; min-height:2px; background:var(--green); border-radius:3px 3px 0 0; }}
  .bar span {{ font-size:8.5px; color:var(--sub); margin-top:4px; transform:rotate(-55deg); white-space:nowrap; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th,td {{ text-align:left; padding:8px 6px; border-bottom:1px solid #eef0f1; }}
  th {{ color:var(--sub); font-weight:600; font-size:11.5px; text-transform:uppercase; letter-spacing:.03em; }}
  td.empty {{ color:var(--sub); text-align:center; padding:20px; }}
  .note {{ font-size:12px; color:var(--sub); margin-top:16px; line-height:1.5; }}
</style></head><body>
<header>
  <h1>📊 Grocery Compare — Usage</h1>
  <p>Tracking since {escape(d['since'])} IST · auto-refreshes every 15s</p>
</header>
<main>
  <div class="cards">
    {card(d['people'], 'Unique visitors')}
    {card(d['visits'], 'Total sessions')}
    {card(d['messages'], 'Messages sent')}
    {card(d['active_24h'], 'Active in 24h')}
  </div>
  <div class="panel">
    <h2>Activity — last 24 hours (per hour, IST)</h2>
    <div class="chart">{bars}</div>
  </div>
  <div class="panel">
    <h2>Recent visitors</h2>
    <table>
      <tr><th>Visitor</th><th>First seen</th><th>Last seen</th><th>Msgs</th></tr>
      {rows}
    </table>
  </div>
  <p class="note">⚠️ In-memory counts — these reset when the app restarts, sleeps
  (free tier, after ~15 min idle) or redeploys. For durable cumulative numbers,
  switch to a database. Visitors are counted by an anonymous per-browser id (no personal data).</p>
</main></body></html>"""
