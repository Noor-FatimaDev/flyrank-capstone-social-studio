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

## 3. Review workflow (draft / approved / rejected / published)
Pending.

## 4. Adapter layer (SocialPublisher + 1 real + 2 mock, swap by config)
Pending.

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