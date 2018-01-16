import codemd.keys as keys
import logging
import time

def config_app(app):
    app.secret_key = keys.SECRET_KEY

    # Setup S3
    app.config['AWS_ACCESS_KEY_ID'] = keys.AWS_ACCESS_KEY_ID
    app.config['AWS_SECRET_ACCESS_KEY'] = keys.AWS_SECRET_ACCESS_KEY
    app.config['FLASKS3_BUCKET_NAME'] = keys.STATIC_BUCKET_NAME

    # Set db configuration options
    # app.config['MONGO_DBNAME'] = 'codemd'
    app.config['MONGO_URI'] = keys.MONGO_URI

    # Setup logging
    timestr = time.strftime("%Y%m%d-%H%M%S")
    log_name = 'logs/codemd_log_{}.log'.format(timestr)
    file_handler, stream_handler = logging.FileHandler(log_name), logging.StreamHandler()
    log = logging.getLogger('codemd')
    log.setLevel(logging.DEBUG)
    file_handler.setLevel(logging.DEBUG)
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)-5s %(levelname)-8s %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    # log.addHandler(file_handler)
    log.addHandler(stream_handler)
