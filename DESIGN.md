# Social Media Studio: Design

## Problem
Turn one blog post into per-platform social variants, have a human approve
each one, and publish each approved variant exactly once at a scheduled time,
even under retries and worker crashes.

## Layers
HTTP routes (thin) -> service layer (all rules) -> SocialPublisher interface
-> adapters -> database access underneath.
- The service layer enforces the approval rule when scheduling AND again
  right before sending, because a variant can be edited back to draft in
  between.
- The service layer only talks to the `SocialPublisher` interface, never to
  a platform directly.

## Data model
- posts(id, source_url, body_markdown, created_at): the single source of
  truth. All generation reads only from here.
- variants(id, post_id, platform, text, status, created_at)
  status: draft | approved | rejected | published
- slots(id, variant_id, scheduled_at)
- publishes(id, variant_id, slot_id, idempotency_key UNIQUE, status,
  started_at, platform_message_id)
  status: pending | in_progress | succeeded | failed | uncertain
- publish_attempts(id, publish_id, result, error, attempted_at): one row per
  try, never overwritten.

`publishes` is one row per publish (variant + slot). `publish_attempts` is
one row per try.

## Idempotency strategy
- Key = variant_id + slot_id, stored in `publishes.idempotency_key` with a
  UNIQUE constraint.
- Insert the publish row as `in_progress` BEFORE calling the platform.
  Update to `succeeded` or `failed` after.
- The UNIQUE constraint stops two workers claiming the same publish.
- A retry of a key already `succeeded` skips posting and returns the
  original result.

## Failure handling
| Outcome | Did it post? | Action |
|---|---|---|
| 429 with retry_after | No | Wait retry_after seconds, then retry |
| Other 4xx (bad token, bad request) | No | Mark `failed`, do not retry blindly |
| Timeout or crash mid-send | Unknown | Mark `uncertain`, verify or flag for a human |

A row stuck in `in_progress` longer than STALE_AFTER_SECONDS (300) is
treated as stale and moved to `uncertain`. A duplicate post is worse than a
missed one, so when unsure the system holds back rather than re-sends.
Telegram allows about 1 message per second per chat, so two variants due in
the same slot are sent with a delay between them.

## Scheduler
A worker loop that polls the database every POLL_INTERVAL_SECONDS (5) for
slots whose `scheduled_at` has passed and whose publish is not yet
`succeeded`. Because all state lives in the database, a restarted worker
resumes safely, and the idempotency key prevents duplicates.

Chosen over a scheduling library because all state already lives in the
database, restart safety is easy to prove, and the logic is easy to explain.

## Constraint profiles
Enforced by code in the service layer. A variant that breaks a rule is
blocked before review, with an error naming the broken rule. Tone rules are
measurable proxies, since code cannot judge human tone.

| Platform | Max length | Max hashtags | Tone rules |
|---|---|---|---|
| X-style | 280 chars | 2 | max 1 exclamation mark; no ALL-CAPS words over 4 letters; no banned words |
| LinkedIn-style | 2000 chars | 5 | max 1 exclamation mark; no ALL-CAPS words; no banned words |
| Telegram | 4096 chars | 3 | max 3 exclamation marks; no ALL-CAPS words over 4 letters |

Banned words (starter list): "guaranteed", "act now", "click here".
Telegram's 4096 limit applies to message text, so variants are sent as plain
text.

## Adapters
`SocialPublisher.publish(variant) -> PublishResult` is the one interface.
- TelegramPublisher (real)
- MockXPublisher and MockLinkedInPublisher (record what they would post in
  the database and show a preview)

Adapter choice comes from configuration (for example
PUBLISH_ADAPTER_X=telegram or mock_x), so swapping adapters changes config,
not business logic.

## API surface
- POST /posts: ingest a URL or pasted Markdown
- POST /posts/{id}/variants/generate
- POST /variants/{id}/approve and /reject
- PATCH /variants/{id}: edit text; the variant returns to draft
- POST /variants/{id}/schedule: 409 with a message if the variant is not
  approved
- GET /publishes and GET /publishes/{id}/attempts

## Non-goals
No image generation, no multi-user accounts, no analytics, and no
publishing to real X, LinkedIn, or Instagram accounts.