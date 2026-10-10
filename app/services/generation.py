from app.db.variants import create_variant, get_post
from app.services.constraints import validate_variant
from app.services.errors import NotFoundError


def _title_and_summary(markdown: str) -> tuple[str, str]:
    lines = [ln.strip() for ln in markdown.splitlines() if ln.strip()]
    title = lines[0].lstrip("#").strip() if lines else ""
    body = [ln for ln in lines[1:] if not ln.startswith("#")]
    summary = body[0] if body else ""
    return title, summary


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _make_x(title: str, summary: str, url: str | None) -> str:
    tags = " #blog"
    head = f"{title}: {summary}" if summary else title
    return _shorten(head, 280 - len(tags)) + tags


def _make_linkedin(title: str, summary: str, url: str | None) -> str:
    text = f"{title}\n\n{summary}" if summary else title
    return _shorten(text, 1900) + "\n\n#blog #writing"


def _make_telegram(title: str, summary: str, url: str | None) -> str:
    text = f"{title}\n\n{summary}" if summary else title
    if url:
        text += f"\n\n{url}"
    return _shorten(text, 4000)


GENERATORS = {"x": _make_x, "linkedin": _make_linkedin, "telegram": _make_telegram}


def generate_variants(post_id: int) -> dict:
    """Build one variant per platform from the STORED post only.

    Variants that break a constraint profile are not saved; they are
    returned under 'blocked' with every broken rule named.
    """
    post = get_post(post_id)
    if post is None:
        raise NotFoundError(f"Post {post_id} not found")

    title, summary = _title_and_summary(post["body_markdown"])
    created, blocked = [], []

    for platform, make in GENERATORS.items():
        text = make(title, summary, post["source_url"])
        errors = validate_variant(platform, text)
        if errors:
            blocked.append({"platform": platform, "errors": errors})
        else:
            variant_id = create_variant(post_id, platform, text)
            created.append({"id": variant_id, "platform": platform, "text": text})

    return {"created": created, "blocked": blocked}