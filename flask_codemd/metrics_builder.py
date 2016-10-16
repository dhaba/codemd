import re
import math
import pymongo
import fnmatch
import logging

import repo_analyser


class MetricsBuilder(object):
    """
    Docstring
    """

    def __init__(self, mongo_collection):
        self.collection = mongo_collection
        self.log = logging.getLogger('codemd.MetricsBuilder')
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')

        # minimum lines of code to be considered in hotspots analysis
        self.LENGTH_THRESH = 10


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

        return docs


    def hotspots(self, end_date=None):
        """
        TODO -- Add docstring
        """

        THRESHOLD = 20 # do not include files less than this many lines

        self.log.debug("Building hotspots information...")

        if end_date == None:
            last_entry = list(self.collection.find(
                        {'revision_id': {'$exists': True}}).sort('date', -1))[0]
            end_date = last_entry['date']

        # Iterate over each modified file and build a dict of dicts, with a key
        # for each filename, and a value containing file info. Structure:
        # {'file_1': {'creation_date': xx, 'last_modified': xx, 'loc': 50,
        #              'bug_dates': [ first_bug_date, ... , last_bug_date ]}}
        files = {}
        max_score = 0
        for mod_file in self.file_history(start_date=None, end_date=end_date):
            if mod_file['filename'] not in files.keys():
                files[mod_file['filename']] = {'creation_date': mod_file['date'],
                                                    'bug_dates': [], 'bug_messages': [],
                                                    'loc': 0, 'score': 0}
            f = files[mod_file['filename']]
            f['loc'] += mod_file['insertions'] - mod_file['deletions']
            f['last_modified'] = mod_file['date']

            if f['loc'] <= 0:
                #self.log.error("!!! PROBLEM: negative loc for file: %s", mod_file['filename'])
                files.pop(mod_file['filename'], None)
                continue

            # Check commit message for bug fixes
            if self.is_bug(mod_file['message']):
                # just or debugging really
                f['bug_dates'].append(mod_file['date'])
                f['bug_messages'].append(mod_file['message'])

                # Add score to each file. Scoring function based on research from Chris
                # Lewis and Rong Ou
                fix_date = mod_file['date']
                time_delta = end_date - f['creation_date']
                if time_delta <= 0:
                    norm_time = 1.0
                else:
                    norm_time = 1 - (float(end_date - fix_date) / (time_delta))
                f['score'] += 1 / (1 + math.exp(-12 * norm_time + 12))

                if f['score'] > max_score:
                    max_score = f['score']

        self.log.info("Highest score: %s", max_score)


        files_to_filter = []

        # Normalize scores
        if max_score > 0:
            for f_name, f_info in files.iteritems():
                # DEBUG TODO -- remove
                if math.isnan(f_info['score']) or math.isnan(f_info['loc']):
                    self.log.error(
                        "Got nan score/loc for file %s, with info: %s", f_name, f_info)
                if f_info['score'] == max_score:
                    self.log.info("Highest score was %s for file %s with info:\n%s",
                                                        max_score, f_name, f_info)
                if f_info['loc'] < THRESHOLD:
                    files_to_filter.append(f_name)

                f_info['score'] /= max_score

        for f in files_to_filter:
            self.log.debug("Removing file %s because it only had %s lines", f, files[f]['loc'])
            files.pop(f, None)

        return {"name": "root", "children": self.__build_filetree(files, attributes=['score', 'loc'])}



    def file_history(self, start_date=None, end_date=None):
        """
        TODO -- add docstring
        """
        # TODO -- add logic for fitlering between dates

        #  NOTE: Dates from query are in unix epoch time
        return self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True }}},
            { "$unwind": "$files_modified" },
            { "$project":{"filename": "$files_modified.filename",
                          "insertions": "$files_modified.insertions",
                          "deletions": "$files_modified.deletions",
                          "message": 1, "author": 1, "date": 1, "_id": 0 }},
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

        TODO -- Add docstring params and returns
        """

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
