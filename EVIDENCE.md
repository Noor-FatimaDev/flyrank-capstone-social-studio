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
Command:
```
python -c "from app.services.generation import generate_variants; import json; print(json.dumps(generate_variants(2), indent=2))"
```
Result (abridged to the variant text):
```
x:        "Hello: A test post. #blog"
linkedin: "Hello\n\nA test post.\n\n#blog #writing"
telegram: "Hello\n\nA test post."
blocked:  []
```
Meaning: generation reads only the stored post (id 2) and builds a
different variant for each platform. All three pass their constraint
profiles, so all three are saved.

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
Telegram adapter written, real-channel proof and config-swap proof still to
add.

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


## 5. Idempotent publish (same variant + slot never posts twice)
Pending.

## 6. Durable scheduling (worker restart mid-batch, zero duplicates)
Pending.

## 7. Publish history
Pending.

## 8. Secrets clean
Pending: `.env` is git-ignored and `.env.example` holds placeholders only.
Will add a `git status` / `git ls-files` transcript showing no `.env` is
tracked.

## 9. README with architecture diagram and one-command run
Pending.