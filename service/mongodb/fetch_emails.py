from pymongo import MongoClient

def get_verified_emails(MONGO_URI):
    client = MongoClient(MONGO_URI)
    db = client["portfolio_db"]
    collection = db["notification_address"]
    emails_cursor = collection.find({"isVerified": True}, {"_id": 0, "email": 1})
    emails = [doc["email"] for doc in emails_cursor]
    client.close()
    return emails
