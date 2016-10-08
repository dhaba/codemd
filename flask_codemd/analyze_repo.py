from repository import Repository
import sys
from collections import defaultdict
import datetime
import pandas as pd
from git import Repo

class AnalyzeRepo(Repository):
        """
        This class extends the Repository class and provides an API to extract
        metrics and store them in MongoDB for use by CodeMD's web application.
        Unlike its parent, this class is optimized to extract all necessary metrics
        in a single iteration of the repository's commits.

        :param working_dir: the directory of the git repository, meaning a .git
        directory is in it (default None=pwd)
        :param collection_name: (String) The name of the collection to store the data.
        It should be the name of the project (i.e. scikit-learn, numpy)
        :param mongo_instance: The instance of the flask PyMongo object where the
        data should be written
        :return:
        """

        def __init__(self, collection_name, mongo_instance, working_dir=None, verbose=False):
            super(CodemdRepository, self).__init__(working_dir=working_dir, verbose=verbose)
            self.collection_name = collection_name
            self.mongo = mongo_instance.db

        def create_entries(self, branch='master'):
            """
            Scans the specified repository, and adds an entry into the
            <repo short name> collection for each commit.

            :return: List of dictionaries (one element for each commit)
            """
            if self.verbose:
                print "Extracting metrics from git repository into collection: ", self.collection_name

            # Create collection
            collection = self.mongo[self.collection_name]

            # List of dictionaries to be converted to json and added in batch
            commits_list = []

            # Enumerate over commits and a build dictionary for each
            for c in self.repo.iter_commits(branch, max_count=sys.maxsize):
                # Build file modifications list (list of dictionaries)
                files_modified = []
                for file_name, file_mods in c.stats.files.iteritems():
                    files_modified.append({'filename': file_name, \
                                         'insertions':file_mods['insertions'], \
                                         'deletions':file_mods['deletions'],
                                         'lines':file_mods['lines']})

                # Build row which includes high level commit data and files modified
                revision_id = c.name_rev.split()[0]
                commit_data = {'revision_id': revision_id, 'date': c.committed_date, \
                               'commiter': c.committer.name, 'author':c.author.name, \
                               'message': c.message, 'files_modified': files_modified}

                commits_list.append(commit_data)

            if self.verbose:
                print 'Adding ' + str(len(commits_list) + ' commits in batch'
            collection.insert_many(commits_list)

            return commits_list
