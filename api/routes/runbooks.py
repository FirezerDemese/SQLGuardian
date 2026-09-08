"""
SQLGuardian - /runbooks routes

Ingest the team's procedures, see what they cover, and see what they do not.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from loguru import logger

from core.conditions import ConditionCode
from core.gap_report import build_gap_report
from core.runbooks import (
    SUPPORTED_EXTENSIONS,
    RunbookIngestError,
    runbook_store,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.get("/")
def list_documents():
    """Every ingested runbook, with what conditions it covers."""
    documents = runbook_store.documents()
    return {
        "supported_formats": sorted(set(SUPPORTED_EXTENSIONS.values())),
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "document_count": len(documents),
        "section_count": len(runbook_store.sections()),
        "conditions_covered": list(runbook_store.covered_conditions()),
        "conditions_not_covered": list(runbook_store.uncovered_conditions()),
        "documents": [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "filename": d.filename,
                "format": d.format,
                "section_count": d.section_count,
                "mapped_section_count": d.mapped_section_count,
                "byte_size": d.byte_size,
                "ingested_at": d.ingested_at,
                "conditions_covered": list(d.conditions_covered),
            }
            for d in documents
        ],
    }


@router.post("/upload")
async def upload_runbook(file: UploadFile = File(...), title: Optional[str] = Query(None)):
    """Ingest one runbook. Markdown, plain text, HTML/Confluence export, PDF or DOCX.

    Re-uploading the same filename replaces the previous version: two copies of
    a procedure in the corpus is how a stale step gets cited during an incident.
    """
    filename = file.filename or "runbook.txt"
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported format '{Path(filename).suffix}'. Supported: "
                + ", ".join(sorted(SUPPORTED_EXTENSIONS))
            ),
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Runbook exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    try:
        document = runbook_store.ingest(filename, raw, title=title)
    except RunbookIngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # parser blew up on a malformed document
        logger.error(f"Runbook ingestion failed for {filename}: {exc}")
        raise HTTPException(status_code=422, detail=f"Could not parse {filename}: {exc}") from exc

    unmapped = document.section_count - document.mapped_section_count
    return {
        "doc_id": document.doc_id,
        "title": document.title,
        "format": document.format,
        "section_count": document.section_count,
        "mapped_section_count": document.mapped_section_count,
        "unmapped_section_count": unmapped,
        "conditions_covered": list(document.conditions_covered),
        "conditions_still_not_covered": list(runbook_store.uncovered_conditions()),
        "note": (
            f"{unmapped} section(s) are not mapped to any condition and will never be "
            f"retrieved. Add a 'Conditions: <CODE>' line to a section to map it "
            f"explicitly." if unmapped else None
        ),
    }


@router.get("/sections")
def list_sections(condition: Optional[str] = Query(None, description="Condition code to scope to")):
    """Sections in the corpus, optionally scoped to one condition code."""
    if condition:
        try:
            code = ConditionCode(condition.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown condition '{condition}'. Known: "
                       + ", ".join(c.value for c in ConditionCode),
            )
        sections = runbook_store.sections_for(code)
    else:
        sections = runbook_store.sections()

    return {
        "condition": condition,
        "count": len(sections),
        "sections": [
            {
                "doc_id": s.doc_id,
                "doc_title": s.doc_title,
                "heading": s.heading,
                "heading_path": list(s.heading_path),
                "anchor": s.anchor,
                "citation": s.citation,
                "source_ref": s.source_ref,
                "conditions": list(s.conditions),
                "mapping_reason": s.mapping_reason,
                "steps": list(s.steps()),
            }
            for s in sections
        ],
    }


@router.delete("/{doc_id}")
def delete_runbook(doc_id: str):
    if not runbook_store.remove(doc_id):
        raise HTTPException(status_code=404, detail=f"No runbook with id '{doc_id}'.")
    return {"removed": doc_id, "conditions_not_covered": list(runbook_store.uncovered_conditions())}


@router.get("/gaps")
def gaps(days: int = Query(90, ge=1, le=3650)):
    """Conditions that fired with no documented procedure, over a window.

    The artifact a DBA lead can act on: it names the procedures the team is
    missing, ranked by how often the gap has already cost them.
    """
    return build_gap_report(days=days, store=runbook_store)
