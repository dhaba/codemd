from codemd import app

from flask import request, session, redirect, url_for, \
     render_template, jsonify
from flask_s3 import create_all
import logging
from bson import json_util

from codemd.repo_analyser import RepoAnalyser
from codemd.metrics_builder import MetricsBuilder
from codemd.data_managers.db_handler import DBHandler

log = logging.getLogger('codemd')

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

# Debug -- for uploading statics
@app.route("/upload")
def upload_statics():
    create_all(app)
    return "Finished uploading statics"

# Debug -- for creating dashboard data
# @app.route("/create_dash_data")
# def create_dash_data():
#     for project_name in mongo.db.collection_names():
#         log.debug("Creating dashboard data for collection: %s", project_name)
#         metrics = MetricsBuilder(project_name)
#         metrics.save_commits()
#     return "Done!"

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

    return render_template("hotspots.html", project_name=project_name,
                           intervals=intervals)


# Route to fetch necessary data from github
@app.route("/fetchdata", methods = ['POST'])
def fetchdata():
    # POST from homepage form, extract data if necessary and redirect to viz
    git_url = request.form['git_url'] # TODO -- validate git url
    project_name = RepoAnalyser.short_name(git_url)

    # Check if we have the data on this repo already, if not clone and extract
    if not DBHandler.project_exists(project_name):
        log.info("Data for project " + project_name + " not found. Fetching data...")
        repo = RepoAnalyser(git_url)
        repo.persist_commits_data()
        # Save viz data for fast loading times
        metrics = MetricsBuilder(project_name)
        metrics.save_commits()
    else:
        log.info("Data for git project " + project_name + " found.")

    return redirect(url_for('show_viz', project_name = project_name))


# Return commits JSON for dashboards
@app.route("/api/commits")
def get_commits():
    project_name = request.args.get('project_name')

    # Safety check to make sure we have the data in mongo
    if not DBHandler.project_exists(project_name):
        log.error("Data for project: %s not found. Go to homepage and \
                  enter git repo", project_name)
        return redirect(url_for('show_home'))

    metrics = MetricsBuilder(project_name)
    commits_data = metrics.load_commits()
    log.info("Extracted %s rows of commits data for project %s",
              len(commits_data), project_name)

    return jsonify(commits_data)


# Return file tree with scores and complexity for hotspots viz
@app.route("/api/hotspots")
def get_hotspots():
    project_name = request.args.get('project_name')
    intervals = extract_interval_params(request.args)

    log.debug("(in api/hotspots/...) intervals = " + str(intervals))

    # Safety check to make sure we have the data in mongo
    if not DBHandler.project_exists(project_name):
        log.error("Data for project: %s not found. Go to homepage and \
                  enter git repo", project_name)
        return redirect(url_for('show_home'))

    metrics = MetricsBuilder(project_name)
    hotspots_data = json_util.dumps(metrics.hotspots(
                                    interval1_start = intervals[0][0],
                                    interval1_end = intervals[0][1],
                                    interval2_start = intervals[1][0],
                                    interval2_end = intervals[1][1]))

    # log.info('hotspots data: %s', hotspots_data) # DEBUG LINE
    return jsonify(hotspots_data)
