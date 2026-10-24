import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent1 import agent1
from chat import handle
from models import CompareRequest

app = FastAPI(title="Grocery Compare")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/compare")
async def compare(req: CompareRequest):
    results = await agent1(req.items, req.location)
    # Rank: stores with no error first, then fewest missing items, then cheapest.
    ranked = sorted(results, key=lambda r: (r.error is not None, len(r.missing), r.subtotal))
    return {"results": [r.model_dump() for r in ranked]}


class ChatRequest(BaseModel):
    session_id: str
    text: str = ""


@app.post("/chat")
async def chat(req: ChatRequest):
    return await handle(req.session_id, req.text)


# Chat UI (served last so API routes above take precedence)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
