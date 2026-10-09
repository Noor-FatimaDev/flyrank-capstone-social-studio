import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "social_studio.db")
BUSY_TIMEOUT_SECONDS = int(os.getenv("BUSY_TIMEOUT_SECONDS", 5))