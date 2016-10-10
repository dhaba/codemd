import logging
import tempfile
import sys
import os
import shutil
import fnmatch
import datetime

from git import Repo

# Dictionary of hard-coded paths to include/exclude for known projects
paths = {"scikit-learn": {"include":["sklearn/*"], "exclude":["README"]} }

class RepoAnalyser(object):
    """
    This class extends the Repository class and provides an API for extracting
    metrics and storing them in MongoDB for use by CodeMD's web application.
    Unlike its parent, this class is optimized to extract all necessary metrics
    in a single iteration of the repository's commits.

    :param git_url: the URL of the git repository, i.e. git://..../.git
    :param mongo_instance: The instance of the flask PyMongo object where the
    data should be written
    :param include_paths:  List of file paths to be included in the extraction.
        Ex: "*.py", "*.js", "*.css", "module1/*"
    :param exclude_paths: List of file paths to exclude from extraction
    :return:
    """

    def __init__(self, git_url, mongo_instance, include_paths=None, exclude_paths=None):
        self.log = logging.getLogger('codemd.RepoAnalyser')
        self.project_name = self.short_name(git_url)
        self.mongo = mongo_instance.db
        self.include_paths = include_paths
        self.exclude_paths = exclude_paths

        # Check for hard-coded paths if none specified
        if (include_paths == None) and (exclude_paths == None) and (self.project_name in paths.keys()):
            project_paths = paths[self.project_name]
            self.include_paths = project_paths["include"]
            self.exclude_paths = project_paths["exclude"]

        self.log.info('cloning repository url: %s into a temporary location...', git_url)
        self.log.debug('Included paths: %s', self.include_paths)
        self.log.debug('Excluded paths: %s', self.exclude_paths)

        self.repo_path = tempfile.mkdtemp()
        self.repo = Repo.clone_from(git_url, self.repo_path)

        self.log.info('Repository [%s] instantiated at directory: %s',
                       self.project_name, self.repo_path)

        # Get local branch name (usually "master" or "develop")
        local_branches = list(self.repo.branches)
        self.branch = local_branches[0].name

        self.log.debug('Repository [%s] has local branches: %s\nUsing branch %s',
                      self.project_name, local_branches, self.branch )


    def __del__(self):
        """
        On delete, clean up any temporary repositories still hanging around
        :return:
        """
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)


    def persist_commits_data(self):
        """
        Scans the specified repository, and adds an entry into the
        <repo short name> collection for each commit.

        :return: List of dictionaries (one element for each commit)
        """

        # Define generator so commits do not have to be built in memory.
        # This is advantageous b/c we can leverage Mongo's insert_many, which should
        # prevent us from having to open/close a db connection repeatedly
        def gen_commit_docs():
            # DEBUG CODE TODO -- delete this
            INCREMENT = 1000
            count = 0
            # END DEBUG
            self.log.info("Starting iteration over commits...")
            for c in self.repo.iter_commits(self.branch, max_count=sys.maxsize):
                # DEBUG CODE
                count += 1
                if count % INCREMENT == 0:
                    self.log.debug("# Commits processed so far: %s", count)
                # END DEBUG

                # Filter ignored files. Skip commit if none of the files are relevant
                files_included = self.__check_file_paths(c.stats.files.keys())
                if len(files_included) == 0:
                    # TODO -- remove debug line below
                    # self.log.debug("# Ignoring commit [%s], no files matched inclusion\n(file names: %s)",
                    #                 c.name_rev.split()[0], c.stats.files.keys())
                    continue

                files_modified = []
                # Build file modifications list (list of dictionaries)
                for file_name in files_included:
                    file_mods = c.stats.files[file_name]
                    files_modified.append({'filename': file_name, \
                                         'insertions':file_mods['insertions'], \
                                         'deletions':file_mods['deletions']})

                # Build row which includes high level commit data and files modified
                revision_id = c.name_rev.split()[0]
                commit_data = {'revision_id': revision_id, 'date': c.committed_date, \
                               'commiter': c.committer.name, 'author':c.author.name, \
                               'message': c.message, 'files_modified': files_modified}

                yield commit_data

        self.log.info("Extracting metrics from git repository into db collection: %s", \
                       self.project_name)

        collection = self.mongo[self.project_name]
        collection.insert_one({'date_updated': datetime.datetime.now(), \
                               'branch': self.branch})
        collection.insert_many(doc for doc in gen_commit_docs())
        self.log.info("Finished inserting documents into Mongo")


    @staticmethod
    def is_valid_git(git_url):
        """
        Checks if the git_url is of valid form (starts with git://.. and ends with
        .git)
        """
        components = git_url.split('/')
        return ((components[0] == 'git:') and (components[-1][-4:] == '.git'))


    @staticmethod
    def short_name(git_url):
        """
        Takes a git URL and return the short name.
        Ex) git://github.com/scikit-learn/scikit-learn.git ==> scikit-learn
        """
        return git_url.split('/')[-1][0:-4]


    def __check_file_paths(self, files):
        """
        Internal method to filter a list of file changes by extensions and paths.

        :param files: List of filenames to filter by self.include_paths and self.exclude_paths
        :return: List of filtered file names
        """

        if self.include_paths == None and self.exclude_paths == None:
            return files

        if self.include_paths is None or self.include_paths == []:
            self.include_paths = ['*']

        filtered_files = []
        for f in files:
            # count up the number of patterns in the ignore paths list that match
            if self.exclude_paths is not None:
                count_exclude = sum([1 if fnmatch.fnmatch(f, path) else 0 for path in self.exclude_paths])
            else:
                count_exclude = 0

            # count up the number of patterns in the include globs list that match
            count_include = sum([1 if fnmatch.fnmatch(f, path) else 0 for path in self.include_paths])

            # if we have one vote or more to include and none to exclude, then we use the file.
            if count_include > 0 and count_exclude == 0:
                filtered_files.append(f)

        return filtered_files
