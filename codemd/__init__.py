import logging
from flask_pymongo import PyMongo
from flask import Flask
from flask_s3 import FlaskS3, create_all

from codemd.config import config_app

# Create and configure app instance
app = Flask(__name__)
config_app(app)

# Create db instance
mongo = PyMongo(app)

# Load views
import codemd.views
