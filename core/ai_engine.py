"""
SQLGuardian - AI Engine
Groq-powered incident analysis. Takes raw DMV snapshot data and returns:
- Plain English explanation of what's wrong
- Root cause analysis
- Specific T-SQL remediation scripts

This is the feature that makes SQLGuardian a portfolio piece for Mercor/Outlier.
"""

import json
from datetime import datetime
from typing import Optional
from loguru import logger

from core.llm import complete_json, model_id


# ---------------------------------------------------------------------------
# System prompt - sets the AI's persona as a senior DBA
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert Senior SQL Server DBA with 15+ years of experience 
in enterprise environments. You specialize in performance tuning, incident response, 
and production troubleshooting.

You will receive real-time health data from SQL Server DMV queries. Your job is to:
1. Explain what is happening in plain English (for both DBAs and non-technical managers)
2. Identify the root cause
3. Provide specific, actionable T-SQL remediation scripts

Always be direct and specific. Never give generic advice. Base everything on the 
actual data provided. Format your response as valid JSON only - no markdown, no 
preamble, just the JSON object.
"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_explain_prompt(snapshot: dict) -> str:
    """Build the prompt for incident explanation."""
    severity = snapshot.get("overall_severity", "unknown")
    server = snapshot.get("server_health", {})
    blocking = snapshot.get("blocking", {})
    waits = snapshot.get("wait_stats", {})
    jobs = snapshot.get("agent_jobs", {})
    disk = snapshot.get("disk_usage", {})
    databases = snapshot.get("database_status", {})

    return f"""Analyze this SQL Server health snapshot and explain what is happening.

OVERALL SEVERITY: {severity.upper()}
SNAPSHOT TIME: {snapshot.get("snapshot_time")}

SERVER HEALTH:
{json.dumps(server, indent=2, default=str)}

BLOCKING:
{json.dumps(blocking, indent=2, default=str)}

TOP WAIT STATS:
{json.dumps(waits.get("top_waits", [])[:5], indent=2, default=str)}

AGENT JOBS:
{json.dumps({"failed_count": jobs.get("failed_count"), "failed_jobs": jobs.get("failed_jobs", [])}, indent=2, default=str)}

DISK USAGE:
{json.dumps(disk, indent=2, default=str)}

DATABASE STATUS:
{json.dumps({"databases_missing_backup": databases.get("databases_missing_backup_names", [])}, indent=2, default=str)}

Respond with ONLY this JSON structure (no markdown, no extra text):
{{
  "severity_label": "one of: healthy / warning / critical",
  "headline": "One sentence summary of the most critical issue right now",
  "dba_summary": "2-3 sentences explaining what is happening technically",
  "manager_summary": "1-2 sentences in plain English for a non-technical manager",
  "top_issues": [
    {{
      "issue": "Issue name",
      "detail": "Specific detail from the data",
      "impact": "What this means for the database/application",
      "priority": "high / medium / low"
    }}
  ],
  "root_cause": "Most likely root cause based on the data"
}}"""


def _build_remediation_prompt(snapshot: dict, issue_focus: Optional[str] = None) -> str:
    """Build the prompt for T-SQL remediation scripts."""
    blocking = snapshot.get("blocking", {})
    jobs = snapshot.get("agent_jobs", {})
    disk = snapshot.get("disk_usage", {})
    databases = snapshot.get("database_status", {})
    waits = snapshot.get("wait_stats", {})

    focus_text = f"\nFocus specifically on: {issue_focus}" if issue_focus else ""

    blocking_policy = ""
    if blocking.get("head_blocker_count", 0) > 0:
        blocking_policy = """
BLOCKING REMEDIATION POLICY (mandatory whenever blocking sessions are present):
Do NOT default to KILL as the first or only suggestion. Order the "remediations"
array as follows:
1. DIAGNOSE FIRST - a script using DBCC INPUTBUFFER(<session_id>) to re-confirm
   exactly what the head blocker is currently running (the current_sql snapshot
   above may be stale by the time the DBA acts on it). risk_level "safe".
2. IDENTIFY THE OWNER - a script against sys.dm_exec_sessions / sys.dm_exec_connections
   returning login_name, host_name, program_name, and client_net_address for the
   blocking session_id, so the DBA can contact that user or application team
   before taking any destructive action. risk_level "safe".
3. CONSIDER A NON-DESTRUCTIVE FIX - if this looks like a reader blocked on an
   uncommitted writer (shared lock waiting on an exclusive lock), offer enabling
   READ_COMMITTED_SNAPSHOT at the database level, or SET TRANSACTION ISOLATION
   LEVEL READ UNCOMMITTED / WITH (NOLOCK) as a query-level option for the blocked
   session. Explicitly state the tradeoff in the description: this permits dirty
   reads of uncommitted data that may later roll back, so it's only appropriate
   if the user understands and accepts that risk for this query. risk_level "medium".
4. KILL AS LAST RESORT - only after the above, include KILL <session_id>,
   risk_level "high", requires_approval true, and explain in the description
   that it terminates in-flight work and forces a rollback which can itself
   take time on large transactions.
"""

    return f"""Generate specific T-SQL remediation scripts for this SQL Server health snapshot.{focus_text}
{blocking_policy}
BLOCKING SESSIONS:
{json.dumps(blocking.get("blocked_sessions", []), indent=2, default=str)}

HEAD BLOCKERS:
{json.dumps(blocking.get("head_blockers", []), indent=2, default=str)}

FAILED AGENT JOBS:
{json.dumps(jobs.get("failed_jobs", []), indent=2, default=str)}

DISK USAGE:
{json.dumps(disk.get("volumes", []), indent=2, default=str)}

DATABASES MISSING BACKUPS:
{json.dumps(databases.get("databases_missing_backup_names", []), indent=2, default=str)}

TOP WAIT TYPES:
{json.dumps(waits.get("top_waits", [])[:5], indent=2, default=str)}

Generate practical T-SQL scripts to address the issues found. 
Respond with ONLY this JSON structure (no markdown, no extra text):
{{
  "remediations": [
    {{
      "title": "Action title",
      "description": "What this script does and why",
      "risk_level": "safe / low / medium / high",
      "requires_approval": true or false,
      "tsql": "-- The actual T-SQL script here\\nSELECT ...",
      "expected_outcome": "What happens after running this"
    }}
  ],
  "immediate_actions": ["Action 1", "Action 2"],
  "monitoring_followup": "What to watch after applying fixes"
}}"""


def _build_nl_query_prompt(question: str, snapshot: dict) -> str:
    """Build the prompt for natural language questions about the server."""
    server = snapshot.get("server_health", {})
    blocking = snapshot.get("blocking", {})
    waits = snapshot.get("wait_stats", {})
    jobs = snapshot.get("agent_jobs", {})
    disk = snapshot.get("disk_usage", {})
    databases = snapshot.get("database_status", {})

    return f"""A DBA is asking this question about their SQL Server: "{question}"

OVERALL SEVERITY: {snapshot.get("overall_severity", "unknown").upper()}
SNAPSHOT TIME: {snapshot.get("snapshot_time")}

SERVER HEALTH:
{json.dumps({"cpu": server.get("cpu"), "memory": server.get("memory"), "uptime_hours": server.get("uptime_hours")}, indent=2, default=str)}

BLOCKING:
{json.dumps({"blocked_session_count": blocking.get("blocked_session_count"), "max_wait_seconds": blocking.get("max_wait_seconds"), "severity": blocking.get("severity"), "head_blockers": blocking.get("head_blockers", [])}, indent=2, default=str)}

TOP WAIT STATS ({waits.get("mode", "cumulative")}):
{json.dumps(waits.get("top_waits", [])[:8], indent=2, default=str)}

AGENT JOBS:
{json.dumps({"failed_count": jobs.get("failed_count"), "running_count": jobs.get("running_count"), "failed_jobs": jobs.get("failed_jobs", [])}, indent=2, default=str)}

DISK USAGE:
{json.dumps(disk.get("volumes", []), indent=2, default=str)}

DATABASE STATUS & BACKUPS:
{json.dumps(databases, indent=2, default=str)}

Answer the DBA's question directly based on this data.
Respond with ONLY this JSON structure:
{{
  "answer": "Direct answer to their question",
  "supporting_data": "Specific numbers or facts from the snapshot that support your answer",
  "follow_up_suggestion": "One thing they should check next"
}}"""


# ---------------------------------------------------------------------------
# Core Groq API caller
# ---------------------------------------------------------------------------

async def _call_groq(prompt: str, system: str = SYSTEM_PROMPT) -> dict:
    """Call the narration model and return the parsed JSON response.

    Transport, model id and empty-content handling all live in core/llm.py.
    """
    return await complete_json(prompt, system)


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

async def explain_snapshot(snapshot: dict) -> dict:
    """
    Takes a full health snapshot and returns an AI-generated incident explanation.
    This is the core feature - plain English + root cause from DMV data.
    """
    try:
        logger.info("AI explain_snapshot called")
        prompt = _build_explain_prompt(snapshot)
        result = await _call_groq(prompt)
        result["generated_at"] = datetime.utcnow().isoformat()
        result["model"] = model_id()
        logger.info(f"AI explanation complete | severity={result.get('severity_label')}")
        return result
    except Exception as e:
        logger.error(f"AI explain_snapshot failed: {e}")
        return {
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
            "headline": "AI analysis unavailable",
            "dba_summary": "Could not generate AI analysis. Check GROQ_API_KEY and connectivity.",
        }


async def suggest_remediation(snapshot: dict, issue_focus: Optional[str] = None) -> dict:
    """
    Takes a health snapshot and returns AI-generated T-SQL remediation scripts.
    Each script includes risk level and requires_approval flag.
    """
    try:
        logger.info(f"AI suggest_remediation called | focus={issue_focus}")
        prompt = _build_remediation_prompt(snapshot, issue_focus)
        result = await _call_groq(prompt)
        result["generated_at"] = datetime.utcnow().isoformat()
        result["model"] = model_id()
        logger.info(f"AI remediation complete | scripts={len(result.get('remediations', []))}")
        return result
    except Exception as e:
        logger.error(f"AI suggest_remediation failed: {e}")
        return {
            "error": str(e),
            "generated_at": datetime.utcnow().isoformat(),
            "remediations": [],
        }


async def answer_nl_question(question: str, snapshot: dict) -> dict:
    """
    Natural language Q&A about the server.
    User types 'why is my server slow?' and gets a grounded answer from real DMV data.
    """
    try:
        logger.info(f"AI NL question: {question[:80]}")
        prompt = _build_nl_query_prompt(question, snapshot)
        result = await _call_groq(prompt)
        result["question"] = question
        result["generated_at"] = datetime.utcnow().isoformat()
        result["model"] = model_id()
        return result
    except Exception as e:
        logger.error(f"AI answer_nl_question failed: {e}")
        return {
            "error": str(e),
            "question": question,
            "answer": "Could not generate answer. Check GROQ_API_KEY.",
            "generated_at": datetime.utcnow().isoformat(),
        }