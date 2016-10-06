from flask.ext.pymongo import PyMongo
from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash, jsonify
from stock_scraper import get_data

# Create app instance
app = Flask(__name__)

# Set db configuration options
app.config['MONGO_DBNAME'] = 'codemd'

# Create db instance
mongo = PyMongo(app)


# Home page
@app.route("/")
def show_home():
    entries = mongo.db.codemd.find()
    return render_template('show_home.html', entries=entries)

# Test route for Circle Packing Hotspot viz
@app.route("/hotspots")
def hotspots():
    return render_template("hotspots.html")

# Test route for D3 viz
@app.route("/d3")
def test_d3():
    return render_template('test_d3.html')

# Test route to get stock data
@app.route("/data")
def data():
    return jsonify(get_data())
