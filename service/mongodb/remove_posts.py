from service.mongodb.client import MongoDBService

def remove_duplicates(duplicate_ids, mongo_uri=None, database_name=None, collection_name=None):
    service = MongoDBService(uri=mongo_uri, db_name=database_name, collection_name=collection_name)
    return service.remove_duplicate_posts(duplicate_ids)