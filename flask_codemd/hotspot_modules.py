from abc import ABCMeta, abstractmethod
import logging
import re
import math
from collections import defaultdict
from itertools import combinations

import json

# ::::  HEURISTICS ::::
# Hard coded rules for inclusion/exclusion of files when calculated various metrics
# Ideally these would be exposed to the user for custom tinkering
LOC_THRESHOLD = 24 # min number of lines to be considered in circle packing

class HotspotModule:
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


class FileInfoModule(HotspotModule):
    """
    Extract high level information including:
        - lines of code (LOC)
        - filename
        - date last modified.
    """

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)

    def process_file(self, current_file):
        if current_file['filename'] not in self.working_data.keys():
            self.working_data[current_file['filename']] = {'creation_date': current_file['date'],
                                            #    'bug_dates': [], 'bug_messages': [],
                                                'loc': 0, 'bug_score': 0, 'bug_count': 0}

        f = self.working_data[current_file['filename']]
        f['loc'] += current_file['insertions'] - current_file['deletions']
        f['last_modified'] = current_file['date']

    def post_process_data(self):
        self.log.info("Starting post processing for FileInfoModule...")
        self.log.debug("Removing files smaller than threshhold...")

        files_to_filter = []
        for f_name, f_info in self.working_data.iteritems():
            if f_info['loc'] < LOC_THRESHOLD:
                files_to_filter.append(f_name)
        self.log.debug("Removing %s files", len(files_to_filter))
        for f in files_to_filter:
            # self.log.debug("Removing file %s because it only had %s lines", f, self.working_data[f]['loc'])
            self.working_data.pop(f, None)
        self.log.info("Finished post processing for FileInfoModule.")


class BugModule(HotspotModule):

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)
        self.regex = re.compile(r'\b(fix(es|ed)?|close(s|d)?)\b')
        self.max_bug_score = 0

    def process_file(self, current_file):
        """
        Responsible for parsing bug score related information out of the file
        """
        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return

        if self.__is_bug(current_file['message']):
            f = self.working_data[current_file['filename']]

            # just for debugging really
            # f['bug_messages'].append(mod_file['message'])
            # f['bug_dates'].append(mod_file['date'])
            f['bug_count'] += 1

            # Add score to each file. Scoring function based on research from Chris
            # Lewis and Rong Ou at Google
            end_date = self.intervals[0][1]
            fix_date = current_file['date']
            time_delta = end_date - f['creation_date']
            if time_delta <= 0:
                norm_time = 1.0
            else:
                norm_time = 1 - (float(end_date - fix_date) / (time_delta))
            f['bug_score'] += 1 / (1 + math.exp(-12 * norm_time + 12))

            if f['bug_score'] > self.max_bug_score:
                self.max_bug_score = f['bug_score']

    def post_process_data(self):
        # Normalize bug scores
        self.log.info("Post processing BugInfoModule...")
        if self.max_bug_score != 0:
            for f in self.working_data:
                self.working_data[f]['bug_score'] /= self.max_bug_score
        self.log.info("Finished post processing for BugInfoModule")

    def __is_bug(self, message):
        """
        DOCSTRING
        """
        return self.regex.match(message) != None


class TemporalModule(HotspotModule):
    """
    Responsible for handling temporal coupling metrics.
    See GitHub page for description of the science behind temporal coupling
    analysis.
    """

    SCORE_KEY_NAME = 'tc_score'

    # Module will only report the NUM_TOP_COUPLES highest entries scored by the
    # temporal coupling algorithm
    NUM_TOP_COUPLES = 64

    # Ignore commits with more than MAX_COMMIT_SIZE files changed
    MAX_COMMIT_SIZE = 8

    # Colors to use for cliques
    CLIQUE_COLORS = ['#e31a1c',  '#6a3d9a', '#33a02c', '#0082c8', '#ffe119', '#000000']

    # Use distance in object graph as weight in scoring function
    USE_MODULE_DISTANCE = True

    # Specifies heuristics for ignoring files in the temporal coupling algorithm
    MODULE_FILTERS = {
        '__is_unit_test' : True, # Ignores all files with 'test' in their file path
        '__is_test_case' : False, # Ignores coupled test case files (ie 'moduleA' and 'moduleA_test')
        '__is_header_file' : True } # Ignores coupled headers for C files (ie 'moduleA.h' and 'moduleA.c')

    # Ignore coupled test case files (ie 'moduleA' and 'moduleA_test')
    IGNORE_TEST_CASES = True

    # Ignore coupled headers for C files (ie 'moduleA.h' and 'moduleA.c')
    IGNORE_HEADERS = True

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)
        self.working_couples = defaultdict(int) # (file1, file2) : # of mutual revisions
        self.working_rev_counts = defaultdict(int) # (file) : # of revisions
        self.commits_buffer = {'commits': [], 'revision_id':None}

    def process_file(self, current_file):
        # Set default temporal coupling data
        mod = current_file['filename']
        self.working_data[mod][self.SCORE_KEY_NAME] = 0
        self.working_data[mod]['tc_percent'] = 0
        self.working_data[mod]['tc_color_opacity'] = 0
        self.working_data[mod]['coupled_module'] = None
        self.working_data[mod]['num_revisions'] = None
        self.working_data[mod]['num_mutual_revisions'] = None
        self.working_data[mod]['tc_color'] = None

        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return

        # Increment revision count for file
        self.working_rev_counts[current_file['filename']] += 1

        # Hack(ish) to regroup the original files from a commit since
        # I unwound them in the original db query
        if ((self.commits_buffer['revision_id'] is not None) and
            (self.commits_buffer['revision_id'] != current_file['revision_id'])):
            # Process the buffer into temporal frequency counts
            self.__process_commits_buffer()

        # Even if we have a full batch, still need to add a new one
        self.commits_buffer['revision_id'] = current_file['revision_id']
        self.commits_buffer['commits'].append(current_file['filename'])

        # DEBUG
        # self.log.debug("\n\nCommits buffer: %s", self.commits_buffer)
        # self.log.debug("\nend commits buffer\n")

    def post_process_data(self):
        """
        Algorithm for scoring temporal frequency
        """
        self.log.info("Starting post processing for TemporalModule...")
        # Process batch of files (last commit)
        self.__process_commits_buffer()

        couples = {}
        for pair, count in self.working_couples.iteritems():
            # Ignore files if necessary
            if self.__should_filter_files(pair[0], pair[1]):
                # self.log.debug("Filtering files %s and %s", pair[0], pair[1])
                continue
            module_distance = self.__module_distance(pair[0], pair[1]) + 1
            avg_pair_revs = (self.working_rev_counts[pair[0]] + self.working_rev_counts[pair[1]]) / 2.0
            score = count/avg_pair_revs * math.log(avg_pair_revs) #* (module_distance/12.0)
            # score = count/avg_pair_revs * math.log(count) * math.log(avg_pair_revs) * module_distance
            couples[pair] = {'score': score, 'total_mutual_revs' : count,
                             'avg_revs': avg_pair_revs,
                             'module_distance': module_distance,
                             'percent_coupled': count/avg_pair_revs,
                             pair[0]: self.working_rev_counts[pair[0]],
                             pair[1]: self.working_rev_counts[pair[1]]}

        self.log.info("Sorting couples...")
        sorted_result = sorted(couples.iteritems(), # TODO -- implement partial sorting
                               key=lambda (k,v): v['score'], reverse=True)
        self.log.info("Finished sorting couples.")

        self.__augment_working_data(sorted_result[0:self.NUM_TOP_COUPLES])
        self.log.info("Finished post processing for TemporalModule.")
        # self.log.debug("Top %s temporal coupling results: %s",
        #                 self.NUM_TOP_COUPLES,
        #                 json.dumps(sorted_result[0:self.NUM_TOP_COUPLES], indent=2))
        # self.log.info("%s", sorted_result[0:self.NUM_TOP_COUPLES])
        # self.log.debug("all couples: %s", json.dumps(sorted_result, indent=2))

    def __process_commits_buffer(self):
        """
        Process current files batch in commits buffer
        """
        if len(self.commits_buffer['revision_id']) < self.MAX_COMMIT_SIZE:
            self.log.debug("Ignoring commit that exceeded max size: %s", self.commits_buffer['commits'])
            self.commits_buffer = {'commits': [], 'revision_id':None}
            return

        if self.commits_buffer['revision_id'] is not None:
            for pair in combinations(self.commits_buffer['commits'], 2):
                ordered_pair = sorted(pair)
                ordered_tuple = (ordered_pair[0], ordered_pair[1])
                self.working_couples[ordered_tuple] += 1

            self.commits_buffer = {'commits': [], 'revision_id':None}
        else:
            self.log.warning("!!! __process_commits_buffer called on empty commits_buffer")

    def __augment_working_data(self, couples):
        """
        Adds temporal coupling data to self.working_data, including a unique color
        parameter for each clique (in an undirected graph, where modules are
        vertices, and 2 coupled modules indicates an edge).

        :param couples: A list of tuples, where first element is a length 2 tuple
        containing the coupled modules, and the second element is a dictionary
        containing information about the couple
        """
        self.log.info("Starting to augment working data with temporal coupling info...")
        max_score = couples[0][1]['score'] # For normalizing scores to set as opacity values
        def add_temporal_data(couple, color):
            """
            Helper method to add temporal coupling information to self.working_data
            """
            data = couple[1]
            for mod in couple[0]:
                # Only update data if score is higher than current value
                if ((self.SCORE_KEY_NAME in self.working_data[mod]) and
                    (self.working_data[mod][self.SCORE_KEY_NAME] > data['score'])):
                    coupled_module = filter(lambda x: x is not mod, couple[0])[0]
                    # self.log.debug("Not writing score for module %s to %s because current" +
                    #                 " score was less than that specified in couple:\n%s",
                    #                 mod, coupled_module, couple)
                else:
                    coupled_module = filter(lambda x: x is not mod, couple[0])[0]
                    self.working_data[mod][self.SCORE_KEY_NAME] = data['score']
                    self.working_data[mod]['tc_color_opacity'] = data['score']/max_score
                    self.working_data[mod]['coupled_module'] = coupled_module
                    self.working_data[mod]['num_revisions'] = data[mod]
                    self.working_data[mod]['num_mutual_revisions'] = data['total_mutual_revs']
                    self.working_data[mod]['tc_color'] = color
                    self.working_data[mod]['tc_percent'] = data['percent_coupled']
                    # self.log.debug("Appended temp coupling data to working data " +
                    #                "module: %s, with data: %s", mod, self.working_data[mod])

        def adj_list_from_couples(couples):
            """
            Helper method to build an adjacency list from couples
            """
            adj_list = defaultdict(set)
            for coup in couples:
                mod1, mod2= coup[0][0], coup[0][1]
                adj_list[mod1].add(mod2)
                adj_list[mod2].add(mod1)
            return adj_list

        def cliques_from_adj_list(adj_list):
            """
            Helper method to detect cliques from and adjacency list.

            :return A list of sets, where each set contains a distinct clique
            """
            cliques = [] # list of sets
            for vertex, neighbors in adj_list.iteritems():
                # If we already know about this guy, skip him
                vertex_exists = False
                for c in cliques:
                    if vertex in c:
                        vertex_exists = True
                        break
                if vertex_exists:
                    continue
                # Iterative DFS
                stack = list(neighbors)
                clique = set([vertex])
                while len(stack) > 0:
                    current = stack.pop()
                    clique.add(current)
                    stack += [v for v in adj_list[current] if v not in clique]
                cliques.append(clique)
            return cliques

        # Determine cliques for appropriate coloring in circle packing
        cliques = cliques_from_adj_list(adj_list_from_couples(couples))

        colors = {} # dict where keys are colors and vals are sets containing modules
        for c in self.CLIQUE_COLORS:
            colors[c] = set()

        # Limit number of cliques to number of clique colors by only picking
        # highest scoring couples
        for coup in couples:
            mod1, mod2 = coup[0][0], coup[0][1]
            clique_found = False
            for c in colors:
                if mod1 in colors[c]:
                    clique_found = True
                    add_temporal_data(coup, c)
                    break
            if not clique_found:
                empty_color = None
                for c in self.CLIQUE_COLORS:
                    if len(colors[c]) == 0:
                        empty_color = c
                        break
                if empty_color is None:
                    # self.log.debug("All cliques were full, ignoring couple: %s, " +
                    #                "with data %s", coup[0], coup[1])
                    # self.log.debug("(cliques full) colors: %s", colors)
                    pass
                else:
                    clique = None
                    for c in cliques:
                        if mod1 in c:
                            clique = c
                    if clique is None:
                        self.log.error("!!! Clique not found for node %s!!!\n Cliques: %s", mod1, cliques)
                    else:
                        # self.log.debug("Assigning color %s to clique: %s", empty_color, clique)
                        add_temporal_data(coup, empty_color)
                        for v in clique:
                            colors[empty_color].add(v)
        # DEBUGGING
        # for c in colors:
        #     self.log.debug("%s", c)
        #     for obj in colors[c]:
        #         self.log.debug("\t%s", obj)

        self.log.info("Finished augmenting working data with temporal coupling info")

    def __module_distance(self, file1, file2):
        """
        Computes the distance between modules based on their file heirarchies by
        counting the number of discrepensies in their path components
        Ex)
                component_1/component_2/module_A
                component_1/component_2/module_B
            would have a distance of 0

                component_1/component_2/module_A
                component_1/component_3/module_B
            would have a distance of 1

                component_1/component_2/module_A
                component_3/component_4/component_5/module_B
            would have a distance of 4
        """
        paths1, paths2 = file1.split('/')[0:-1], file2.split('/')[0:-1]
        count = max(len(paths1), len(paths2))
        for i in xrange(min(len(paths1), len(paths2))):
            if paths1[i] == paths2[i]: count -= 1
        return count

    def __should_filter_files(self, file1, file2):
        """
        Determines if files should be ignored according to heuristics defined
        as class constants

        returns True if files should be ignored, false otherwise
        """
        # First make sure these files exist in working_data (they could have
        # been removed for being too short for example)
        if (not ((file1 in self.working_data) and (file2 in self.working_data))):
            return True
        # Now apply all optional filters
        for func in [k for (k, v) in self.MODULE_FILTERS.iteritems() if v]:
            func_name = '_' + self.__class__.__name__ + func
            if getattr(self, func_name)(file1, file2): return True
        return False

    def __is_unit_test(self, file1, file2):
        """
        Checks if the string 'test' exists in the file path
        """
        test_string = "test"
        return ((test_string in file1) or (test_string in file2))

    def __is_test_case(self, file1, file2):
        """
        Does some simple string matching to determine if file1 and file2 are module
        and test (ie 'moduleA' and 'moduleA_test')
        """
        test_string = "test"
        file1, file2 = file1.split('/')[-1], file2.split('/')[-1]
        return (((file1 in file2) and test_string in file2) or
               ((file2 in file1) and test_string in file1))

    def __is_header_file(self, file1, file2):
        """
        Does simple string matching to determine if file1 and file2 are header
        and implementation files (ie 'moduleA.h' and 'moduleA.c')
        """
        # self.log.debug("calling is_header_file on %s and %s", file1, file2)
        file1, file2 = file1.split('/')[-1], file2.split('/')[-1]
        is_same_module = (file1.split(".")[0] == file2.split(".")[0])
        f1_ext, f2_ext = file1.split(".")[-1], file2.split(".")[-1]
        return (is_same_module and ((f1_ext == 'h' and f2_ext == 'c')
               or (f1_ext == 'c' and f2_ext == 'h')))

class KnowledgeMapModule(HotspotModule):
    """
    Extracts top contributors for each module
    """

    # 21 optimally distinct colors of maximum contrast based on research by Kenneth Kelly
    AUTHOR_COLORS = ['#BE0032', '#F3C300', '#875692', '#F38400',
                  '#A1CAF1', '#BE0032', '#C2B280', '#848482', '#008856', '#E68FAC',
                  '#0067A5', '#F99379', '#604E97', '#F6A600', '#B3446C', '#DCD300',
                  '#882D17', '#8DB600', '#654522', '#E25822', '#2B3D26', '#222222']
    # If we run out of colors above, use off white for 'other' author
    OTHER_COLOR = '#F2F3F4'

    def __init__(self, working_data, intervals):
        HotspotModule.__init__(self, working_data, intervals)
        self.authors_key = {}
        self.top_authors_count = defaultdict(int)

    def process_file(self, current_file):
        module = self.working_data[current_file['filename']]
        if 'top_authors' not in module:
            module['top_authors'] = defaultdict(int)

        num_changes = current_file['insertions'] + current_file['deletions']
        module['top_authors'][current_file['author']] += num_changes

    def post_process_data(self):
        # Get top few contributors for each file
        self.log.info("Starting post processing for KnowledgeMap." +
                      " Sorting modules for top authors...")
        for module in self.working_data.itervalues():
            sorted_authors = sorted(module['top_authors'].iteritems(),
                                    key = lambda (k, v): v, reverse=True)
            self.top_authors_count[sorted_authors[0][0]] += 1
            module['top_authors'] = sorted_authors[0:3]

        self.log.info("Finished sorting modules for top authors." +
                      " Determining appropriate color map...")
        sorted_top_authors = sorted(self.top_authors_count.iteritems(),
                                    key = lambda (k, v): v, reverse=True)
        for i in range(len(self.AUTHOR_COLORS)):
            self.authors_key[sorted_top_authors[i][0]] = self.AUTHOR_COLORS[i]
        for module in self.working_data.itervalues():
            top_author = module['top_authors'][0][0]
            if top_author in self.authors_key:
                module['author_color'] = self.authors_key[top_author]
            else:
                module['author_color'] = self.OTHER_COLOR
            # Convert top_authors to a dict for front end
            module['top_authors'] = {k:v for k, v in module['top_authors']}
        self.log.info("Finished building author color map.")

        # self.log.debug("Author key: %s", json.dumps(self.authors_key, indent=2))
        # self.log.debug("Top Authors: %s", json.dumps(self.authors_key, indent=2))
        self.log.info("Finished post processing for KnowledgeMap.")
