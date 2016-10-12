import re
import json
import math


class MetricsBuilder(object):
    """
    Docstring
    """

    def __init__(self, mongo_collection):
        self.collection = mongo_collection


    def commits(self):
        """
        TODO -- Add docstring
        """
        cursor = self.collection.aggregate([ \
            { "$match" : {'revision_id': { '$exists': True }}},
            { "$unwind": "$files_modified" },
            { "$group": {
                "_id": "$date",
                "author": { "$first": "$author"},
                "insertions": { "$sum": "$files_modified.insertions"},
                "deletions":  { "$sum": "$files_modified.deletions"}
            }},
            { "$sort": {"_id":1}}, # _id is the date at this point
            { "$project": {"date":"$_id", "_id": 0, "insertions": 1,
                           "deletions": 1, "author": 1}}
        ])

        return [doc for doc in cursor]

    def hotspots(self, end_date = None):
        """
        TODO -- Add docstring
        """

        if end_date == None:
            last_entry = list(self.collection.find(
                        {'revision_id': { '$exists': True }}).sort('date', -1))[0]
            end_date = last_entry['date']

        # Regular expression to find commits containg "fixes/fixed or closes/closed"
        regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')
        # TODO -- filter these found bugs using Github issues or some external source

        # Iterate over each modified file and build a dict of dicts, with a key
        # for each filename, and a value containing file info. Structure:
        # {'file_1': {'creation_date': xx, 'last_modified': xx, 'loc': 50,
        #              'bug_dates': [ first_bug_date, ... , last_bug_date ]}}
        files = {}
        for mod_file in self.file_history(start_date=None, end_date=end_date):
            if mod_file['filename'] not in files.keys():
                files[mod_file['filename']] = {'creation_date' : mod_file['date'],
                                                    'bug_dates': [], 'bug_messages': [],
                                                    'loc': 0, 'score': 0 }
            f = files[mod_file['filename']]
            f['loc'] += mod_file['insertions'] - mod_file['deletions']
            f['last_modified'] = mod_file['date']

            # Check commit message for bug fixes
            if regex.match(mod_file['message']) != None:
                f['bug_dates'].append(mod_file['date']) # just or debugging really
                f['bug_messages'].append(mod_file['message'])

                # Add score to each file. Scoring function based on research from Chris
                # Lewis and Rong Ou
                fix_date = mod_file['date']
                norm_time = 1 - (float(end_date - fix_date) /
                                (end_date - f['creation_date']))
                f['score'] += 1 / (1 + math.exp(-12 * norm_time + 12))

        return self.__build_filetree(files, attributes=['score', 'loc'])


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
            { "$sort": {"date": 1} } ])


    def __build_filetree(self, files, attributes=[], component_delim="/"):
        """
        Takes a dictionary (files) with keys corresponding to file paths, and builds a
        tree from the file path with the leaves having attributes selected from
        the value dictionary of param files. .

        Each non-leaf has keys 'name' and 'children'.
        Each leaf has keys 'name', and whatever else is specified in the attributes
        parameter

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
                    # If this is the terminal node, add the info. Otherwise add children
                    if wanted_node == components[-1]:
                        for attr in attributes:
                            new_node[attr] = file_info[attr]
                        current_node.append(new_node)
                    else:
                        new_node['children'] = []
                        current_node.append(new_node)
                        current_node = new_node['children']

        return tree


# min = col.find({'revision_id': { '$exists': True }}).sort('date', 1)

# cursor = col.aggregate([ \
#     { "$match" : {'revision_id': { '$exists': True }}},
#     { "$unwind": "$files_modified" },
#     { "$project":{"filename": "$files_modified.filename",
#                   "insertions": "$files_modified.insertions",
#                   "deletions": "$files_modified.deletions",
#                   "message": 1, "author": 1, "date": 1, "_id": 0 }},
#     { "$sort": {"date": 1} } ])
