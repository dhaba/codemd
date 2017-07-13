from abc import ABCMeta, abstractmethod
import logging
import re
import math
from collections import defaultdict
from itertools import combinations

import json

# ::::  HEURISTICS ::::
# Hard coded rules for inclusion/exclusion of files when calculated various metrics
# Ideally these would be exposed to the user for custom tinkering
LOC_THRESHOLD = 24 # min number of lines to be considered in circle packing

class HotspotModule:
    """
    Abstract class for processing files to build metrics for circle packing viz

    :param working_data: A dictionary of dictionaries containing file info. Ex:
        "file_name" : {
            "loc": ...,
            "bug_score": ...,
            "creation_date": ...,
            ....
        }

    :param intervals: An array of tuples, identifying the (start_time, end_time)
    for each interval. For only one interval, pass an array with one element.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, working_data, intervals):
        self.log = logging.getLogger('codemd.MetricsBuilder.HotspotsUtil.' + \
                                     self.__class__.__name__)
        self.working_data = working_data
        self.intervals = intervals

    @abstractmethod
    def process_file(self, current_file):
        pass

    @abstractmethod
    def post_process_data(self):
        pass

    def is_file_in_scope(self, current_file):
        """
        Utility method to check if the current file edit is within our interval
        """
        start_scope, end_scope = self.intervals[0][0], self.intervals[0][1]
        current_scope = current_file['date']
        if ((current_scope >= start_scope) and (current_scope <= end_scope)):
            return True
        else:
            return False


class FileInfoModule(HotspotModule):
    """
    Extract high level information including:
        - lines of code (LOC)
        - filename
        - date last modified.
    """

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)

    def process_file(self, current_file):
        if current_file['filename'] not in self.working_data.keys():
            self.working_data[current_file['filename']] = {'creation_date': current_file['date'],
                                            #    'bug_dates': [], 'bug_messages': [],
                                                'loc': 0, 'bug_score': 0, 'bug_count': 0}

        f = self.working_data[current_file['filename']]
        f['loc'] += current_file['insertions'] - current_file['deletions']
        f['last_modified'] = current_file['date']

    def post_process_data(self):
        self.log.debug("Starting post processing for FileInfoModule")
        self.log.debug("Removing files smaller than threshhold...")

        files_to_filter = []
        for f_name, f_info in self.working_data.iteritems():
            if f_info['loc'] < LOC_THRESHOLD:
                files_to_filter.append(f_name)
        self.log.debug("Removing %s files", len(files_to_filter))
        for f in files_to_filter:
            # self.log.debug("Removing file %s because it only had %s lines", f, files[f]['loc'])
            self.working_data.pop(f, None)


class BugModule(HotspotModule):

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')
        self.max_bug_score = 0

    def process_file(self, current_file):
        """
        Responsible for parsing bug score related information out of the file
        """
        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return

        if self.__is_bug(current_file['message']):
            f = self.working_data[current_file['filename']]

            # just for debugging really
            # f['bug_messages'].append(mod_file['message'])
            # f['bug_dates'].append(mod_file['date'])
            f['bug_count'] += 1

            # Add score to each file. Scoring function based on research from Chris
            # Lewis and Rong Ou at Google
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

    def post_process_data(self):
        # Normalize bug scores
        self.log.debug("Post processing bug info...normalizing bug scores")
        if self.max_bug_score != 0:
            for f in self.working_data:
                self.working_data[f]['bug_score'] /= self.max_bug_score

    def __is_bug(self, message):
        """
        DOCSTRING
        """
        return self.regex.match(message) != None


class TemporalModule(HotspotModule):
    """
    Responsible for handling temporal coupling metrics.
    See GitHub page for description of the science behind temporal coupling
    analysis.
    """

    # Module will only report the NUM_TOP_COUPLES highest entries scored by the
    # temporal coupling algorithm
    NUM_TOP_COUPLES = 20

    # Ignore coupled test case files (ie 'moduleA' and 'moduleA_test')
    IGNORE_TEST_CASE_COUPLES = True

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)
        self.working_couples = defaultdict(int) # (file1, file2) : # of mutual revisions
        self.working_rev_counts = defaultdict(int) # (file) : # of revisions
        self.commits_buffer = {'commits': [], 'revision_id':None}

    def process_file(self, current_file):
        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return

        # Increment revision count for file
        self.working_rev_counts[current_file['filename']] += 1

        # Hack(ish) to regroup the original files from a commit since
        # I unwound them in the original db query
        if ((self.commits_buffer['revision_id'] is not None) and
            (self.commits_buffer['revision_id'] != current_file['revision_id'])):
            # Process the buffer into temporal frequency counts
            self.__process_commits_buffer()

        # Even if we have a full batch, still need to add a new one
        self.commits_buffer['revision_id'] = current_file['revision_id']
        self.commits_buffer['commits'].append(current_file['filename'])

        # DEBUG
        # self.log.debug("\n\nCommits buffer: %s", self.commits_buffer)
        # self.log.debug("\nend commits buffer\n")

    def post_process_data(self):
        """
        Algorithm for scoring temporal frequency
        """
        # Process batch of files (last commit)
        self.__process_commits_buffer()

        couples = {}
        for pair, count in self.working_couples.iteritems():
            # Ignore files and their test cases if specified to do so
            if self.IGNORE_TEST_CASE_COUPLES and self.__is_test_case(pair[0], pair[1]):
                continue
            avg_pair_revs = (self.working_rev_counts[pair[0]] + self.working_rev_counts[pair[1]]) / 2.0
            score = count/avg_pair_revs * math.log(avg_pair_revs)
            couples[pair] = {'score': score, 'total_mutual_revs' : count, 'avg_revs': avg_pair_revs,
                             pair[0]: self.working_rev_counts[pair[0]],
                             pair[1]: self.working_rev_counts[pair[1]]}


        # for key, val in couples.iteritems():
        #     self.log.debug("%s : %s", key, val)

        sorted_result = sorted(couples.iteritems(),
                               key=lambda (k,v): v['score'], reverse=True)

        self.log.debug("Top %s temporal coupling results: %s",
                        self.NUM_TOP_COUPLES,
                        json.dumps(sorted_result[0:self.NUM_TOP_COUPLES], indent=2))
        # self.log.debug("all couples: %s", json.dumps(sorted_result, indent=2))

    def __process_commits_buffer(self):
        """
        Process current files batch in commits buffer
        """
        if self.commits_buffer['revision_id'] is not None:
            for pair in combinations(self.commits_buffer['commits'], 2):
                ordered_pair = sorted(pair)
                ordered_tuple = (ordered_pair[0], ordered_pair[1])
                self.working_couples[ordered_tuple] += 1

                if ordered_tuple == ("pandas/computation/expr.py", "pandas/computation/ops.py"):
                    # self.log.debug("COMMITS BUFFER: %s", self.commits_buffer)
                    self.log.debug("---count thus far: %s\n commits_buffer: %s", self.working_couples[(ordered_pair[0], ordered_pair[1])], self.commits_buffer)

            self.commits_buffer = {'commits': [], 'revision_id':None}
        else:
            self.log.warning("!!! __process_commits_buffer called on empty commits_buffer")

    def __is_test_case(self, file1, file2):
        """
        Does some simple string matching to determine if file1 and file2 are module
        and test (ie 'moduleA' and 'moduleA_test')
        """
        file1, file2 = file1.split('/')[-1], file2.split('/')[-1]
        test_string = "test"
        return (((file1 in file2) and test_string in file2) or
               ((file2 in file1) and test_string in file1))
