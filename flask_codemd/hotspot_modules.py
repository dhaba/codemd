from abc import ABCMeta, abstractmethod
import logging
import re
import math
from collections import defaultdict
from itertools import combinations

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

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)
        self.working_couples = defaultdict(int)
        self.working_rev_counts = defaultdict(int)
        self.commits_buffer = {'commits': [], 'date':None}

    def process_file(self, current_file):
        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return
            
        # Increment revision count for file
        self.working_rev_counts[current_file['filename']] += 1

        # Hack(ish) to regroup the original files from a commit since
        # I unwound them in the original db query
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

        # DEBUG
        # self.log.debug("\n\nCommits buffer: %s", self.commits_buffer)
        # self.log.debug("\nend commits buffer\n")

    def post_process_data(self):
        # Algorithm for scoring temporal frequency
        for pair, count in self.working_couples.iteritems():
            avg_of_pair = (
                (self.working_rev_counts[pair[0]] + self.working_rev_counts[pair[1]]) / 2.0)
            self.working_couples[pair] /= avg_of_pair

        # TODO --- figure out how to normalize these temp. frequencies for viz
        # DEBUG
        # sorted_result = sorted(self.working_couples.items(),
        #                        key=lambda x: x[1], reverse=True)
        # self.log.info("\n\nTop 15 temporal frequencies: %s\n\n", sorted_result[:15])
        # for result in sorted_result[0:25]:
        #     pairs = result[0]
        #     first = pairs[0]
        #     second = pairs[1]
        #     score = result[1]
        #     self.log.debug("------------------------------------------------")
        #     self.log.debug("Coupling between file %s and %s :", first, second)
        #     self.log.debug("Score: %s", score)
        #     self.log.debug("Joint Occurences: %s", debug_copy[pair])
        #     self.log.debug("Total count for %s:  %s", first,
        #                    self.working_rev_counts[first])
        #     self.log.debug("Total count for %s:  %s", second,
        #                    self.working_rev_counts[second])
