import argparse
import humanfriendly
from pathlib import Path
import time
import os
import logging

parser = argparse.ArgumentParser(
    description="Generate files into a directory for testing with the RFI-file-monitor"
)
parser.add_argument("destination", type=str, help="Directory to write files to")
parser.add_argument(
    "--filesize",
    type=str,
    help="The filesize that the files will be generated with",
    default="1MB",
)
parser.add_argument(
    "--sleeptime",
    type=int,
    help="The time between two files being written, in seconds",
    default=2,
)
parser.add_argument(
    "--prefix",
    type=str,
    help="The prefix that will be used to construct the filenames",
    default="file",
)
parser.add_argument(
    "--extension",
    type=str,
    help="The extension that will be used for the filenames",
    default=".txt",
)
parser.add_argument(
    "--nfiles",
    type=int,
    help="The number of files that will be generated",
    default=20,
)
parser.add_argument(
    "--startindex",
    type=int,
    help="Start numbering files with this number",
    default=0,
)
parser.add_argument(
    "--nsaves",
    type=int,
    help="Save file multiple times. Uses sleeptime for time between saves",
    default=1,
)

args = parser.parse_args()
filesize = humanfriendly.parse_size(args.filesize, binary=True)

for i in range(args.nfiles):
    path = Path(
        args.destination, f"{args.prefix}{i + args.startindex}{args.extension}"
    )
    for j in range(args.nsaves):
        path.write_bytes(os.urandom(filesize))
        time.sleep(args.sleeptime)
    logging.warning(f"Writing {str(path)}")
    time.sleep(args.sleeptime)
