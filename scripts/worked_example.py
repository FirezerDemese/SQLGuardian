"""
Run the whole response path against a fixed snapshot, with no SQL Server needed.

    python scripts/worked_example.py            # deterministic parts only
    python scripts/worked_example.py --narrate  # also calls the model

Condition -> retrieved team procedure with citation -> ordered actions ->
drafted reports. Everything except the final narration is deterministic, so
this prints the same thing every time.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Generated prose can contain characters the default Windows console codepage
# cannot encode (a non-breaking hyphen, for one).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from core.actions import build_action_plan                      # noqa: E402
from core.conditions import detect_conditions                   # noqa: E402
from core.gap_report import GapLog, build_gap_report, record_firings   # noqa: E402
from core.incident import evidence_from_snapshot                # noqa: E402
from core.reports import render_business_report, render_technical_report  # noqa: E402
from core.runbooks import RunbookStore                          # noqa: E402

SAMPLES = ROOT / "docs" / "runbook-samples"


def snapshot() -> dict:
    """The incident: a full volume, a log that cannot truncate, a blocking chain,
    a failed backup job and databases outside their backup window."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_conftest", ROOT / "tests" / "conftest.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    # The fixtures are plain functions under the pytest decorator.
    base = module.blocking_snapshot.__wrapped__()
    return module.multi_condition_snapshot.__wrapped__(base)


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


async def main(narrate_too: bool) -> int:
    import tempfile

    workdir = Path(tempfile.mkdtemp(prefix="sqlguardian-example-"))
    store = RunbookStore(workdir / "runbooks")
    log = GapLog(workdir / "firings.jsonl")

    rule("1. INGEST THE TEAM'S RUNBOOKS")
    for path in sorted(SAMPLES.iterdir()):
        if path.is_file():
            document = store.ingest_path(path)
            print(f"  {document.filename:44} {document.format:9} "
                  f"{document.section_count} sections, "
                  f"{document.mapped_section_count} mapped -> "
                  f"{', '.join(document.conditions_covered) or 'no condition'}")

    snap = snapshot()
    conditions = detect_conditions(snap)

    rule("2. CONDITIONS, RANKED BY BLAST RADIUS")
    for index, condition in enumerate(conditions, start=1):
        print(f"  {index}. {condition.code.value:22} {condition.severity:8} "
              f"impact={condition.impact_score:3}  {condition.title}")

    focus = next(c for c in conditions if c.code.value == "BLOCKING_CHAIN")

    rule(f"3. EVIDENCE FOR {focus.code.value}")
    for line in focus.evidence:
        print(f"  - {line}")
    print("\n  Not yet:")
    for line in focus.hold_off:
        print(f"  - {line}")

    rule("4. RETRIEVED TEAM PROCEDURE")
    retrieved = store.retrieve(focus)
    for item in retrieved:
        print(f"  Citation     : {item.section.citation}")
        print(f"  Why this one : {item.match_reason}")
        print(f"  Mapped by    : {item.section.mapping_reason}")
        print("  Steps        :")
        for step_number, step in enumerate(item.section.steps(), start=1):
            print(f"     {step_number}. {step}")
        print()

    rule("5. ORDERED ACTIONS (least destructive first)")
    plan = build_action_plan(focus, retrieved)
    print(f"  guidance_source = {plan['guidance_source']}\n")
    for index, action in enumerate(plan["actions"], start=1):
        flags = []
        if action["requires_approval"]:
            flags.append("approval required")
        if action["destructive"]:
            flags.append("DESTRUCTIVE")
        if not action["reversible"]:
            flags.append("irreversible")
        print(f"  {index:2}. [{action['blast_radius']:9}] [{action['source']:7}] "
              f"{action['action'][:88]}")
        if flags:
            print(f"      ! {', '.join(flags)}")
        if action["citation"]:
            print(f"      source: {action['citation']}")
        print(f"      undo  : {action['how_to_undo'][:110]}")

    rule("6. RUNBOOK GAP REPORT")
    record_firings(conditions, instance="SQLPROD01", store=store, log=log)
    report = build_gap_report(days=90, store=store, log=log)
    print(f"  {report['headline']}\n")
    print(f"  covered   : {[i['condition'] for i in report['covered_firings']]}")
    print(f"  uncovered : {[i['condition'] for i in report['uncovered_firings']]}")

    citations = [item.section.citation for c in conditions for item in store.retrieve(c)]
    evidence = evidence_from_snapshot(snap, conditions, "SQLPROD01", citations)

    narration = None
    if narrate_too:
        from core.narrator import narrate

        rule("7. NARRATION (model)")
        narration = await narrate(evidence)
        print(f"  model     : {narration.model}")
        print(f"  available : {narration.available}")
        print(f"  verified  : {narration.verified}")
        if narration.unsupported_numbers:
            print(f"  numbers not in the evidence: {narration.unsupported_numbers}")
        if narration.business_leaks:
            print(f"  identifiers leaked into the business summary: {narration.business_leaks}")

    rule("8. TECHNICAL REPORT")
    print(render_technical_report(evidence, narration))

    rule("9. BUSINESS SUMMARY")
    print(render_business_report(evidence, narration))

    print(f"\n(working directory: {workdir})")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--narrate", action="store_true", help="also call the model")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.narrate)))
