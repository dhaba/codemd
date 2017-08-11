import logging

from codemd.metrics.circle_packing.modules.file_info import FileInfoModule
from codemd.metrics.circle_packing.modules.bugs import BugModule
from codemd.metrics.circle_packing.modules.knowledge_map import KnowledgeMapModule
from codemd.metrics.circle_packing.modules.temporal_coupling import TemporalCouplingModule

class CirclePackingMetrics(object):
    """
    Helper class for computing hotspot metrics (temporal coupling, code age,
    knowledge map, bug scores), for use in Circle Packing viz.

    Should only be used internally by MetricsBuilder.

    :param intervals: An array of tuples, identifying the (start_time, end_time) for
    each interval. For only one interval, pass an array with one element.
    NOTE : Assumes times are in epoch unix! Blame github lol.
    """

    def __init__(self, intervals):
        self.log = logging.getLogger('codemd.CirclePackingMetrics')
        self.log.info("CirclePackingMetrics created with interval: %s", intervals)

        # Local Variables to track metrics
        self.intervals = intervals
        self.working_data = {} # high level file info, dict of dicts. key is filename
        self.modules = []
        self.counter = 0

        # working data will be appended after an interval is popped
        self.completedData = []

        self.__reset_modules()


    def execute_with_gen(self, gen):
        """
        Starts mining the cursor for hotspot metrics. Return a list
        containing the completed file structures from analysis.

        Returns a generator for optimal performance
        """
        for f in gen:
            if len(self.intervals) > 0:
                self.__feed_file(f)

        if len(self.intervals) > 0:
            self.log.debug("Calling __post_process_data from execute_with_gen")
            self.__post_process_data()

        return self.completedData

    def __feed_file(self, current_file):
        """
        Accepts a file from MetricsBuilder and extracts it into various metrics
        as needed
        """
        # TODO -- parralelize processing... add input queue to this feed_file
        # this could all be made a lot quicker

        self.counter += 1
        if self.counter % 2048 == 0:
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
                self.__reset_modules()
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


    def __reset_modules(self):
        # Reset modules data so they are fresh to recompute the next interval
        self.log.debug("Reseting modules data...")
        self.modules = [FileInfoModule(self.working_data, self.intervals),
                        BugModule(self.working_data, self.intervals),
                        TemporalCouplingModule(self.working_data, self.intervals),
                        KnowledgeMapModule(self.working_data, self.intervals)]
