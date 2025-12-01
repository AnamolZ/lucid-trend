
from pymongo import MongoClient

def fetch_posts(MONGO_URI, DATABASE_NAME, COLLECTION_NAME):
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    
    posts = list(collection.find({}, {"_id": 0, "id": 1, "title": 1, "description": 1}))
    client.close()
    return posts