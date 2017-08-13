from codemd.metrics.circle_packing.modules.base import CirclePackingModule
from collections import defaultdict

class KnowledgeMapModule(CirclePackingModule):
    """
    Extracts top contributors for each module
    """

    MODULE_KEY = "knowledge_info"
    DEFAULT_DATA = {"author": None, "color": None,
                    "top_authors": defaultdict(int)}

    # Optimally distinct colors of maximum contrast based on research by Kenneth Kelly
    AUTHOR_COLORS = ['#BE0032', '#F3C300', '#F38400',
                  '#A1CAF1', '#C2B280', '#848482', '#008856', '#E68FAC',
                  '#0067A5', '#F99379', '#604E97', '#B3446C', '#DCD300',
                  '#882D17', '#8DB600', '#654522', '#E25822', '#2B3D26', '#222222']
    # If we run out of colors above, use off white for 'other' author
    OTHER_COLOR = '#F2F3F4'

    def __init__(self, working_data, intervals):
        CirclePackingModule.__init__(self, working_data, intervals)

    def process_file(self, current_file):
        knowledge_info = self.get_or_create_key(current_file['filename'])
        num_changes = current_file['insertions'] + current_file['deletions']
        knowledge_info['top_authors'][current_file['author']] += num_changes

    def post_process_data(self):
        authors_key = {}
        top_authors_count = defaultdict(int)
        # Get top few contributors for each file
        self.log.info("Starting post processing for KnowledgeMap." +
                      " Sorting modules for top authors...")
        for module in self.working_data:
            knowledge_info = self.get_or_create_key(module)
            sorted_authors = sorted(knowledge_info['top_authors'].iteritems(),
                                    key = lambda (k, v): v, reverse=True)
            top_authors_count[sorted_authors[0][0]] += 1
            knowledge_info['top_authors'] = sorted_authors[0:3]
            knowledge_info['author'] = sorted_authors[0][0]

        self.log.info("Finished sorting modules for top authors." +
                      " Determining appropriate color map...")
        sorted_top_authors = sorted(top_authors_count.iteritems(),
                                    key = lambda (k, v): v, reverse=True)
        for i in xrange(min(len(sorted_top_authors), len(self.AUTHOR_COLORS))):
            authors_key[sorted_top_authors[i][0]] = self.AUTHOR_COLORS[i]
        for module in self.working_data:
            knowledge_info = self.get_or_create_key(module)
            top_author = knowledge_info['author']
            if top_author in authors_key:
                knowledge_info['color'] = authors_key[top_author]
            else:
                knowledge_info['color'] = self.OTHER_COLOR
            # Convert top_authors to a dict for front end
            knowledge_info['top_authors'] = {k:v for k, v in knowledge_info['top_authors']}
            # DEBUG
            # self.log.debug("module %s with working_data: %s", module, self.working_data[module])

        self.log.info("Finished building author color map.")
        # self.log.debug("Author key: %s", json.dumps(author_keys, indent=2))
        # self.log.debug("Top Authors: %s", json.dumps(author_keys, indent=2))
        self.log.info("Finished post processing for KnowledgeMap.")

    def persist_mappings(self):
        # All this modules data is in working_data
        return
