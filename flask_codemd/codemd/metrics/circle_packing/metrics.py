import logging

from codemd.metrics.circle_packing.metrics_store import CirclePackingMetricsStore

from codemd.data_managers.db_handler import DBHandler

import pdb

class CirclePackingMetrics(object):
    """
    Helper class for computing hotspot metrics (temporal coupling, code age,
    knowledge map, bug scores), for use in Circle Packing viz.

    Should only be used internally by MetricsBuilder.

    :param intervals: An array of tuples, identifying the (start_time, end_time) for
    each interval. For only one interval, pass an array with one element.
    NOTE : Assumes times are in epoch unix! Blame github lol.
    """

    def __init__(self, project_name, intervals=None):
        self.log = logging.getLogger('codemd.CirclePackingMetrics')
        self.project_name = project_name
        self.intervals = intervals
        self.__process_intervals()
        self.working_data = {} # high level file info, dict of dicts. key is filename
        self.modules = []
        self.counter = 0
        self.completedData = [] # working data will be appended after an interval is popped
        self.metrics_store = CirclePackingMetricsStore(self)
        self.log.info("CirclePackingMetrics created with interval: %s", intervals)

    def __process_intervals(self):
        """
        Helper method to deal with None values and edge cases in self.intervals
        """
        # TODO -- move this behavior to CirclePackingMetrics
        if self.intervals is None:
            start = DBHandler.first_revision_date(self.project_name)
            end = DBHandler.last_revision_date(self.project_name)
            self.intervals = [[start, end]]
            return
        if ((len(self.intervals) > 1) and (self.intervals[1] == [None, None])):
            self.intervals.pop()
        if self.intervals[0][0] is None:
            self.intervals[0][0] = DBHandler.first_revision_date(self.project_name)
        if self.intervals[-1][1] is None:
            self.intervals[-1][1] = DBHandler.last_revision_date(self.project_name)

    def create_checkpoints(self):
        self.log.info("Creating circle packing checkpoints for project %s", self.project_name)
        self.metrics_store.persist_checkpoints()

    def compute_file_hierarchy(self):
        # NOTE -- this logic won't fly with multiple intervals. Implement that if necessary.
        self.log.info("Loading checkpoint module data differentials for interval: %s...",
                       self.intervals)
        self.metrics_store.load_interval()

        self.log.info("Processing remaining files not caught in checkpoint differntial interval...")
        self.log.debug("Processing first chunk...")
        for f in self.metrics_store.gen_first_missing_files():
            for mod in self.modules:
                if mod.is_scoped:
                    self.__feed_file(f)
        self.log.debug("Processing last chunk...")
        for f in self.metrics_store.gen_second_missing_files():
            for mod in self.modules:
                self.__feed_file(f)

        self.log.info("Done processing remaining files. Starting post proessing...")

        pdb.set_trace()

        self.__post_process_data()
        self.log.info("Done with post processing.")
        return self.completedData




    # def __process_intervals(self, intervals):
    #     """
    #     Process possible "None" values in intervals to appropriate start and end dates
    #     """
    #     if intervals is None:
    #         self.intervals
    #     self.log.debug("Processing interval array %s ...", intervals)
    #     if len(intervals) == 1:
    #         if intervals[0] is None:
    #             interval1_start = 0
    #             self.log.info("intervals[0] was None. Defaulted to 0")
    #         if intervals[1] is None:
    #             interval1_end = float('inf')
    #             self.log.info("Interval_end1 was none. Defaulted to last entry: %s", interval1_end)
    #
    #             self.intervals = [(interval1_start, interval1_end)]
    #     else:
    #         self.intervals = intervals
    #         self.log.warning("Interval of length 2 detected, assuming values"
    #             + "are all valid: %s", self.intervals)

    # def __execute_with_gen(self, gen):
    #     """
    #     Starts mining the cursor for hotspot metrics. Return a list
    #     containing the completed file structures from analysis.
    #
    #     Returns a generator for optimal performance
    #     """
    #     for f in gen:
    #         if len(self.intervals) > 0:
    #             self.__feed_file(f)
    #
    #     if len(self.intervals) > 0:
    #         self.log.debug("Calling __post_process_data from execute_with_gen")
    #         self.__post_process_data()
    #
    #     return self.completedData

    def __feed_file(self, current_file):
        """
        Accepts a file from MetricsBuilder and extracts it into various metrics
        as needed
        """
        # TODO -- parralelize processing... add input queue to this feed_file
        # this could all be made a lot quicker

        self.counter += 1
        if self.counter % 512 == 0:
            self.log.info("Processing files ... files complete so far: %s", self.counter)

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
            # Recall this method if we still have work to do
            if (len(self.intervals) > 0):
                self.metrics_store.reset_modules()
                self.__feed_file(current_file)
            else:
                return

        # Sanity check 1
        if (self.intervals[0][1] < current_file['date']):
            self.log.error("!!!!!\nCurrent file date is passed our end interval! \
                            Something has gone terribly wrong! \
                            Current interval: %s\nCurrent date: %s\nCurrent file: %s \
                            \n!!!!!!!",
                            self.intervals[0], current_file['date'], current_file)

        # Sanity check 2
        if len(self.intervals) == 0:
            self.log.error("!!!!!\nError -- passed file_info even though object has \
                            no more intervals left to parse! File info: %s\n!!!!",
                            current_file)
            return

        # Now actually deal with parsing these metrics...
        for mod in self.modules:
            mod.process_file(current_file)

    def __post_process_data(self):
        """
        Invoked when we finish up an interval
        """
        # DEBUG - print cached_data
        # print json.dumps(self.working_data, indent=1)
        for mod in self.modules:
            mod.post_process_data()

        # Add data to self.completedData, pop an interval off
        self.log.debug("Popping off interval: %s", self.intervals[0])
        self.intervals.pop(0)
        self.completedData.append(self.working_data.copy())
