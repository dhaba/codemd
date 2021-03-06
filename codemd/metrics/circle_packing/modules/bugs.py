from codemd.metrics.circle_packing.modules.base import CirclePackingModule
import re
import math

import pdb

class BugModule(CirclePackingModule):

    MODULE_KEY = 'bug_info'
    DEFAULT_DATA = {'count': 0, 'score': 0, 'opacity': 0, 'bugs': []}

    def __init__(self, working_data, intervals):
        CirclePackingModule.__init__(self, working_data, intervals)
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')

    def process_file(self, current_file):
        """
        Responsible for parsing bug score related information out of the file
        """
        file_name = current_file['filename']
        bug_info = self.get_or_create_key(file_name)

        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return

        if self.__is_bug(current_file['message']):
            bug_info['count'] += 1
            bug_info['bugs'].append(current_file['date'])

    def post_process_data(self):
        self.log.info("Post processing BugInfoModule...")

        self.log.debug("Computing bug scores...")
        # Add score to each file. Scoring function based on research from Chris
        # Lewis and Rong Ou at Google
        max_score = 0
        end_date = self.intervals[0][1]
        start_date = self.intervals[0][0]
        time_delta = end_date - start_date
        for file_name in self.working_data:
            bug_info = self.get_or_create_key(file_name)
            for fix_date in bug_info['bugs']:
                if time_delta <= 0:
                    norm_time = 1.0
                else:
                    norm_time = 1 - (float(end_date - fix_date) / (time_delta))
                bug_info['score'] += 1 / (1 + math.exp(-12 * norm_time + 12))
                if bug_info['score'] > max_score:
                    max_score = bug_info['score']
            # Remove bugs list once we are done using it for computations
            del bug_info['bugs']

        # Set opacity by normalizing bug scores
        if max_score != 0:
            for file_name in self.working_data:
                bug_info = self.get_or_create_key(file_name)
                bug_info['opacity'] = bug_info['score']/max_score

        self.log.info("Finished post processing for BugInfoModule")

    def __is_bug(self, message):
        """
        DOCSTRING
        """
        return self.regex.match(message) != None

    def subtract_module(self, other):
        self.log.debug("Subtracting bugs module data...")
        for file_name in other.working_data:
            # Sanity check TODO -- delete
            if file_name not in self.working_data:
                self.log.error("!!! file %s from other module was not in this modules working data!",
                                file_name)
                continue
            data = self.get_or_create_key(file_name)
            other_data = other.get_or_create_key(file_name)
            # Subtract bug counts
            data['count'] -= other_data['count']
            # Subtract all the bug dates
            for other_bug in other_data['bugs']:
                # Sanity check TODO -- delete
                if other_bug not in data['bugs']:
                    self.log.error("!!! other bug date %s was not in module's own bugs!",
                                    other_bug)
                    continue
                data['bugs'].remove(other_bug)
        self.log.debug("Finished subtracting bugs module data")
        return self
