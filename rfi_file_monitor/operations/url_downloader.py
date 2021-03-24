import requests

# pylint: disable=import-error
from requests.packages.urllib3.util.retry import Retry

from ..file import URL
from ..queue_manager import QueueManager
from .s3_downloader import S3DownloaderOperation
from ..utils import get_file_creation_timestamp, TimeoutHTTPAdapter
from ..utils.decorators import supported_filetypes, with_pango_docs
from ..utils.exceptions import SkippedOperation

import logging
import datetime
from dateutil.parser import parse as parsedate
from pathlib import Path

logger = logging.getLogger(__name__)

SESSION = requests.Session()
adapter = TimeoutHTTPAdapter(
    timeout=2.5,
    max_retries=Retry(
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=[
            "HEAD",
            "GET",
            "PUT",
            "DELETE",
            "OPTIONS",
            "TRACE",
            "POST",
        ],
        total=5,
    ),
    pool_maxsize=QueueManager.MAX_JOBS,
)
SESSION.mount("https://", adapter)
SESSION.mount("http://", adapter)


@supported_filetypes(filetypes=URL)
@with_pango_docs(filename="url_downloader.pango")
class UrlDownloaderOperation(S3DownloaderOperation):

    NAME = "URL Downloader"
    CHUNK_SIZE = 1024 * 50

    def run(self, file: URL):

        # Check if file already exists in the destination folder
        destination = Path(
            self.params.download_destination, *file.relative_filename.parts
        )

        # try a get request to get the response header only
        response = SESSION.get(file.filename, allow_redirects=True, stream=True)
        try:
            logger.debug(f"{response.status_code=}")
            response.raise_for_status()
        except Exception as e:
            return str(e)

        try:
            url_size = int(response.headers["Content-Length"])
        except Exception:
            url_size = None

        if destination.exists():
            # get the filesize
            try:
                file_size = destination.stat().st_size
                if url_size == file_size:
                    url_time = parsedate(
                        response.headers["Last-Modified"]
                    ).astimezone()
                    file_time = datetime.datetime.fromtimestamp(
                        get_file_creation_timestamp(destination)
                    ).astimezone()
                    if url_time < file_time:
                        raise SkippedOperation(
                            "File has been downloaded already"
                        )
            except SkippedOperation:
                raise
            except Exception:
                pass
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("wb") as f:
            downloaded_bytes = 0
            last_percentage = 0

            for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)

                    if url_size:
                        downloaded_bytes += self.CHUNK_SIZE
                        percentage = (downloaded_bytes / url_size) * 100
                        if int(percentage) > last_percentage:
                            last_percentage = int(percentage)
                            file.update_progressbar(self.index, last_percentage)
