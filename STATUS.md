# Grocery Compare — build status

_Last updated: 2026-10-24_

## Done ✅

- **Backend** — full FastAPI app in this folder (`main.py`, `agent1.py`, `matcher.py`,
  `adapters/zepto.py`, `adapters/instamart.py`, `models.py`, `cache.py`). Passes offline
  tests (health, `/compare` flow, ranking, agent-result parser).
- **AgenticOrg agent** — "Grocery Price Matcher" created in **shadow mode**.
  - Agent ID: `21b417e7-76fa-4e20-ae11-651a37c5fdc5`
  - Domain: ops · Model: openai gpt-5.6-luna · Confidence floor 50% · HITL off · retries 1 · **no tools**
  - Validated with both guide tests. Test 2 (prompt-injection + empty candidates) output:
    `{"platform":"zepto","matches":[{"id":"i2","sku_id":"e12","confidence":0.95},{"id":"i3","sku_id":null,"confidence":0}]}`
    → ignored the injection, returned null for the no-match item. Cost ~$0.0004/run.
  - Confirmed response shape is `data.output.matches` — the backend parser handles it.

## Blocked — needs you / Pine Labs mentors ⛔

1. **A working API key.** The emailed key `ao_sk_…3b1239` is rejected (HTTP 401) on every
   agent endpoint. Your account role is **developer**, and creating API keys needs an
   **admin** scope (`agenticorg:admin`) — so neither you nor I can mint one from this login.
   → Ask a Pine Labs/Airtribe admin (mentor lounge) to **issue a fresh `ao_sk_` key** or
   **grant your account admin**. Put the key in `.env` as `AGENTICORG_API_KEY`.
2. **Apify token** (for Zepto search). apify.com → Settings → Integrations → API token.
   Put it in `.env` as `APIFY_TOKEN`.

## Remaining steps (once unblocked)

1. Fill `AGENTICORG_API_KEY` and `APIFY_TOKEN` in `.env`.
2. Test the key: `GET /api/v1/agents` with `Authorization: Bearer <key>` should return 200.
3. Run the backend locally (Python 3.11) and hit `/compare` (see `README.md`).
4. Push to GitHub, deploy on Render (build/start commands in `README.md`), add the same env vars.
5. (Optional) Turn on Swiggy Instamart: set `SWIGGY_TOKEN`, run `tools/list_swiggy_tools.py`,
   fill `SEARCH_TOOL` in `adapters/instamart.py`, set `ENABLE_INSTAMART=true`.

## UPDATE 2026-10-24 — end-to-end working ✅

The emailed key was NOT dead — it works on the `/run` endpoint (the one the backend uses);
only the `/agents` list endpoint rejects it. Full `/compare` flow verified live:
real Zepto search (Apify) → live agent match → totals → ranking. Example: milk ₹22×2 +
bread ₹52 = ₹96, "unicorn cheese" correctly null. matcher.py + zepto.py both pass against
the real services. Remaining for MVP v1: push to GitHub + deploy on Render.

## DEPLOYED 2026-10-24 ✅ LIVE

- GitHub: https://github.com/apk2001/grocery-compare (private)
- Render: https://grocery-compare-wdzz.onrender.com  (Singapore, free tier)
  - `GET /` → {"ok":true};  `GET /docs` → Swagger UI
  - `POST /compare` verified live: Aavin milk ₹22×2 = ₹44, real Zepto search + live agent.
- Note: free instance sleeps after ~15 min idle; first request then takes ~50s to wake.

## SECOND AGENT 2026-10-24 ✅ LIVE — WhatsApp-style chat app

- Same Render URL: https://grocery-compare-wdzz.onrender.com/  (chat UI at /)
- Flow: greet → grocery list → live Zepto search + AgenticOrg match → per-store
  comparison with cheapest marked → tap a store → cart with per-item "Open in
  store" deep links + pay button.
- Backend: chat.py state machine over the existing compare engine. parse_list is
  isolated as a hook for a future AgenticOrg parse agent.
- Verified live in production (commit 7425a18).
- Honest limit: web can't auto-fill a Zepto/Instamart cart or trigger their
  payment from a redirect — that needs the Playwright-on-own-account step.
  The app hands over deep links instead.

## SECOND STORE 2026-10-24 — Blinkit (graceful)

- Added adapters/blinkit.py (Apify solidcode~blinkit-scraper), wired into agent1
  (ENABLE_BLINKIT=true, reuses APIFY_TOKEN). Chat shows Zepto vs Blinkit with
  honest "best pick" + apples-to-apples savings only for equal coverage.
- CAVEAT: every Blinkit/Instamart Apify actor is PAY_PER_EVENT; the free Apify
  plan only partially allows them (random 402s), so Blinkit is intermittent on
  free. The app hides a store that returns nothing, so it never looks broken.
  Reliable 2-store comparison needs Apify billing added. Zepto actor is free.
