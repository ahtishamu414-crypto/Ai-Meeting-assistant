import os

from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# MONGODB CONFIGURATION
# ============================================================

MONGODB_URI = os.getenv("MONGODB_URI")

DATABASE_NAME = os.getenv(
    "DATABASE_NAME",
    "meeting_db"
)


# ============================================================
# VALIDATE MONGODB URI
# ============================================================

if not MONGODB_URI:
    raise ValueError(
        "MONGODB_URI is not configured in .env"
    )


# ============================================================
# MONGODB CLIENT
# ============================================================

client = MongoClient(
    MONGODB_URI
)


# ============================================================
# DATABASE
# ============================================================

db = client[
    DATABASE_NAME
]


# ============================================================
# COLLECTIONS
# ============================================================

meetings_collection = db[
    "meetings"
]

slack_meetings_collection = db[
    "slack_meetings"
]


# ============================================================
# TEST CONNECTION
# ============================================================

try:

    client.admin.command(
        "ping"
    )

    print(
        "MongoDB connected successfully."
    )

except Exception as e:

    print(
        "MongoDB connection failed:",
        e
    )