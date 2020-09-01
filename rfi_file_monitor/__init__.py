import logging
import sys

from .application import Application

import bugsnag
from bugsnag.handlers import BugsnagHandler

__version__ = "0.1.2"
BUGSNAG_API_KEY = 'b19e59eb84b9eb30d31d57a97e03406a'

logger = logging.getLogger(__name__)

bugsnag.configure(
    api_key=BUGSNAG_API_KEY,
    app_version=__version__,
    auto_notify=True,
    auto_capture_sessions=True,
    notify_release_stages=["production"],
)

# main entrypoint
def main():
    # set up logging
    monitor_logger = logging.getLogger('rfi_file_monitor')
    monitor_logger.setLevel(logging.DEBUG)

    log_fmt_long = logging.Formatter(
        fmt='%(asctime)s %(name)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # log to stdout
    log_handler_stream = logging.StreamHandler(sys.stdout)
    log_handler_stream.setFormatter(log_fmt_long)
    log_handler_stream.setLevel(logging.DEBUG)
    monitor_logger.addHandler(log_handler_stream)

    # log to bugsnag
    log_handler_bugsnag = BugsnagHandler()
    log_handler_bugsnag.setLevel(logging.INFO)
    monitor_logger.addHandler(log_handler_bugsnag)

    logger.info('Started')
    app = Application()
    rv = app.run(sys.argv)
    logger.info('Finished')
    sys.exit(rv)
