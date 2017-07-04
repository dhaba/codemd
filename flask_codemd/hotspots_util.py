import math
from collections import defaultdict
from itertools import combinations
import logging
import re
import datetime
import metrics_builder

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
        self.working_data = {} # high level file info, dict of dicts. key is filename

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

        Returns a generator for optimal performance
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
        self.__process_contribution_info(current_file)


    def __process_general_info(self, current_file):
        """
        Extract high level information like lines of code, name, ect.
        """
        # self.log.debug("Extracting general information from file: %s", current_file['filename'])

        if current_file['filename'] not in self.working_data.keys():
            self.working_data[current_file['filename']] = {'creation_date': current_file['date'],
                                                'bug_dates': [], 'bug_messages': [],
                                                'loc': 0, 'bug_score': 0, 'bug_count': 0}

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
            f['bug_count'] += 1

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

        # TODO FIXME
        # Hack to regroup the original files from a commit since
        # I unwound them in the original db query like an idiot
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
        self.log.debug("\n\nCommits buffer: %s", self.commits_buffer)
        self.log.debug("\nend commits buffer\n")


    def __process_contribution_info(self, current_file):
        """
        Responsible for extracting information pertaining to developer contributions
        and knowledge map
        """
        #print current_file
        pass


    def __process_age_info(self, f):
        """
        Responsible for calculating code age

        Should compute:
            - date last modified for each file
            - composite modifications, computed with logistic function to weight
              recent modifications higher than others
        """
        pass
        # self.log.debug("Processing age info...")
        #
        # for commit in self.commits:
        #     if commit.age > 10:
        #         commit.age += 10
        #     else:
        #         commit.age -= 1



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
            avg_of_pair = (
                (self.working_rev_counts[pair[0]] + self.working_rev_counts[pair[1]]) / 2.0)
            self.working_couples[pair] /= avg_of_pair

        sorted_result = sorted(self.working_couples.items(),
                               key=lambda x: x[1], reverse=True)

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
            self.log.debug("Total count for %s:  %s", first,
                           self.working_rev_counts[first])
            self.log.debug("Total count for %s:  %s", second,
                           self.working_rev_counts[second])

        # Add data to self.completedData, pop an interval off
        self.log.debug("Popping off interval: %s. Adding dataset to completed data.",
                       self.intervals[0])

        self.log.debug("Removing files smaller than threshhold...")
        files_to_filter = []
        for f_name, f_info in cached_data.iteritems():
            if f_info['loc'] < metrics_builder.LOC_THRESHOLD:
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
