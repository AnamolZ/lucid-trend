from pymongo import MongoClient

def remove_duplicates(duplicate_ids, MONGO_URI, DATABASE_NAME, COLLECTION_NAME):
    if not duplicate_ids:
        print("No duplicates found.")
        return
    
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]
    
    for dup_id in duplicate_ids:
        collection.delete_many({"id": dup_id})
        print(f"Deleted duplicate post: {dup_id}")
    
    client.close()