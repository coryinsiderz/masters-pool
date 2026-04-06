import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.environ["DATABASE_URL"]
    SECRET_KEY = os.environ["SECRET_KEY"]
    PICKS_DEADLINE = "2026-04-09T07:30:00-04:00"
    ESPN_POLL_INTERVAL = int(os.environ.get("ESPN_POLL_INTERVAL", 300))
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cory")
    ENABLE_POLLING = os.environ.get("ENABLE_POLLING", "1")
    ENABLE_PROJECTIONS_POLLING = os.environ.get("ENABLE_PROJECTIONS_POLLING", "0")
    PROJECTIONS_POLL_INTERVAL = int(os.environ.get("PROJECTIONS_POLL_INTERVAL", 1800))  # 30 min default
