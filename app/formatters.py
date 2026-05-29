"""
Output formatters — converts structured extraction results
into Slack and Email formatted messages.
"""

from __future__ import annotations

from app.models import (
    ActionItem,
    Decision,
    Escalation,
    Priority,
    UnresolvedQuestion,
)

# ── Priority badges ──────────────────────────────────────────────────────────

_PRIORITY_EMOJI = {
    Priority.HIGH: "🔴",
    Priority.MEDIUM: "🟡",
    Priority.LOW: "🟢",
}

_PRIORITY_LABEL = {
    Priority.HIGH: "HIGH",
    Priority.MEDIUM: "MEDIUM",
    Priority.LOW: "LOW",
}


def format_slack(
    summary: str,
    decisions: list[Decision],
    action_items: list[ActionItem],
    unresolved: list[UnresolvedQuestion],
    escalations: list[Escalation],
    meeting_title: str = "Meeting",
    participants: list[str] | None = None,
) -> str:
    """
    Format results as a Slack message.
    Uses Slack's mrkdwn syntax: *bold*, bullet points, emoji.
    """
    lines: list[str] = []

    # Header
    lines.append(f"📋 *{meeting_title}*")
    lines.append("")

    # Participants
    if participants:
        lines.append(f"👥 *Participants:* {', '.join(participants)}")
        lines.append("")

    # Summary
    lines.append("*Summary*")
    for line in summary.strip().split("\n"):
        lines.append(f"> {line.strip()}")
    lines.append("")

    # Decisions
    if decisions:
        lines.append(f"✅ *Decisions ({len(decisions)})*")
        for d in decisions:
            flag = " ⚠️" if d.confidence < 0.6 else ""
            lines.append(f"  • {d.text}{flag}")
        lines.append("")

    # Action Items
    if action_items:
        lines.append(f"🎯 *Action Items ({len(action_items)})*")
        for ai in action_items:
            flag = " ⚠️" if ai.confidence < 0.6 else ""
            priority_emoji = _PRIORITY_EMOJI.get(ai.priority, "🟡")
            lines.append(f"  • {priority_emoji} {ai.task}")
            lines.append(f"    👤 {ai.owner}  |  📅 {ai.deadline}{flag}")
        lines.append("")

    # Unresolved
    if unresolved:
        lines.append(f"❓ *Unresolved Questions ({len(unresolved)})*")
        for uq in unresolved:
            flag = " ⚠️" if uq.confidence < 0.6 else ""
            lines.append(f"  • {uq.question}{flag}")
        lines.append("")

    # Escalations
    if escalations:
        lines.append(f"🚨 *Needs Human Review ({len(escalations)})*")
        for esc in escalations:
            lines.append(f"  • [{esc.reason.value}] {esc.item_summary}")
        lines.append("")

    return "\n".join(lines).strip()


def format_email(
    summary: str,
    decisions: list[Decision],
    action_items: list[ActionItem],
    unresolved: list[UnresolvedQuestion],
    escalations: list[Escalation],
    meeting_title: str = "Meeting",
    participants: list[str] | None = None,
) -> str:
    """
    Format results as a professional email body.
    Uses plain text with clear section headers.
    """
    lines: list[str] = []

    lines.append(meeting_title.upper())
    lines.append("=" * 50)
    lines.append("")

    if participants:
        lines.append(f"Participants: {', '.join(participants)}")
        lines.append("")

    lines.append("SUMMARY")
    lines.append("-" * 50)
    lines.append(summary.strip())
    lines.append("")
    lines.append("")

    if decisions:
        lines.append("DECISIONS MADE")
        lines.append("-" * 50)
        for i, d in enumerate(decisions, 1):
            confidence_note = f" [confidence: {d.confidence:.0%}]" if d.confidence < 0.8 else ""
            lines.append(f"  {i}. {d.text}{confidence_note}")
            if d.context:
                lines.append(f"     Context: {d.context}")
        lines.append("")

    if action_items:
        lines.append("ACTION ITEMS")
        lines.append("-" * 50)
        for i, ai in enumerate(action_items, 1):
            confidence_note = f" [confidence: {ai.confidence:.0%}]" if ai.confidence < 0.8 else ""
            priority_label = _PRIORITY_LABEL.get(ai.priority, "MEDIUM")
            lines.append(f"  {i}. [{priority_label}] {ai.task}")
            lines.append(f"     Owner: {ai.owner}")
            lines.append(f"     Deadline: {ai.deadline}{confidence_note}")
            lines.append("")

    if unresolved:
        lines.append("UNRESOLVED QUESTIONS")
        lines.append("-" * 50)
        for i, uq in enumerate(unresolved, 1):
            confidence_note = f" [confidence: {uq.confidence:.0%}]" if uq.confidence < 0.8 else ""
            lines.append(f"  {i}. {uq.question}{confidence_note}")
            if uq.suggested_owner and uq.suggested_owner != "Unknown":
                lines.append(f"     Suggested follow-up: {uq.suggested_owner}")
        lines.append("")

    if escalations:
        lines.append("⚠ ITEMS REQUIRING HUMAN REVIEW")
        lines.append("-" * 50)
        for i, esc in enumerate(escalations, 1):
            lines.append(f"  {i}. [{esc.reason.value.upper()}] {esc.item_summary}")
            lines.append(f"     Reason: {esc.details}")
            lines.append("")

    lines.append("")
    lines.append("---")
    lines.append("Generated by Meeting-to-Action Pipeline Agent")
    lines.append("Review escalated items and confirm action item assignments.")

    return "\n".join(lines).strip()
