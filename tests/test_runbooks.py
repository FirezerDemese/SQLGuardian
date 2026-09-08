"""Ingestion keeps procedures whole, and retrieval is scoped and cited."""

from __future__ import annotations

import pytest

from core.conditions import ConditionCode, detect_conditions
from core.runbooks import (
    RunbookIngestError,
    RunbookStore,
    map_conditions,
    parse_document,
)

from conftest import SAMPLES


ALL_SAMPLES = sorted(p.name for p in SAMPLES.iterdir() if p.is_file())


@pytest.mark.parametrize("filename", ALL_SAMPLES)
def test_every_sample_format_ingests_end_to_end(tmp_path, filename):
    """Markdown, plain text, HTML/Confluence, PDF and DOCX all round-trip."""
    store = RunbookStore(tmp_path / "rb")
    document = store.ingest_path(SAMPLES / filename)

    assert document.section_count > 0
    assert document.format in {"markdown", "text", "html", "pdf", "docx"}
    for section in store.sections():
        assert section.heading, "a chunk with no heading cannot be cited"
        assert section.anchor
        assert section.doc_filename == filename
        assert section.source_ref, "a chunk needs a location inside the document"


def test_chunks_keep_their_surrounding_procedure(tmp_path):
    """A retrieved step must arrive with its heading path, not orphaned."""
    store = RunbookStore(tmp_path / "rb")
    store.ingest_path(SAMPLES / "dba-blocking-and-long-queries.md")

    blocking = [s for s in store.sections() if "Blocking chain" in s.heading][0]
    assert blocking.heading_path[0] == "Platform DBA Runbook - Contention"
    assert len(blocking.heading_path) == 2
    # The whole numbered procedure survives as one chunk.
    assert len(blocking.steps()) == 7
    assert "Fulfilment on-call" in blocking.body


def test_every_section_produces_a_resolvable_citation(store):
    for section in store.sections():
        citation = section.citation
        assert section.doc_title in citation
        assert section.anchor in citation
        assert section.source_ref in citation


def test_explicit_annotation_beats_keyword_matching():
    conditions, reason = map_conditions(
        ("Overnight batch", "Warehouse load stalled"),
        "Conditions: BLOCKING_CHAIN\n\n1. Check the load window.",
    )
    assert conditions == ("BLOCKING_CHAIN",)
    assert reason == "declared in the document"


def test_html_comment_annotation_is_honoured(tmp_path):
    """Confluence pages carry the annotation invisibly, in a comment."""
    store = RunbookStore(tmp_path / "rb")
    store.ingest_path(SAMPLES / "confluence-export-storage.html")
    disk = store.sections_for(ConditionCode.DISK_PRESSURE)
    assert disk
    assert disk[0].mapping_reason == "declared in the document"


def test_keyword_mapping_records_the_phrase_that_matched():
    conditions, reason = map_conditions(
        ("Storage", "Volume running out of free space"),
        "Check free space on the volume and raise a request.",
    )
    assert ConditionCode.DISK_PRESSURE.value in conditions
    assert "free space" in reason or "disk space" in reason


def test_unmapped_sections_are_never_retrieved(store, blocking_snapshot):
    """Scoping is the point: a contacts page cannot answer a blocking incident."""
    condition = detect_conditions(blocking_snapshot)[0]
    retrieved = store.retrieve(condition)
    assert retrieved
    for item in retrieved:
        assert ConditionCode.BLOCKING_CHAIN.value in item.section.conditions


def test_retrieval_returns_the_teams_procedure_for_a_blocking_chain(store, blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    top = store.retrieve(condition)[0]

    assert top.section.doc_filename == "dba-blocking-and-long-queries.md"
    assert "Blocking chain" in top.section.heading
    assert "OrderSync" in top.section.body       # ranked up by the live program name
    assert "OrderSync" in top.match_reason.lower() or top.score > 1.0


def test_retrieval_ranks_on_facts_from_the_live_condition(store, blocking_snapshot):
    """The section naming the affected application outranks a generic one."""
    condition = detect_conditions(blocking_snapshot)[0]
    results = store.retrieve(condition)
    assert results == tuple(sorted(results, key=lambda r: (-r.score, r.section.anchor)))


def test_retrieval_is_empty_when_the_team_has_no_procedure(empty_store, blocking_snapshot):
    """An empty result is a real answer, not a failure."""
    condition = detect_conditions(blocking_snapshot)[0]
    assert empty_store.retrieve(condition) == ()


def test_retrieval_is_deterministic(store, blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    first = [r.section.anchor for r in store.retrieve(condition)]
    second = [r.section.anchor for r in store.retrieve(condition)]
    assert first == second


def test_reingesting_replaces_rather_than_duplicates(tmp_path):
    store = RunbookStore(tmp_path / "rb")
    store.ingest_path(SAMPLES / "dba-blocking-and-long-queries.md")
    before = len(store.sections())
    store.ingest_path(SAMPLES / "dba-blocking-and-long-queries.md")
    assert len(store.sections()) == before
    assert len(store.documents()) == 1


def test_anchors_are_stable_across_a_reingest(tmp_path):
    """Old citations have to keep resolving after a runbook is edited."""
    store = RunbookStore(tmp_path / "rb")
    store.ingest_path(SAMPLES / "backup-and-log-procedures.txt")
    before = {s.heading: s.anchor for s in store.sections()}
    store.ingest_path(SAMPLES / "backup-and-log-procedures.txt")
    after = {s.heading: s.anchor for s in store.sections()}
    assert before == after


def test_the_corpus_survives_a_restart(tmp_path):
    store = RunbookStore(tmp_path / "rb")
    store.ingest_path(SAMPLES / "wait-stats-triage.docx")
    reopened = RunbookStore(tmp_path / "rb")
    assert len(reopened.sections()) == len(store.sections())
    assert reopened.covered_conditions() == store.covered_conditions()


def test_an_unsupported_format_is_refused():
    with pytest.raises(RunbookIngestError, match="Unsupported"):
        parse_document("procedures.xlsx", b"anything")


def test_a_scanned_pdf_is_refused_rather_than_silently_empty(tmp_path):
    """No OCR in this pipeline; an image-only PDF has to say so, not ingest blank."""
    import sys

    sys.path.insert(0, str(SAMPLES.parent.parent / "scripts"))
    from make_sample_runbooks import write_pdf

    blank = tmp_path / "scan.pdf"
    write_pdf(blank, lines=[])          # valid PDF, one page, no text objects

    with pytest.raises(RunbookIngestError, match="No extractable text"):
        parse_document("scan.pdf", blank.read_bytes())


def test_a_corrupt_pdf_is_a_rejected_document_not_a_server_error():
    with pytest.raises(RunbookIngestError, match="not a readable PDF"):
        parse_document("broken.pdf", b"%PDF-1.4\nthis is not a pdf\n")


def test_document_coverage_is_reported_honestly(store):
    """A section mapped to nothing is counted as unmapped, not quietly dropped."""
    for document in store.documents():
        assert document.mapped_section_count <= document.section_count
    escalation = [d for d in store.documents() if d.format == "pdf"][0]
    assert escalation.mapped_section_count < escalation.section_count
