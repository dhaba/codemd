from codemd.metrics.circle_packing.modules.base import CirclePackingModule

class FileInfoModule(CirclePackingModule):
    """
    Extract high level information including:
        - lines of code (LOC)
        - filename
        - number of revisions
        - date last modified.
    """

    MODULE_KEY = 'file_info'

    # Default data for module specific data in working_data
    DEFAULT_DATA = {'creation_date': None, 'loc': 0, 'total_revisions': 0}

     # Minimum number of lines to be considered in circle packing
    LOC_THRESHOLD = 8

    def __init__(self, working_data, intervals):
        CirclePackingModule.__init__(self, working_data, intervals)

    def process_file(self, current_file):
        default_data = self.DEFAULT_DATA
        default_data['creation_date'] = current_file['date']

        f = self.get_or_create_key(current_file['filename'], default_data = default_data)
        f['loc'] += current_file['insertions'] - current_file['deletions']
        f['total_revisions'] += 1
        f['last_modified'] = current_file['date']

    def post_process_data(self):
        self.log.info("Starting post processing for FileInfoModule...")
        self.log.debug("Removing files smaller than threshhold...")

        files_to_filter = []
        for f_name, data in self.working_data.iteritems():
            f_info = data[self.MODULE_KEY]
            if f_info['loc'] < self.LOC_THRESHOLD:
                files_to_filter.append(f_name)
        self.log.debug("Removing %s files for being less than %s lines of code",
                       len(files_to_filter), self.LOC_THRESHOLD)
        for f in files_to_filter:
            # self.log.debug("Removing file %s because it only had %s lines", f, self.working_data[f]['loc'])
            self.working_data.pop(f, None)
        self.log.info("Finished post processing for FileInfoModule.")
