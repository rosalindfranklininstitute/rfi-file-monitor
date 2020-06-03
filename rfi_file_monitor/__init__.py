import logging
import sys

from .application import Application

# main entrypoint
def main():
    logging.basicConfig(level=logging.DEBUG)
    logging.info('Started')
    app = Application()
    rv = app.run(sys.argv)
    logging.info('Finished')
    sys.exit(rv)
