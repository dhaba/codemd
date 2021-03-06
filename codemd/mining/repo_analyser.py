import logging
import tempfile
import sys
import os
import shutil
import fnmatch
from git import Repo
from codemd.data_managers.db_handler import DBHandler

# Dictionary of hard-coded paths to include/exclude for known projects
paths = {"scikit-learn": {"include":["sklearn/*"], "exclude":['README', '*.md', '*.txt', '*.yml']},
         "django":       {"include":["django/*", "tests/*"],
                          "exclude":['*.md', '*.txt', '*.yml', '*.mo', '*.po']},
         "sass":         {"include":["lib/*"],  "exclude":[]},
         "rails":        {"include":["actioncable/*",	"actionmailer/*", "actionpack/*",
         	              "actionview/*",	"activejob/*",	 "activemodel/*",
                          "activerecord/*", "activesupport/*", "railties/*",
                          "tasks/*", "tools/*"],
                          "exclude":["*.md", "*.yml", "MIT-LICENSE", "*.gemspec",
                          "*.rdoc", "*.gitkeep", "*.json", "*.gitignore", "*.txt"]},
         "node":         {"include":["lib/*", "deps/*", "tools/*", "src/*", "benchmark/*", "test/*"],
                          "exclude":['*.md', "*.yml", "*.txt"]},
         "pandas":       {"include":["asv_bench/*", "bench/*", "pandas/*", "scripts/*"],
                          "exclude":['*.md', 'doc/*', '*.rst', '*.svg', '*.png']},
         "numpy":        {"include":["numpy/*", "tools/*"],  "exclude":['numpy/doc/*', '*.md', '*.txt, *.yml']},
         "redox":        {"include":['crates/*', 'drivers/*' ,'filesystem/*',
                                    'initfs/etc/*', 'kernel/*', 'liballoc_malloc/*',
                                    'liballoc_system/*', 'setup/*'],
                          "exclude":['*.md', "*.yml", "*.txt"]},
         "hibernate-orm":{"include":["*"],
                          "exclude":['*.md', "*.yml", "*.txt"]} }

# Always exclude these paths
always_exclude = ["*.md", "*.yml", "MIT-LICENSE", "*.gemspec", "Gemfile", ".bower",
"*.rdoc", "*.gitkeep", "*.json", "*.gitignore", "*.txt", ".json", ".git", ".png",
".gif", ".jpg", "README.*", "*.dat", "LICENSE", "*.log", "*.pdf"]

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

    def __init__(self, git_url, full_name=None, description="", include_paths=[], exclude_paths=[]):
        self.log = logging.getLogger('codemd.RepoAnalyser')
        self.project_name = self.short_name(git_url)
        self.include_paths = include_paths
        self.exclude_paths = exclude_paths
        if full_name is None:
            full_name = self.project_name
        self.full_name = full_name
        self.description = description

        # Check for hard-coded paths if none specified
        if (len(include_paths) == 0) and (len(exclude_paths) == 0) and (self.project_name in paths.keys()):
            project_paths = paths[self.project_name]
            self.include_paths = project_paths["include"]
            self.exclude_paths = project_paths["exclude"]

        self.exclude_paths = list(set(self.exclude_paths + always_exclude))

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

    def persist_meta_data(self):
        """
        Persists the meta data for this repo, including the project name, description,
        and icon image url
        :return:
        """
        self.log.info("Persisting meta data for project %s", self.full_name)
        db_handler = DBHandler(self.project_name)
        db_handler.persist_meta_data(self.full_name, self.description)

    def persist_commits_data(self):
        """
        Scans the specified repository, and adds an entry into the
        <repo short name> collection for each commit.

        :return: List of dictionaries (one element for each commit)
        """
        def gen_commit_docs():
            """
            Define generator so commits do not have to be built in memory.
            This is advantageous b/c we can leverage Mongo's insert_many, which should
            prevent us from having to open/close a db connection repeatedly
            """
            INCREMENT = 1024
            count = 0
            self.log.info("Starting iteration over commits...")
            for c in self.commits_iterator():
                # Ignoring merges, as all the info will be contained in upstream
                if len(c.parents) > 1:
                    continue

                # DEBUG CODE
                count += 1
                if count % INCREMENT == 0:
                    self.log.debug("# Commits processed so far: %s", count)
                # END DEBUG

                # Filter ignored files. Skip commit if none of the files are relevant
                files_included = self.__check_file_paths(c.stats.files.keys())
                if len(files_included) == 0:
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

        db_handler = DBHandler(self.project_name)
        db_handler.persist_documents_from_gen(gen_commit_docs())


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


    def commits_iterator(self):
        """
        Return a pointer to iterator self.repo.iter_commits(...)
        This method is necessary because we should only specify the 'path' keyword
        arg if we have values in self.include_paths
        """

        if (self.include_paths == None or len(self.include_paths) == 0):
            return self.repo.iter_commits(self.branch, max_count=sys.maxsize)
        else:
            return self.repo.iter_commits(self.branch, paths=self.include_paths, max_count=sys.maxsize)


    def __check_file_paths(self, files):
        """
        Internal method to filter a list of file changes by extensions and paths.
        If a file is NOT in the include path, we treat it as if it's in the ignore
        path also.

        :param files: List of filenames to filter by self.include_paths and self.exclude_paths
        :return: List of filtered file names
        """

        filtered_files = []
        for f in files:
            exclude_count, include_count = 0, 0
            for path in self.exclude_paths:
                if fnmatch.fnmatch(f, path):
                    exclude_count += 1
            if len(self.include_paths) == 0:
                include_count = 1
            else:
                for path in self.include_paths:
                    if fnmatch.fnmatch(f, path):
                        include_count += 1
            if exclude_count == 0 and include_count >= 1:
                filtered_files.append(f)

        return filtered_files
