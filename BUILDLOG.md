# Build Log (AI usage)

I used Claude as a tutor and pair-programmer while building this capstone.
It explained each design decision through checkpoint questions, and it wrote
the first version of most code and docs, which I ran, tested, and committed.
This log records where AI helped, where it was wrong, and what I changed.

## Phase 1: Design

**Where AI helped**
- Walked me through the design decisions one at a time: idempotency key built
  from variant + slot, writing an `in_progress` row BEFORE calling the
  platform, a stale `in_progress` row meaning "unknown" (not "failed"), the
  approval check living in the service layer and running twice, and the
  `SocialPublisher` interface as the seam between app and platform.
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

## Phase 2: Database, ingestion, validation, generation

**Where AI helped**
- Proposed the folder layout (routes / services / adapters / db), the SQLite
  schema (CHECK constraints on status, UNIQUE on idempotency_key, indexes),
  the connection helper (WAL mode, busy timeout, foreign keys ON), and the
  first versions of `validate_variant`, the ingestion service, the template
  generator, and the routes.
- Recommended SQLite over PostgreSQL. I first mixed up the answer letters,
  then agreed with the reasoning: nothing to install, small scale, and the
  UNIQUE constraint works the same.

**Where AI was wrong or sloppy, and what I did**
- It gave me a Python call (`ingest_post(...)`) to type straight into
  PowerShell, which failed. Python code has to run through `python -c`.
- Its first curl command for POST /posts failed because PowerShell mangled the
  quotes in the JSON body. We switched to piping the body in with
  `--data-binary "@-"`. The server was fine; the 422 it returned for the
  broken JSON was correct behaviour.
- Its first validator test used 300 capital letters, which accidentally broke
  a third rule (ALL-CAPS). I re-ran it with lowercase to prove just the two
  rules I meant to test. It also printed all 300 letters in the error message,
  which is ugly; noted as a possible cleanup.
- Its checkpoint example title `BREAKING NEWS!!!` would have been blocked on
  ALL three platforms, not "some", so it proved less than intended. We used
  `Big news!!` instead, which blocks X and LinkedIn but passes Telegram.
- I ran a test from the `app/db` folder and got `ModuleNotFoundError: No
  module named 'app'`. Python commands and uvicorn must run from the repo
  root. That was my mistake, not a code bug.
- A test command included a stray `Out-Null` line that did nothing.

**What I changed or learned**
- Made the busy timeout configurable:
  `int(os.getenv("BUSY_TIMEOUT_SECONDS", 5))`, and added both new variables
  to `.env.example`.
- SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set on every
  connection. `CREATE TABLE IF NOT EXISTS` makes the init script safe to run
  twice.
- The validator returns EVERY broken rule so a user can fix all problems in
  one pass. Code can only check measurable proxies for tone (exclamation
  marks, ALL-CAPS, banned words), not real tone.
- Validation runs on generation, on every edit, and again at approval,
  because text can change after the first check (time of check vs. time of
  use).
- A variant that breaks a rule is blocked with a named error, never silently
  trimmed or saved as a draft.
- Error codes: 422 means the caller sent something wrong, 502 / 504 mean the
  other site failed or timed out, and 500 is only for my own bugs. A 500 must
  never be used for bad input.
- Typed exceptions with a `status_code`, all subclasses of `ServiceError`,
  and ONE handler in `main.py`, so routes have no try/except and the service
  layer never imports FastAPI.
- Ingestion rejects posts over 100,000 characters instead of trimming them.
- Generation reads only the stored post. Calling generate twice skips any
  platform that already has a non-rejected variant, so a double click creates
  no duplicates, but a rejected platform can be regenerated.

## Phase 3: Review workflow (in progress)

**Where AI helped**
- Proposed the allowed moves and wrote the review service and routes:
  approve is draft -> approved only; reject is draft or approved -> rejected;
  edit is draft or approved -> draft with the new text validated first;
  rejected and published are final.

**What I learned**
- A request for a state change that the current state does not allow is a
  409 Conflict with a message that names the current state. It is not a 404
  (the variant exists) and not a 500.
- The "is it still a draft?" check lives inside the `UPDATE ... WHERE status
  IN (...)` and I check `rowcount`, so the check and the change happen as one
  step. Two reviewers acting at the same moment cannot both succeed. This is
  the same idea as the UNIQUE idempotency key.
- Setting a published variant back to approved would let the scheduler
  publish it again, which would undo the idempotency guarantee.

## Still to log
- Scheduling (slots, the refusal of unapproved variants)
- Adapters and idempotent publish
- Worker, crash-restart proof, and publish history