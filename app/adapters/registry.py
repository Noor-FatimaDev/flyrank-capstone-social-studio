from app.adapters.base import SocialPublisher
from app.adapters.discord import DiscordPublisher
from app.adapters.mock import MockLinkedInPublisher, MockXPublisher
from app.config import DISCORD_WEBHOOK_URL, PUBLISH_ADAPTERS

FACTORIES = {
    "discord": lambda: DiscordPublisher(DISCORD_WEBHOOK_URL),
    "mock_x": MockXPublisher,
    "mock_linkedin": MockLinkedInPublisher,
}


def get_publisher(platform: str) -> SocialPublisher:
    """Pick the adapter for a platform's variants from configuration."""
    name = PUBLISH_ADAPTERS.get(platform)
    if name is None:
        raise RuntimeError(f"No adapter configured for platform '{platform}'")
    factory = FACTORIES.get(name)
    if factory is None:
        raise RuntimeError(
            f"Unknown adapter '{name}'. Choose one of: {', '.join(FACTORIES)}"
        )
    return factory()