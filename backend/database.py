import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb://localhost:27017"
)

MONGO_DB = os.getenv(
    "MONGO_DB",
    "movewell"
)

client = MongoClient(MONGO_URL)

db = client[MONGO_DB]

users_collection = db["users"]