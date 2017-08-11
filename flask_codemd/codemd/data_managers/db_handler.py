import logging
import pymongo
import datetime

from codemd import mongo

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
        if DBHandler.project_exists(project_name):
            self.log.debug("DBHandler found project %s", project_name)
            self.collection = mongo.db[project_name]
        else:
            self.log.info("DBHandler creating new collection for project %s", project_name)
            self.collection = mongo.db[project_name]
            self.collection.create_index([("date", pymongo.ASCENDING)])
            self.collection.insert_one({'date_updated': datetime.datetime.now()})

    @classmethod
    def project_exists(cls, project_name):
        """
        Checks if a collection exists for the specified project_name

        :param project_name: The name of the project
        :type project_name: str

        :returns: True or False
        """
        return project_name in mongo.db.collection_names()

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

    def last_revision_date(self):
        """
        Returns the date of the last revision in the project

        :returns: Date of last revision, as an int in unix epoch time
        """
        return list(self.collection.find(
            {'revision_id': {'$exists': True}}).sort('date', -1).limit(1))[0]['date']

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
