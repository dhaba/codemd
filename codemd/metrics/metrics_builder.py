import re
import logging
import json
from codemd.data_managers.s3_handler import S3Handler
from codemd.data_managers.db_handler import DBHandler

from codemd.metrics.circle_packing.metrics import CirclePackingMetrics

from codemd.metrics.circle_packing.modules.file_info import FileInfoModule
from codemd.metrics.circle_packing.modules.bugs import BugModule
from codemd.metrics.circle_packing.modules.knowledge_map import KnowledgeMapModule
from codemd.metrics.circle_packing.modules.temporal_coupling import TemporalCouplingModule

import pdb

class MetricsBuilder(object):
    """
    Docstring
    """

    def __init__(self, project_name):
        self.project_name = project_name
        self.log = logging.getLogger('codemd.MetricsBuilder')
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')
        self.db_handler = DBHandler(project_name)

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

    def load_commits(self):
        handler = S3Handler(self.project_name)
        commits_data = handler.load_dashboard_data()
        return commits_data

    def save_circle_packing_data(self):
        packing_metrics = CirclePackingMetrics(self.project_name)
        packing_metrics.create_checkpoints()
        full_metrics = packing_metrics.compute_file_hierarchy()[0]
        file_tree = self.__build_filetree(full_metrics)
        handler = S3Handler(self.project_name)
        handler.save_cp_data(file_tree)

    def circle_packing(self, intervals):
        """
        Calculates temporal frequency, bug score,
        knowledge map, and code age for use in circle packing viz.

        All dates are assumed to be in unix epoch format (parse them in the
                                                           view controllers)

        TODO -- params, docstring, refactor, ect
        """
        if ((intervals is None) or (intervals == [[None, None],[None, None]])):
            self.log.debug("Full project history requested, loading data from json...")
            handler = S3Handler(self.project_name)
            data = handler.load_cp_data()
            return data

        self.log.debug("Building circle packing metrics with interval: %s", intervals)

        packing_metrics = CirclePackingMetrics(self.project_name, intervals)
        file_heirarchy = packing_metrics.compute_file_hierarchy()

        self.log.debug("Finished circle packing building process...")

        # TODO -- handle multiple intervals with build_filetree
        return json.dumps(self.__build_filetree(file_heirarchy[0]))

    def __build_filetree(self, files, component_delim="/"):
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
        tree = []
        file_tree = {"name": "root", "children":tree}
        attributes = [FileInfoModule.MODULE_KEY, BugModule.MODULE_KEY,
                      TemporalCouplingModule.MODULE_KEY,
                      KnowledgeMapModule.MODULE_KEY]

        self.log.debug("Starting object tree algorithm...")
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
        return file_tree

    def is_bug(self, message):
        """
        Uses a regular expression to check if commit message indicates a defect
        was fixed
        """
        return self.regex.match(message) != None
