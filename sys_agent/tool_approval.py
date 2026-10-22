"""DeepShell Agent 一次性人工审批票据。

所属模块：sys_agent。
职责：在内存中绑定本次写入的文件名和完整内容；批准票据只能消费一次。
模型只能生成待审批请求，不能决定审批结论；审批内容绝不写入 Trace。
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, model_validator
from sys_agent.sandbox_file import MAX_CONTENT_BYTES, SandboxedTextWriter, SandboxError, validate_payload
from sys_agent.tool_schema import StrictToolArgs


class CreateTextFileArgs(StrictToolArgs):
    """仅接受顶层文件名与少量 UTF-8 文本，不接受 path/overwrite 等字段。"""
    filename: str = Field(min_length=5, max_length=67)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_BYTES)

    @model_validator(mode='after')
    def check_sandbox(self):
        validate_payload(self.filename, self.content)
        return self


CREATE_TEXT_FILE_SCHEMA = {
    'name': 'create_text_file',
    'description': '仅在专用 Agent 工作区创建一个新的 .txt 文件；必须先经用户逐次人工批准，不能覆盖已有文件。',
    'parameters': {
        'type': 'object',
        'properties': {
            'filename': {'type': 'string', 'description': '单个文件名，例如 hello.txt；禁止目录路径'},
            'content': {'type': 'string', 'description': f'文本内容，UTF-8 最多 {MAX_CONTENT_BYTES} 字节'},
        },
        'required': ['filename', 'content'],
        'additionalProperties': False,
    },
}


def blocked_direct_handler(**_kwargs):
    """保护可能仍会读取 function_map 的旧代码，禁止直接调用写入。"""
    raise PermissionError('此工具必须通过 ToolExecutor 审批执行')


@dataclass(frozen=True)
class ApprovalTicket:
    request_id: str
    filename: str
    content: str
    digest: str
    created_at: float
    workspace: str


class ApprovalStore:
    """只在内存中持有审批请求；无跨进程持久授权。"""

    def __init__(self, workspace: str | Path, ttl_seconds: float = 120.0):
        self.writer = SandboxedTextWriter(workspace)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._tickets: dict[str, ApprovalTicket] = {}

    def prepare(self, filename: str, content: str) -> dict:
        """仅登记请求，不发生写操作；返回对模型安全的公开元数据。"""
        payload = validate_payload(filename, content)
        ticket = ApprovalTicket(
            request_id=secrets.token_urlsafe(24), filename=filename, content=content,
            digest=hashlib.sha256(payload).hexdigest(), created_at=time.monotonic(),
            workspace=str(self.writer.root),
        )
        with self._lock:
            now = time.monotonic()
            self._tickets = {key: value for key, value in self._tickets.items()
                             if now - value.created_at <= self.ttl_seconds}
            self._tickets[ticket.request_id] = ticket
        return {'request_id': ticket.request_id, 'filename': ticket.filename,
                'sha256': ticket.digest, 'content_bytes': len(payload)}

    def get_for_review(self, request_id: str) -> dict | None:
        """仅供受信任的本地 Qt 审批界面读取完整内容，禁止送入 LLM/Trace。"""
        with self._lock:
            ticket = self._tickets.get(request_id)
        if ticket is None:
            return None
        if time.monotonic() - ticket.created_at > self.ttl_seconds:
            with self._lock:
                self._tickets.pop(request_id, None)
            return None
        return {'request_id': ticket.request_id, 'filename': ticket.filename,
                'content': ticket.content, 'sha256': ticket.digest,
                'workspace': ticket.workspace}

    def resolve(self, request_id: str, approved: bool) -> dict:
        """消费审批票据；拒绝、过期、批准都消耗一次。不能重新使用。"""
        with self._lock:
            ticket = self._tickets.pop(request_id, None)
        if ticket is None:
            return {'success': False, 'code': 'APPROVAL_INVALID', 'message': '审批请求不存在或已使用'}
        if time.monotonic() - ticket.created_at > self.ttl_seconds:
            return {'success': False, 'code': 'APPROVAL_EXPIRED', 'message': '审批已过期'}
        if approved is not True:
            return {'success': False, 'code': 'APPROVAL_DENIED', 'message': '文件写入未获批准'}
        if str(self.writer.root) != ticket.workspace:
            return {'success': False, 'code': 'APPROVAL_INVALID', 'message': '审批工作区已改变'}
        try:
            # 执行时再次验证；写入的永远是原申请中保存的不可变文件名和内容。
            path = self.writer.create(ticket.filename, ticket.content)
        except (OSError, SandboxError) as exc:
            return {'success': False, 'code': 'WRITE_FAILED', 'message': f'文件创建失败：{type(exc).__name__}'}
        return {'success': True, 'code': 'SUCCESS', 'message': '用户已批准，文件创建成功',
                'data': {'path': path, 'sha256': ticket.digest}}


@dataclass(frozen=True)
class OperationTicket:
    request_id: str
    tool: str
    payload: str
    preview: str
    effect: str
    digest: str
    created_at: float
    handler: object


class OperationApprovalStore:
    """Freeze arguments and handler together. GUI approval consumes exactly one request."""

    def __init__(self, ttl_seconds=120.0):
        self.ttl_seconds = ttl_seconds
        self._tickets = {}
        self._lock = threading.Lock()

    def prepare(self, tool, arguments, handler, effect, extra_preview=None):
        import json
        payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True, allow_nan=False)
        preview = json.dumps({'tool': tool, 'arguments': arguments,
                              **({'execution_plan': extra_preview} if extra_preview is not None else {})},
                             ensure_ascii=False, indent=2, allow_nan=False)
        ticket = OperationTicket(secrets.token_urlsafe(24), tool, payload, preview, effect,
                                 hashlib.sha256(preview.encode('utf-8')).hexdigest(), time.monotonic(), handler)
        with self._lock:
            now = time.monotonic()
            self._tickets = {key: value for key, value in self._tickets.items()
                             if now - value.created_at <= self.ttl_seconds}
            self._tickets[ticket.request_id] = ticket
        return ticket.request_id

    def get_for_review(self, request_id):
        with self._lock:
            ticket = self._tickets.get(request_id)
        if ticket is None:
            return None
        return {'request_id': ticket.request_id, 'tool': ticket.tool,
                'content': ticket.preview, 'effect': ticket.effect, 'sha256': ticket.digest}

    def resolve(self, request_id, approved):
        import json
        with self._lock:
            ticket = self._tickets.pop(request_id, None)
        if ticket is None:
            return dict(tool='', success=False, code='APPROVAL_INVALID', message='审批请求不存在或已使用')
        if time.monotonic() - ticket.created_at > self.ttl_seconds:
            return dict(tool=ticket.tool, success=False, code='APPROVAL_EXPIRED', message='审批已过期')
        if approved is not True:
            return dict(tool=ticket.tool, success=False, code='APPROVAL_DENIED', message='用户未批准此操作')
        return ticket.handler(json.loads(ticket.payload)).model_dump(mode='python')
