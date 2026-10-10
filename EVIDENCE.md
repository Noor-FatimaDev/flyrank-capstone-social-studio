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

Meaning: the service raises typed exceptions and one handler in `main.py`
turns each into JSON with its own status code. The route has no try/except.
Malformed JSON is also rejected with a 422, never a 500.

## 2. Constraint profiles enforced by code
**Status:** validator done (`app/services/constraints.py`); not yet wired
into generation or the edit/approve endpoints.

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