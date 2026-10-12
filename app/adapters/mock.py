from app.adapters.base import Outcome, PublishResult, SocialPublisher
from app.db.mock_posts import record_mock_post


class MockPublisher(SocialPublisher):
    """Does not call any platform. Records what it WOULD post in the database."""

    def __init__(self, name: str):
        self.name = name

    def publish(self, variant: dict, idempotency_key: str) -> PublishResult:
        row_id = record_mock_post(
            self.name, variant["id"], variant["text"], idempotency_key
        )
        return PublishResult(Outcome.POSTED, message_id=f"{self.name}-{row_id}")


class MockXPublisher(MockPublisher):
    def __init__(self):
        super().__init__("mock_x")


class MockLinkedInPublisher(MockPublisher):
    def __init__(self):
        super().__init__("mock_linkedin")