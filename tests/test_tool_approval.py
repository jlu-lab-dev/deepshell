"""Day4 受控文件与审批回归测试：只操作 pytest 的隔离 tmp_path。"""
import os
import time
import pytest
from pydantic import ValidationError

from sys_agent.sandbox_file import SandboxedTextWriter, SandboxError
from sys_agent.tool_approval import ApprovalStore, CreateTextFileArgs


@pytest.mark.parametrize('name', [
    '../evil.txt', 'folder/evil.txt', r'folder\\evil.txt', 'C:evil.txt',
    'CON.txt', 'LPT1.txt', '.hidden.txt', 'bad.py', 'bad name.txt',
])
def test_reject_path_or_filename(name):
    with pytest.raises(ValidationError):
        CreateTextFileArgs.model_validate({'filename': name, 'content': 'hello'})


def test_reject_invalid_content():
    for bad in ('', 'x' * 2049, '中' * 683, 'ok\x00bad'):
        with pytest.raises(ValidationError):
            CreateTextFileArgs.model_validate({'filename': 'ok.txt', 'content': bad})


def test_prepare_without_writing_and_reject(tmp_path):
    store = ApprovalStore(tmp_path / 'workspace')
    req = store.prepare('a.txt', 'hello')
    assert not (tmp_path / 'workspace' / 'a.txt').exists()
    review = store.get_for_review(req['request_id'])
    assert review['content'] == 'hello'
    assert store.resolve(req['request_id'], False)['code'] == 'APPROVAL_DENIED'
    assert not (tmp_path / 'workspace' / 'a.txt').exists()
    assert store.resolve(req['request_id'], True)['code'] == 'APPROVAL_INVALID'


def test_once_only_and_bound_content(tmp_path):
    store = ApprovalStore(tmp_path / 'workspace')
    req = store.prepare('a.txt', 'original')
    assert store.resolve(req['request_id'], True)['success'] is True
    assert (tmp_path / 'workspace' / 'a.txt').read_text() == 'original'
    assert store.resolve(req['request_id'], True)['code'] == 'APPROVAL_INVALID'


def test_no_overwrite_after_approval(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    (root / 'a.txt').write_text('existing')
    store = ApprovalStore(root)
    req = store.prepare('a.txt', 'NEW')
    out = store.resolve(req['request_id'], True)
    assert out['code'] == 'WRITE_FAILED'
    assert (root / 'a.txt').read_text() == 'existing'


def test_expired_ticket(tmp_path):
    store = ApprovalStore(tmp_path / 'workspace', ttl_seconds=-1)
    req = store.prepare('a.txt', 'hello')
    assert store.resolve(req['request_id'], True)['code'] == 'APPROVAL_EXPIRED'


def test_symlink_target_not_overwritten(tmp_path):
    root = tmp_path / 'workspace'
    root.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('untouched')
    try:
        (root / 'a.txt').symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip('Windows 环境未开放符号链接权限')
    store = ApprovalStore(root)
    req = store.prepare('a.txt', 'malicious')
    assert store.resolve(req['request_id'], True)['code'] == 'WRITE_FAILED'
    assert outside.read_text() == 'untouched'


def test_filename_and_digest_provided_for_review(tmp_path):
    store = ApprovalStore(tmp_path / 'workspace')
    req = store.prepare('sample.txt', 'abc')
    assert req['content_bytes'] == 3
    assert 'content' not in req  # 返回给模型/Trace 的元数据不含原文
    review = store.get_for_review(req['request_id'])
    assert review['sha256'] == req['sha256']
    assert review['filename'] == 'sample.txt'


def test_cannot_write_to_symlink_workspace(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('Windows 环境未开放符号链接权限')
    store = ApprovalStore(alias)
    req = store.prepare('a.txt', 'payload')
    assert store.resolve(req['request_id'], True)['code'] == 'WRITE_FAILED'
    assert not (real / 'a.txt').exists()


@pytest.mark.parametrize('decision', ['true', 1, {}, None])
def test_only_boolean_true_can_approve(tmp_path, decision):
    store = ApprovalStore(tmp_path / 'workspace')
    ticket = store.prepare('a.txt', 'content')
    assert store.resolve(ticket['request_id'], decision)['code'] == 'APPROVAL_DENIED'
    assert not store.writer.root.exists()


def test_review_changes_do_not_change_ticket(tmp_path):
    store = ApprovalStore(tmp_path / 'workspace')
    ticket = store.prepare('a.txt', 'original')
    review = store.get_for_review(ticket['request_id'])
    review.update(filename='changed.txt', content='changed')
    assert store.resolve(ticket['request_id'], True)['success']
    assert (store.writer.root / 'a.txt').read_text(encoding='utf-8') == 'original'


def test_ticket_is_bound_to_reviewed_workspace(tmp_path):
    store = ApprovalStore(tmp_path / 'workspace')
    ticket = store.prepare('a.txt', 'original')
    store.writer.root = tmp_path / 'different'
    assert store.resolve(ticket['request_id'], True)['code'] == 'APPROVAL_INVALID'
    assert not store.writer.root.exists()


def test_concurrent_approval_consumes_ticket_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    store = ApprovalStore(tmp_path / 'workspace')
    ticket = store.prepare('a.txt', 'once')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.resolve(ticket['request_id'], True), range(2)))
    assert sorted(result['code'] for result in results) == ['APPROVAL_INVALID', 'SUCCESS']
