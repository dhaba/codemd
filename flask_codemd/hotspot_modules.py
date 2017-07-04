from abc import ABCMeta, abstractmethod

class HotspotModule:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __process_file(self):
        pass

    @abstractmethod
    def __post_process_data(self, file_heirarchy):
        pass


class TemporalModule(HotspotModule):

    def __init__(self):
        pass

    def __process_file(self):
        pass

    def __post_process_data(self, file_heirarchy):
        pass


class BugModule(HotspotModule):

    def __init__(self):
        pass

    def __process_file(self):
        pass

    def __post_process_data(self, file_heirarchy):
        pass
