import logging
import pymongo
import datetime

from bson.binary import Binary
import pickle

from codemd import mongo

import pdb

class DBHandler(object):
    """
    This class is responsible for all interactions with mongodb.
    This includes:
        - persisting data during initial repo analysis
        - fetching data for circle packing metrics
    """

    def __init__(self, project_name):
        """
        :param mongo_collection: A references the the pymongo collection
        :type mongo_collection: pymongo.collection.Collection
        """
        self.log = logging.getLogger('codemd.DBHandler')
        self.project_name = project_name
        self.collection = None # Collection /w github repo dump
        self.cp_collection = None # Collection /w precomputed circle packing data
        self.__set_collections()

    def __set_collections(self):
        """
        Sets internal collection attributes (self.collection and self.cp_collection)
        to associated mongodb collections
        """
        # Set self.collection
        if DBHandler.project_exists(self.project_name):
            self.log.debug("Found commits collection %s", self.project_name)
            self.collection = mongo.db[self.project_name]
        else:
            self.log.info("Creating new commits collection for project %s",
                           self.project_name)
            self.collection = mongo.db[self.project_name]
            self.collection.create_index([("date", pymongo.ASCENDING)])
            self.collection.insert_one({'date_updated': datetime.datetime.now()})

        # Set self.cp_collection
        if DBHandler.project_exists(self.cp_collection_name()):
            self.log.info("Found cp_data collection %s",self.cp_collection_name())
            self.cp_collection = mongo.db[self.cp_collection_name()]
        else:
            self.log.info("DBHandler creating circle packing data collection under "
                          + "name: %s", self.cp_collection_name())
            self.cp_collection = mongo.db[self.cp_collection_name()]
            self.cp_collection.create_index([("date", pymongo.ASCENDING)])

    @classmethod
    def project_exists(cls, project_name):
        """
        Checks if a collection exists for the specified project_name

        :param project_name: The name of the project
        :type project_name: str

        :returns: True or False
        """
        return project_name in mongo.db.collection_names()

    @classmethod
    def last_revision_date(cls, project_name):
        """
        Returns the date of the last revision in the project

        :returns: Date of last revision, as an int in unix epoch time
        """
        return list(mongo.db[project_name].find(
            {'revision_id': {'$exists': True}}).sort('date', -1).limit(1))[0]['date']

    @classmethod
    def first_revision_date(cls, project_name):
        """
        Returns the date of the first revision in the project

        :returns: Date of first revision, as an int in unix epoch time
        """
        return list(mongo.db[project_name].find(
            {'revision_id': {'$exists': True}}).sort('date', 1).limit(1))[0]['date']

    def persist_documents_from_gen(self, doc_gen):
        """
        Inserts the documents yielded by doc_gen into
        """
        self.log.info("Starting insertion of documents into db for project %s...", \
                       self.project_name)
        self.collection.insert_many(doc for doc in doc_gen)
        self.log.info("Finished inserting documents into db.")

    def fetch_commits(self):
        """
        Fetches all commits for the given collection, binning them by revision
        id and appending file modification metricsl. This is for use in interactive
        dashboard visualizations

        :returns: A pymongo cursor to all commits for the given project
        """
        return self.collection.aggregate([
                {"$match": {'revision_id': {'$exists': True}}},
                {"$unwind": "$files_modified"},
                {"$group": {
                    "_id": "$revision_id",
                    "date": {"$first": "$date"},
                    "message": {"$first": "$message"},
                    "author": {"$first": "$author"},
                    "insertions": {"$sum": "$files_modified.insertions"},
                    "deletions":  {"$sum": "$files_modified.deletions"}
                }},
                {"$sort": {"date": 1}},  # _id is the date at this point
                {"$project": {"date": 1, "_id": 0, "insertions": 1,
                               "deletions": 1, "author": 1, "message": 1}}
            ])

    def file_history(self, start_date=None, end_date=None):
        """
        Fetches all file modifications in the given interval by unwinding commits
        into individual file modifications.

        :param start_date: The start date to begin fetching (in unix epoch)
        :param end_date: The end date to begin fetching (in unix epoch)
        """
        if end_date is None:
            end_date = DBHandler.last_revision_date(self.project_name)
        if start_date is None:
            start_date = DBHandler.first_revision_date(self.project_name)
        self.log.debug("Fetching file history from %s to %s", start_date, end_date)
        return self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True },
                          'date': { '$lte': end_date, "$gte": start_date }}},
            { "$unwind": "$files_modified" },
            { "$project":{"filename": "$files_modified.filename",
                          "insertions": "$files_modified.insertions",
                          "deletions": "$files_modified.deletions",
                          "message": 1, "author": 1, "date": 1, "revision_id":1,
                          "_id": 0 }},
            { "$sort": {"date": 1} } ], allowDiskUse=True)

    def revision_count(self):
        """
        Counts total number of entires in the collection
        """
        return self.collection.count()

    def file_history_count(self):
        """
        Counts the number of file modifications over the entire project history
        This will be equal to the number of entires in self.file_history
        If one commit changes 3 files, then this coutns as 3 modifications.
        """
        return list(self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True }}},
            {'$unwind':'$files_modified'},
            {'$group':{'_id':'null', 'count':{'$sum':1}}}
            ]))[0]['count']

    def cp_collection_name(self):
        return self.project_name + "_" + "cp_data"

    def file_complexity_history(self, filename):
        """
        Fetches all commits for a given file, sorted in ascending order by date

        :returns: A pymongo cursor to all commits for the given project
        """
        file_string = "$" + filename
        return self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True }}},
            {  "$match" : {'filename' : file_string}},
            { "$unwind": "$files_modified" },
            { "$project":{"filename": "$files_modified.filename",
                          "insertions": "$files_modified.insertions",
                          "deletions": "$files_modified.deletions",
                          "message": 1, "author": 1, "date": 1, "_id": 0 }},
            { "$sort": {"date": 1} } ], allowDiskUse=True)

    def persist_packing_data(self, date, module_key, data):
        bson_data = Binary(pickle.dumps(data))
        self.cp_collection.insert_one({'date': date, 'module_key': module_key,
                                       'data': bson_data})

    def find_closest_checkpoint(self, date, before=True):
        """
        Fetches the closest checkpoint date that is before or equal to date
        if before == True or after date if before == False
        """
        if before:
            sort, comparison = pymongo.DESCENDING, "$lte"
        else:
            sort, comparison = pymongo.ASCENDING, "$gte"
        return list(self.cp_collection.find( \
            {'date': {comparison: date}}).sort('date', sort).limit(1))[0]['date']

    def fetch_checkpoint_data(self, date):
        """
        Fetches all checkpoint data at checkpoint <date>, unserializing data as
        necessary.

        :param date: The date of the checkpoint. Should be in unix epoch time
        :type date: int
        :returns: A pymongo cursor the data for the closest checkpoint
        :rtype: pymongo.cursor
        """
        # Fetch all checkpoints at date
        checkpoints = self.cp_collection.find({'date': date}, {'_id': 0})
        # Return a generator that unseralizes the data
        for checkpoint in checkpoints:
            checkpoint['data'] = pickle.loads(checkpoint['data'])
            yield checkpoint
