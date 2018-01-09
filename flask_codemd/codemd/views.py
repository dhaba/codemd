from codemd import app

from flask import request, session, redirect, url_for, \
     render_template, jsonify, make_response
from flask_s3 import create_all
import logging
from bson import json_util

from codemd.mining.repo_analyser import RepoAnalyser
from codemd.metrics.metrics_builder import MetricsBuilder
from codemd.data_managers.db_handler import DBHandler
from codemd.utils import extract_interval_params

log = logging.getLogger('codemd')

DASHBOARD_VISTED_COOKIE = "has_visted_dash"
CP_VISTED_COOKIE = "has_visted_cp"

# Debug
@app.route("/build_cp_data/<project_name>")
def build_cp_data(project_name):
    builder = MetricsBuilder(project_name)
    builder.save_circle_packing_data()
    return "Done!"


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
    # TODO -- make below "first visit" checking code DRYer
    has_visited = request.cookies.get(DASHBOARD_VISTED_COOKIE)
    should_show = False
    if has_visited is None:
        log.info("First visit on dashboard detected, setting show_tutorial to True.")
        should_show = True
    else:
        log.info("Dashboard visited before, setting show_tutorial to False.")

    resp = make_response(render_template("dashboard.html", project_name=project_name, show_tutorial=should_show))
    resp.set_cookie(DASHBOARD_VISTED_COOKIE, '1')
    return resp


# Routes for circle packing viz
@app.route("/circle_packing/<project_name>")
def circle_packing(project_name):
    intervals = extract_interval_params(request.args)
    log.debug("Getting info for project name: %s\nwith intervals: %s",
              project_name, intervals)

    has_visited = request.cookies.get(CP_VISTED_COOKIE)
    should_show = False
    if has_visited is None:
        log.info("First visit on CirclePacking detected, setting show_tutorial to True.")
        should_show = True
    else:
        log.info("CirclePacking visited before, setting show_tutorial to False.")

    resp = make_response(render_template("circle_packing.html", project_name=project_name,
                           intervals=intervals, show_tutorial=should_show))
    resp.set_cookie(CP_VISTED_COOKIE, '1')
    return resp


# Route to fetch necessary data from github
@app.route("/fetchdata", methods = ['POST'])
def fetchdata():
    # POST from homepage form, extract data if necessary and redirect to viz
    git_url = request.form['inputUrl'] # TODO -- validate git url
    project_name = RepoAnalyser.short_name(git_url)
    full_name = request.form['inputProjectName']
    project_desc = request.form['inputDescription']

    log.debug("url: %s\ninternal name: %s\nfull name: %s\ndesc: %s",
                    git_url, project_name, full_name, project_desc)

    # Check if we have the data on this repo already, if not clone and extract
    if not DBHandler.project_exists(project_name):
        log.info("Data for project " + project_name + " not found. Fetching data...")
        repo = RepoAnalyser(git_url, full_name=full_name, description=project_desc)
        repo.persist_meta_data()
        repo.persist_commits_data()

        # Save viz/circle packing data for fast loading times
        metrics = MetricsBuilder(project_name)
        log.debug("Saving dashboard data...")
        metrics.save_commits()
        log.debug("Saving checkpoint data...")
        metrics.save_circle_packing_data()
        log.debug("Done saving project data.")
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


# Return file tree with scores and complexity for circle_packing viz
@app.route("/api/circle_packing")
def get_circle_packing():
    project_name = request.args.get('project_name')
    intervals = extract_interval_params(request.args)

    log.debug("(in api/circle_packing/...) intervals = " + str(intervals))

    # Safety check to make sure we have the data in mongo
    if not DBHandler.project_exists(project_name):
        log.error("Data for project: %s not found. Go to homepage and \
                  enter git repo", project_name)
        return redirect(url_for('show_home'))

    metrics = MetricsBuilder(project_name)
    #circle_packing_data = json_util.dumps(metrics.circle_packing(intervals))
    circle_packing_data = metrics.circle_packing(intervals)

    # log.info('circle_packing data: %s', circle_packing_data) # DEBUG LINE
    return jsonify(circle_packing_data)
