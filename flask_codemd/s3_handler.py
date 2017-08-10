import keys
from boto.s3.key import Key
from boto.s3.connection import S3Connection
import json
import logging

class S3Handler(object):

    DASHBOARD_DATA_FOLDER = "dashboard_data"

    def __init__(self, project_name):
        self.project_name = project_name
        self.conn = S3Connection(aws_access_key_id=keys.AWS_ACCESS_KEY_ID, \
                                 aws_secret_access_key=keys.AWS_SECRET_ACCESS_KEY)
        self.log = logging.getLogger('codemd.S3Handler')
        self.bucket = self.conn.get_bucket(keys.DATA_BUCKET_NAME)
        self.key = Key(self.bucket)
        self.log.info("")

    def save_dashboard_data(self, data):
        """
        Saves the dashboard data as json to the S3 bucket, under the path:
            "dashboard_data"/"project_name".json

        :param project_name: The name of the project (which should be name of
                             mongodb collection)
        :param data: The data to be saved (assumes type is a list or dictionary)
        """
        path = self.__dashboard_path()
        self.log.info("Saving dashboard data to S3 bucket at path: %s...", path)
        self.key.key = path
        try:
            self.key.set_contents_from_string(json.dumps(data))
            self.log.info("Finished saving dashboard data")
        except Exception as e:
            self.log.error("!!! Error saving dashboard data:\n\t%s", e.message)

    def load_dashboard_data(self):
        path = self.__dashboard_path()
        self.log.info("Loading dashboard data at path %s...", path)
        self.key.key = path
        data = None
        try:
            data = self.key.get_contents_as_string()
            self.log.info("Finished loading dashboard data")
        except Exception as e:
            self.log.error("!!! Error loading dashboard data:\n\t%s", e.message)
        return data

    def __dashboard_path(self):
        return self.DASHBOARD_DATA_FOLDER + "/" + self.project_name + ".json"
