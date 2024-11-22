import pymongo
import os


class MongodbConnection:
    """
    This class is a wrapper for mongodb python client
    This is a singleton class
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongodbConnection, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.client = pymongo.MongoClient(os.getenv("MONGODB_URI"))
        self.db = self.client[os.getenv('MONGODB_DB')]

    def run_pipeline(self, pipeline: list, collection='conversations'):
        """
        Run aggregation pipeline in MongoDB
        Args:
            pipeline: MongoDB pipeline
            collection: MongoDB Collection name

        Returns:

        """
        return self.db[collection].aggregate(pipeline)