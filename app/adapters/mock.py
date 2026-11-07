import time

from app.adapters.base import (
    Lookup,
    LookupResult,
    Outcome,
    PublishResult,
    SocialPublisher,
)
from app.config import MOCK_PUBLISH_DELAY_SECONDS
from app.db.mock_posts import find_mock_post, record_mock_post


class MockPublisher(SocialPublisher):
    """Does not call any platform. Records what it WOULD post in the database."""

    def __init__(self, name: str):
        self.name = name

    def publish(self, variant: dict, idempotency_key: str) -> PublishResult:
        row_id = record_mock_post(
            self.name, variant["id"], variant["text"], idempotency_key
        )
        if MOCK_PUBLISH_DELAY_SECONDS:
            # TEST ONLY: widens the window between "the platform has the post"
            # and "our database says succeeded", so a crash can be shown there.
            time.sleep(MOCK_PUBLISH_DELAY_SECONDS)
        return PublishResult(Outcome.POSTED, message_id=f"{self.name}-{row_id}")

    def lookup(self, idempotency_key: str) -> LookupResult:
        # The mock keeps its own records, so it can answer for certain.
        row = find_mock_post(idempotency_key)
        if row is None:
            return LookupResult(Lookup.NOT_FOUND)
        return LookupResult(Lookup.FOUND, message_id=f"{row['adapter']}-{row['id']}")


class MockXPublisher(MockPublisher):
    def __init__(self):
        super().__init__("mock_x")


class MockLinkedInPublisher(MockPublisher):
    def __init__(self):
        super().__init__("mock_linkedin")