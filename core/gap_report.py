"""
SQLGuardian - Runbook gap report

Every time a condition fires, this records whether the team had a documented
procedure for it. The accumulated answer - "these conditions have fired N times
in the last 90 days and your runbooks do not cover any of them" - is the
artifact a DBA lead can act on, and it is the clearest evidence that the tool
knows the difference between having an answer and having YOUR answer.

No monitoring vendor produces this, because it requires knowing what the team
documented, which is exactly what a vendor does not have.

Storage is an append-only JSONL file. Append-only matters: a coverage claim you
can silently rewrite is not evidence.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

from loguru import logger

from config.settings import settings
from core.conditions import Condition, ConditionCode
from core.runbooks import RunbookStore, runbook_store


@dataclass(frozen=True)
class FiringRecord:
    """One condition firing and whether the corpus covered it."""

    condition: str
    severity: str
    instance: str
    detected_at: str
    covered: bool
    citations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "severity": self.severity,
            "instance": self.instance,
            "detected_at": self.detected_at,
            "covered": self.covered,
            "citations": list(self.citations),
        }


class GapLog:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or Path(settings.incident_store_dir) / "condition_firings.jsonl")

    def record(self, record: FiringRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict()) + "\n")

    def records(self, since: Optional[datetime] = None) -> tuple[FiringRecord, ...]:
        if not self.path.exists():
            return ()
        out: list[FiringRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping unparseable line in the condition firing log.")
                continue
            if since is not None:
                try:
                    when = datetime.fromisoformat(data["detected_at"])
                except (KeyError, ValueError):
                    continue
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                if when < since:
                    continue
            out.append(FiringRecord(
                condition=data.get("condition", ""),
                severity=data.get("severity", ""),
                instance=data.get("instance", ""),
                detected_at=data.get("detected_at", ""),
                covered=bool(data.get("covered")),
                citations=tuple(data.get("citations") or ()),
            ))
        return tuple(out)


gap_log = GapLog()


def record_firings(
    conditions: Sequence[Condition],
    instance: str = "primary",
    store: Optional[RunbookStore] = None,
    log: Optional[GapLog] = None,
) -> tuple[FiringRecord, ...]:
    """Record each fired condition against the corpus. Returns what was written."""
    store = store or runbook_store
    log = log or gap_log

    written: list[FiringRecord] = []
    for condition in conditions:
        retrieved = store.retrieve(condition)
        record = FiringRecord(
            condition=condition.code.value,
            severity=condition.severity,
            instance=instance,
            detected_at=condition.detected_at,
            covered=bool(retrieved),
            citations=tuple(item.section.citation for item in retrieved),
        )
        log.record(record)
        written.append(record)
        if not retrieved:
            logger.warning(
                f"No documented procedure covers {condition.code.value} on [{instance}]. "
                f"Recorded as a runbook gap."
            )
    return tuple(written)


def build_gap_report(
    days: int = 90,
    store: Optional[RunbookStore] = None,
    log: Optional[GapLog] = None,
) -> dict:
    """The report: what fired, how often, and what the runbooks do not cover.

    Reports three distinct things, which are not the same and must not be
    conflated:
      uncovered_firings  - conditions that fired with no team procedure. The
                           urgent list: it already happened and nobody had a
                           documented answer.
      covered_firings    - conditions that fired and were answered from the
                           corpus. Evidence the runbooks are earning their keep.
      never_fired_gaps   - conditions with no procedure that have not fired yet.
                           Cheaper to write today than at 3am.
    """
    store = store or runbook_store
    log = log or gap_log
    since = datetime.now(timezone.utc) - timedelta(days=days)
    records = log.records(since=since)

    fired = Counter(r.condition for r in records)
    uncovered = Counter(r.condition for r in records if not r.covered)
    covered = Counter(r.condition for r in records if r.covered)
    last_seen: dict[str, str] = {}
    for record in records:
        current = last_seen.get(record.condition)
        if current is None or record.detected_at > current:
            last_seen[record.condition] = record.detected_at

    corpus_covered = set(store.covered_conditions())

    uncovered_firings = [
        {
            "condition": code,
            "firings": count,
            "last_seen": last_seen.get(code),
            "severity_seen": sorted({
                r.severity for r in records if r.condition == code and not r.covered
            }),
        }
        for code, count in uncovered.most_common()
    ]

    covered_firings = [
        {
            "condition": code,
            "firings": count,
            "last_seen": last_seen.get(code),
            "citations": sorted({
                citation
                for r in records if r.condition == code and r.covered
                for citation in r.citations
            })[:5],
        }
        for code, count in covered.most_common()
    ]

    never_fired_gaps = [
        code.value for code in ConditionCode
        if code.value not in corpus_covered and fired.get(code.value, 0) == 0
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "total_firings": len(records),
        "documents_in_corpus": len(store.documents()),
        "conditions_covered_by_corpus": sorted(corpus_covered),
        "conditions_not_covered_by_corpus": list(store.uncovered_conditions()),
        "uncovered_firings": uncovered_firings,
        "covered_firings": covered_firings,
        "never_fired_gaps": never_fired_gaps,
        "headline": _headline(uncovered_firings, days, len(store.documents())),
    }


def _headline(uncovered_firings: Iterable[dict], days: int, doc_count: int) -> str:
    """One deterministic sentence. Not model output."""
    items = list(uncovered_firings)
    total = sum(item["firings"] for item in items)
    if doc_count == 0:
        if not items:
            return (
                "No runbooks have been ingested. Any condition that fires will be "
                "answered with generic guidance only."
            )
        return (
            f"No runbooks have been ingested. {len(items)} condition type(s) fired "
            f"{total} time(s) in the last {days} days and were answered with generic "
            f"guidance only: {', '.join(item['condition'] for item in items)}."
        )
    if not items:
        return (
            f"Every condition that fired in the last {days} days was answered from a "
            f"documented team procedure."
        )
    return (
        f"{len(items)} condition type(s) fired {total} time(s) in the last {days} days "
        f"with no documented procedure: {', '.join(item['condition'] for item in items)}."
    )
