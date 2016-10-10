class MetricsBuilder(object):
    """
    Docstring
    """

    def __init__(self, mongo_collection):
        self.collection = mongo_collection

    def commits(self):
        # Query mongo collection and build commit metrics
        cursor = self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True }}},
            { "$unwind": "$files_modified" },
            { "$group": {
                "_id": "$date",
                "author": { "$first": "$author"},
                "insertions": { "$sum": "$files_modified.insertions"},
                "deletions":  { "$sum": "$files_modified.deletions"}
            }},
            { "$sort": {"_id":1}},
            { "$project": {"date":"$_id", "_id": 0, "insertions": 1,
                           "deletions": 1, "author": 1}}
        ])

        return [doc for doc in cursor]
