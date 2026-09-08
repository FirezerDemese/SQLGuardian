"""Action ordering is computed from metadata. Destructive is always last."""

from __future__ import annotations

import pytest

from core.actions import (
    ACTION_CATALOG,
    Action,
    BlastRadius,
    build_action_plan,
    classify_step,
    order_actions,
)
from core.conditions import ConditionCode, detect_conditions


def _read_only(name: str) -> Action:
    return Action(
        action=name, what_it_does="reads", expected_effect="you know more",
        blast_radius=BlastRadius.READ_ONLY, reversible=True,
        how_to_undo="Nothing to undo; this only reads.",
        requires_approval=False, source="generic",
    )


def _destructive(name: str, radius: BlastRadius = BlastRadius.SESSION) -> Action:
    return Action(
        action=name, what_it_does="destroys", expected_effect="work is lost",
        blast_radius=radius, reversible=False,
        how_to_undo="Not reversible.", requires_approval=True,
        destructive=True, source="generic",
    )


def test_every_condition_has_actions(multi_condition_snapshot, blocking_snapshot):
    """A condition with no catalogued response is a hole in the product."""
    assert set(ACTION_CATALOG) == set(ConditionCode)


def test_destructive_actions_are_always_last():
    actions = [
        _destructive("kill it"),
        _read_only("look at it"),
        _destructive("delete it", BlastRadius.HOST),
        _read_only("check the owner"),
    ]
    ordered = order_actions(actions)
    assert [a.destructive for a in ordered] == [False, False, True, True]


def test_ordering_follows_blast_radius():
    actions = [
        Action(action="instance change", what_it_does="", expected_effect="",
               blast_radius=BlastRadius.INSTANCE, reversible=True, how_to_undo="revert",
               requires_approval=True, source="generic"),
        Action(action="database change", what_it_does="", expected_effect="",
               blast_radius=BlastRadius.DATABASE, reversible=True, how_to_undo="revert",
               requires_approval=True, source="generic"),
        _read_only("read"),
    ]
    assert [a.blast_radius for a in order_actions(actions)] == [
        BlastRadius.READ_ONLY, BlastRadius.DATABASE, BlastRadius.INSTANCE
    ]


def test_ordering_is_deterministic_and_independent_of_input_order():
    actions = [_read_only("b"), _destructive("z"), _read_only("a")]
    assert [a.action for a in order_actions(actions)] == [
        a.action for a in order_actions(list(reversed(actions)))
    ]


def test_a_runbook_action_without_a_citation_is_rejected():
    """A step with no citation is not usable in an incident."""
    with pytest.raises(ValueError, match="no citation"):
        Action(action="do the thing", what_it_does="", expected_effect="",
               blast_radius=BlastRadius.READ_ONLY, reversible=True,
               how_to_undo="", requires_approval=False, source="runbook")


def test_a_destructive_action_must_require_approval():
    with pytest.raises(ValueError, match="must require approval"):
        Action(action="kill it", what_it_does="", expected_effect="",
               blast_radius=BlastRadius.SESSION, reversible=False,
               how_to_undo="Not reversible.", requires_approval=False,
               destructive=True, source="generic")


@pytest.mark.parametrize("step,expected_destructive", [
    ("Kill the head blocker with duty manager approval", True),
    ("Run DBCC SHRINKFILE on the log", True),
    ("Fail over to the secondary replica", True),
    ("Take a COPY_ONLY backup to the share", False),
    ("Record the session id in the incident channel", False),
    ("Check whether the job is disabled", False),
])
def test_runbook_steps_are_classified_conservatively(step, expected_destructive):
    _, destructive, approval = classify_step(step)
    assert destructive is expected_destructive
    if destructive:
        assert approval is True


def test_an_unrecognised_write_step_still_requires_approval():
    radius, destructive, approval = classify_step("ALTER DATABASE X SET RECOVERY SIMPLE")
    assert destructive is False        # not in the destructive list
    assert approval is True            # but it writes, so it is gated anyway
    assert radius is BlastRadius.DATABASE


def test_plan_prefers_the_team_procedure_and_says_so(store, blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    retrieved = store.retrieve(condition)
    plan = build_action_plan(condition, retrieved)

    assert plan["has_team_procedure"] is True
    assert plan["guidance_source"] == "runbook"
    assert plan["citations"]
    runbook_actions = [a for a in plan["actions"] if a["source"] == "runbook"]
    assert runbook_actions
    for action in runbook_actions:
        assert action["citation"], "every runbook-sourced step carries its citation"


def test_plan_labels_generic_guidance_when_there_is_no_procedure(empty_store, blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    plan = build_action_plan(condition, empty_store.retrieve(condition))

    assert plan["has_team_procedure"] is False
    assert plan["guidance_source"] == "generic"
    assert plan["citations"] == []
    assert {a["source"] for a in plan["actions"]} == {"generic"}


def test_kill_is_never_the_first_suggestion(empty_store, blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    plan = build_action_plan(condition, empty_store.retrieve(condition))
    actions = plan["actions"]

    assert "kill" not in actions[0]["action"].lower()
    kills = [i for i, a in enumerate(actions) if a["action"].lower().startswith("kill")]
    assert kills, "the option still has to be offered, just not first"
    assert kills[0] == len(actions) - 1
    assert actions[kills[0]]["requires_approval"] is True
    assert actions[kills[0]]["reversible"] is False


def test_every_action_states_how_to_undo_it(store, multi_condition_snapshot):
    for condition in detect_conditions(multi_condition_snapshot):
        plan = build_action_plan(condition, store.retrieve(condition))
        for action in plan["actions"]:
            assert action["how_to_undo"].strip(), f"{action['action']} has no rollback"
            if not action["reversible"]:
                assert "not reversible" in action["how_to_undo"].lower()


def test_plan_carries_what_not_to_do_yet(store, blocking_snapshot):
    condition = detect_conditions(blocking_snapshot)[0]
    plan = build_action_plan(condition, store.retrieve(condition))
    assert plan["hold_off"]
    assert any("kill" in line.lower() for line in plan["hold_off"])


def test_plans_are_generated_for_every_detected_condition(store, multi_condition_snapshot):
    for condition in detect_conditions(multi_condition_snapshot):
        plan = build_action_plan(condition, store.retrieve(condition))
        assert plan["actions"], f"no actions for {condition.code.value}"
