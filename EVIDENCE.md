# Evidence

One proof per requirement box. Every command and result below was run
locally from the repo root with the virtual environment active.

## 1. Ingestion
**Status:** service and `POST /posts` route done.

### A valid pasted post is stored and its id returned
Command:
```
python -c "from app.services.ingestion import ingest_post; print(ingest_post(markdown='# Hello\n\nA test post.'))"
```
Result:
```
2
```
Meaning: a valid post is accepted and stored, and the new post's id is
returned. The id is 2 because an earlier test post already existed.

### Upstream failure is a clean error, not a crash
Command:
```
python -c "from app.services.ingestion import ingest_post; ingest_post(url='https://localhost:9')"
```
Result (last line of the traceback):
```
app.services.ingestion.UpstreamError: Could not fetch the URL: ConnectError
```
Meaning: the low-level `httpx.ConnectError` (connection refused) was caught
and re-raised as my own `UpstreamError`, which carries `status_code = 502`.
Nothing is stored when the fetch fails.

### An oversized post is rejected with a descriptive error and nothing is stored
Command:
```
python -c "from app.services.ingestion import ingest_post; ingest_post(markdown='a' * 100001)"
```
Result (last line of the traceback):
```
app.services.ingestion.PostTooLongError: The post is too long (100001 > 100000 characters)
```
Meaning: the post is one character over the 100,000 limit, so it is
rejected before anything is written to the database. The exception carries
`status_code = 422`.

### POST /posts over HTTP: success, upstream failure, and bad input
Command (success):
```
'{"markdown": "# Hello\n\nA test post."}' | curl.exe -i -X POST http://127.0.0.1:8000/posts -H "Content-Type: application/json" --data-binary "@-"
```
Result: HTTP/1.1 201 Created, body `{"id":3}`

Command (upstream failure):
```
'{"url": "https://localhost:9"}' | curl.exe -i -X POST http://127.0.0.1:8000/posts -H "Content-Type: application/json" --data-binary "@-"
```
Result: HTTP/1.1 502 Bad Gateway, body `{"error":"Could not fetch the URL: ConnectError"}`

Command (bad input, both url and markdown):
```
'{"url": "https://example.com", "markdown": "x"}' | curl.exe -i -X POST http://127.0.0.1:8000/posts -H "Content-Type: application/json" --data-binary "@-"
```
Result: HTTP/1.1 422 Unprocessable Content, body `{"error":"Send exactly one of 'url' or 'markdown'"}`

Meaning: the service raises typed exceptions (all subclasses of
`ServiceError`) and one handler in `main.py` turns each into JSON with its
own status code. The route has no try/except. Malformed JSON is also
rejected with a 422, never a 500.

## 2. Constraint profiles enforced by code
**Status:** validator done and wired into variant generation, which is
idempotent and exposed at `POST /posts/{id}/variants/generate`. Not yet wired
into the edit and approve endpoints (those are not built yet).

### A rule-breaking variant is reported with every broken rule named
Command:
```
python -c "from app.services.constraints import validate_variant; print(validate_variant('x', 'a' * 300 + ' #a #b #c'))"
```
Result:
```
['length: 309 characters exceeds the x limit of 280', 'hashtags: 3 hashtags exceeds the x limit of 2']
```
Meaning: the variant breaks the length rule and the hashtag rule, and both
are reported by name in one pass.

### A valid variant passes
Command:
```
python -c "from app.services.constraints import validate_variant; print(validate_variant('x', 'Short and clean'))"
```
Result:
```
[]
```
Meaning: a valid variant returns an empty list, so nothing is blocked.

### One stored post produces different variants for different platforms
Command (fresh database, post 1 already ingested):
```
curl.exe -i -X POST http://127.0.0.1:8000/posts/1/variants/generate
```
Result: HTTP/1.1 200 OK, body
```
{"created":[{"id":1,"platform":"x","text":"Hello: A test post. #blog"},{"id":2,"platform":"linkedin","text":"Hello\n\nA test post.\n\n#blog #writing"},{"id":3,"platform":"discord","text":"Hello\n\nA test post."}],"blocked":[],"skipped":[]}
```
Meaning: generation reads only the stored post and builds a different
variant for each platform. All three pass their constraint profiles, so all
three are saved.

### Generation blocks rule-breaking variants and reports them by name
Command:
```
python -c "from app.services.ingestion import ingest_post; from app.services.generation import generate_variants; import json; pid = ingest_post(markdown='# Big news!!\n\nSomething happened today.'); print(json.dumps(generate_variants(pid), indent=2))"
```
Result (abridged):
```
created: [ telegram (id 4): "Big news!!\n\nSomething happened today." ]
blocked: [ x:        "tone: 2 exclamation marks exceeds the x limit of 1",
           linkedin: "tone: 2 exclamation marks exceeds the linkedin limit of 1" ]
```
Meaning: the title has two exclamation marks. X and LinkedIn allow only
one, so those two variants are not saved and each error names the broken
rule. Telegram allows three, so its variant passes and is saved. One
failing platform does not block the others.

Note: captured before the real target changed from Telegram to Discord. The platform now named `discord` was then called `telegram`; its tone limits were the same, so the behaviour shown is identical.

### Calling generate twice creates no duplicates
Command:
```
curl.exe -i -X POST http://127.0.0.1:8000/posts/2/variants/generate
```
Result: HTTP/1.1 200 OK, body
```
{"created":[],"blocked":[],"skipped":[{"platform":"x","reason":"a non-rejected variant already exists"},{"platform":"linkedin","reason":"a non-rejected variant already exists"},{"platform":"telegram","reason":"a non-rejected variant already exists"}]}
```
Meaning: post 2 already had all three variants from an earlier call, so the
second call created nothing and said why. A platform whose variant was
rejected can still be regenerated.

Note: captured before the real target changed from Telegram to Discord. The platform now named `discord` was then called `telegram`; its tone limits were the same, so the behaviour shown is identical.

### Generating for a post that does not exist is a clean 404
Command:
```
curl.exe -i -X POST http://127.0.0.1:8000/posts/999/variants/generate
```
Result: HTTP/1.1 404 Not Found, body `{"error":"Post 999 not found"}`
Meaning: `NotFoundError` is a `ServiceError`, so the single handler in
`main.py` returns a clean 404 instead of a 500.

### A rejected platform can be regenerated without touching the others
Command (after variant 2, post 2's LinkedIn variant, was rejected):
```
curl.exe -i -X POST http://127.0.0.1:8000/posts/2/variants/generate
```
Result: HTTP/1.1 200 OK, body
```
{"created":[{"id":5,"platform":"linkedin","text":"Hello\n\nA test post.\n\n#blog #writing"}],"blocked":[],"skipped":[{"platform":"x","reason":"a non-rejected variant already exists"},{"platform":"telegram","reason":"a non-rejected variant already exists"}]}
```
Meaning: only the platform with no live variant gets a new one. X and
Telegram still have non-rejected variants, so they are skipped and no
duplicates are created.

Note: captured before the real target changed from Telegram to Discord. The platform now named `discord` was then called `telegram`; its tone limits were the same, so the behaviour shown is identical.

## 3. Review workflow (draft / approved / rejected / published)
**Status:** approve, edit, reject and scheduling (including the refusal of
unapproved variants) proven over HTTP.

### Approving a draft works; approving it again is a 409
Commands (variant 1 is post 2's X variant, starting as a draft):
```
curl.exe -i -X POST http://127.0.0.1:8000/variants/1/approve
curl.exe -i -X POST http://127.0.0.1:8000/variants/1/approve
```
Results:
```
HTTP/1.1 200 OK
{"id":1,"post_id":2,"platform":"x","text":"Hello: A test post. #blog","status":"approved","created_at":"2026-10-10 09:55:19"}

HTTP/1.1 409 Conflict
{"error":"Variant 1 is approved; only draft variants can be approved"}
```
Meaning: only a draft can be approved. A repeat call is refused with a 409
that explains the current state, and the variant is left unchanged.

### An edit that breaks the platform rules is rejected and not saved
Command:
```
'{"text": "Edited text #a #b #c"}' | curl.exe -i -X PATCH http://127.0.0.1:8000/variants/1 -H "Content-Type: application/json" --data-binary "@-"
```
Result:
```
HTTP/1.1 422 Unprocessable Content
{"error":"hashtags: 3 hashtags exceeds the x limit of 2"}
```
Meaning: validation runs on every edit, so the three-hashtag text is
refused with the broken rule named, and the stored text is unchanged.


### A valid edit sends the variant back to draft
Command (variant 1 was approved):
```
'{"text": "Edited text #a"}' | curl.exe -i -X PATCH http://127.0.0.1:8000/variants/1 -H "Content-Type: application/json" --data-binary "@-"
```
Result:
```
HTTP/1.1 200 OK
{"id":1,"post_id":2,"platform":"x","text":"Edited text #a","status":"draft","created_at":"2026-10-10 09:55:19"}
```
Meaning: editing an approved variant replaces the text and returns it to
draft, so changed text must be reviewed and approved again before it can be
scheduled.

### Rejecting works once; rejecting again is a 409
Commands (variant 2 is post 2's LinkedIn variant):
```
curl.exe -i -X POST http://127.0.0.1:8000/variants/2/reject
curl.exe -i -X POST http://127.0.0.1:8000/variants/2/reject
```
Results:
```
HTTP/1.1 200 OK
{"id":2,"post_id":2,"platform":"linkedin","text":"Hello\n\nA test post.\n\n#blog #writing","status":"rejected","created_at":"2026-10-10 09:55:19"}

HTTP/1.1 409 Conflict
{"error":"Variant 2 is rejected; only draft or approved variants can be rejected"}
```
Meaning: a draft or approved variant can be rejected. A rejected variant is
final, and a repeat call is refused with a 409 that names its state.

### Scheduling: unapproved variants are refused, approved ones can be scheduled
Commands (variant 1 starts as a draft; run in this order):
```
'{"scheduled_at": "2026-10-12T09:00:00Z"}' | curl.exe -i -X POST http://127.0.0.1:8000/variants/1/schedule -H "Content-Type: application/json" --data-binary "@-"
curl.exe -i -X POST http://127.0.0.1:8000/variants/1/approve
'{"scheduled_at": "2026-10-12T09:00:00Z"}' | curl.exe -i -X POST http://127.0.0.1:8000/variants/1/schedule -H "Content-Type: application/json" --data-binary "@-"
```
Results:
```
HTTP/1.1 409 Conflict
{"error":"Variant 1 is draft; only approved variants can be scheduled"}

HTTP/1.1 200 OK   (approve)
{"id":1,"post_id":2,"platform":"x","text":"Edited text #a","status":"approved","created_at":"2026-10-10 09:55:19"}

HTTP/1.1 201 Created
{"slot_id":1,"variant_id":1,"scheduled_at":"2026-10-12T09:00:00Z","created":true}
```
Meaning: scheduling a draft is refused with a 4xx and an error naming the
status. After approval the same request creates a slot.

### Scheduling the same variant and time twice creates no second slot
Command (repeat of the successful request above):
```
'{"scheduled_at": "2026-10-12T09:00:00Z"}' | curl.exe -i -X POST http://127.0.0.1:8000/variants/1/schedule -H "Content-Type: application/json" --data-binary "@-"
```
Result:
```
HTTP/1.1 200 OK
{"slot_id":1,"variant_id":1,"scheduled_at":"2026-10-12T09:00:00Z","created":false}
```
Meaning: the same slot id comes back with `created: false`. A UNIQUE index on
`slots(variant_id, scheduled_at)` makes the database decide, so a double
click cannot create two slots (which would have two different idempotency
keys and so two posts).

### A time in the past is refused
Command:
```
'{"scheduled_at": "2020-01-01T09:00:00Z"}' | curl.exe -i -X POST http://127.0.0.1:8000/variants/1/schedule -H "Content-Type: application/json" --data-binary "@-"
```
Result:
```
HTTP/1.1 422 Unprocessable Content
{"error":"scheduled_at must be in the future"}
```
Meaning: bad input gets a clean 422 with a message. Times are stored as UTC
in one fixed format so the worker can compare them reliably.

## 4. Adapter layer (SocialPublisher + 1 real + 2 mock, swap by config)
**Status:** interface, both mock adapters and the registry done; mock proven.
All adapters proven: the mocks, the real Discord adapter, and the config swap.

### A mock adapter publishes through the interface and records what it would post
Commands:
```
python -m app.db.init_db
python -c "from app.adapters.registry import get_publisher; p = get_publisher('x'); print(p.name, p.publish({'id': 1, 'text': 'hello #a'}, 'v1:s1'))"
python -c "from app.db.mock_posts import list_mock_posts; print(list_mock_posts())"
```
Results:
```
Database initialised.
mock_x PublishResult(outcome=<Outcome.POSTED: 'posted'>, message_id='mock_x-1', error=None, retry_after=None)
[{'id': 1, 'adapter': 'mock_x', 'variant_id': 1, 'text': 'hello #a', 'idempotency_key': 'v1:s1', 'created_at': '2026-10-12 18:58:53'}]
```
Meaning: the app asks the registry for the adapter configured for platform
"x" and calls `publish()` on the interface. The mock returns a `POSTED`
result and records the post in the `mock_posts` table. That table is not
unique on the idempotency key, so a duplicate publish would show up as two
rows.


### The real Discord adapter posts to a live channel, once
Command (variant 3 is the discord variant, scheduled as slot 2; the webhook
URL lives only in `.env` and is not shown here):
```
curl.exe -i -X POST http://127.0.0.1:8000/slots/2/publish
curl.exe -i -X POST http://127.0.0.1:8000/slots/2/publish
```
Results:
```
HTTP/1.1 200 OK
{"publish_id":2,"status":"succeeded","platform_message_id":"1561129731514966170","sent_now":true,"note":null}

HTTP/1.1 200 OK
{"publish_id":2,"status":"succeeded","platform_message_id":"1561129731514966170","sent_now":false,"note":"not sent: already handled"}
```
Meaning: the first call sent the message through the Discord webhook and
stored Discord's own message id as `platform_message_id`, so the publish
record links to the live message. The second call sent nothing and returned
the same record.

Channel check: I opened the Discord channel and the published message is
there.

### Swapping the adapter in configuration publishes the same campaign through the mock
Commands (the setting is for this terminal session only; no code changed):
```
$env:PUBLISH_ADAPTER_DISCORD="mock_x"
python -c "from app.services.ingestion import ingest_post; from app.services.generation import generate_variants; from app.services.review import approve_variant; from app.services.scheduling import schedule_variant; from app.services.publishing import publish_slot; pid = ingest_post(markdown='# Swap test\n\nSame campaign, different adapter.'); v = [x for x in generate_variants(pid)['created'] if x['platform'] == 'discord'][0]; approve_variant(v['id']); s = schedule_variant(v['id'], '2026-10-25T09:00:00Z'); print(publish_slot(s['slot_id']))"
Remove-Item Env:PUBLISH_ADAPTER_DISCORD
python -c "from app.db.mock_posts import list_mock_posts; print(list_mock_posts())"
```
Results:
```
{'publish_id': 3, 'status': 'succeeded', 'platform_message_id': 'mock_x-2', 'sent_now': True, 'note': None}
[{'id': 1, 'adapter': 'mock_x', 'variant_id': 1, 'text': 'Hello: A test post. #blog', 'idempotency_key': 'v1:s1', 'created_at': '2026-10-17 21:28:08'}, {'id': 2, 'adapter': 'mock_x', 'variant_id': 6, 'text': 'Swap test\n\nSame campaign, different adapter.', 'idempotency_key': 'v6:s3', 'created_at': '2026-10-19 18:54:23'}]
```
Meaning: with `PUBLISH_ADAPTER_DISCORD=mock_x`, a discord-platform variant is
published through the mock: the message id is `mock_x-2` (not a Discord id)
and the post is recorded in `mock_posts`. Only configuration changed; no code
outside the adapters was touched.

## 5. Idempotent publish (same variant + slot never posts twice)
**Status:** proven with the mock adapter and with the real Discord adapter.
The worker-crash proof is in section 6.

### Publishing the same slot twice sends exactly once
Setup (fresh database): post 1 ingested, variants generated, variants 1 (x)
and 3 (discord) approved and scheduled for 2026-10-20T09:00:00Z, which
created slots 1 and 2.

Commands:
```
curl.exe -i -X POST http://127.0.0.1:8000/slots/1/publish
curl.exe -i -X POST http://127.0.0.1:8000/slots/1/publish
python -c "from app.db.mock_posts import list_mock_posts; print(list_mock_posts())"
```
Results:
```
HTTP/1.1 200 OK
{"publish_id":1,"status":"succeeded","platform_message_id":"mock_x-1","sent_now":true,"note":null}

HTTP/1.1 200 OK
{"publish_id":1,"status":"succeeded","platform_message_id":"mock_x-1","sent_now":false,"note":"not sent: already handled"}

[{'id': 1, 'adapter': 'mock_x', 'variant_id': 1, 'text': 'Hello: A test post. #blog', 'idempotency_key': 'v1:s1', 'created_at': '2026-10-17 21:28:08'}]
```
Meaning: the first call claims the publish (UNIQUE idempotency key `v1:s1`),
sends through the adapter, and records `succeeded`. The second call cannot
claim it, so it sends nothing and returns the original result. The mock
records every send and is not unique on the key, so exactly one row proves
exactly one send.

### A published variant cannot be approved again
Command:
```
curl.exe -i -X POST http://127.0.0.1:8000/variants/1/approve
```
Result:
```
HTTP/1.1 409 Conflict
{"error":"Variant 1 is published; only draft variants can be approved"}
```
Meaning: after a successful publish the variant is `published`, and approving
it again is refused, so it cannot be put back in the scheduler's path.


## 6. Durable scheduling (worker restart mid-batch, zero duplicates)
**Status:** proven for a crash in the middle of a publish, using the mock
adapter. Limits are listed at the end of this section.

### A normal batch of six slots publishes each slot once, and a restart sends nothing again
Setup: `seed.py` creates six approved slots that are due immediately; the
worker polls the database every 5 seconds.

Commands:
```
python seed.py
python worker.py
python worker.py
```
Result: the first run logged `slot 1` to `slot 6 -> succeeded
(sent_now=True)`, one line each. The second run, started after it, sent
nothing.

Meaning: each due slot is published once, and a restart finds no work left,
so a clean restart creates no duplicates.

### Probe 5: the worker is stopped in the middle of a publish, and the restart finishes the job without sending again
Setup: the database was deleted first, so this run starts from a known state
(six fresh slots from `seed.py`, no old rows to confuse the counts). Three
settings were made in the terminal for this demo only:

| Setting | Value | Why |
|---|---|---|
| `PUBLISH_ADAPTER_DISCORD` | `mock_x` | publish through the mock, so nothing real is sent |
| `MOCK_PUBLISH_DELAY_SECONDS` | `4` | each publish takes 4 seconds, which leaves a window to stop the worker while a publish is in progress |
| `STALE_AFTER_SECONDS` | `5` | a publish still `publishing` after 5 seconds counts as abandoned; it is longer than the 4-second delay so a slow but live publish is not mistaken for a crashed one |

Commands:
```
Remove-Item .\social_studio.db
python seed.py
python worker.py        # pressed Ctrl+C right after "slot 2 -> succeeded"
python worker.py        # restarted, left to finish
```

Worker log, first run (stopped with Ctrl+C):
```
2026-11-07 23:17:03,907 INFO worker started; polling every 5 seconds
2026-11-07 23:17:23,160 INFO slot 1 -> succeeded (sent_now=True)
2026-11-07 23:17:27,312 INFO slot 2 -> succeeded (sent_now=True)
2026-11-07 23:17:28,403 INFO worker stopped
```

Worker log, second run (restart):
```
2026-11-07 23:17:38,038 INFO worker started; polling every 5 seconds
2026-11-07 23:17:38,184 INFO settled 1 stale publish(es)
2026-11-07 23:17:42,305 INFO slot 4 -> succeeded (sent_now=True)
2026-11-07 23:17:46,485 INFO slot 5 -> succeeded (sent_now=True)
2026-11-07 23:17:50,595 INFO slot 6 -> succeeded (sent_now=True)
```

Command (read the three tables directly after the restart finished):
```
python -c "import sqlite3; c=sqlite3.connect('social_studio.db'); c.row_factory=sqlite3.Row; [(print('---', t), [print(dict(r)) for r in c.execute('select * from '+t)]) for t in ('publishes','publish_attempts','mock_posts')]"
```

Result:
```
--- publishes
{'id': 1, 'variant_id': 1, 'slot_id': 1, 'idempotency_key': 'v1:s1', 'status': 'succeeded', 'started_at': '2026-11-07T18:17:18Z', 'retry_at': None, 'platform_message_id': 'mock_x-1'}
{'id': 2, 'variant_id': 2, 'slot_id': 2, 'idempotency_key': 'v2:s2', 'status': 'succeeded', 'started_at': '2026-11-07T18:17:23Z', 'retry_at': None, 'platform_message_id': 'mock_linkedin-2'}
{'id': 3, 'variant_id': 3, 'slot_id': 3, 'idempotency_key': 'v3:s3', 'status': 'succeeded', 'started_at': '2026-11-07T18:17:27Z', 'retry_at': None, 'platform_message_id': 'mock_x-3'}
{'id': 4, 'variant_id': 4, 'slot_id': 4, 'idempotency_key': 'v4:s4', 'status': 'succeeded', 'started_at': '2026-11-07T18:17:38Z', 'retry_at': None, 'platform_message_id': 'mock_x-4'}
{'id': 5, 'variant_id': 5, 'slot_id': 5, 'idempotency_key': 'v5:s5', 'status': 'succeeded', 'started_at': '2026-11-07T18:17:42Z', 'retry_at': None, 'platform_message_id': 'mock_linkedin-5'}
{'id': 6, 'variant_id': 6, 'slot_id': 6, 'idempotency_key': 'v6:s6', 'status': 'succeeded', 'started_at': '2026-11-07T18:17:46Z', 'retry_at': None, 'platform_message_id': 'mock_x-6'}
--- publish_attempts
{'id': 1, 'publish_id': 1, 'result': 'posted', 'error': None, 'attempted_at': '2026-11-07 18:17:23'}
{'id': 2, 'publish_id': 2, 'result': 'posted', 'error': None, 'attempted_at': '2026-11-07 18:17:27'}
{'id': 3, 'publish_id': 3, 'result': 'recovered', 'error': 'post found after a crash; marked succeeded without re-sending', 'attempted_at': '2026-11-07 18:17:38'}
{'id': 4, 'publish_id': 4, 'result': 'posted', 'error': None, 'attempted_at': '2026-11-07 18:17:42'}
{'id': 5, 'publish_id': 5, 'result': 'posted', 'error': None, 'attempted_at': '2026-11-07 18:17:46'}
{'id': 6, 'publish_id': 6, 'result': 'posted', 'error': None, 'attempted_at': '2026-11-07 18:17:50'}
--- mock_posts
{'id': 1, 'adapter': 'mock_x', 'variant_id': 1, 'text': 'Demo post one: Why idempotency matters. #blog', 'idempotency_key': 'v1:s1', 'created_at': '2026-11-07 18:17:19'}
{'id': 2, 'adapter': 'mock_linkedin', 'variant_id': 2, 'text': 'Demo post one\n\nWhy idempotency matters.\n\n#blog #writing', 'idempotency_key': 'v2:s2', 'created_at': '2026-11-07 18:17:23'}
{'id': 3, 'adapter': 'mock_x', 'variant_id': 3, 'text': 'Demo post one\n\nWhy idempotency matters.', 'idempotency_key': 'v3:s3', 'created_at': '2026-11-07 18:17:27'}
{'id': 4, 'adapter': 'mock_x', 'variant_id': 4, 'text': 'Demo post two: Retries without double posts. #blog', 'idempotency_key': 'v4:s4', 'created_at': '2026-11-07 18:17:38'}
{'id': 5, 'adapter': 'mock_linkedin', 'variant_id': 5, 'text': 'Demo post two\n\nRetries without double posts.\n\n#blog #writing', 'idempotency_key': 'v5:s5', 'created_at': '2026-11-07 18:17:42'}
{'id': 6, 'adapter': 'mock_x', 'variant_id': 6, 'text': 'Demo post two\n\nRetries without double posts.', 'idempotency_key': 'v6:s6', 'created_at': '2026-11-07 18:17:46'}
```

How to read it:
- **Where the crash hit.** The worker log times are local (UTC+5) and the
  database times are UTC, so `23:17:28` in the log is `18:17:28` in the
  database. Slot 3's publish started at `18:17:27` and its mock post was
  written the same second. Ctrl+C came at `18:17:28`, inside slot 3's
  4-second delay. So the post existed but the publish row was never marked
  `succeeded`; it was left `publishing`.
- **Recovery ran.** On restart the first thing logged was `settled 1 stale
  publish(es)`, and `publish_attempts` has exactly one row with result
  `recovered` (attempt 3, publish 3). Its note says the post was found and
  the publish was marked succeeded without re-sending. There is no `slot 3
  -> succeeded` line in the second run.
- **Nothing was sent twice.** `mock_posts` has exactly six rows, one per
  idempotency key `v1:s1` to `v6:s6`, so `v3:s3` appears once. The mock
  records every send and is not unique on the key, so a re-send would have
  shown as a seventh row.
- **Everything finished.** All six `publishes` rows are `succeeded`, and the
  restart went on to publish slots 4, 5 and 6.

Meaning: a worker stopped in the middle of a publish, after the post was
sent but before it was recorded, does not lose that slot and does not send it
again. The restart looks the post up by its idempotency key, finds it, and
settles the publish. The proof is the `recovered` attempt together with one
`mock_posts` row for `v3:s3`: the first shows the crash and the recovery path
really happened, the second shows nothing was sent twice.

Settings cleared afterwards:
```
Remove-Item Env:PUBLISH_ADAPTER_DISCORD, Env:MOCK_PUBLISH_DELAY_SECONDS, Env:STALE_AFTER_SECONDS
```

### What this does not prove
- **Mock adapter only.** Recovery works here because the mock can be asked
  whether a post with a given idempotency key already exists. Discord cannot
  answer that. For the real Discord adapter a crash in this same window is
  designed to end as `uncertain`, not `succeeded` or `pending`, so a person
  decides. That path has not been run.
- **One crash window.** The crash was after the post was recorded and before
  the publish was marked `succeeded`. A crash before the adapter call (nothing
  sent) was not tested.
- **A polite stop, not a hard kill.** Ctrl+C lets the worker log `worker
  stopped`. A forced kill of the process was not tested.
- **One worker.** Two workers running at the same time were not tested.

## 7. Publish history
**Status:** endpoints proven over HTTP; the recovery case is shown in
section 6 (read from the database, not through the endpoints).

### Every publish and every attempt is visible
Commands:
```
curl.exe -i http://127.0.0.1:8000/publishes
curl.exe -i http://127.0.0.1:8000/publishes/1/attempts
```
Results:
```
HTTP/1.1 200 OK
[{"id":1,"variant_id":1,"slot_id":1,"idempotency_key":"v1:s1","status":"succeeded","started_at":"2026-10-17T21:28:08Z","retry_at":null,"platform_message_id":"mock_x-1"}]

HTTP/1.1 200 OK
[{"id":1,"publish_id":1,"result":"posted","error":null,"attempted_at":"2026-10-17 21:28:08"}]
```
Meaning: one publish row for the variant and slot (one success), and one
attempt row with its result. Retries would add attempt rows without ever
adding a second publish row.


## 8. Secrets clean
**Status:** proven. `.env` and database files are git-ignored and not
tracked, and `.env.example` holds placeholders only.

### The real `.env` and the database are ignored
Command:
```
git check-ignore -v .env social_studio.db
```
Result:
```
.gitignore:1:.env       .env
.gitignore:2:*.db       social_studio.db
```
Meaning: `.gitignore` line 1 covers `.env` (which holds the real Discord
webhook URL) and line 2 covers every `*.db` file, so neither can be added by
accident.

### Nothing secret is tracked
Command:
```
git ls-files | Select-String "\.env|\.db"
```
Result:
```
.env.example
```
Meaning: of every file git tracks, the only match for `.env` or `.db` is
`.env.example`. No `.env` and no database file is in the repository.
`.gitignore` only stops new files from being added, so this listing, not the
ignore rule alone, is the proof that nothing was committed earlier.

### `.env.example` holds placeholders only
Command:
```
Get-Content .env.example
```
Result:
```
DISCORD_WEBHOOK_URL=your-webhook-url-here

DATABASE_PATH=social_studio.db
BUSY_TIMEOUT_SECONDS=5

PUBLISH_ADAPTER_X=mock_x
PUBLISH_ADAPTER_LINKEDIN=mock_linkedin
PUBLISH_ADAPTER_DISCORD=discord

STALE_AFTER_SECONDS=300
POLL_INTERVAL_SECONDS=5

MOCK_PUBLISH_DELAY_SECONDS=0
```
Meaning: the only secret-shaped value, the webhook URL, is a placeholder.
Every other line is a harmless setting with its default. A new reader copies
this file to `.env` and fills in their own webhook URL.

Note: the Probe 5 demo in section 6 overrode three of these settings
(`PUBLISH_ADAPTER_DISCORD`, `MOCK_PUBLISH_DELAY_SECONDS`,
`STALE_AFTER_SECONDS`) for one terminal session only; the defaults above were
not edited.

## 9. README with architecture diagram and one-command run
Pending.