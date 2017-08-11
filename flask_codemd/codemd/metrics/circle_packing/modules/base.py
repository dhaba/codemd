import logging
from abc import ABCMeta, abstractmethod, abstractproperty
import copy

class CirclePackingModule:
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

    @abstractproperty
    def MODULE_KEY(self):
        pass

    @abstractproperty
    def DEFAULT_DATA(self):
        pass

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
        return ((current_scope >= start_scope) and (current_scope <= end_scope))

    def get_or_create_key(self, file_name, key=None, default_data=None):
        """
        Utility method to either create a key for a specific module in working_data
        or return it if it already exists.

        :param file_name: The filename to lookup in self.working_data
        :param key: The key name to return or create
                    (ie self.working_data[file_name][key])
        :param defaultData: A dictionary containing the default values for key
                            (ie self.working_data[file_name][key] = defaultData)

        :return self.working_data[file_name][key] (which is a dictionary)
        """
        if key is None:
            key = self.MODULE_KEY
        if default_data is None:
            default_data = self.DEFAULT_DATA

        if file_name not in self.working_data.keys():
            self.working_data[file_name] = {}
        if key not in self.working_data[file_name]:
            self.working_data[file_name][key] = copy.deepcopy(default_data)
        return self.working_data[file_name][key]
