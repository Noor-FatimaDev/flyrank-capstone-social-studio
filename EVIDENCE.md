# Evidence

One proof per requirement box. Every command and result below was run
locally from the repo root with the virtual environment active.

## 1. Ingestion
**Status:** in progress (service written; HTTP route not built yet).

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
and re-raised as my own `UpstreamError`. That exception carries
`status_code = 502`, which the route layer will return once the route
exists. Nothing is stored when the fetch fails.

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