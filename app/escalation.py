"""
Escalation engine — applies rule-based checks on extracted items
to flag anything that requires human review.

Rules:
  1. Action item with no clear owner → escalate
  2. Action item with missing/ambiguous deadline → escalate
  3. Two people appear to own the same task → escalate
  4. Any item below confidence threshold → escalate
  5. High-priority item with no deadline → escalate
  6. Overloaded owner (3+ action items) → escalate
"""

from __future__ import annotations

import logging
from collections import defaultdict

from app.config import settings
from app.models import (
    ActionItem,
    Decision,
    Escalation,
    EscalationReason,
    Priority,
    UnresolvedQuestion,
)

logger = logging.getLogger(__name__)

# Signals that an owner is not clearly assigned
_UNKNOWN_OWNER_SIGNALS = {
    "unknown",
    "unknown speaker",
    "someone",
    "somebody",
    "anyone",
    "tbd",
    "to be determined",
    "not specified",
    "not assigned",
    "",
    "n/a",
    "na",
    "none",
}

# Signals that a deadline is ambiguous
_AMBIGUOUS_DEADLINE_SIGNALS = {
    "not specified",
    "tbd",
    "to be determined",
    "soon",
    "asap",
    "sometime",
    "later",
    "eventually",
    "when possible",
    "not sure",
    "unclear",
    "",
    "n/a",
    "na",
    "none",
}

# Threshold for overloaded owner detection
_OVERLOADED_OWNER_THRESHOLD = 3


def run_escalation_checks(
    decisions: list[Decision],
    action_items: list[ActionItem],
    unresolved: list[UnresolvedQuestion],
) -> list[Escalation]:
    """
    Apply all escalation rules and return a list of flagged items.
    Each escalation includes what was flagged and why.
    """
    escalations: list[Escalation] = []

    # ── Check decisions ──────────────────────────────────────────────────
    for dec in decisions:
        if dec.confidence < settings.confidence_threshold:
            escalations.append(
                Escalation(
                    item_type="decision",
                    item_summary=dec.text[:120],
                    reason=EscalationReason.LOW_CONFIDENCE,
                    details=(
                        f"Confidence {dec.confidence:.0%} is below threshold "
                        f"({settings.confidence_threshold:.0%}). "
                        f"Context: {dec.context or 'none provided'}"
                    ),
                )
            )

    # ── Check action items ───────────────────────────────────────────────
    owner_count: dict[str, int] = defaultdict(int)

    for ai in action_items:
        owner_lower = ai.owner.strip().lower()
        deadline_lower = ai.deadline.strip().lower()

        # Track owner task counts for overload detection
        if owner_lower not in _UNKNOWN_OWNER_SIGNALS:
            owner_count[owner_lower] += 1

        # Rule 1: No clear owner
        if owner_lower in _UNKNOWN_OWNER_SIGNALS:
            escalations.append(
                Escalation(
                    item_type="action_item",
                    item_summary=ai.task[:120],
                    reason=EscalationReason.NO_OWNER,
                    details=(
                        f"Task \"{ai.task}\" has no clear owner. "
                        f"Owner field is '{ai.owner}'. "
                        "A human should assign this to someone specific."
                    ),
                )
            )

        # Rule 2: Missing or ambiguous deadline
        if deadline_lower in _AMBIGUOUS_DEADLINE_SIGNALS:
            escalations.append(
                Escalation(
                    item_type="action_item",
                    item_summary=ai.task[:120],
                    reason=EscalationReason.NO_DEADLINE
                    if deadline_lower in {"not specified", "", "n/a", "na", "none"}
                    else EscalationReason.AMBIGUOUS_DEADLINE,
                    details=(
                        f"Task \"{ai.task}\" has deadline '{ai.deadline}'. "
                        "This is too vague to be actionable. "
                        "A human should set a specific date."
                    ),
                )
            )

        # Rule 4: Low confidence
        if ai.confidence < settings.confidence_threshold:
            escalations.append(
                Escalation(
                    item_type="action_item",
                    item_summary=ai.task[:120],
                    reason=EscalationReason.LOW_CONFIDENCE,
                    details=(
                        f"Confidence {ai.confidence:.0%} is below threshold "
                        f"({settings.confidence_threshold:.0%}). "
                        "The agent is not sure this is a real action item."
                    ),
                )
            )

        # Rule 5: High-priority item with no deadline
        if (
            ai.priority == Priority.HIGH
            and deadline_lower in _AMBIGUOUS_DEADLINE_SIGNALS
        ):
            # Avoid duplicate if already flagged by Rule 2
            already_flagged = any(
                e.item_summary == ai.task[:120]
                and e.reason == EscalationReason.HIGH_PRIORITY_NO_DEADLINE
                for e in escalations
            )
            if not already_flagged:
                escalations.append(
                    Escalation(
                        item_type="action_item",
                        item_summary=ai.task[:120],
                        reason=EscalationReason.HIGH_PRIORITY_NO_DEADLINE,
                        details=(
                            f"High-priority task \"{ai.task}\" has no specific deadline. "
                            "This is risky — a human should set a deadline immediately."
                        ),
                    )
                )

    # Rule 3: Ownership conflict — detect duplicate tasks across owners
    task_owners: dict[str, list[str]] = defaultdict(list)
    for ai in action_items:
        owner_lower = ai.owner.strip().lower()
        if owner_lower not in _UNKNOWN_OWNER_SIGNALS:
            task_key = ai.task.strip().lower()[:80]
            task_owners[task_key].append(ai.owner)

    for task_key, owners in task_owners.items():
        unique_owners = set(o.lower() for o in owners)
        if len(unique_owners) > 1:
            escalations.append(
                Escalation(
                    item_type="action_item",
                    item_summary=task_key[:120],
                    reason=EscalationReason.OWNERSHIP_CONFLICT,
                    details=(
                        f"Multiple people appear to own the same task: "
                        f"{', '.join(owners)}. A human should clarify "
                        "who is the single owner."
                    ),
                )
            )

    # Rule 6: Overloaded owner
    for owner, count in owner_count.items():
        if count >= _OVERLOADED_OWNER_THRESHOLD:
            # Find the actual display name (first occurrence, capitalized)
            display_name = owner
            for ai in action_items:
                if ai.owner.strip().lower() == owner:
                    display_name = ai.owner
                    break
            escalations.append(
                Escalation(
                    item_type="action_item",
                    item_summary=f"{display_name} has {count} action items",
                    reason=EscalationReason.OVERLOADED_OWNER,
                    details=(
                        f"{display_name} is assigned {count} action items from this meeting. "
                        f"This may be too much for one person. Consider redistributing tasks."
                    ),
                )
            )

    # ── Check unresolved questions ───────────────────────────────────────
    for uq in unresolved:
        if uq.confidence < settings.confidence_threshold:
            escalations.append(
                Escalation(
                    item_type="unresolved",
                    item_summary=uq.question[:120],
                    reason=EscalationReason.LOW_CONFIDENCE,
                    details=(
                        f"Confidence {uq.confidence:.0%} is below threshold "
                        f"({settings.confidence_threshold:.0%}). "
                        "Unsure if this was truly left unresolved."
                    ),
                )
            )

    logger.info("Escalation check complete: %d items flagged", len(escalations))
    return escalations
