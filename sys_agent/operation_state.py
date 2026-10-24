"""Executor-local effect receipts. No persistence, argument logging or automatic replay."""
from copy import deepcopy
import hashlib
import json
import os
import threading
import uuid

from sys_agent.tool_policy import freeze_paths


class OperationState:
    def __init__(self):
        self._records = {}
        self._lock = threading.Lock()

    @staticmethod
    def fingerprint(tool, args):
        args = freeze_paths(tool, args)
        for field in ('path', 'src', 'dst', 'directory', 'destination_directory',
                      'search_directory', 'image_path', 'attachment_path'):
            if args.get(field):
                args[field] = os.path.normcase(os.path.normpath(args[field]))
        if 'file_paths' in args:
            args['file_paths'] = [os.path.normcase(os.path.normpath(p)) for p in args['file_paths']]
        payload = json.dumps([tool, args], sort_keys=True, ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def get(self, tool, args):
        with self._lock:
            return deepcopy(self._records.get(self.fingerprint(tool, args)))

    def start(self, tool, args):
        """Atomically reserve before invoking a handler, including concurrent tickets."""
        key = self.fingerprint(tool, args)
        with self._lock:
            if key in self._records:
                return None
            record = dict(operation_id=uuid.uuid4().hex, tool=tool, status='RUNNING')
            self._records[key] = record
            return deepcopy(record)

    def finish(self, tool, args, success):
        with self._lock:
            record = self._records[self.fingerprint(tool, args)]
            # A failed handler can have partially changed the system. Never infer rollback.
            record['status'] = 'SUCCEEDED' if success else 'UNKNOWN'
            return deepcopy(record)

    def snapshot(self):
        with self._lock:
            return deepcopy(list(self._records.values()))
