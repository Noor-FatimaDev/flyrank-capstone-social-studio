import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "social_studio.db")
BUSY_TIMEOUT_SECONDS = int(os.getenv("BUSY_TIMEOUT_SECONDS", 5))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

PUBLISH_ADAPTERS = {
    "x": os.getenv("PUBLISH_ADAPTER_X", "mock_x"),
    "linkedin": os.getenv("PUBLISH_ADAPTER_LINKEDIN", "mock_linkedin"),
    "discord": os.getenv("PUBLISH_ADAPTER_DISCORD", "discord"),
}

STALE_AFTER_SECONDS = int(os.getenv("STALE_AFTER_SECONDS", 300))

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 5))