import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "meeting_db")

client = MongoClient(MONGODB_URI)

db = client[DATABASE_NAME]

meetings_collection = db["meetings"]