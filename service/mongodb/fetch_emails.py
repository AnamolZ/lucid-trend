from service.mongodb.client import MongoDBService

def get_verified_emails(mongo_uri=None):
    service = MongoDBService(uri=mongo_uri)
    return service.get_verified_subscribers()