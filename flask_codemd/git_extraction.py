from codemd_repository import CodemdRepository
from bson.binary import Binary
import cPickle as pickle
import json

import pandas as pd
import numpy as np

def persist_git_metrics(git_url, pretty_name, mongo_collection):
    """
    Method to store pandas dataframe pickles as pandas binaries

    :param git_url: A valid git url (ex: git://github.com/scikit-learn/scikit-learn)
    :param pretty_name: The short name of the git project (ex: scikit-learn)
    :param mongo_collection: The application's mongo instance
    """
    repo = CodemdRepository(working_dir=git_url, verbose=True)
    commits_df, files_df = repo.commits_files_history()

    print "Storing pickled df to collection for git_url: ", git_url

    mongo_collection.insert_one({'git_url':git_url, 'pretty_name': pretty_name, \
                                'last_update':datetime.datetime.now(), \
                                'pickles': {'commits_df': Binary(pickle.dumps(commits_df)), \
                                            'files_df': Binary(pickle.dumps(files_df))}})


def fetch_dfs_from_collection(git_url, mongo_collection):
    """
    Returns a tuple of dfs (commits_df, files_df), which are built from their
    pickles stored in mongo
    """

    desired_doc = mongo_collection.find_one({'git_url': git_url})
    pickles = desired_doc['pickles']

    commits_df = pickle.loads(pickles['commits_df'])
    files_df = pickle.loads(pickles['files_df'])
    return (commits_df, files_df)


def loc_json(files_df):
    """
    Returns JSON structure for D3 circle packing viz, in a tree structure by component.
    The terminal nodes are the modules, with the single property "loc" which refers
    to the number of lines of code the object has
    """

def build_json_tree_from_df(df, filename_column="filename", component_delim="/", attributes=[]):
    """
    Takes a dataframe containing a column indicating a file path (module)
    and columns representing various attributes, and builds a json tree from the
    file path with the leaves having attributes indicated by the column
    names in the attributes parameter.

    Each non-leaf has keys 'name' and 'children'.
    Each leaf has keys 'name', and whatever else is specified in the attributes
    parameter

    Ex)
    A df containing rows:
        ['component1/subcomponent/module1', '15']
        ['component1/subcomponent/module2', '30']
    Will be transformed to:
        {name: component1,
            children:{ name: subcomponent,
                children:{
                    {name: module1, attribute1:15},
                    {name: module2, attribute1:30}
        }}}

    This algorithm is general enough for any number of nested components. It works by
    traversing the tree top-down, keeping a pointer to the current layer, and
    creating a node for each component that does not exist yet. When it gets to
    the terminal node (bottom-most layer) it will add the attributes indicated
    in the attributes parameter
    (sidenote: this was suprisingly non-trivial to implement lol)
    """

    tree = []
    for index, row in df.iterrows():
        components = row[filename_column].split(component_delim)
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
                # If this is the terminal node, add the info. Otherwise add children
                if wanted_node == components[-1]:
                    for attr in attributes:
                        new_node[attr] = row[attr]
                    current_node.append(new_node)
                else:
                    new_node['children'] = []
                    current_node.append(new_node)
                    current_node = new_node['children']

    return json.dumps(tree)
