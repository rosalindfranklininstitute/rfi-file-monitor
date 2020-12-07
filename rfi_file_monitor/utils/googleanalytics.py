from __future__ import annotations

import requests

from . import ExitableThread
from ..version import __version__

import logging
from queue import Queue, Full
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GoogleAnalyticsConsumer(ExitableThread):
    def __init__(self, context):
        super().__init__()
        self._context = context
        self._session = requests.Session()

    def run(self):
        while not self.should_exit:
            if not self._context._queue.empty():
                ec, ea, el = self._context._queue.get()
                data = self._context._base_payload.copy()
                data.update(ec=ec, ea=ea)
                if el:
                    data.update(el=el)
                response = self._session.post(url=self._context._endpoint, params=data, allow_redirects=True)
                try:
                    response.raise_for_status()
                    logger.debug(f'Event sent to Google Analytics!: {data} -> {response.status_code}')
                except Exception as e:
                    logger.debug(f'post failure: {str(e)}')
 
            time.sleep(0.1)

class GoogleAnalyticsContext:

    def __init__(self, endpoint: str, tracking_id: str, application_name: str, application_version: str, config_file: Path):
        self._endpoint = endpoint
        self._tracking_id = tracking_id
        self._application_name = application_name
        self._application_version = application_version
        self._config_file = config_file

        self._queue = Queue(maxsize=10000)

        if self._config_file.exists() and self._config_file.is_file():
            _uuid = self._config_file.read_text().strip()
            if not self._valid_uuid(_uuid):
                _uuid = str(uuid.uuid4())
                self._config_file.write_text(_uuid)
        else:
            _uuid = str(uuid.uuid4())
            try:
                self._config_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                self._config_file.write_text(_uuid)
            except Exception:
                pass

        self._base_payload = dict(
            v=1, # protocol version
	        tid=tracking_id,
	        t='event',
	        an=application_name,
	        av=application_version,
            cid=_uuid,
            # without user-agent, requests does not work!
            ua='Opera/9.80 (Windows NT 6.0) Presto/2.12.388 Version/12.14',
        )

        # launch consumer thread
        self._consumer_thread = GoogleAnalyticsConsumer(self)
        self._consumer_thread.start()
    
    def __del__(self):
        if self._consumer_thread.is_alive():
            self._consumer_thread.should_exit = True

    @property
    def consumer_thread(self):
        return self._consumer_thread

    def send_event(self, category: str, action: str, label: Optional[str] = None):
        if len(category) > 150:
            logger.warning(f'Category {category} is too long')
            return
        elif len(action) > 500:
            logger.warning(f'Action {action} is too long')
            return
        elif label is not None and len(label) > 500:
            logger.warning(f'Label {label} is too long')
            return

        try:
            if self._consumer_thread.is_alive():
                self._queue.put_nowait((category, action, label))
        except Full:
            logger.exception('queue is full!')

    def _valid_uuid(self, _uuid):
        try:
            uuid.UUID(_uuid)
        except ValueError:
            return False
        return True
