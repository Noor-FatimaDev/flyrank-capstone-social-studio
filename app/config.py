import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "social_studio.db")
BUSY_TIMEOUT_SECONDS = int(os.getenv("BUSY_TIMEOUT_SECONDS", 5))

# Secret: read from the environment only. Never log or return it.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Which adapter publishes each platform's variants. Swapping an adapter is a
# config change only, e.g. PUBLISH_ADAPTER_X=discord.
PUBLISH_ADAPTERS = {
    "x": os.getenv("PUBLISH_ADAPTER_X", "mock_x"),
    "linkedin": os.getenv("PUBLISH_ADAPTER_LINKEDIN", "mock_linkedin"),
    "discord": os.getenv("PUBLISH_ADAPTER_DISCORD", "discord"),
}