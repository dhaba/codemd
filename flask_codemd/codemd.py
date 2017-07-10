from bson import json_util
import logging
import time
import os.path
import json

from flask_pymongo import PyMongo
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify

from repo_analyser import RepoAnalyser
from metrics_builder import MetricsBuilder


# Create app instance
app = Flask(__name__)
app.secret_key = "somesupersecretkeythatnoonewilleverguess"


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
file_handler.setLevel(logging.NOTSET)
stream_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-5s %(levelname)-8s %(message)s')
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
log.addHandler(file_handler)
log.addHandler(stream_handler)



def extract_interval_params(request_args):
    """
    Take a url request object and extracts the associated intervals and returns
    them as a list of tuples

    params request_args: an instance of request.args
    return: A list of lists, ie [[start1, end1], [start2, end2]]
    """
    intervals = [[None, None], [None, None]]
    start1, end1 = request_args.get("start1"), request_args.get("end1")
    start2, end2 = request_args.get("start2"), request_args.get("end2")
    if ((start1 and end1) and (start1 != 'null') and (end1 != 'null')):
        intervals[0] = [int(start1), int(end1)]
    if ((start2 and end2) and (start2 != 'null') and (end2 != 'null')):
        intervals[1] = [int(start2), int(end2)]

    return intervals


# Debug
@app.route("/test")
def show_test():
    return render_template('test_dash.html')

# Home page
@app.route("/")
def show_home():
    return render_template('show_home.html')


# Main page for circle packing visualizations
@app.route("/dashboards/<project_name>")
def show_viz(project_name):
    return render_template("viz.html", project_name=project_name)


# Routes for circle packing viz
@app.route("/hotspots/<project_name>")
def hotspots(project_name):

    intervals = extract_interval_params(request.args)
    log.debug("Getting info for project name: %s\nwith intervals: %s",
              project_name, intervals)

    log.debug("intervals:" + str(intervals))

    return render_template("hotspots.html", project_name=project_name,
                           intervals=intervals)


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

    # Check if we have JSON already
    file_path = "./json_data/" + project_name
    if os.path.isfile(file_path):
        log.debug("Found file for commits data at path at %s. \
                   Serving to page...", file_path)
        commits_json = json_util.loads(file_path)
        return jsonify(commits_json)

    log.debug("File not found at path %s. Extracting from db...", file_path)
    metrics = MetricsBuilder(mongo.db[project_name])
    commits_data = metrics.commits()
    log.info("Extracted %s rows of commits data for project %s",
              len(commits_data), project_name)
    commits_json = json_util.dumps(commits_data)
    log.info("Length after dumping to json: %s", len(commits_json))

    # log.info("Saving file to path: %s", file_path)
    # with open(file_path, 'w') as outfile:
    #     json.dump(commits_json, url_for('static', outfile))

    return jsonify(commits_json)

# Return file tree with scores and complexity for hotspots viz
@app.route("/api/hotspots")
def get_hotspots():
    project_name = request.args.get('project_name')
    intervals = extract_interval_params(request.args)

    log.debug("(in api/hotspots/...) intervals = " + str(intervals))

    # Safety check to make sure we have the data in mongo
    if project_name not in mongo.db.collection_names():
        log.error("Data for project: %s not found. Go to homepage and \
                  enter git repo", project_name)
        return redirect(url_for('show_home'))

    metrics = MetricsBuilder(mongo.db[project_name])
    hotspots_data = json_util.dumps(metrics.hotspots(
                                    interval1_start = intervals[0][0],
                                    interval1_end = intervals[0][1],
                                    interval2_start = intervals[1][0],
                                    interval2_end = intervals[1][1]))

    # log.info('hotspots data: %s', hotspots_data) # DEBUG LINE

    return jsonify(hotspots_data)


if __name__ == "__main__":
    app.debug = True
    app.run()
