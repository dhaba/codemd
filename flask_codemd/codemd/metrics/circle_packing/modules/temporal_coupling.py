from codemd.metrics.circle_packing.modules.base import CirclePackingModule
from collections import defaultdict
from itertools import combinations
import math

class TemporalCouplingModule(CirclePackingModule):
    """
    Responsible for handling temporal coupling metrics.
    See GitHub page for description of the science behind temporal coupling
    analysis.
    """

    MODULE_KEY = 'tc_info'

    DEFAULT_DATA = {'score': 0, 'percent': 0, 'color_opacity': 0,
                    'coupled_module': None, 'num_revisions': 0,
                    'num_mutual_revisions': 0, 'color': None}

    # Module will only report the NUM_TOP_COUPLES highest entries scored by the
    # temporal coupling algorithm
    NUM_TOP_COUPLES = 64

    # Ignore commits with more than MAX_COMMIT_SIZE files changed
    MAX_COMMIT_SIZE = 8

    # Colors to use for cliques
    CLIQUE_COLORS = ['#e31a1c',  '#6a3d9a', '#33a02c', '#0082c8', '#ffe119',
                     '#df57d9', '#6e4c19', '#dbc488', '#000000']

    # Use distance in object graph as weight in scoring function
    USE_MODULE_DISTANCE = False

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
        CirclePackingModule.__init__(self, working_data, intervals)
        self.working_couples = defaultdict(int) # (file1, file2) : # of mutual revisions
        self.working_rev_counts = defaultdict(int) # (file) : # of revisions
        self.commits_buffer = {'commits': [], 'revision_id':None}
        self.num_ignored_commits = 0

    def process_file(self, current_file):
        # Set default temporal coupling data
        tc_info = self.get_or_create_key(current_file['filename'])

        # For this module, only worry about processing in our interval scope
        if not self.is_file_in_scope(current_file):
            return

        # Increment revision count for file. This is different from the revision
        # count in the general info because this count is scoped to the current interval
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

    def post_process_data(self):
        """
        Algorithm for scoring temporal frequency
        """
        self.log.info("Starting post processing for TemporalModule...")
        # Process batch of files (last commit)
        self.__process_commits_buffer()
        self.log.info("Number of ignored commits: %s", self.num_ignored_commits)

        couples = {}
        for pair, count in self.working_couples.iteritems():
            mod1, mod2 = pair[0], pair[1]
            # Ignore files if necessary
            if self.__should_filter_files(mod1, mod2):
                # self.log.debug("Filtering files %s and %s", mod1, mod2)
                continue

            module_distance = self.__module_distance(mod1, mod2) + 1
            avg_pair_revs = (self.working_rev_counts[mod1] + self.working_rev_counts[mod2]) / 2.0
            score = count/avg_pair_revs * math.log((self.working_rev_counts[mod1] + self.working_rev_counts[mod2]))
            if (self.USE_MODULE_DISTANCE):
                score *= (module_distance/12.0)

            couples[pair] = {'score': score, 'total_mutual_revs' : count,
                             'avg_revs': avg_pair_revs,
                             'module_distance': module_distance,
                             'percent_coupled': count/avg_pair_revs,
                             mod1: self.working_rev_counts[mod1],
                             mod2: self.working_rev_counts[mod2]}

        self.log.info("Sorting couples...")
        sorted_result = sorted(couples.iteritems(), # TODO -- implement partial sorting
                               key=lambda (k,v): v['score'], reverse=True)
        self.log.info("Finished sorting couples.")

        self.__augment_working_data(sorted_result)

        self.log.info("Finished post processing for TemporalModule.")

        # FOR DEBUGGING
        # self.log.debug("Top %s temporal coupling results: %s",
        #                 self.NUM_TOP_COUPLES,
        #                 json.dumps(sorted_result[0:self.NUM_TOP_COUPLES], indent=2))
        # self.log.info("Sorted results: %s", sorted_result[0:self.NUM_TOP_COUPLES])
        # self.log.debug("all couples: %s", json.dumps(sorted_result, indent=2))

    def __process_commits_buffer(self):
        """
        Process current files batch in commits buffer
        """
        if len(self.commits_buffer['revision_id']) < self.MAX_COMMIT_SIZE:
            self.log.debug("Ignoring commit that exceeded max size: %s", self.commits_buffer['commits'])
            self.num_ignored_commits += 1
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

    def __augment_working_data(self, sorted_couples):
        """
        Adds temporal coupling data to self.working_data, including a unique color
        parameter for each clique (in an undirected graph, where modules are
        vertices, and 2 coupled modules indicates an edge).

        :param couples: A list of tuples, where first element is a length 2 tuple
        containing the coupled modules, and the second element is a dictionary
        containing information about the couple
        """
        self.log.info("Starting to augment working data with temporal coupling info...")

        # Only use top NUM_TOP_COUPLES for circle packing coloring
        couples = sorted_couples[0:self.NUM_TOP_COUPLES]
        other_couples = sorted_couples[self.NUM_TOP_COUPLES:]
        max_score = couples[0][1]['score'] # For normalizing scores to set as opacity values

        def add_temporal_data(couple, color):
            """
            Helper method to add temporal coupling information to self.working_data
            """
            data = couple[1]
            for mod in couple[0]:
                # Only update data if score is higher than current value
                tc_info = self.working_data[mod][self.MODULE_KEY]
                if tc_info['score'] < data['score']:
                    coupled_module = filter(lambda x: x is not mod, couple[0])[0]
                    tc_info['score'] = data['score']
                    tc_info['opacity'] = data['score']/max_score
                    tc_info['coupled_module'] = coupled_module
                    tc_info['num_revisions'] = data[mod]
                    tc_info['num_mutual_revisions'] = data['total_mutual_revs']
                    tc_info['color'] = color
                    tc_info['percent'] = data['percent_coupled']
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
                if empty_color is not None:
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

        # Add data for remaining (non colored) couples
        for coup in other_couples:
            add_temporal_data(coup, None)

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
