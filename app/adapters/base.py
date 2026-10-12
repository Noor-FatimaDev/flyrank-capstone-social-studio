from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Outcome(str, Enum):
    POSTED = "posted"              # it is live on the platform
    REJECTED = "rejected"          # definitely NOT posted; do not retry blindly
    RATE_LIMITED = "rate_limited"  # definitely NOT posted; retry after a delay
    UNKNOWN = "unknown"            # may or may not have posted; never re-send blindly


@dataclass
class PublishResult:
    outcome: Outcome
    message_id: str | None = None   # the platform's id for the live post
    error: str | None = None        # short, safe-to-log explanation
    retry_after: int | None = None  # seconds, only for RATE_LIMITED


class SocialPublisher(ABC):
    """The one interface the app talks to. It never knows which platform is behind it."""

    name: str

    @abstractmethod
    def publish(self, variant: dict, idempotency_key: str) -> PublishResult:
        """Publish variant['text']. Must not raise for expected platform failures;
        report them through the PublishResult instead."""