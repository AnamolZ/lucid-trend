from service.mongodb.client import MongoDBService

def fetch_posts(mongo_uri=None, database_name=None, collection_name=None):
    service = MongoDBService(uri=mongo_uri, db_name=database_name, collection_name=collection_name)
    return service.fetch_all_posts()