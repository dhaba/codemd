import re
import math
import pymongo
import fnmatch
import logging
from collections import defaultdict
from itertools import combinations
import datetime

import repo_analyser

import pdb


# ::::  HEURISTICS ::::
# Hard coded rules for inclusion/exclusion of files when calculated various metrics
# Ideally these would be exposed to the user for custom tinkering

LOC_THRESHOLD = 30 # min number of lines to be considered in circle packing


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

        # TODO -- calculate moving average on code churn metrics

        return docs


    def hotspots(self, interval1_start=None, interval1_end=None, interval2_start=None, interval2_end=None):
        """
        All-in-one superhero method to calculate temporal frequency, bug score,
        knowledge map, and code age. I should break this up but I'm way too tired
        lol.

        Acceptable invocations: t.b.d.

        All dates are assumed to be in unix epoch format (parse them in the
                                                           view controllers)

        !! Note !! I'm just assuming interval1_end is interval2_start to simply
        the edge cases for now

        TODO -- params, docstring, refactor, ect
        """

        self.log.debug("Building hotspots information.")

        if interval1_start is None:
            interval1_start = 0
            self.log.debug("Interval1_start was None. Defaulted to 0")

        if interval1_end is None:
            last_entry = list(self.collection.find(
                        {'revision_id': {'$exists': True}}).sort('date', -1))[0]
            interval1_end = last_entry['date']
            self.log.debug("Interval_end1 was none. Defaulted to last entry: %s", interval1_end)

        scan_intervals = [(interval1_start, interval1_end)]

        if interval2_end is not None:
            scan_intervals.append((interval1_end, interval2_end))

        hotspots_util = HotspotsUtil(scan_intervals)

        self.log.debug("Begin hotspot building process...")

        files_list = hotspots_util.execute_with_gen(self.file_history())

        self.log.debug("Finished hotspot building process...")

        # TODO -- check if this is empty and handle error
        # files = hotspots_util.completedData[0]

        return {"name": "root", "children": self.__build_filetree(files_list[0], attributes=['bug_score', 'loc'])}


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
        This was surprisingly nontrivial lol.

        TODO -- Add docstring params and returns
        """

        self.log.debug("Building object tree...")
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
        self.log.debug("Finished building object tree.")
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


class HotspotsUtil(object):
    """
    Helper class for computing hotspot metrics (temporal coupling, code age,
    knowledge map, bug scores), for use in Circle Packing viz.

    Should only be used internally by MetricsBuilder.

    :param intervals: An array of tuples, identifying the (start_time, end_time) for
    each interval. For only one interval, pass an array with one element.
    NOTE : Assumes times are in epoch unix! Blame github lol.
    """

    def __init__(self, intervals):
        self.log = logging.getLogger('codemd.MetricsBuilder.HotspotsUtil')
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')

        self.log.info("HotspotsUtil created with interval: %s", intervals)

        # Local Variables to track metrics
        self.intervals = intervals
        self.working_data = {} # high level file info

        # For temporal coupling analysis
        self.working_couples = defaultdict(int)
        self.working_rev_counts = defaultdict(int)

        # working data will be appended after an interval is popped
        self.completedData = []

        # convenience
        self.max_bug_score = 0
        self.commits_buffer = {'commits': [], 'date':None}


    def execute_with_gen(self, gen):
        """
        Starts mining the cursor for hotspot metrics. Return a list
        containing the completed file structures from analysis.
        """

        for f in gen:
            self.__feed_file(f)

        if len(self.intervals) > 0:
            self.__post_process_data()

        return self.completedData

    def __feed_file(self, current_file):
        """
        Accepts a file from MetricsBuilder and extracts it into various metrics
        as needed
        """

        # TODO -- parralelize processing... add input queue to this feed_file
        # this could all be made a lot quicker

        # Sanity check
        if len(self.intervals) == 0:
            self.log.error("Error -- passed file_info even though object has \
                            no more intervals left to parse! File info: %s", current_file)
            return

        start_scope, end_scope = self.intervals[0][0], self.intervals[0][1]
        current_scope = current_file['date']

        # TODO -- current logic just keeps going in between intervals
        # (so the case where start1 != end2 will fail miserably)
        # relying on input checking before it propagates to this point ATM

        # Check if file passed out of range
        if current_scope > end_scope:
            self.log.info("Interval %s out of range for file date %s\n\nCopying data and \
                           starting next interval (if any).", self.intervals[0], current_file)
            self.__post_process_data()
            # Reset relative values on working data
            self.__reset_working_data()

        # Now actually deal with parsing these metrics...
        self.__process_general_info(current_file)
        self.__process_bug_info(current_file)
        self.__process_temporal_info(current_file)


    def __process_general_info(self, current_file):
        """
        Extract high level information like lines of code, name, ect.
        """
        # self.log.debug("Extracting general information from file: %s", current_file['filename'])

        if current_file['filename'] not in self.working_data.keys():
            self.working_data[current_file['filename']] = {'creation_date': current_file['date'],
                                                'bug_dates': [], 'bug_messages': [],
                                                'loc': 0, 'bug_score': 0}

        f = self.working_data[current_file['filename']]
        f['loc'] += current_file['insertions'] - current_file['deletions']
        f['last_modified'] = current_file['date']


    def __process_bug_info(self, current_file):
        """
        Responsible for parsing bug score related information out of the file
        """

        if self.__is_bug(current_file['message']):
            f = self.working_data[current_file['filename']]

            # just for debugging really
            # f['bug_messages'].append(mod_file['message'])
            # f['bug_dates'].append(mod_file['date'])

            # Sanity check
            if (self.intervals[0][1] < current_file['date']):
                self.log.error("Current file date is passed our end interval! \
                                Something has gone terribly wrong! \
                                Current interval: %s\nCurrent date: %s",
                                self.intervals[0], current_file['date'])

            # Add score to each file. Scoring function based on research from Chris
            # Lewis and Rong Ou
            end_date = self.intervals[0][1]
            fix_date = current_file['date']
            time_delta = end_date - f['creation_date']
            if time_delta <= 0:
                norm_time = 1.0
            else:
                norm_time = 1 - (float(end_date - fix_date) / (time_delta))
            f['bug_score'] += 1 / (1 + math.exp(-12 * norm_time + 12))

            if f['bug_score'] > self.max_bug_score:
                self.max_bug_score = f['bug_score']


    def __process_temporal_info(self, current_file):
        """
        Responsible for handling temporal coupling metrics
        """

        # Increment revision count for file
        self.working_rev_counts[current_file['filename']] += 1

        # Dirty hack to regroup the original files from a commit since
        # I unwound them in the original db query like a bad
        if ((self.commits_buffer['date'] is not None) and
            (self.commits_buffer['date'] != current_file['date'])):
            # Process the buffer into temporal frequency counts
            commits = self.commits_buffer['commits']

            for pair in combinations(commits, 2):
                ordered_pair = sorted(pair)
                self.working_couples[(ordered_pair[0], ordered_pair[1])] += 1

            self.commits_buffer = {'commits': [], 'date':None}

        # Even if we have a full batch, still need to add a new one
        self.commits_buffer['date'] = current_file['date']
        self.commits_buffer['commits'].append(current_file['filename'])


    def __process_contribution_info(self, current_file):
        """
        Responsible for extracting information pertaining to developer contributions
        and knowledge map
        """
        pass


    def __process_age_info(self, f):
        """
        Responsible for calculating code age
        """
        pass


    def __post_process_data(self):
        """
        Invoked when we finish up an interval
        """
        # Create a new COPY of the data for next interval.
        self.log.debug("Starting postprocessing. Copying data...")
        cached_data = self.working_data.copy()

        # Normalize bug scores
        if self.max_bug_score != 0:
            for f in cached_data:
                cached_data[f]['bug_score'] /= self.max_bug_score

        debug_copy = self.working_couples.copy()

        # Algorithm for scoring temporal frequency
        for pair, count in self.working_couples.iteritems():
            avg_of_pair = ((self.working_rev_counts[pair[0]] + self.working_rev_counts[pair[1]]) / 2.0)
            self.working_couples[pair] /= avg_of_pair


        sorted_result = sorted(self.working_couples.items(), \
                               key = lambda x: x[1], reverse=True)

        # TODO --- figure out how to normalize these temp. frequencies for viz
        # DEBUG
        # self.log.info("\n\nTop 15 temporal frequencies: %s\n\n", sorted_result[:15])
        for result in sorted_result[0:25]:
            pairs = result[0]
            first = pairs[0]
            second = pairs[1]
            score = result[1]
            self.log.debug("------------------------------------------------")
            self.log.debug("Coupling between file %s and %s :", first, second)
            self.log.debug("Score: %s", score)
            self.log.debug("Joint Occurences: %s", debug_copy[pair])
            self.log.debug("Total count for %s:  %s", first, self.working_rev_counts[first])
            self.log.debug("Total count for %s:  %s", second, self.working_rev_counts[second])

        # Add data to self.completedData, pop an interval off
        self.log.debug("Popping off interval: %s. Adding dataset to completed data.",
                                                                self.intervals[0])

        self.log.debug("Removing files smaller than threshhold...")
        files_to_filter = []
        for f_name, f_info in cached_data.iteritems():
            if f_info['loc'] < LOC_THRESHOLD:
                files_to_filter.append(f_name)
        self.log.debug("Removing %s files", len(files_to_filter))
        for f in files_to_filter:
            # self.log.debug("Removing file %s because it only had %s lines", f, files[f]['loc'])
            cached_data.pop(f, None)

        self.completedData.append(cached_data)
        self.intervals.pop(0)


    def __reset_working_data(self):
        # Reset appropriate params on self.working_data
        # Be mindful to keep bug information, but reset temporal coupling
        self.log.debug("Reseting working data...")

        self.working_couples = defaultdict(int)
        self.working_rev_counts = defaultdict(int)
        self.commits_buffer = {'commits': [], 'date':None}


    def __is_bug(self, message):
        """
        DOCSTRING
        """
        return self.regex.match(message) != None
