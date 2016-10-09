from flask.ext.pymongo import PyMongo
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify
# from git_extraction import CodemdRepository, persist_git_metrics, fetch_dfs_from_collection

from repo_analyser import RepoAnalyser
from bson import json_util

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
    return render_template("viz.html", project_name = project_name)

# Route to fetch necessary data from github
@app.route("/data", methods = ['POST', 'GET'])
def data():
    if request.method == "POST":
        # POST from homepage, extract data if necessary and redirect to viz
        git_url = request.form['git_url'] # TODO -- validate git url
        project_name = git_url.split('/')[-1][0:-4]
        repo = RepoAnalyser(project_name, mongo, working_dir=git_url)

        # Check if we have the data on this repo already, if not clone and extract
        if project_name not in mongo.db.collection_names():
            print "Data for project ", project_name, " not found. Fetching data..."
            repo = RepoAnalyser(project_name, mongo, verbose=True, working_dir = git_url)
            repo.persist_vcs_data()
        else:
            print "Data for git project ", project_name, " found."

        return redirect(url_for('show_viz', project_name = project_name))
    else:
        # Else, return JSON for project
        project_name = request.args.get('project_name')
        if project_name not in mongo.db.collection_names():
            print "Data for project: ", project_name, " not found. Go to homepage and enter git repo"
            return None

        # Query data from Mongo DB into json...
        print "data found for project: ", project_name
        commits = mongo.db[project_name].find({'revision_id': { '$exists': True}}, {'message': 0, '_id': 0})
        data = json_util.dumps(commits, default=json_util.default)
        return jsonify(data)


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
