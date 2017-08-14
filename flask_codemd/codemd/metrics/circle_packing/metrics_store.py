import logging
import itertools
from codemd.data_managers.db_handler import DBHandler

from codemd.metrics.circle_packing.modules.file_info import FileInfoModule
from codemd.metrics.circle_packing.modules.bugs import BugModule
from codemd.metrics.circle_packing.modules.knowledge_map import KnowledgeMapModule
from codemd.metrics.circle_packing.modules.temporal_coupling import TemporalCouplingModule

import pdb

class CirclePackingMetricsStore(object):

    MAX_CHECKPOINTS = 16

    def __init__(self, metrics):
        self.log = logging.getLogger('codemd.CirclePackingMetricsStore')
        self.modules = metrics.modules
        self.metrics = metrics
        self.db_handler = DBHandler(metrics.project_name)
        self.intervals = metrics.intervals
        self.first_checkpoint = None
        self.last_checkpoint = None
        self.reset_modules()

    def persist_checkpoints(self):
        total_mods = self.db_handler.file_history_count()
        chunk_size = total_mods/self.MAX_CHECKPOINTS
        finished_day = None
        total_count, count, chunks_processed = 0, 0, 0

        self.log.info("Starting persisting cricle packing data with\n"
                        + "MAX_CHECKPOINTS: %s\nchunk_size: %s\ntotal_mods: %s",
                        self.MAX_CHECKPOINTS, chunk_size, total_mods)

        for f in self.db_handler.file_history():
            if total_count == 0:
                self.log.debug("Storing first blank checkpoint at date %s", f['date'])
                self.__save_checkpoint(f['date'])
            if count >= chunk_size:
                if finished_day is None:
                    finished_day = f['date']
                elif finished_day != f['date']:
                    count = count - chunk_size
                    chunks_processed += 1
                    self.log.debug("Complete chunk,"
                                    + "\n\tchunks_processed = %s\n\toverflow = %s",
                                    chunks_processed, count - 1)
                    self.__save_checkpoint(finished_day)
                    finished_day = None
            for mod in self.modules:
                mod.process_file(f)
            count += 1
            total_count += 1
            if total_count % 512 == 0:
                self.log.debug("Total files processed so far: %s", total_count)

        self.log.debug("Storing last checkpoint at date: %s", f['date'])
        self.__save_checkpoint(f['date'])

        self.log.info("Finished persisting circle packing data.")

    def load_interval(self):
        """
        Loads circle packing data at:
            - the first checkpoint AFTER the start of the interval
            - the first checkpoint BEFORE the end of the interval
        And then instructs the circle packing modules to load the diffrence.

        """
        start, end = self.intervals[0][0], self.intervals[0][1]

        self.first_checkpoint = self.db_handler.find_closest_checkpoint(start, before=False)
        self.last_checkpoint = self.db_handler.find_closest_checkpoint(end, before=True)
        self.log.debug("Found first checkpoint %s and second checkpoint %s for interval: %s",
                        self.first_checkpoint, self.last_checkpoint, self.intervals)

        self.log.debug("Creating modules from first checkpoint data...")
        first_modules = self.__create_modules(self.db_handler.fetch_checkpoint_data(self.first_checkpoint))
        self.log.debug("Creating modules from second checkpoint data...")
        last_modules = self.__create_modules(self.db_handler.fetch_checkpoint_data(self.last_checkpoint))

        self.log.debug("Setting self.modules to difference of last and second checkpoint data...")
        self.modules = []
        for last_mod, first_mod in itertools.izip(last_modules, first_modules):
            # Sanity check TODO -- remove this
            if last_mod.MODULE_KEY != first_mod.MODULE_KEY:
                self.log.error("you fucked up somewhere! module keys dont match")
                pdb.set_trace()
            self.modules.append(last_mod.subtract_module(first_mod))

        # Hack to set working data after loading - TODO find a clean solution
        self.metrics.working_data = self.modules[0].working_data
        self.metrics.modules = self.modules

        self.log.debug("Finished loading interval")

    def gen_first_missing_files(self):
        """
        Returns a generator to the first chunk of file not caught between the
        checkpoint interval (ie all files from interval start to first checkpoint)
        """
        # Subtract one from first_checkpoint date because all the data on the
        # specific date was loaded during the load_interval process
        return self.db_handler.file_history(start_date = self.intervals[0][0],
                                            end_date = self.first_checkpoint - 1)

    def gen_second_missing_files(self):
        """
        Returns a generator to the second chunk of file not caught between the
        checkpoint interval (ie all files from second checkpoint to interval end)
        """
        # Add one to last_checkpoint date because all the data on the
        # specific date was loaded during the load_interval process
        return self.db_handler.file_history(start_date = self.last_checkpoint + 1,
                                            end_date = self.intervals[0][1])

    def reset_modules(self):
        # Reset modules data so they are fresh to recompute the next interval
        self.log.debug("Resetting modules...")
        self.modules = self.__blank_modules()

    def __blank_modules(self):
        working_data = {}
        return [FileInfoModule(working_data, self.intervals),
                        BugModule(working_data, self.intervals),
                        TemporalCouplingModule(working_data, self.intervals),
                        KnowledgeMapModule(working_data, self.intervals)]

    def __create_modules(self, checkpoint_data_gen):
        """
        Instantiates a new instance of each module in self.modules and populates
        each one with the data from the checkpoint_data

        :param checkpoint_data_gen: A generator to a list of checkpoint data caches
        :type checkpoint_data_gen: pymongo.cursor.Cursor
        :return: A new module for each in self.modules loaded with the checkpoint data
        :rtype: list
        """
        new_modules = self.__blank_modules()

        for data in checkpoint_data_gen:
            self.log.debug("Creating module <%s> from checkpoint data",
                            data['module_key'])

            # Hack to set working data for all modules
            if data['module_key'] == FileInfoModule.MODULE_KEY:
                working_data = data['data']['working_data']
                for mod in new_modules:
                    mod.working_data = working_data

            mod = [m for m in new_modules if m.MODULE_KEY == data['module_key']]
            if len(mod) == 0:   # Sanity check TODO -- delete this
                self.log.error("Could not find corresponding module for key %s!", data['module_key'])
                continue
            mod = mod[0]

            mod.load_data(data['data'])
        return new_modules

    def __save_checkpoint(self, checkpoint_date):
        self.log.debug("Saving circle packing checkpoint at date %s", checkpoint_date)
        for mod in self.modules:
            self.db_handler.persist_packing_data(checkpoint_date, mod.MODULE_KEY,
                                                mod.persist_mappings())
