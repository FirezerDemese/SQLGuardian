"""The runbook gap report: what fired that the team has no procedure for."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.conditions import ConditionCode, detect_conditions
from core.gap_report import GapLog, build_gap_report, record_firings


@pytest.fixture
def log(tmp_path) -> GapLog:
    return GapLog(tmp_path / "firings.jsonl")


def test_a_firing_with_no_procedure_is_recorded_as_a_gap(
    empty_store, log, blocking_snapshot
):
    conditions = detect_conditions(blocking_snapshot)
    written = record_firings(conditions, instance="SQLPROD01", store=empty_store, log=log)

    assert [r.condition for r in written] == [ConditionCode.BLOCKING_CHAIN.value]
    assert written[0].covered is False
    assert written[0].citations == ()


def test_a_firing_answered_from_the_corpus_is_recorded_as_covered(
    store, log, blocking_snapshot
):
    conditions = detect_conditions(blocking_snapshot)
    written = record_firings(conditions, instance="SQLPROD01", store=store, log=log)

    assert written[0].covered is True
    assert written[0].citations
    assert "dba-blocking-and-long-queries.md" in written[0].citations[0]


def test_the_report_names_the_uncovered_conditions(empty_store, log, multi_condition_snapshot):
    conditions = detect_conditions(multi_condition_snapshot)
    record_firings(conditions, instance="SQLPROD01", store=empty_store, log=log)

    report = build_gap_report(days=90, store=empty_store, log=log)

    uncovered = {item["condition"] for item in report["uncovered_firings"]}
    assert ConditionCode.DISK_PRESSURE.value in uncovered
    assert ConditionCode.BLOCKING_CHAIN.value in uncovered
    assert report["covered_firings"] == []
    assert report["total_firings"] == len(conditions)


def test_the_report_counts_repeat_firings(empty_store, log, blocking_snapshot):
    conditions = detect_conditions(blocking_snapshot)
    for _ in range(6):
        record_firings(conditions, instance="SQLPROD01", store=empty_store, log=log)

    report = build_gap_report(days=90, store=empty_store, log=log)
    blocking = [
        item for item in report["uncovered_firings"]
        if item["condition"] == ConditionCode.BLOCKING_CHAIN.value
    ][0]
    assert blocking["firings"] == 6
    assert "6 time(s)" in report["headline"]


def test_the_headline_says_so_when_everything_was_covered(store, log, blocking_snapshot):
    record_firings(detect_conditions(blocking_snapshot), store=store, log=log)
    report = build_gap_report(days=90, store=store, log=log)

    assert report["uncovered_firings"] == []
    assert "answered from a documented team procedure" in report["headline"]


def test_the_headline_says_so_when_no_runbooks_exist_at_all(empty_store, log):
    report = build_gap_report(days=90, store=empty_store, log=log)
    assert "No runbooks have been ingested" in report["headline"]


def test_conditions_with_no_procedure_that_have_not_fired_are_listed_separately(
    empty_store, log, blocking_snapshot
):
    """Cheaper to write the procedure today than at 3am."""
    record_firings(detect_conditions(blocking_snapshot), store=empty_store, log=log)
    report = build_gap_report(days=90, store=empty_store, log=log)

    assert ConditionCode.BLOCKING_CHAIN.value not in report["never_fired_gaps"]
    assert ConditionCode.DISK_PRESSURE.value in report["never_fired_gaps"]


def test_the_window_excludes_older_firings(empty_store, log, blocking_snapshot):
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    conditions = [
        type(c)(**{**c.__dict__, "detected_at": old}) for c in detect_conditions(blocking_snapshot)
    ]
    record_firings(conditions, store=empty_store, log=log)

    assert build_gap_report(days=90, store=empty_store, log=log)["total_firings"] == 0
    assert build_gap_report(days=365, store=empty_store, log=log)["total_firings"] == 1


def test_the_log_is_append_only(empty_store, log, blocking_snapshot):
    """A coverage claim you can silently rewrite is not evidence."""
    conditions = detect_conditions(blocking_snapshot)
    record_firings(conditions, store=empty_store, log=log)
    first = log.path.read_text(encoding="utf-8")
    record_firings(conditions, store=empty_store, log=log)
    second = log.path.read_text(encoding="utf-8")

    assert second.startswith(first)
    assert len(second.splitlines()) == 2


def test_an_unparseable_line_does_not_break_the_report(empty_store, log, blocking_snapshot):
    record_firings(detect_conditions(blocking_snapshot), store=empty_store, log=log)
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write("{ this is not json\n")

    assert build_gap_report(days=90, store=empty_store, log=log)["total_firings"] == 1


def test_the_scheduler_records_one_firing_per_episode_not_per_poll(
    monkeypatch, empty_store, log, blocking_snapshot, healthy_snapshot
):
    """Otherwise the report measures polling frequency instead of pain."""
    import core.scheduler as scheduler

    recorded: list[str] = []

    def fake_record(conditions, instance="primary"):
        recorded.extend(c.code.value for c in conditions)

    monkeypatch.setattr(scheduler, "record_firings", fake_record)
    monkeypatch.setattr(scheduler, "_open_conditions", set())

    blocking = detect_conditions(blocking_snapshot)
    for _ in range(5):
        scheduler._record_new_firings(blocking, "SQLPROD01")
    assert recorded == [ConditionCode.BLOCKING_CHAIN.value]

    # It clears, then comes back: that is a second incident and is recorded again.
    scheduler._record_new_firings(detect_conditions(healthy_snapshot), "SQLPROD01")
    scheduler._record_new_firings(blocking, "SQLPROD01")
    assert recorded == [ConditionCode.BLOCKING_CHAIN.value] * 2
