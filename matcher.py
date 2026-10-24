"""Calls the AgenticOrg agent to pick the best product per grocery item.

Uses the documented REST endpoint directly (POST /api/v1/agents/{id}/run) so it
runs on any Python 3.9+ without the agenticorg SDK. The agent only *chooses*
products from candidates we pass in; it never sees or computes prices.
"""
import json
import os

import httpx

BASE = os.environ.get("AGENTICORG_BASE_URL", "https://agenticorg.hackathon.pinelabs.com").rstrip("/")
AGENT_ID = os.environ["AGENT_ID"]
API_KEY = os.environ["AGENTICORG_API_KEY"]
RUN_URL = f"{BASE}/api/v1/agents/{AGENT_ID}/run"


def _extract_matches(obj, depth=0):
    """Dig through the response envelope for our {"matches": [...]} payload.

    The exact result shape is not documented, so we search common wrapper keys
    and parse JSON that may arrive as a (possibly fenced) string.
    """
    if depth > 6:
        return None
    if isinstance(obj, dict):
        if isinstance(obj.get("matches"), list):
            return obj
        for key in ("output", "result", "response", "data", "outputs", "content", "message", "text"):
            if key in obj:
                found = _extract_matches(obj[key], depth + 1)
                if found:
                    return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = _extract_matches(item, depth + 1)
            if found:
                return found
        return None
    if isinstance(obj, str):
        text = obj.strip()
        if text.startswith("```"):
            text = text[3:]
            if "\n" in text:
                text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0].strip()
        try:
            return _extract_matches(json.loads(text), depth + 1)
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def match(items, candidates_by_item, platform):
    payload = {
        "platform": platform,
        "items": [
            {
                "item": i.model_dump(),
                "candidates": [c.model_dump() for c in candidates_by_item.get(i.id, [])],
            }
            for i in items
        ],
    }
    # Send the payload both as a structured input and as a `task` string, since
    # chat-style agents read `task` while others read structured inputs.
    body = {
        "action": "process",
        "inputs": {"task": json.dumps(payload), **payload},
        "context": {},
    }
    with httpx.Client(timeout=120) as client:
        r = client.post(RUN_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json=body)
    r.raise_for_status()
    data = r.json()
    print("AGENTICORG RAW RESULT:", json.dumps(data)[:2000])  # keep for debugging

    status = data.get("status")
    if status and status not in ("completed", "success", "ok"):
        raise ValueError(f"Agent run status={status}: {str(data)[:500]}")

    found = _extract_matches(data)
    if not found:
        raise ValueError(f"Could not find matches in agent result: {str(data)[:500]}")
    return {m["id"]: m for m in found.get("matches", [])}
