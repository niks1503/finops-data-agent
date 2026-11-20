"""REST API: POST /ask {"question": "..."} -> answer, SQL, rows and run metrics."""
from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from finops_agent.agent import FinOpsAgent

app = FastAPI(title="FinOps Data Agent", version="1.0.0")


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, examples=["Which account spent the most last month?"])


@lru_cache(maxsize=1)
def get_agent() -> FinOpsAgent:
    return FinOpsAgent()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask")
def ask(q: Question) -> dict:
    try:
        agent = get_agent()
    except RuntimeError as exc:  # e.g. missing GEMINI_API_KEY
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return agent.ask(q.question).to_dict()
