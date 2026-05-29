"""
FastAPI application — Meeting-to-Action Pipeline.

Endpoints:
  GET  /          → serves the frontend UI
  POST /process   → accepts transcript, returns structured extraction
  POST /upload    → accepts file upload (.txt, .md, .vtt, .srt)
  GET  /sample    → returns a sample transcript for demo
  GET  /health    → health check for deployment
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent import process_transcript
from app.config import settings
from app.escalation import run_escalation_checks
from app.formatters import format_email, format_slack
from app.models import (
    ActionItem,
    Decision,
    ErrorResponse,
    Priority,
    ProcessingResult,
    TranscriptRequest,
    UnresolvedQuestion,
)
from app.sample_transcript import SAMPLE_TRANSCRIPT

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description="Automates meeting transcript → structured action items with escalation logic.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Helper: process and build response ───────────────────────────────────────

async def _process_and_respond(transcript: str) -> ProcessingResult:
    """Shared logic for processing a transcript and building the response."""

    # ── Process with Gemini ──────────────────────────────────────────────
    start = time.monotonic()
    raw_result = await process_transcript(transcript)
    total_time = round(time.monotonic() - start, 2)

    # ── Parse into Pydantic models ───────────────────────────────────────
    decisions = [Decision(**d) for d in raw_result.get("decisions", [])]

    # Parse action items with priority handling
    action_items = []
    for a in raw_result.get("action_items", []):
        # Normalize priority field
        priority_raw = a.get("priority", "medium").lower().strip()
        if priority_raw in ("high", "h", "urgent", "critical"):
            a["priority"] = "high"
        elif priority_raw in ("low", "l", "nice to have", "optional"):
            a["priority"] = "low"
        else:
            a["priority"] = "medium"
        action_items.append(ActionItem(**a))

    unresolved_items = [
        UnresolvedQuestion(**u) for u in raw_result.get("unresolved", [])
    ]
    summary = raw_result.get("summary", "No summary generated.")
    meeting_title = raw_result.get("meeting_title", "Untitled Meeting")
    participants = raw_result.get("participants", [])

    # ── Run escalation checks ────────────────────────────────────────────
    escalations = run_escalation_checks(decisions, action_items, unresolved_items)

    # ── Format outputs ───────────────────────────────────────────────────
    slack_output = format_slack(
        summary, decisions, action_items, unresolved_items, escalations,
        meeting_title=meeting_title, participants=participants,
    )
    email_output = format_email(
        summary, decisions, action_items, unresolved_items, escalations,
        meeting_title=meeting_title, participants=participants,
    )

    # ── Build response ───────────────────────────────────────────────────
    metadata = raw_result.get("_metadata", {})
    metadata["total_processing_seconds"] = total_time
    metadata["escalation_count"] = len(escalations)

    return ProcessingResult(
        meeting_title=meeting_title,
        participants=participants,
        summary=summary,
        decisions=decisions,
        action_items=action_items,
        unresolved=unresolved_items,
        escalations=escalations,
        slack_output=slack_output,
        email_output=email_output,
        processing_metadata=metadata,
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the single-page frontend."""
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint for deployment platforms."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/sample")
async def get_sample():
    """Return a sample meeting transcript for demo purposes."""
    return {"transcript": SAMPLE_TRANSCRIPT}


@app.post(
    "/process",
    response_model=ProcessingResult,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    },
)
async def process_meeting(request: TranscriptRequest):
    """
    Process a meeting transcript and return structured extraction.

    Accepts raw transcript text and returns:
    - Meeting title and participants
    - Decisions made
    - Action items with owners, deadlines, and priorities
    - Unresolved questions
    - Escalations (items needing human review)
    - Formatted Slack and Email outputs
    """
    transcript = request.transcript.strip()

    # ── Input validation ─────────────────────────────────────────────────
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Empty transcript",
                "detail": "The transcript is empty or contains only whitespace.",
                "suggestions": [
                    "Paste the actual meeting transcript text",
                    "Ensure the transcript has at least a few sentences",
                ],
            },
        )

    if len(transcript) < settings.min_transcript_length:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Transcript too short",
                "detail": (
                    f"Transcript is {len(transcript)} characters. "
                    f"Minimum is {settings.min_transcript_length}."
                ),
                "suggestions": [
                    "Provide a longer transcript with meaningful content",
                    "Include at least several exchanges between participants",
                ],
            },
        )

    if len(transcript) > settings.max_transcript_length:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Transcript too long",
                "detail": (
                    f"Transcript is {len(transcript):,} characters. "
                    f"Maximum is {settings.max_transcript_length:,}."
                ),
                "suggestions": [
                    "Split into smaller segments",
                    "Trim irrelevant sections before processing",
                ],
            },
        )

    # ── Process ──────────────────────────────────────────────────────────
    try:
        return await _process_and_respond(transcript)
    except ValueError as e:
        logger.error("Agent parsing error: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Agent processing error",
                "detail": str(e),
                "suggestions": [
                    "Try again — the agent may produce valid output on retry",
                    "Simplify or clean up the transcript",
                ],
            },
        )
    except Exception as e:
        logger.exception("Unexpected error during processing")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal processing error",
                "detail": f"An unexpected error occurred: {type(e).__name__}: {e}",
                "suggestions": [
                    "Check your API key configuration",
                    "Try again in a few moments",
                ],
            },
        )


@app.post(
    "/upload",
    response_model=ProcessingResult,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    },
)
async def upload_and_process(file: UploadFile = File(...)):
    """
    Upload a transcript file and process it.
    Supports .txt, .md, .vtt, and .srt files.
    """
    # Validate file type
    allowed_extensions = {".txt", ".md", ".vtt", ".srt", ".text"}
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Unsupported file type",
                "detail": f"File '{filename}' has extension '{ext}'. Allowed: {', '.join(sorted(allowed_extensions))}",
                "suggestions": [
                    "Upload a .txt, .md, .vtt, or .srt file",
                    "Or paste the transcript text directly",
                ],
            },
        )

    # Read file content
    try:
        content = await file.read()
        transcript = content.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "File encoding error",
                "detail": "Could not read the file. Ensure it is UTF-8 encoded.",
                "suggestions": ["Re-save the file as UTF-8", "Paste the text directly"],
            },
        )

    if not transcript or len(transcript) < settings.min_transcript_length:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "File content too short",
                "detail": f"File contains only {len(transcript)} characters.",
                "suggestions": ["Upload a file with more meeting content"],
            },
        )

    if len(transcript) > settings.max_transcript_length:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "File content too long",
                "detail": f"File is {len(transcript):,} characters. Maximum is {settings.max_transcript_length:,}.",
                "suggestions": ["Split the file or trim irrelevant sections"],
            },
        )

    try:
        return await _process_and_respond(transcript)
    except ValueError as e:
        logger.error("Agent parsing error on file upload: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Agent processing error",
                "detail": str(e),
                "suggestions": ["Try again — the agent may produce valid output on retry"],
            },
        )
    except Exception as e:
        logger.exception("Unexpected error processing uploaded file")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal processing error",
                "detail": f"{type(e).__name__}: {e}",
                "suggestions": ["Check API key configuration", "Try again"],
            },
        )


# ── Global exception handler ────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — never expose stack traces."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again.",
            "suggestions": [],
        },
    )
