from bson import json_util
import logging

from flask_pymongo import PyMongo
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify

from repo_analyser import RepoAnalyser


# Create app instance
app = Flask(__name__)
app.secret_key = "sillycats123"

# Set db configuration options
app.config['MONGO_DBNAME'] = 'codemd'

# Create db instance
mongo = PyMongo(app)

# Setup logging
log = logging.getLogger('codemd')
log.setLevel(logging.DEBUG)
file_handler, stream_handler = logging.FileHandler('codemd_log.log'), logging.StreamHandler()
file_handler.setLevel(logging.DEBUG)
stream_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-5s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
log.addHandler(file_handler)
log.addHandler(stream_handler)


# Home page
@app.route("/")
def show_home():
    return render_template('show_home.html')


# Main page for circle packing visualizations
@app.route("/viz/<project_name>")
def show_viz(project_name):
    return render_template("viz.html", project_name=project_name)


# Route to fetch necessary data from github
@app.route("/fetchdata", methods = ['POST'])
def fetchdata():
    # POST from homepage, extract data if necessary and redirect to viz
    git_url = request.form['git_url'] # TODO -- validate git url
    project_name = RepoAnalyser.short_name(git_url)

    # Check if we have the data on this repo already, if not clone and extract
    if project_name not in mongo.db.collection_names():
        log.info("Data for project " + project_name + " not found. Fetching data...")
        repo = RepoAnalyser(git_url, mongo)
        repo.persist_commits_data()
    else:
        log.info("Data for git project " + project_name + " found.")

    return "Success!" # debug line
    return redirect(url_for('show_viz', project_name = project_name))
    # else:
    #     # Else, return JSON for project
    #     project_name = request.args.get('project_name')
    #     if project_name not in mongo.db.collection_names():
    #         print "Data for project: ", project_name, " not found. Go to homepage and enter git repo"
    #         return None
    #
    #     # Query data from Mongo DB into json...
    #     print "data found for project: ", project_name
    #     commits = mongo.db[project_name].find({'revision_id': { '$exists': True}}, {'message': 0, '_id': 0})
    #     json_data = json_util.dumps(commits, default=json_util.default)
    #     return jsonify(json_data)


# Test route for Circle Packing Hotspot viz
@app.route("/hotspots")
def hotspots():
    return render_template("hotspots.html")
