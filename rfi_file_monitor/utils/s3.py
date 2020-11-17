import boto3.s3.transfer

from ..file import File

import os
from threading import Lock
from pathlib import Path
import hashlib
from typing import Optional

KB = 1024
MB = KB * KB
TransferConfig = boto3.s3.transfer.TransferConfig(max_concurrency=1, multipart_chunksize=8*MB, multipart_threshold=8*MB)

def calculate_etag(file: str):
    # taken from https://stackoverflow.com/a/52300584
    with open(file, 'rb') as f:
        md5hash = hashlib.md5()
        filesize = 0
        block_count = 0
        md5string = b''
        for block in iter(lambda: f.read(TransferConfig.multipart_chunksize), b''):
            md5hash = hashlib.md5()
            md5hash.update(block)
            md5string += md5hash.digest()
            filesize += len(block)
            block_count += 1

    if filesize > TransferConfig.multipart_threshold:
        md5hash = hashlib.md5()
        md5hash.update(md5string)
        md5hash = md5hash.hexdigest() + "-" + str(block_count)
    else:
        md5hash = md5hash.hexdigest()

    return md5hash


# taken from https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
class S3ProgressPercentage(object):

    def __init__(self, file: File, filename: str, operation_index: int, size: Optional[float] = None):
        self._file = file
        if size:
            self._size = size
        else:
            self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._last_percentage = 0
        self._operation_index = operation_index

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename
        self._seen_so_far += bytes_amount
        percentage = (self._seen_so_far / self._size) * 100
        if int(percentage) > self._last_percentage:
            self._last_percentage = int(percentage)
            self._file.update_progressbar(self._operation_index, self._last_percentage)