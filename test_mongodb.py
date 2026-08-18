import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MONGODB_URI")

print("========================================")
print("MONGODB CONNECTION TEST")
print("========================================")

print("MongoDB URI configured:", bool(uri))

if not uri:
    print("❌ MONGODB_URI is missing from .env")
    raise SystemExit(1)

try:
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=10000,
    )

    print("Testing MongoDB connection...")

    result = client.admin.command("ping")

    print("Ping result:", result)
    print("✅ MongoDB connection successful.")

except Exception as e:

    print("❌ MongoDB connection failed.")
    print()
    print("Error type:")
    print(type(e).__name__)
    print()
    print("Error:")
    print(e)

finally:

    try:
        client.close()
    except:
        pass