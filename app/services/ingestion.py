import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

from app.db.posts import create_post
from app.services.errors import ServiceError

FETCH_TIMEOUT_SECONDS = 10
MAX_POST_CHARS = 100_000


class IngestionError(ServiceError):
    status_code = 400


class InvalidInputError(IngestionError):
    status_code = 422  # the caller sent something wrong


class PostTooLongError(IngestionError):
    status_code = 422  # the caller sent something we won't accept


class UpstreamTimeoutError(IngestionError):
    status_code = 504  # the other site did not answer in time


class UpstreamError(IngestionError):
    status_code = 502  # the other site failed or refused


def fetch_url_as_markdown(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        raise InvalidInputError("url must start with http:// or https://")
    try:
        response = httpx.get(
            url, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True
        )
    except httpx.TimeoutException as exc:
        raise UpstreamTimeoutError(
            f"Could not fetch the URL: the site did not respond within "
            f"{FETCH_TIMEOUT_SECONDS} seconds"
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamError(
            f"Could not fetch the URL: {exc.__class__.__name__}"
        ) from exc

    if response.status_code >= 400:
        raise UpstreamError(
            f"Could not fetch the URL: the site returned {response.status_code}"
        )

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    markdown = markdownify(str(soup.body or soup)).strip()
    if not markdown:
        raise UpstreamError("Could not fetch the URL: the page had no readable text")
    return markdown


def ingest_post(url: str | None = None, markdown: str | None = None) -> int:
    if bool(url) == bool(markdown):
        raise InvalidInputError("Send exactly one of 'url' or 'markdown'")

    if url:
        body = fetch_url_as_markdown(url)
        source = url
    else:
        body = markdown.strip()
        source = None

    if not body:
        raise InvalidInputError("The post is empty")

    if len(body) > MAX_POST_CHARS:
        raise PostTooLongError(
            f"The post is too long ({len(body)} > {MAX_POST_CHARS} characters)"
        )

    return create_post(source, body)