from bson import json_util
import logging
import time

from flask_pymongo import PyMongo
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify

from repo_analyser import RepoAnalyser
from metrics_builder import MetricsBuilder


# Create app instance
app = Flask(__name__)
app.secret_key = "sillycats123"

# Set db configuration options
app.config['MONGO_DBNAME'] = 'codemd'
# app.config['MONGO_URI'] = 'mongodb://default:hireme@ds021434.mlab.com:21434/codemd'

# Create db instance
mongo = PyMongo(app)

# Setup logging
timestr = time.strftime("%Y%m%d-%H%M%S")
log_name = 'logs/codemd_log_{}.log'.format(timestr)
log = logging.getLogger('codemd')
log.setLevel(logging.DEBUG)
file_handler, stream_handler = logging.FileHandler(log_name), logging.StreamHandler()
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
@app.route("/dashboards/<project_name>")
def show_viz(project_name):
    return render_template("viz.html", project_name=project_name)


# Route to fetch necessary data from github
@app.route("/fetchdata", methods = ['POST'])
def fetchdata():
    # POST from homepage form, extract data if necessary and redirect to viz
    git_url = request.form['git_url'] # TODO -- validate git url
    project_name = RepoAnalyser.short_name(git_url)

    # Check if we have the data on this repo already, if not clone and extract
    if project_name not in mongo.db.collection_names():
        log.info("Data for project " + project_name + " not found. Fetching data...")
        repo = RepoAnalyser(git_url, mongo)
        repo.persist_commits_data()
    else:
        log.info("Data for git project " + project_name + " found.")

    return redirect(url_for('show_viz', project_name = project_name))


# Return commits JSON for dashboards
@app.route("/api/commits")
def get_commits():
    project_name = request.args.get('project_name')

    # Safety check to make sure we have the data in mongo
    # TODO -- write helper function so i'm not copy pasting this every time
    if project_name not in mongo.db.collection_names():
        log.error("Data for project: %s not found. Go to homepage and \
                  enter git repo", project_name)
        return redirect(url_for('show_home'))

    metrics = MetricsBuilder(mongo.db[project_name])
    commits_data = metrics.commits()
    log.info("Extracted %s rows of commits data for project %s", len(commits_data),
             project_name)
    commits_json = json_util.dumps(commits_data)
    log.info("Length after dumping to json: %s", len(commits_json))

    return jsonify(commits_json)

# Return file tree with scores and complexity for hotspots viz
@app.route("/api/hotspots")
def get_hotspots():
    project_name = request.args.get('project_name')
    # Safety check to make sure we have the data in mongo
    if project_name not in mongo.db.collection_names():
        log.error("Data for project: %s not found. Go to homepage and \
                  enter git repo", project_name)
        return redirect(url_for('show_home'))

    metrics = MetricsBuilder(mongo.db[project_name])
    hotspots_data = json_util.dumps(metrics.hotspots())

    return jsonify(hotspots_data)


# Test route for Circle Packing Hotspot viz TODO remove this
@app.route("/hotspots/<project_name>")
def hotspots(project_name):
    log.debug("Getting info for project name: %s", project_name)
    return render_template("hotspots.html", project_name=project_name)


if __name__ == "__main__":
    app.debug = True
    app.run()
