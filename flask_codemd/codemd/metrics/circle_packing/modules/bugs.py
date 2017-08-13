from codemd.metrics.circle_packing.modules.base import CirclePackingModule
import re
import math

class BugModule(CirclePackingModule):

    MODULE_KEY = 'bug_info'
    DEFAULT_DATA = {'count': 0, 'score': 0, 'opacity': 0}

    def __init__(self, working_data, intervals):
        CirclePackingModule.__init__(self, working_data, intervals)
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')
        self.max_bug_score = 0

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

            # Add score to each file. Scoring function based on research from Chris
            # Lewis and Rong Ou at Google
            end_date = self.intervals[0][1]
            start_date = self.intervals[0][0]
            fix_date = current_file['date']
            time_delta = end_date - start_date
            if time_delta <= 0:
                norm_time = 1.0
            else:
                norm_time = 1 - (float(end_date - fix_date) / (time_delta))
            bug_info['score'] += 1 / (1 + math.exp(-12 * norm_time + 12))

            if bug_info['score'] > self.max_bug_score:
                self.max_bug_score = bug_info['score']

    def post_process_data(self):
        # Normalize bug scores
        self.log.info("Post processing BugInfoModule...")
        if self.max_bug_score != 0:
            for f in self.working_data:
                bug_info = self.working_data[f][self.MODULE_KEY]
                bug_info['opacity'] = bug_info['score']/self.max_bug_score
        self.log.info("Finished post processing for BugInfoModule")

    def __is_bug(self, message):
        """
        DOCSTRING
        """
        return self.regex.match(message) != None

    def persist_mappings(self):
        return {'max_bug_score': self.max_bug_score}
