import re
import logging
from db_handler import DBHandler
from hotspots_util import HotspotsUtil
from hotspot_modules import FileInfoModule, BugModule, TemporalModule, KnowledgeMapModule
from s3_handler import S3Handler

class MetricsBuilder(object):
    """
    Docstring
    """

    def __init__(self, project_name):
        self.project_name = project_name
        self.db_handler = DBHandler(project_name)
        self.log = logging.getLogger('codemd.MetricsBuilder')
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')

    def commits(self):
        """
        TODO -- Add docstring
        """
        self.log.info("Fetching commits info from db...")
        cursor = self.db_handler.fetch_commits()
        self.log.info("Finished fetching commits. Building revisions list /w appropriate"
                        "metrics...")

        docs = []
        total_insertions, total_deletions = 0, 0
        for doc in cursor:
            total_insertions += doc['insertions']
            total_deletions += doc['deletions']
            docs.append({'bug': self.is_bug(doc['message']),
                         'date': doc['date'], 'author': doc['author'],
                         'insertions': doc['insertions'], 'total_insertions': total_insertions,
                         'deletions': doc['deletions'], 'total_deletions': total_deletions })

        self.log.info("Finished building revisions list")
        return docs

    def save_commits(self):
        docs = self.commits()
        self.log.info("Saving commits data for project: %s", self.project_name)
        handler = S3Handler(self.project_name)
        handler.save_dashboard_data(docs)


    def hotspots(self, interval1_start=None, interval1_end=None, interval2_start=None, interval2_end=None):
        """
        Calculates temporal frequency, bug score,
        knowledge map, and code age for use in circle packing viz.

        All dates are assumed to be in unix epoch format (parse them in the
                                                           view controllers)

        TODO -- params, docstring, refactor, ect
        """
        # Build appropriate interval (and handle edge cases)
        if interval1_start is None:
            interval1_start = 0
            self.log.info("Interval1_start was None. Defaulted to 0")

        if interval1_end is None:
            interval1_end = self.db_handler.last_revision_date()
            self.log.info("Interval_end1 was none. Defaulted to last entry: %s", interval1_end)

        scan_intervals = [(interval1_start, interval1_end)]

        if interval2_end is not None:
            self.log.warning("Interval 2 detected: " + interval2_end + " ..of type: " + type(interval2_end))
            scan_intervals.append((interval2_start, interval2_end))

        self.log.debug("Building circle packing metrics with interval: %s", scan_intervals)

        hotspots_util = HotspotsUtil(scan_intervals)
        file_heirarchy = hotspots_util.execute_with_gen(self.db_handler.file_history(scan_intervals[0][0],
                                                        scan_intervals[-1][1]))

        self.log.debug("Finished circle packing building process...")

        # TODO -- handle multiple intervals with build_filetree
        attrs = [FileInfoModule.MODULE_KEY, BugModule.MODULE_KEY, TemporalModule.MODULE_KEY,
                KnowledgeMapModule.MODULE_KEY]
        return {"name": "root", "children": self.__build_filetree(file_heirarchy[0], attributes=attrs)}

    def __build_filetree(self, files, attributes=None, component_delim="/"):
        """
        Takes a dictionary (files) with keys corresponding to file paths, and builds a
        tree from the file path with the leaves having attributes selected from
        the value dictionary of param files.

        Every node has keys 'name' and 'children'.
        Each leaf i also has whatever properties from files.values()[i]
        which are specified in the attributes parameter

        This algorithm is general enough for any number of nested components. It works
        by splitting file's name into path components, traversing the tree top-down,
        keeping a pointer to the current layer, and creating a node for each
        component that does not exist yet. When it gets to the terminal node
        (bottom-most layer) it will add the attributes indicated in the attributes parameter

        TODO -- Add docstring params and returns
        """
        self.log.debug("Starting object tree algorithm...")
        tree = []
        for filename, file_info in files.iteritems():
            components = filename.split(component_delim)
            current_node = tree
            # Traverse through components, building nodes as necessary
            for component in components:
                wanted_node = component
                last_node = current_node
                for node in current_node:
                    if node['name'] == wanted_node:
                        current_node = node['children']
                        break
                # If I couldn't find item in list of children, create one
                if last_node == current_node:
                    new_node = {'name': wanted_node}
                    new_node['children'] = []
                    # If this is the terminal node, add the info. Otherwise add children
                    if wanted_node == components[-1]:
                        for attr in attributes:
                            new_node[attr] = file_info[attr]
                        current_node.append(new_node)
                    else:
                        current_node.append(new_node)
                        current_node = new_node['children']
        self.log.debug("Finished building object tree")
        # FOR DEBUGING (verbose af)
        # self.log.debug("Object tree: \n%s ... ", json.dumps(tree[0:2], indent=2))
        return tree

    def is_bug(self, message):
        """
        Uses a regular expression to check if commit message indicates a defect
        was fixed
        """
        return self.regex.match(message) != None
