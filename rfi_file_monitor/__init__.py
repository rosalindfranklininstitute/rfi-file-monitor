import logging
import sys

from .application import Application

__version__ = "0.1.0"

# main entrypoint
def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Started')
    app = Application()
    rv = app.run(sys.argv)
    logging.info('Finished')
    sys.exit(rv)
