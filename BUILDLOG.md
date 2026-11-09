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

## Phase 3: Review workflow and scheduling

**Where AI helped**
- Proposed the allowed moves and wrote the review service and routes:
  approve is draft -> approved only; reject is draft or approved -> rejected;
  edit is draft or approved -> draft with the new text validated first;
  rejected and published are final.
- Wrote the first version of scheduling: a slot ties one approved variant to
  one future time.

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
- Scheduling refuses anything that is not approved (409 naming the status)
  and any time in the past (422). Times are stored as UTC in one fixed
  format so the worker can compare them reliably.
- A UNIQUE index on `slots(variant_id, scheduled_at)` lets the database
  decide, so a double click returns the same slot with `created: false`. Two
  slots for the same variant and time would have two idempotency keys, and so
  two posts.

## Phase 4: Adapter layer

**Where AI helped**
- Wrote the first version of the `SocialPublisher` interface, the registry
  that picks an adapter by configuration (`PUBLISH_ADAPTER_<PLATFORM>`), the
  two mock adapters, and the real Discord adapter that posts through a
  webhook.

**What went wrong, and what I did**
- My plan was to publish to Telegram for real. When I tried it, 
  `api.telegram.org` was unreachable from my network, so there was no way to
  prove a real publish. I switched the real target to a Discord webhook
  instead, which I could reach and could check by opening the channel.
- The platform that was called `telegram` in my early work is now `discord`.
  Its tone limits were the same, so the older evidence entries still show the
  right behaviour, and each of those entries carries a note saying so.

**What I decided myself**
- The real target is Discord, not Telegram, for the network reason above. The
  Discord message limit I use is 2000 characters.
- The Discord webhook URL lives only in `.env`, which is git-ignored.
  `.env.example` holds a placeholder.
- The mock table is deliberately not UNIQUE on the idempotency key, so a
  duplicate send would show up as two rows instead of being hidden by the
  database.

**What I learned**
- Swapping `PUBLISH_ADAPTER_DISCORD=mock_x` publishes the same campaign
  through a mock with no code change outside the adapters. That is the proof
  that the interface is a real seam.

## Phase 5: Idempotent publish

**Where AI helped**
- Wrote the publish service: claim a `publishes` row first (UNIQUE idempotency
  key `v<variant>:s<slot>`), then send, then record `succeeded`.

**What I learned**
- Publishing the same slot twice sends once. The second call cannot claim the
  row, so it returns the original result with `sent_now: false` and the note
  "not sent: already handled".
- I proved this with the mock and with a live Discord channel: the message
  exists in the channel and the second call sent nothing.
- After a successful publish the variant is `published`, and approving it
  again is a 409, so it can never be put back in the scheduler's path.

## Phase 6: Worker and crash recovery

**Where AI helped**
- Wrote the polling worker, `seed.py` (six approved slots due immediately),
  and the stale-publish recovery. On restart, a publish still `publishing`
  after `STALE_AFTER_SECONDS` is looked up by its idempotency key. If the post
  exists, the publish is marked `succeeded` and a `recovered` attempt is
  written, without sending again.
- Drafted the Probe 5 entry in EVIDENCE.md section 6 from the logs and
  database output I ran and pasted.

**What went wrong, and what I did**
- My first Probe 5 attempt proved nothing. I pressed Ctrl+C after the batch
  had already finished, so nothing was ever stopped mid-publish. My next
  normal run also finished all six slots with no crash. The mock publishes
  instantly, so there was no window to interrupt.
- Fix: a `MOCK_PUBLISH_DELAY_SECONDS=4` setting so each publish takes four
  seconds, and a Ctrl+C right after `slot 2 -> succeeded`, while slot 3 was
  mid-publish. I also had to delete the database first, because old finished
  slots would have muddied the counts.
- `STALE_AFTER_SECONDS` was set to 5, longer than the 4-second delay. If it
  were shorter, a slow publish that was still running would look abandoned,
  get recovered, and be published a second time.
- AI gave me a PowerShell one-liner with escaped double quotes to list the
  database tables. PowerShell removed the escapes and it failed with a
  SyntaxError. The fix was a version with single quotes only.
- The worker log shows local time (UTC+5) and the database stores UTC, so I had
  to convert before I could line up the crash with slot 3's timestamps.
  `23:17:28` in the log is `18:17:28` in the database.

**What I learned**
- If a worker crashes after the post is sent but before it is marked
  `succeeded`, the slot is not lost and not sent twice. The proof is two
  things together: a `recovered` attempt (the crash and recovery really
  happened) and exactly one `mock_posts` row for `v3:s3` (nothing was sent
  twice).
- With the mock, the post can be looked up by its idempotency key. Discord
  cannot be asked that, so for the real adapter the same crash is designed to
  end as `uncertain`, so a person decides. Retrying risks a duplicate post;
  marking it succeeded risks hiding a lost one. I have not run that path, and
  EVIDENCE.md says so.
- Probe 5 stops the worker politely with Ctrl+C, covers one crash window, and
  uses one worker. A forced kill, a crash before the send, and two workers are
  not tested, and EVIDENCE.md lists these limits.
- `.gitignore` only stops new files from being added. The proof that nothing
  secret is in the repository is `git ls-files`, which shows only
  `.env.example`.
- "Your branch is up to date with origin/main" only means my commits are
  pushed. It says nothing about files I have not committed.

## Known limitations I found (also listed in the README)
- Discord cannot tell me whether a post was made, so a crash in the window
  between sending and recording ends as `uncertain` for a person to decide.
- The service returns errors as `{"error": ...}`, but FastAPI's own
  validation errors come back as `{"detail": ...}`. There are two error
  shapes, and I have not unified them.
- The worker retries a misconfigured slot on every poll instead of backing
  off.
- Fetching a URL a user supplies is unsafe on a public server, because a
  caller could point it at internal addresses. Fine on my own machine, not
  fine to deploy as it is.

## Still to log
- README and the final walk through the Requirements boxes