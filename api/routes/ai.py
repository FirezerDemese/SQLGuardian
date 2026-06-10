"""
SQLGuardian - /ai routes
AI-powered incident analysis and remediation using Groq LLM.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.ai_engine import explain_snapshot, suggest_remediation, answer_nl_question
from core.scheduler import get_cached_snapshot
from core.monitor import get_full_snapshot

router = APIRouter()


class ExplainRequest(BaseModel):
    fresh: bool = False


class SuggestRequest(BaseModel):
    issue_focus: Optional[str] = None
    fresh: bool = False


class AskRequest(BaseModel):
    question: str


def _get_snapshot(fresh: bool) -> dict:
    """Get cached or fresh snapshot."""
    if fresh:
        return get_full_snapshot()
    snapshot = get_cached_snapshot()
    if not snapshot:
        return get_full_snapshot()
    return snapshot


@router.post("/explain")
async def explain(req: ExplainRequest = ExplainRequest()):
    """
    AI explains the current server health in plain English.
    Returns a DBA summary, management summary, top issues, and root cause.
    """
    snapshot = _get_snapshot(req.fresh)
    if "error" in snapshot:
        raise HTTPException(status_code=503, detail="Could not retrieve snapshot")
    return await explain_snapshot(snapshot)


@router.post("/suggest")
async def suggest(req: SuggestRequest = SuggestRequest()):
    """
    AI generates T-SQL remediation scripts for current issues.
    Optionally focus on a specific issue (e.g. 'blocking', 'disk space', 'failed jobs').
    """
    snapshot = _get_snapshot(req.fresh)
    if "error" in snapshot:
        raise HTTPException(status_code=503, detail="Could not retrieve snapshot")
    return await suggest_remediation(snapshot, req.issue_focus)


@router.post("/ask")
async def ask(req: AskRequest):
    """
    Natural language Q&A grounded in real DMV data.
    Ask anything: 'Why is my server slow?', 'Which database is the biggest?', etc.
    """
    if not req.question or len(req.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question too short")
    snapshot = _get_snapshot(fresh=False)
    return await answer_nl_question(req.question, snapshot)