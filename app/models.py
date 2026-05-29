"""
Pydantic models for request/response validation.
Defines the complete schema for the Meeting-to-Action pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from enum import Enum


# ── Request ──────────────────────────────────────────────────────────────────

class TranscriptRequest(BaseModel):
    """Incoming request with raw meeting transcript."""
    transcript: str = Field(
        ...,
        min_length=1,
        description="Raw meeting transcript text",
    )


# ── Enums ────────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    """Priority level for action items."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Extracted Items ──────────────────────────────────────────────────────────

class Decision(BaseModel):
    """A decision made during the meeting."""
    text: str = Field(..., description="The decision statement")
    context: str = Field(default="", description="Surrounding context or rationale")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Extraction confidence (0.0–1.0)",
    )


class ActionItem(BaseModel):
    """An action item with owner, deadline, and priority."""
    task: str = Field(..., description="Description of the task")
    owner: str = Field(default="Unknown", description="Person responsible")
    deadline: str = Field(default="Not specified", description="Due date or timeframe")
    priority: Priority = Field(default=Priority.MEDIUM, description="Priority level")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Extraction confidence (0.0–1.0)",
    )


class UnresolvedQuestion(BaseModel):
    """A question or topic that was not resolved in the meeting."""
    question: str = Field(..., description="The unresolved question")
    context: str = Field(default="", description="Why it's unresolved")
    suggested_owner: str = Field(
        default="Unknown",
        description="Who might need to follow up",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Extraction confidence (0.0–1.0)",
    )


# ── Escalation ───────────────────────────────────────────────────────────────

class EscalationReason(str, Enum):
    """Why an item was escalated for human review."""
    NO_OWNER = "no_clear_owner"
    NO_DEADLINE = "missing_deadline"
    OWNERSHIP_CONFLICT = "ownership_conflict"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_DEADLINE = "ambiguous_deadline"
    NOISY_TRANSCRIPT = "noisy_transcript"
    HIGH_PRIORITY_NO_DEADLINE = "high_priority_no_deadline"
    OVERLOADED_OWNER = "overloaded_owner"


class Escalation(BaseModel):
    """An item flagged for human review."""
    item_type: str = Field(..., description="Type: decision | action_item | unresolved")
    item_summary: str = Field(..., description="Brief description of the flagged item")
    reason: EscalationReason = Field(..., description="Why it was escalated")
    details: str = Field(default="", description="Detailed explanation for the human reviewer")


# ── Response ─────────────────────────────────────────────────────────────────

class ProcessingResult(BaseModel):
    """Complete response from the /process endpoint."""
    meeting_title: str = Field(default="Untitled Meeting", description="Inferred meeting title")
    participants: list[str] = Field(default_factory=list, description="Identified participants")
    summary: str = Field(..., description="3-line meeting summary")
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    unresolved: list[UnresolvedQuestion] = Field(default_factory=list)
    escalations: list[Escalation] = Field(default_factory=list)
    slack_output: str = Field(default="", description="Formatted Slack message")
    email_output: str = Field(default="", description="Formatted email summary")
    processing_metadata: dict = Field(
        default_factory=dict,
        description="Metadata: model used, token counts, latency",
    )


class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str
    detail: str
    suggestions: list[str] = Field(default_factory=list)
