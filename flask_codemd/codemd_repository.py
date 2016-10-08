from repository import Repository
import sys
from collections import defaultdict
import datetime
import pandas as pd
from git import Repo

class CodemdRepository(Repository):
    """
    This class extends the Repository class and provides an API to extract
    metrics into Pandas DataFrames for use by CodeMD's web application.
    Unlike its parent, this class is optimized to extract all necessary metrics
    in a single iteration of the repository's commits.

    :param working_dir: the directory of the git repository, meaning a .git
    directory is in it (default None=pwd)
    :return:
    """

    # def __init__(self, working_dir=None, verbose=False):
    #     super(CodemdRepository, self).__init__(working_dir=working_dir, verbose=verbose)

    def commits_files_history(self, branch='master'):
        """
        Iterates through commit history and returns two dataframes: one containing
        the entire commit history, and another containing the a row for each file
        modified in each commit.

        :param branch: the branch to return commits for

        :return: A tuple of 2 DataFrames: (commits_df, files_df)
        """
        if self.verbose:
            print 'Extracting metrics from git repository...'

        # Dictionaries to hold data for commit info and file info
        commits_dict, files_dict = defaultdict(list), defaultdict(list)

        for c in self.repo.iter_commits(branch, max_count=sys.maxsize):
            revision_id = c.name_rev.split()[0]

            # Add top level commit information to commits_dict
            commits_dict['revision_id'].append(revision_id)
            commits_dict['date'].append(c.committed_date)
            commits_dict['committer'].append(c.committer.name)
            commits_dict['author'].append(c.author.name)
            commits_dict['message'].append(c.message)

            # Enumerate over modified files and add row to files_dict
            for file_name, file_mods in c.stats.files.iteritems():
                files_dict['revision_id'].append(revision_id)
                files_dict['filename'].append(file_name)
                files_dict['insertions'].append(file_mods['insertions'])
                files_dict['deletions'].append(file_mods['deletions'])
                files_dict['lines'].append(file_mods['lines'])

        if self.verbose:
            print 'Building pandas dataframe from metrics...'


        # Create pandas dataframes
        commits_df, files_df = pd.DataFrame(commits_dict), pd.DataFrame(files_dict)
        commits_df.date = pd.to_datetime(commits_df.date.map(datetime.datetime.fromtimestamp))
        commits_df.set_index(keys=['date'], drop=True, inplace=True)

        return commits_df, files_df
