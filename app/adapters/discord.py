import math

import httpx

from app.adapters.base import Outcome, PublishResult, SocialPublisher


class DiscordPublisher(SocialPublisher):
    """Publishes through a Discord webhook (one POST request).

    The webhook URL is a secret: anyone who has it can post to the channel.
    It must never be logged or returned in an error message.
    """

    name = "discord"

    def __init__(self, webhook_url: str, timeout: int = 10):
        if not webhook_url:
            raise RuntimeError("DISCORD_WEBHOOK_URL must be set in .env")
        self._url = webhook_url
        self._timeout = timeout

    def publish(self, variant: dict, idempotency_key: str) -> PublishResult:
        try:
            # wait=true makes Discord return the created message (with its id).
            response = httpx.post(
                self._url,
                params={"wait": "true"},
                json={"content": variant["text"]},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            # Timeout or dropped connection: we do not know if it posted.
            # Only the class name is returned, because the full text can
            # include the URL, which is the secret.
            return PublishResult(
                Outcome.UNKNOWN,
                error=f"network error: {exc.__class__.__name__}",
            )

        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}

        status = response.status_code

        if status == 200 and "id" in data:
            return PublishResult(Outcome.POSTED, message_id=str(data["id"]))
        if status == 204:
            return PublishResult(Outcome.POSTED)

        if status == 429:
            retry_after = max(1, math.ceil(float(data.get("retry_after", 1))))
            return PublishResult(
                Outcome.RATE_LIMITED,
                error="rate limited by Discord",
                retry_after=retry_after,
            )

        if 400 <= status < 500:
            return PublishResult(
                Outcome.REJECTED,
                error=data.get("message", f"status {status}"),
            )

        # 5xx or an unexpected 2xx body: we cannot tell whether it posted.
        return PublishResult(
            Outcome.UNKNOWN, error=f"unexpected response (status {status})"
        )