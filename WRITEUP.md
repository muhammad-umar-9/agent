# Meeting-to-Action Pipeline — Write-Up

## Why This Problem?

Every meeting generates follow-ups that someone has to manually extract: who's doing what, by when, and what was left unresolved. In practice, **project managers spend 30–60 minutes after every meeting** writing these up — and still miss things. I've watched teams lose action items, forget decisions, and re-debate settled topics because the post-meeting summary was incomplete or never written.

This problem is worth solving because it's **universal** (every team has meetings), **repetitive** (same extraction pattern every time), and **high-stakes** (missed action items derail projects).

## Who Is the User?

**Project managers, team leads, and scrum masters** — anyone who runs meetings and is responsible for distributing action items afterward. They paste a transcript (from Zoom, Teams, Otter.ai, or manual notes) and get structured, assignable output in seconds.

## Architecture

```
[Transcript Input] → [FastAPI Backend] → [Gemini Agent] → [Structured JSON]
                                                                  ↓
                                                    [Escalation Engine]
                                                          ↓
                                              [Slack + Email Formatters]
```

**Agentic decisions the system makes autonomously:**
- **Extracts** decisions, action items (with owners, deadlines, priorities), and unresolved questions from messy, noisy transcripts
- **Assigns confidence scores** (0.0–1.0) to every extracted item based on how clearly it was stated
- **Infers priority** (high/medium/low) from urgency cues in the conversation
- **Identifies participants** and normalizes name variations automatically
- **Generates** a meeting title from context

**When it escalates to a human (8 rules):**
1. No clear owner assigned to an action item
2. Missing or vague deadline ("soon", "ASAP", "TBD")
3. Ownership conflict — two people seem to own the same task
4. Low confidence — the agent isn't sure something is real
5. Ambiguous deadline language
6. High-priority item without a specific deadline
7. Overloaded owner — one person has 3+ action items
8. Transcript too noisy to extract meaningful data

**Failure handling:**
- Retry with exponential backoff on API errors (up to 2 retries)
- Input validation with helpful error messages and suggestions
- Robust JSON parsing that handles markdown fences and malformed output
- Global exception handler that never exposes stack traces

## What I Learned

1. **Prompt engineering is the entire product** — the quality of extraction lives or dies by the system prompt. Structured output format, confidence scoring instructions, and explicit "never invent" rules were critical.
2. **Escalation rules are the differentiator** — anyone can call an LLM. The value is in the 8 rule-based checks that flag what needs human attention. This is what makes it *agentic* vs. just "summarize text."
3. **Confidence scores unlock trust** — users trust the system more when they can see *how sure* it is. A 95% confidence item feels reliable; a 45% item says "double-check me."
4. **Messy input is the real test** — clean transcripts are easy. Real meetings have crosstalk, filler words, and people saying "someone should do that" without specifying who. Handling this gracefully required careful prompt design and escalation logic.
