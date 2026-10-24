import os

import uvicorn
from fastapi import FastAPI

from agent1 import agent1
from models import CompareRequest

app = FastAPI(title="Grocery Compare")


@app.get("/")
def health():
    return {"ok": True}


@app.post("/compare")
async def compare(req: CompareRequest):
    results = await agent1(req.items, req.location)
    # Rank: stores with no error first, then fewest missing items, then cheapest.
    ranked = sorted(results, key=lambda r: (r.error is not None, len(r.missing), r.subtotal))
    return {"results": [r.model_dump() for r in ranked]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
