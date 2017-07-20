import re
import pymongo
import fnmatch
import logging
import repo_analyser
from hotspots_util import HotspotsUtil
import json

import pdb

class MetricsBuilder(object):
    """
    Docstring
    """

    def __init__(self, mongo_collection):
        self.collection = mongo_collection
        self.log = logging.getLogger('codemd.MetricsBuilder')
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')


    def commits(self):
        """
        TODO -- Add docstring
        """
        self.log.debug("Fetching commits info from db...")

        cursor = self.collection.aggregate([
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

        self.log.debug("Finished fetching commits. Building list /w appropriate"
                        "metrics...")

        docs = []
        total_insertions, total_deletions = 0, 0
        for doc in cursor:
            total_insertions += doc['insertions']
            total_deletions += doc['deletions']
            docs.append({'bug': self.is_bug(doc['message']), 'date': doc['date'],
                         'insertions': doc['insertions'], 'total_insertions': total_insertions,
                         'deletions': doc['deletions'], 'total_deletions': total_deletions,
                         'author': doc['author']})

        # TODO -- calculate moving average on code churn metrics and store in
        # inteveral tree or some other computationaly conveient data struct

        return docs


    def file_complexity_history(self, filename):
        file_string = "$" + filename
        cursor = self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True }}},
            {  "$match" : {'filename' : file_string}},
            { "$unwind": "$files_modified" },
            { "$project":{"filename": "$files_modified.filename",
                          "insertions": "$files_modified.insertions",
                          "deletions": "$files_modified.deletions",
                          "message": 1, "author": 1, "date": 1, "_id": 0 }},
            { "$sort": {"date": 1} } ], allowDiskUse=True)
        return cursor


    def defect_rates(self):
        """
        (For EDA) Returns a list of each module and number of defects, sorted by
        number of defects
        """

        self.log.info("Building defects information.")
        interval1_start = 0

        last_entry = list(self.collection.find(
                    {'revision_id': {'$exists': True}}).sort('date', -1))[0]
        interval1_end = last_entry['date']
        scan_intervals = [(interval1_start, interval1_end)]
        hotspots_util = HotspotsUtil(scan_intervals)

        files_list = hotspots_util.execute_with_gen(self.file_history())

        self.log.info("Finished defects building process")

        flat_data = []
        for fname, info in files_list[0].iteritems():
            info['filename'] = fname
            flat_data.append(info)

        # TODO -- check if this is empty and handle error
        # files = hotspots_util.completedData[0]

        return flat_data


    def hotspots(self, interval1_start=None, interval1_end=None, interval2_start=None, interval2_end=None):
        """
        All-in-one superhero method to calculate temporal frequency, bug score,
        knowledge map, and code age, for use in circle packing viz.

        All dates are assumed to be in unix epoch format (parse them in the
                                                           view controllers)

        !! Note !! I'm just assuming interval1_end == interval2_start to simplify
        the edge cases for now

        TODO -- params, docstring, refactor, ect
        """
        # Build appropriate interval (and handle edge cases)
        if interval1_start is None:
            interval1_start = 0
            self.log.info("Interval1_start was None. Defaulted to 0")

        if interval1_end is None:
            last_entry = list(self.collection.find(
                        {'revision_id': {'$exists': True}}).sort('date', -1))[0]
            interval1_end = last_entry['date']
            self.log.info("Interval_end1 was none. Defaulted to last entry: %s", interval1_end)

        scan_intervals = [(interval1_start, interval1_end)]

        if interval2_end is not None:
            self.log.warning("\n\nINTERVAL 2 WAS NOT NULL!!!! IT WAS " + interval2_end + " ..of type: " + type(interval2_end) + "\n\n")
            scan_intervals.append((interval1_end, interval2_end))

        self.log.debug("Building circle packing metrics with interval: %s", scan_intervals)

        hotspots_util = HotspotsUtil(scan_intervals)
        file_heirarchy = hotspots_util.execute_with_gen(self.file_history(scan_intervals[0][0],
                                                        scan_intervals[-1][1]))

        self.log.debug("Finished circle packing building process...")

        # TODO -- handle multiple intervals with build_filetree
        attrs = ['loc', 'bug_score', 'bug_count', 'tc_score', 'coupled_module',
                 'num_revisions', 'num_mutual_revisions', 'tc_color',
                 'tc_color_opacity', 'tc_percent', 'top_authors', 'author_color']
        return {"name": "root", "children": self.__build_filetree(file_heirarchy[0], attributes=attrs)}


    def file_history(self, start_date=None, end_date=None):
        """
        TODO -- add docstring
        """
        #  NOTE: Dates from query are in unix epoch time
        return self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True },
                          'date': { '$lte': end_date }}},
            { "$unwind": "$files_modified" },
            { "$project":{"filename": "$files_modified.filename",
                          "insertions": "$files_modified.insertions",
                          "deletions": "$files_modified.deletions",
                          "message": 1, "author": 1, "date": 1, "revision_id":1,
                          "_id": 0 }},
            { "$sort": {"date": 1} } ], allowDiskUse=True)


    def __build_filetree(self, files, attributes=[], component_delim="/"):
        """
        Takes a dictionary (files) with keys corresponding to file paths, and builds a
        tree from the file path with the leaves having attributes selected from
        the value dictionary of param files.

        Every node has keys 'name' and 'children'.
        Each leaf i also has whatever properties from files.values()[i]
        which are specified in the attributes parameter

        This algorithm is general enough for any number of nested components. It works
        by splitting file's name into path components, traversing the tree top-down,
        keeping a pointer to the current layer, and creating a node for each
        component that does not exist yet. When it gets to the terminal node
        (bottom-most layer) it will add the attributes indicated in the attributes parameter
        This turned out to be slightly nontrivial lol (but v fun).

        TODO -- Add docstring params and returns
        """
        self.log.debug("Starting object tree algorithm...")
        tree = []
        for filename, file_info in files.iteritems():
            components = filename.split(component_delim)
            current_node = tree
            # Traverse through components, building nodes as necessary
            for component in components:
                wanted_node = component
                last_node = current_node
                for node in current_node:
                    if node['name'] == wanted_node:
                        current_node = node['children']
                        break
                # If I couldn't find item in list of children, create one
                if last_node == current_node:
                    new_node = {'name': wanted_node}
                    new_node['children'] = []
                    # If this is the terminal node, add the info. Otherwise add children
                    if wanted_node == components[-1]:
                        for attr in attributes:
                            new_node[attr] = file_info[attr]
                        current_node.append(new_node)
                    else:
                        current_node.append(new_node)
                        current_node = new_node['children']
        self.log.debug("Finished building object tree")
        # FOR DEBUGING (verbose af)
        # self.log.debug("Object tree: \n%s ... ", json.dumps(tree[0:2], indent=2))
        return tree


    def is_bug(self, message):
        """
        DOCSTRING
        """
        return self.regex.match(message) != None

    def fix_fuckups(self, collection_name):
        # Dirty hack to alter previously created documents and filter things I
        # should of filtered in the first place, and also index the date
        paths = repo_analyser.paths[collection_name]
        include_paths = paths['include']
        exclude_paths = paths['exclude']

        print "Fixing mistakes."
        print "Include paths: " + str(include_paths)
        print "Exclude paths: " + str(exclude_paths)

        def check_file_path(f):
            include_count = 0
            for path in exclude_paths:
                if fnmatch.fnmatch(f, path):
                    return False
            for path in include_paths:
                if fnmatch.fnmatch(f, path):
                    include_count += 1
            if include_count == 0:
                return False
            return True

        self.collection.create_index([("date", pymongo.ASCENDING)])
        docs = self.collection.find({'revision_id': { '$exists': True }})
        for doc in docs:
            updated_files = []
            files_mod = doc['files_modified']
            for f in files_mod:
                if check_file_path(f['filename']):
                    updated_files.append(f)
                else:
                    print "Removing file: " + f['filename']
            if len(updated_files) != len(files_mod):
                self.collection.update_one({'date': doc['date']}, {'$set' : {'files_modified':updated_files}})
