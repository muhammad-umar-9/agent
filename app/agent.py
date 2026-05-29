"""
Core agent logic — Groq API interaction and transcript processing.

This module contains the carefully engineered prompt and the async
function that calls Groq to extract structured meeting data.
Uses the Groq SDK (OpenAI-compatible).
"""

from __future__ import annotations

import json
import time
import logging
import asyncio
from typing import Any

from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

# ── Configure Groq client ────────────────────────────────────────────────────

client = Groq(api_key=settings.groq_api_key)

# ── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert meeting analyst agent. Your task is to process raw meeting \
transcripts — which may contain crosstalk, filler words, unclear speakers, and \
messy formatting — and extract structured, actionable information.

## Your Extraction Targets

You must extract EXACTLY these categories:

### 1. MEETING TITLE
Infer a short, descriptive title for this meeting (max 10 words).

### 2. PARTICIPANTS
List all speakers/participants identified in the transcript.

### 3. DECISIONS
Statements where the group agreed on something. Look for signals like:
- "We agreed to…", "Let's go with…", "The decision is…"
- Consensus moments, even if implicit ("Everyone nodded", "No objections")
- Final choices after debate

### 4. ACTION ITEMS
Tasks assigned to specific people. For each, extract:
- **task**: What needs to be done (be specific, not vague)
- **owner**: The person responsible. If unclear, set to "Unknown"
- **deadline**: When it's due. If not stated, set to "Not specified"
- **priority**: "high", "medium", or "low" based on urgency cues (tone, words like \
"urgent", "critical", "top priority", "ASAP", or blocking other work = high; \
normal work items = medium; nice-to-haves = low)

### 5. UNRESOLVED QUESTIONS
Topics raised but not resolved. Things that need follow-up:
- Questions someone asked but nobody answered
- Topics deferred to a later meeting
- Disagreements that weren't settled

### 6. MEETING SUMMARY
A concise 3-line summary capturing:
- Line 1: What the meeting was about (purpose/topic)
- Line 2: Key outcomes or decisions
- Line 3: Critical next steps

## Confidence Scoring

For EVERY extracted item, assign a confidence score (0.0 to 1.0):
- **0.9–1.0**: Crystal clear, explicitly stated
- **0.7–0.89**: Strongly implied, high confidence
- **0.5–0.69**: Reasonable inference, but some ambiguity
- **0.3–0.49**: Weak signal, might be wrong
- **0.0–0.29**: Very uncertain, flagging just in case

## Speaker Handling
- If speaker names are identified, use them
- If a speaker is unclear, use "Unknown Speaker"
- Normalize name variations (e.g., "Sarah", "S.", "Sarah K." → use the most complete form)

## Critical Rules
1. NEVER invent information not in the transcript
2. NEVER silently drop items — if confidence is low, include them with a low score
3. Be specific in task descriptions — "fix the bug" is bad, "fix the login timeout \
bug in the auth service" is good
4. If the transcript is too short or noisy to extract anything meaningful, say so explicitly

## Output Format

Return a single valid JSON object (no markdown fencing, no extra text) with this \
exact structure:

{
  "meeting_title": "Short Meeting Title",
  "participants": ["Person A", "Person B"],
  "summary": "Line 1\\nLine 2\\nLine 3",
  "decisions": [
    {
      "text": "decision statement",
      "context": "why this was decided",
      "confidence": 0.95
    }
  ],
  "action_items": [
    {
      "task": "specific task description",
      "owner": "Person Name",
      "deadline": "Friday EOD",
      "priority": "high",
      "confidence": 0.85
    }
  ],
  "unresolved": [
    {
      "question": "the unresolved question",
      "context": "why it's unresolved",
      "suggested_owner": "Person Name",
      "confidence": 0.7
    }
  ]
}

Return ONLY the JSON object. No preamble, no explanation, no markdown code fences.
"""

# ── Agent Function ───────────────────────────────────────────────────────────

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1.5


def _clean_json_text(raw_text: str) -> str:
    """Strip markdown fences and other noise from the raw model output."""
    text = raw_text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()

    # Find the first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace : last_brace + 1]

    return text


async def process_transcript(transcript: str) -> dict[str, Any]:
    """
    Send the transcript to Groq and parse the structured extraction.

    Returns a dict matching the JSON schema above, plus metadata.
    Raises ValueError if the model returns unparseable output.
    Retries up to MAX_RETRIES times on transient failures.
    """
    user_message = (
        "Here is the meeting transcript to process:\n\n"
        "--- TRANSCRIPT START ---\n"
        f"{transcript}\n"
        "--- TRANSCRIPT END ---\n\n"
        "Extract the meeting title, participants, all decisions, action items, "
        "unresolved questions, and the 3-line summary. Return ONLY valid JSON."
    )

    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            start_time = time.monotonic()

            # Groq SDK is synchronous, so run in a thread
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=4096,
            )

            elapsed = round(time.monotonic() - start_time, 2)

            # Extract the text content
            raw_text = response.choices[0].message.content.strip()
            cleaned = _clean_json_text(raw_text)

            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.error(
                    "Model returned invalid JSON (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    raw_text[:500],
                )
                last_error = ValueError(
                    f"Agent returned unparseable output. JSON error: {e}. "
                    f"Raw output preview: {raw_text[:200]}"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                    continue
                raise last_error from e

            # Attach processing metadata
            usage = response.usage
            result["_metadata"] = {
                "model": settings.groq_model,
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "latency_seconds": elapsed,
                "attempts": attempt + 1,
            }

            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                "Groq API error (attempt %d/%d): %s",
                attempt + 1,
                MAX_RETRIES + 1,
                e,
            )
            last_error = e
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                continue

    # If we exhausted retries
    raise last_error or RuntimeError("All retry attempts failed")
