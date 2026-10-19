import ctypes
import sys
from contextlib import contextmanager
from datetime import datetime
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

if sys.platform == "win32":
    ctypes.WinDLL(r"C:\Windows\System32\MSVCP140.dll")

from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtWidgets import QDialog, QWidget
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from database.db_manager import Base
from database.models.knowledge_base import Document, KnowledgeBase
from database.repository.knowledge_base_repository import KnowledgeBaseRepository
from rag.rag_manager import RAGManager
from ui.knowledge_base import dataset_page
from ui.knowledge_base.enter_knowledge_base import EnterKnowledgeBase


@pytest.mark.parametrize("actual_count, expected", [(2, True), (1, False), (0, False)])
def test_rag_verifies_actual_writes(actual_count, expected):
    rag = object.__new__(RAGManager.__wrapped__)
    rag.config = {"supported_file_types": [".pdf"]}
    chunks = [SimpleNamespace(metadata={}) for _ in range(2)]
    rag.document_processor = Mock()
    rag.document_processor.chunk_documents.return_value = chunks
    rag.vector_db = Mock()
    rag.vector_db._collection.get.return_value = {"ids": list(range(actual_count))}
    rag._rebuild_bm25_index = Mock()

    assert rag.add_document("manual.pdf", doc_id=123, knowledge_base=456) is expected
    rag.vector_db.add_documents.assert_called_once_with(chunks)
    rag.vector_db._collection.get.assert_called_once_with(
        where={"doc_id": {"$eq": "123"}}, include=[]
    )
    assert all(chunk.metadata == {"doc_id": "123", "knowledge_base": "456"}
               for chunk in chunks)
    assert rag._rebuild_bm25_index.call_count == int(expected)


def test_rag_rejects_empty_chunks(caplog):
    rag = object.__new__(RAGManager.__wrapped__)
    rag.config = {"supported_file_types": [".pdf"]}
    rag.document_processor = Mock()
    rag.document_processor.chunk_documents.return_value = []
    rag.vector_db = Mock()
    assert rag.add_document("empty.pdf", "doc") is False
    rag.vector_db.add_documents.assert_not_called()
    assert any(record.exc_info for record in caplog.records)


@pytest.fixture
def repository():
    # 独立内存数据库，避免访问用户的 SQLite 数据。
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session_scope():
        with factory() as session:
            with session.begin():
                yield session

    repo = object.__new__(KnowledgeBaseRepository.__wrapped__)
    repo.db_manager = SimpleNamespace(session_scope=session_scope)
    with session_scope() as session:
        session.add(KnowledgeBase(
            id="kb", name="test", embedding_model="test", collection_name="test",
            persist_directory="test", chunk_size=128, chunk_overlap=32,
            document_count=1, chunk_count=5
        ))
        session.add(Document(
            id="doc", kb_id="kb", filename="manual.pdf", file_path="manual.pdf",
            file_type="pdf", status="active", chunk_count=2
        ))
    yield repo
    engine.dispose()


def test_repository_updates_status_and_counts_without_double_counting(repository):
    for status, count, total in [
        ("indexing", 0, 3), ("active", 911, 914),
        ("active", 911, 914), ("failed", 0, 3)
    ]:
        assert repository.update_document_index("doc", status, count)
        doc = repository.get_document_by_id("doc")
        assert (doc.status, doc.chunk_count) == (status, count)
        assert repository.get_knowledge_base("kb").chunk_count == total
    assert repository.update_document_index("missing", "active", 1) is False
    with pytest.raises(ValueError):
        repository.update_document_index("doc", "invalid")


def test_repository_handles_commit_failure(repository, monkeypatch):
    original = repository.db_manager.session_scope

    @contextmanager
    def failing_transaction():
        with original() as session:
            yield session
            raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(repository.db_manager, "session_scope", failing_transaction)
    assert repository.update_document_index("doc", "active", 911) is False
    monkeypatch.setattr(repository.db_manager, "session_scope", original)
    assert repository.get_document_by_id("doc").chunk_count == 2
    assert repository.get_knowledge_base("kb").chunk_count == 5


@pytest.mark.parametrize("mode", ["success", "failure", "exception", "empty", "read_error"])
def test_worker_result_and_cleanup(qtbot, monkeypatch, mode):
    rag = Mock()
    rag.add_document.return_value = mode != "failure"
    rag.vector_db._collection.get.return_value = {"ids": [] if mode == "empty" else ["1", "2"]}
    if mode == "exception":
        rag.add_document.side_effect = RuntimeError("index error")
    if mode == "read_error":
        rag.vector_db._collection.get.side_effect = RuntimeError("read error")
    monkeypatch.setattr(dataset_page, "RAGManager", lambda: rag)
    worker = dataset_page.DocumentIndexWorker("manual.pdf", "kb", "doc")
    with qtbot.waitSignal(worker.result_ready, timeout=3000) as result:
        worker.start()
    assert worker.wait(3000)
    assert result.args[:3] == ["doc", mode == "success", 2 if mode == "success" else 0]
    assert rag.delete_document.call_count == int(mode != "success")
    worker.deleteLater()


def test_upload_queue_keeps_gui_responsive_and_updates_on_main_thread(qtbot, monkeypatch):
    entered, release = Event(), Event()
    indexing_threads, update_threads, created, messages = [], [], [], []
    rag = Mock()

    def index(*args, **kwargs):
        indexing_threads.append(QThread.currentThread())
        entered.set()
        if not release.wait(3):
            raise RuntimeError("test timed out waiting for GUI")
        return len(indexing_threads) == 1

    rag.add_document.side_effect = index
    rag.vector_db._collection.get.return_value = {"ids": ["chunk"]}
    monkeypatch.setattr(dataset_page, "RAGManager", lambda: rag)

    def add_record(data):
        created.append(data)
        return SimpleNamespace(id=str(len(created)))

    def update(*args):
        update_threads.append((QThread.currentThread(), args))
        return True

    repo = Mock()
    repo.add_document.side_effect = add_record
    repo.update_document_index.side_effect = update
    monkeypatch.setattr(dataset_page, "KnowledgeBaseRepository", lambda: repo)

    class UploadDialog(QDialog):
        def exec_(self):
            return QDialog.Accepted

        def get_selected_files(self):
            return ["one.pdf", "two.pdf"]

    monkeypatch.setattr(dataset_page, "UploadDialog", UploadDialog)
    monkeypatch.setattr(dataset_page.QMessageBox, "information", lambda *args: messages.append(args))
    parent = QWidget()
    parent.load_documents = Mock()
    qtbot.addWidget(parent)
    page = dataset_page.DatasetPage(SimpleNamespace(id="kb"), parent)
    page.add_document()
    try:
        qtbot.waitUntil(entered.is_set, timeout=3000)
        page.add_document()  # 重复上传不得产生新任务。
        assert len(created) == 2
        assert all(data["status"] == "indexing" and data["chunk_count"] == 0 for data in created)
        timer_fired = []
        QTimer.singleShot(0, lambda: timer_fired.append(True))
        qtbot.waitUntil(lambda: bool(timer_fired), timeout=1000)
    finally:
        release.set()
        qtbot.waitUntil(lambda: page._index_worker is None, timeout=5000)

    gui_thread = parent.thread()
    assert all(thread != gui_thread for thread in indexing_threads)
    assert all(thread == gui_thread for thread, _ in update_threads)
    assert [args for _, args in update_threads] == [("1", "active", 1), ("2", "failed", 0)]
    assert (page._upload_success, page._upload_failed) == (1, 1)
    assert not page._pending_uploads
    assert "成功 1 个，失败 1 个" in messages[-1][-1]


@pytest.mark.parametrize("status,count,text,color", [
    ("indexing", 0, "解析中", "#FF9500"),
    ("active", 911, "解析成功", "#34C759"),
    ("failed", 0, "解析失败", "#FF3B30"),
    ("active", 0, "等待解析", "#8E8E93")
])
def test_status_display(qtbot, monkeypatch, status, count, text, color):
    monkeypatch.setattr(dataset_page, "KnowledgeBaseRepository", Mock())
    page = dataset_page.DatasetPage()
    qtbot.addWidget(page)
    page.load_files([SimpleNamespace(
        id="doc", filename="manual.pdf", status=status, chunk_count=count,
        created_at=datetime(2026, 1, 1)
    )])
    label = page.tableWidget.cellWidget(0, 4)
    assert label.text() == text
    assert color in label.styleSheet()


def test_window_cannot_close_during_indexing(qtbot, monkeypatch):
    window = EnterKnowledgeBase.__new__(EnterKnowledgeBase)
    QWidget.__init__(window)
    qtbot.addWidget(window)
    worker = Mock()
    worker.isRunning.return_value = True
    window.dataset_page = SimpleNamespace(_index_worker=worker)
    monkeypatch.setattr(dataset_page.QMessageBox, "information", Mock())
    window.show()
    assert window.close() is False
    assert window.isVisible()
    worker.isRunning.return_value = False
    assert window.close() is True
