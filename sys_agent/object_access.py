"""Optional task-object policy, enforced by ToolExecutor rather than model text.

The backend provides metadata and scoped lookup without ambient directory enumeration.
No policy is inferred from untrusted model arguments. GUI-wide permission remains the
Registry/Executor/approval policy; callers may install a narrower immutable task scope.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import ntpath

from sys_agent.sandbox_file import SandboxError, resolve_object_path
from sys_agent.tool_policy import READ_ONLY_TOOL_NAMES

FILE_READ_TOOLS = frozenset({'read_file', 'read_table_data', 'find_file',
                             'find_files_by_extension', 'find_path_by_keywords'})


class ObjectAccessDenied(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ObjectScope:
    root: str
    objects: frozenset[str]
    max_read_calls: int = 16
    max_file_bytes: int = 16384
    max_result_bytes: int = 32768
    max_total_result_bytes: int = 131072
    max_results: int = 16


class ObjectAccessPolicy:
    def __init__(self, scope, backend, effect_validator, *, virtual=False):
        self.scope, self.backend, self.effect_validator = scope, backend, effect_validator
        self.virtual = virtual
        self.objects = frozenset(self.resolve(p) for p in scope.objects)
        self.read_calls = self.result_bytes = 0
        self.read_handler_ms = 0.0
        self.denials = []
        self.completed_effects = set()

    def resolve(self, value):
        try:
            return resolve_object_path(value, self.scope.root, virtual=self.virtual)
        except SandboxError as exc:
            raise ObjectAccessDenied('INVALID_OBJECT_PATH') from exc

    def record_denial(self, tool, error):
        # No path, command, content, or argument values in audit events.
        self.denials.append({'tool': tool, 'code': error.code})

    def _fingerprint(self, tool, args):
        from sys_agent.tool_policy import freeze_paths
        frozen = freeze_paths(tool, args)
        for field in {'path','src','dst','directory','destination_directory','search_directory','image_path','attachment_path'}:
            if frozen.get(field):
                frozen[field] = ntpath.normcase(ntpath.normpath(frozen[field]))
        if 'file_paths' in frozen:
            frozen['file_paths'] = [ntpath.normcase(ntpath.normpath(p)) for p in frozen['file_paths']]
        return json.dumps({'tool': tool, 'args': frozen}, sort_keys=True, ensure_ascii=False)

    def query_objects(self, tool, args):
        field = {'find_file': 'path', 'find_files_by_extension': 'directory',
                 'find_path_by_keywords': 'search_directory'}[tool]
        directory = self.resolve(args.get(field, '.'))
        candidates = {p for p in self.objects if ntpath.commonpath([directory, p]) == directory}
        if tool == 'find_path_by_keywords':
            depth = args.get('search_depth', 3)
            candidates = {p for p in candidates if ntpath.relpath(p, directory).count('\\') <= depth}
        if tool == 'find_file':
            term = args['filename'].casefold()
            if not term or any(c in term for c in '*?\\/'):
                raise ObjectAccessDenied('UNSCOPED_ENUMERATION')
            candidates = {p for p in candidates if term in ntpath.basename(p).casefold()}
        elif tool == 'find_files_by_extension':
            extensions = {x.casefold() for x in args['extensions']}
            candidates = {p for p in candidates if ntpath.splitext(p)[1] in extensions}
        else:
            terms = args['keywords']
            if not terms or any(not x for x in terms):
                raise ObjectAccessDenied('UNSCOPED_ENUMERATION')
            candidates = {p for p in candidates if all(x.casefold() in p.casefold() for x in terms)}
        if not candidates:
            raise ObjectAccessDenied('OBJECT_OUT_OF_SCOPE')
        # Only ask metadata about declared objects; no ambient directory listing.
        return sorted(p for p in candidates if self.backend.exists(p))[:self.scope.max_results]

    def preview(self, tool, args):
        """Pure check; batch preflight does not consume read or execution budgets."""
        if tool in FILE_READ_TOOLS:
            if self.read_calls >= self.scope.max_read_calls:
                raise ObjectAccessDenied('READ_BUDGET_EXCEEDED')
            if tool in {'read_file', 'read_table_data'}:
                target = self.resolve(args['path'])
                if target not in self.objects:
                    raise ObjectAccessDenied('OBJECT_OUT_OF_SCOPE')
                if self.backend.size(target) > self.scope.max_file_bytes:
                    raise ObjectAccessDenied('FILE_SIZE_LIMIT')
            else:
                self.query_objects(tool, args)
            return
        try:
            paths = self.backend.effect_paths(tool, args)
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            raise ObjectAccessDenied('TASK_ARGUMENT_MISMATCH') from exc
        for target in paths:
            if self.resolve(target) not in self.objects:
                raise ObjectAccessDenied('OBJECT_OUT_OF_SCOPE')
        if not self.effect_validator(tool, args):
            raise ObjectAccessDenied('TASK_ARGUMENT_MISMATCH')
        if tool in READ_ONLY_TOOL_NAMES:
            return
        if self._fingerprint(tool, args) in self.completed_effects:
            raise ObjectAccessDenied('DUPLICATE_SIDE_EFFECT')
        sources = [self.resolve(p) for p in args.get('file_paths', [])]
        if len(set(sources)) != len(sources):
            raise ObjectAccessDenied('DUPLICATE_SOURCE')
        destinations = [self.resolve(p) for p in self.backend.exclusive_destinations(tool, args)]
        if len(set(destinations)) != len(destinations):
            raise ObjectAccessDenied('TARGET_COLLISION')
        for target in destinations:
            if self.backend.exists(self.resolve(target)):
                raise ObjectAccessDenied('TARGET_EXISTS')

    def before(self, tool, args):
        self.preview(tool, args)
        if tool in FILE_READ_TOOLS:
            self.read_calls += 1

    def read_scoped(self, tool, args):
        """Never invoke an ambient filesystem handler in a scoped read.

        The trusted backend receives an explicit finite object selection. Missing
        scoped-read support fails closed in Executor instead of falling back.
        """
        targets = ([self.resolve(args['path'])] if tool in {'read_file','read_table_data'}
                   else self.query_objects(tool,args))
        return self.backend.read_objects(tool,args,tuple(targets))

    def after(self, tool, args, raw, elapsed_ms):
        size = len(json.dumps(raw, ensure_ascii=False, allow_nan=False).encode('utf-8'))
        if tool in FILE_READ_TOOLS:
            self.read_handler_ms += elapsed_ms
            if size > self.scope.max_result_bytes or self.result_bytes + size > self.scope.max_total_result_bytes:
                raise ObjectAccessDenied('READ_RESULT_LIMIT')
            for field in ('found_paths', 'file_paths'):
                values = raw.get(field, [])
                if len(values) > self.scope.max_results:
                    raise ObjectAccessDenied('READ_RESULT_LIMIT')
                if any(self.resolve(p) not in self.objects for p in values):
                    raise ObjectAccessDenied('OBJECT_OUT_OF_SCOPE')
            self.result_bytes += size
        elif tool not in READ_ONLY_TOOL_NAMES and raw.get('success'):
            self.completed_effects.add(self._fingerprint(tool, args))
