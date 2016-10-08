from flask.ext.pymongo import PyMongo
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify
from git_extraction import CodemdRepository, persist_git_metrics, fetch_dfs_from_collection

from analyze_repo import AnalyzeRepo

# Create app instance
app = Flask(__name__)
app.secret_key = "sillycats123"

# Set db configuration options
app.config['MONGO_DBNAME'] = 'codemd'

# Create db instance
mongo = PyMongo(app)
# git_repos = mongo.db.git_repos


# Home page
@app.route("/")
def show_home():
    # entries = mongo.db.codemd.find()
    # return render_template('show_home.html', entries=entries)
    return render_template('show_home.html')

# Main page for circle packing visualizations
@app.route("/viz/<project_name>")
def show_viz(project_name):

    if "git_url" not in session.keys():
        print "No git url specified from home page...redicting to index"
        return redirect(url_for('show_home'))

    # Build dataframes from pickles; store in session
    print "(inside show_viz) Extracting pickles, to df..."
    commits_df, files_df = fetch_dfs_from_collection(session['git_url'], mongo.db.git_repos)

    print "(inside show_viz) Converting dfs to json..."
    commits_json, files_json = commits_df.to_json(), files_df.to_json()

    return commits_json

    return render_template("viz.html", commits_json = commits_json, \
                           files_json = files_json)

# Route to fetch necessary data from github
@app.route("/fetchdata", methods = ['POST'])
def fetchdata():
    git_repos = mongo.db.git_repos
    git_url = request.form['git_url'] # TODO -- validate git url
    session['git_url'] = request.form['git_url']
    pretty_name = git_url.split('/')[-1][0:-4]
    desired_doc = git_repos.find_one({'git_url': git_url})

    if not desired_doc:
        # Start process of cloning repo and extracting data...
        print "Data for git url ", git_url, " not found. Fetching data..."
        persist_git_metrics(git_url, pretty_name, git_repos)
    else:
        print "Data found for git url ", git_url

    return redirect(url_for('show_viz', project_name = pretty_name))



# Test route for Circle Packing Hotspot viz
@app.route("/hotspots")
def hotspots():
    return render_template("hotspots.html")

# Test route for D3 viz
# @app.route("/d3")
# def test_d3():
#     return render_template('test_d3.html')

# Test route to get stock data
# @app.route("/data")
# def data():
#     return jsonify(get_data())
