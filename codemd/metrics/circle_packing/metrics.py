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
        # NOTE -- this logic won't fly with multiple intervals.
        self.log.info("Loading checkpoint module data differentials for interval: %s...",
                       self.intervals)
        if self.metrics_store.load_interval():
            self.log.info("Processing remaining files not caught in checkpoint differntial interval...")
            self.log.debug("Processing first chunk...")
            for f in self.metrics_store.gen_first_missing_files():
                self.__feed_file(f, only_scoped=True)
            self.log.debug("Processing last chunk...")
            for f in self.metrics_store.gen_second_missing_files():
                self.__feed_file(f)
        else:
            self.log.info("No checkpoints found in intervals, processing data " +
                          "from first available checkpoint to interval start...")
            for f in self.metrics_store.gen_first_missing_files():
                self.__feed_file(f)
            self.log.debug("Done processing from checkpoint to interval start")
            self.log.debug("Processing entire interval: %s", self.intervals[0])
            for f in self.metrics_store.gen_second_missing_files():
                self.__feed_file(f)

        self.log.info("Done processing remaining files. Starting post processing...")
        self.__post_process_data()
        self.log.info("Done with post processing")
        return self.completedData

    def __feed_file(self, f, only_scoped=False):
        for mod in self.modules:
            if only_scoped:
                if mod.is_scoped:
                    mod.process_file(f)
            else:
                mod.process_file(f)

    def __post_process_data(self):
        """
        Invoked when we finish up an interval
        """
        for mod in self.modules:
            mod.post_process_data()
        self.log.debug("Popping off interval: %s", self.intervals[0])
        self.intervals.pop(0)
        self.completedData.append(self.working_data.copy())
