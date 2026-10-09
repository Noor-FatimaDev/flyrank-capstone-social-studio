# Build Log (AI usage)

I used Claude as a tutor and pair-programmer while building this capstone.
This log records where it helped, where it was wrong, and what I changed.

## Phase 1: Design

**Where AI helped**
- Walked me through the design decisions one at a time with checkpoint
  questions: idempotency key built from variant + slot, writing an
  `in_progress` row BEFORE calling the platform, a stale `in_progress` row
  meaning "unknown" (not "failed"), the approval check living in the service
  layer and running twice, and the `SocialPublisher` interface as the seam.
- Drafted the first version of DESIGN.md, which I reviewed and edited.

**Where AI was wrong or overstated, and what I did**
- It first said GitHub had pre-created my `.gitignore` and `README.md`. That
  was wrong: they were my own new files, just uncommitted.
- It first described retries as "new rows in publish_attempts", which did not
  fit a UNIQUE idempotency key. We fixed it: one `publishes` row per
  (variant, slot), one `publish_attempts` row per try.
- It suggested putting the design doc in `docs/`; I kept DESIGN.md at the repo
  root so a reviewer can find it.
- It made the "evaluator will ask about 2-3 lines" rule sound like a live
  interview. The brief only says review is asynchronous through the portal,
  so I treat it as "my docs must show I understand my code."

**What I decided myself**
- Scheduler: a database-polling worker instead of a scheduling library,
  because restart safety is easy to prove and it is easier to explain.
- LinkedIn-style max length: changed from 1300 to 2000 characters. X-style
  stays at 280.
- Checked Telegram's 4096-character message limit against Telegram's own
  documentation instead of trusting the AI's number.

## Phase 2: Database and validation (in progress)

**Where AI helped**
- Proposed the folder layout (routes / services / adapters / db), the SQLite
  schema (CHECK constraints on status, UNIQUE on idempotency_key, indexes),
  the connection helper (WAL mode, busy timeout, foreign keys ON), and the
  first version of `validate_variant`.

**What I changed or learned**
- Made the busy timeout configurable: `int(os.getenv("BUSY_TIMEOUT_SECONDS", 5))`
  and added both new variables to `.env.example`.
- Learned SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set on
  every connection, and that `IF NOT EXISTS` makes the init script safe to
  run more than once.
- Learned the validator should return EVERY broken rule so a user can fix all
  problems in one pass, and that code can only check measurable proxies for
  tone (exclamation marks, ALL-CAPS, banned words), not real tone.

## Still to log
- Ingestion (URL fetch, error codes 422 / 502 / 504)
- Variant generation
- Review workflow endpoints
- Adapters and idempotent publish
- Worker, crash-restart proof, and publish history