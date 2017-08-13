import logging
from codemd.data_managers.db_handler import DBHandler

class CirclePackingMetricsStore(object):

    MAX_CHECKPOINTS = 4

    def __init__(self, metrics):
        self.log = logging.getLogger('codemd.CirclePackingMetricsStore')
        self.interval = metrics.intervals
        self.modules = metrics.modules
        self.working_data = metrics.working_data
        self.db_handler = DBHandler(metrics.project_name)

        # Used to calculate remaining files that need to be processed outside of
        # data loaded from checkpoint interval
        self.first_checkpoint = None
        self.last_checkpoint = None

    def persist_checkpoints(self):
        total_mods = self.db_handler.file_history_count()
        chunk_size = total_mods/self.MAX_CHECKPOINTS
        finished_day = None
        count, chunks_processed = 0, 0

        self.log.info("Starting persisting cricle packing data with\n"
                        + "MAX_CHECKPOINTS: %s\nchunk_size: %s\ntotal_mods: %s",
                        self.MAX_CHECKPOINTS, chunk_size, total_mods)

        for f in self.db_handler.file_history():
            if count >= chunk_size:
                if finished_day is None:
                    finished_day = f['date']
                    self.log.debug("Reached maximum chunk size at date: %s", finished_day)
                elif finished_day != f['date']:
                    # then we are done with this chunk
                    self.log.debug("ENCOUNTERED NEW DATE: %s", f['date'])
                    count = count - chunk_size
                    chunks_processed += 1
                    self.log.debug("Finished rest of commits for date in chunk"
                                    + "\nchunks_processed = %s\noverflow = %s",
                                    chunks_processed, count - 1)
                    self.__save_checkpoint(finished_day)
                    finished_day = None
                else: # DEBUG
                    self.log.debug("Overflowing revision: %s ... at date: %s",
                                    f['revision_id'], f['date'])
            count += 1
            for mod in self.modules:
                mod.process_file(f)

        # Store last checkpoint
        self.log.debug("Storing last checkpoint...")
        self.__save_checkpoint(f['date'])

        self.log.info("Finished persisting circle packing data.")

    def __save_checkpoint(self, checkpoint_date):
        self.log.debug("Saving circle packing checkpoint at date %s", checkpoint_date)
        for mod in self.modules:
            self.db_handler.persist_packing_data(checkpoint_date, mod.MODULE_KEY,
                                                mod.persist_mappings())


    def load_interval(self):
        """
        Loads circle packing data at:
            - the first checkpoint AFTER the start of the interval
            - the first checkpoint BEFORE the end of the interval
        And then instructs the circle packing modules to load the diffrence.

        """
        start, end = self.interval[0][0], self.interval[0][1]
        if start is None:
            start = self.db_handler.first_revision_date()
        if end is None:
            end = self.db_handler.last_revision_date()

        self.first_checkpoint = self.db_handler.find_closest_checkpoint(start, before=True)
        self.last_checkpoint = self.db_handler.find_closest_checkpoint(end, before=False)

        self.log.debug("Found start date %s and end date %s for interval: %s",
                        self.first_checkpoint, self.last_checkpoint, self.interval)

        # how the fuck to tell modules to load from the difference of 2 generators? fuckz


        # self.log.info("Loading first checkpoint closest to date: %s", closest_date)
        # checkpoint_date = self.db_handler.find_closest_checkpoint(closest_date)
        # self.log.info("Found closest checkpoint at date: %s", checkpoint_date)

        # DEBUG
        # for checkpoint_data in self.db_handler.fetch_checkpoint_data(checkpoint_date):
        #     self.log.debug("checkpoint data: %s", checkpoint_data)

        # set self.last_checkpoint once we figure out what it is from db_manager

    def gen_remaining_files(self):
        if self.last_checkpoint is None:
            self.log.error("Get remaining file called without self.last_checkpoint set!!!")
            return
