# Test that Python can connect to MongoDB Atlas
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Load the .env file from the project root
project_folder = Path(__file__).resolve().parents[2]
load_dotenv(project_folder / ".env")

mongo_uri = os.getenv("MONGO_URI")
db_name = os.getenv("MONGO_DB_NAME", "transitiq")

if not mongo_uri:
    raise SystemExit("MONGO_URI not found. Check that .env is in the project root.")

client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)

try:
    # Check the connection
    client.admin.command("ping")
    print("Connected to MongoDB Atlas!")

    db = client[db_name]
    test_collection = db["connection_test"]

    # Insert a test document
    result = test_collection.insert_one({
        "message": "Hello from TransitIQ",
        "created_at": datetime.now(timezone.utc)
    })
    print("Inserted test document with _id:", result.inserted_id)

    # Read it back
    document = test_collection.find_one({"_id": result.inserted_id})
    print("Read back from database:", document)

except PyMongoError as error:
    print("MongoDB error:", error)

finally:
    client.close()
    print("Connection closed.")