from app.database import db

print("Connected successfully!")
print(db.list_collection_names())