from __future__ import annotations

import boto3.s3.transfer

from ..file import File
from . import ExitableThread

import os
import hashlib
from typing import Optional, Union
import threading
import logging

logger = logging.getLogger(__name__)

KB = 1024
MB = KB * KB
TransferConfig = boto3.s3.transfer.TransferConfig(max_concurrency=1, multipart_chunksize=8*MB, multipart_threshold=8*MB, use_threads=False)

def calculate_etag(file: Union[str, os.PathLike]):
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
        md5hash_digested = md5hash.hexdigest() + "-" + str(block_count)
    else:
        md5hash_digested = md5hash.hexdigest()

    return md5hash_digested


# taken from https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
class S3ProgressPercentage(object):

    def __init__(self,
        file: File,
        filename: Union[str, os.PathLike],
        operation_index: int,
        size: Optional[float] = None,
        manager: Optional[boto3.s3.transfer.TransferManager] = None,
        ):
        
        self._file = file
        if size:
            self._size = size
        else:
            self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._last_percentage = 0
        self._operation_index = operation_index
        self._manager = manager

    def __call__(self, bytes_amount):
        current_thread = threading.current_thread()

        if isinstance(current_thread, ExitableThread) and current_thread.should_exit and self._manager is not None:
            # see https://github.com/boto/s3transfer/pull/144
            # use shutdown when fixed
            self._manager._shutdown(cancel=True, cancel_msg='Job cancelled')
            return
        elif not isinstance(current_thread, ExitableThread):
            logger.warning('S3ProgressPercentage not running in ExitableThread!!!!!')
        elif current_thread is threading.main_thread():
            logger.warning('S3ProgressPercentage __call__ running in main thread!')


        # To simplify, assume this is hooked up to a single filename
        self._seen_so_far += bytes_amount
        percentage = (self._seen_so_far / self._size) * 100
        if int(percentage) > self._last_percentage:
            self._last_percentage = int(percentage)
            self._file.update_progressbar(self._operation_index, self._last_percentage)