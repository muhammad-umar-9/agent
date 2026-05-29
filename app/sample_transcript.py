"""
Sample meeting transcript for demo purposes.
Realistic, messy, with crosstalk and various signals for the agent to parse.
"""

SAMPLE_TRANSCRIPT = """\
[Meeting: Weekly Product Sync — May 26, 2026, 10:00 AM]

Sarah Chen: Alright everyone, let's get started. We have a lot to cover today. Mike, can you give us the sprint update?

Mike Rodriguez: Yeah sure. So, uh, the backend migration is about 70% done. We hit a blocker with the database schema — the legacy tables have some weird foreign key constraints that don't map cleanly to the new ORM.

Sarah Chen: How bad is it? Are we talking days or weeks?

Mike Rodriguez: I think... maybe three to four days if I focus on it. But I also need to finish the API rate limiter, which was supposed to be done last sprint.

Priya Sharma: Can I jump in? The rate limiter is actually blocking my work on the dashboard. Without it, I can't test the real-time data feeds properly.

Sarah Chen: Okay, so Mike, the rate limiter should be your top priority then. Can you get that done by Wednesday?

Mike Rodriguez: Wednesday is tight but... yeah, I can do Wednesday if I push the schema work to next week.

Sarah Chen: Let's do that. Rate limiter by Wednesday. The schema migration can wait.

[crosstalk]

David Park: Sorry, I was on mute — what about the customer-facing docs? The support team has been asking about the new API endpoints and I keep telling them "soon."

Sarah Chen: Good point. Who was supposed to handle the docs?

Mike Rodriguez: I thought Priya was doing it?

Priya Sharma: No, I said I could review them, not write them. I don't even know the new endpoints that well.

David Park: Well, someone needs to own this. We've been going back and forth for two weeks.

Sarah Chen: Okay let me think... David, you know the support angle. Can you draft the initial docs and Mike can review for technical accuracy?

David Park: I mean... I can try, but I'm also swamped with the customer onboarding automation. When do you need them?

Sarah Chen: Let's say end of next week? Friday the 5th?

David Park: [sighs] Alright, I'll figure it out.

Priya Sharma: Quick question — are we still planning to support the v1 API after the migration? Some enterprise clients are on it and I'm not sure we've decided.

Sarah Chen: That's a really good question. I actually don't know. We should probably check with the enterprise team before making that call.

Mike Rodriguez: I heard from Alex that they want at least 6 months of overlap, but that was informal. Nothing confirmed.

Sarah Chen: Let's not make assumptions. Priya, can you set up a meeting with the enterprise team to get a definitive answer? Try to do it this week if possible.

Priya Sharma: Sure, I'll reach out to Alex and cc you.

David Park: One more thing — the monitoring dashboard. I noticed the error rate alerts haven't been working since last Thursday. Anyone know what happened?

Mike Rodriguez: Oh that might be me... I was refactoring the alerting pipeline and I might have accidentally disabled some webhooks. Let me check after this meeting.

Sarah Chen: Mike, please fix that today if possible. We can't be flying blind on errors.

Mike Rodriguez: Yeah, on it.

Sarah Chen: Okay, let me also bring up the Q3 roadmap. I had a call with the VP yesterday and she wants us to present our priorities at the all-hands next Monday. I'll draft the slides but I need input from each of you by Thursday.

Priya Sharma: What kind of input? Like our individual project updates?

Sarah Chen: Yes, plus any resource requests or risk flags. Just a short paragraph each.

David Park: Can do.

Mike Rodriguez: Sure.

Sarah Chen: Great. I think that covers everything. Oh wait — one more thing. The new hire starts next Monday. Lisa... something. Lisa Park? No relation to you, David. [laughs] Can someone be her onboarding buddy for the first week?

David Park: I can do it. I remember how lost I was my first week.

Sarah Chen: Perfect. Thanks David. Alright everyone, let's wrap up. Good meeting.\
"""
