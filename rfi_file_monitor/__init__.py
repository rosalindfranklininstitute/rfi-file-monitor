import logging
import sys
import os
from pathlib import PurePath

import bugsnag
from bugsnag.handlers import BugsnagHandler
from .version import __version__

# set AWS_DATA_PATH to allow using Ceph specific boto3 API
os.environ["AWS_DATA_PATH"] = str(
    PurePath(__file__).parent.joinpath("data", "models")
)

BUGSNAG_API_KEY = "b19e59eb84b9eb30d31d57a97e03406a"

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
    from .application import Application

    # set up logging
    monitor_logger = logging.getLogger("rfi_file_monitor")
    monitor_logger.setLevel(logging.DEBUG)

    log_fmt_long = logging.Formatter(
        fmt="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # log to stdout
    log_handler_stream = logging.StreamHandler(sys.stdout)
    log_handler_stream.setFormatter(log_fmt_long)
    log_handler_stream.setLevel(logging.DEBUG)
    monitor_logger.addHandler(log_handler_stream)

    # # log to bugsnag
    # log_handler_bugsnag = BugsnagHandler()
    # log_handler_bugsnag.setLevel(logging.WARNING)
    # monitor_logger.addHandler(log_handler_bugsnag)

    app = Application()
    rv = app.run(sys.argv)
    sys.exit(rv)
