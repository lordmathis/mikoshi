"""ResearchAgent file-state ops: exception visibility and deletion."""

import logging
from unittest.mock import MagicMock

from mikoshi.agents.research.agent import ResearchAgent
from mikoshi.workspace import WorkspaceFileNotFoundError


def _make_agent(service):
    agent = ResearchAgent.__new__(ResearchAgent)
    agent.chat_id = "chat-1"
    agent.workspace_id = "ws-1"
    agent._workspace_service = service
    agent._active_queue = None
    agent.db = MagicMock()
    return agent


class _FlakyService:
    def __init__(self, exc):
        self._exc = exc

    def read_file(self, workspace_id, path):
        raise self._exc

    def list_files_flat(self, workspace_id):
        raise self._exc

    def delete_file(self, workspace_id, path):
        raise self._exc


class TestReadFile:
    def test_missing_file_returns_empty_silently(self, caplog):
        agent = _make_agent(
            _FlakyService(WorkspaceFileNotFoundError("File not found: RESEARCH_PLAN.md"))
        )
        with caplog.at_level(logging.WARNING):
            assert agent.read_file("RESEARCH_PLAN.md") == ""
        assert caplog.records == []

    def test_io_error_returns_empty_but_logs(self, caplog):
        agent = _make_agent(_FlakyService(PermissionError("disk says no")))
        with caplog.at_level(logging.WARNING):
            assert agent.read_file("RESEARCH_PLAN.md") == ""
        assert any("read_file" in r.getMessage() for r in caplog.records)


class TestFileExists:
    def test_io_error_returns_false_but_logs(self, caplog):
        agent = _make_agent(_FlakyService(OSError("io hiccup")))
        with caplog.at_level(logging.WARNING):
            assert agent.file_exists("REPORT.md") is False
        assert any("file_exists" in r.getMessage() for r in caplog.records)


class TestListFiles:
    def test_io_error_returns_empty_but_logs(self, caplog):
        agent = _make_agent(_FlakyService(OSError("io hiccup")))
        with caplog.at_level(logging.WARNING):
            assert agent.list_files() == []
        assert any("list_files" in r.getMessage() for r in caplog.records)


class _RecordingService:
    def __init__(self, files):
        self._files = files
        self.deleted = []

    def delete_file(self, workspace_id, path):
        self.deleted.append(path)


class TestDeleteFile:
    def test_delegates_to_service(self):
        service = _RecordingService(["synthesis/batch_01.md"])
        agent = _make_agent(service)

        agent.delete_file("synthesis/batch_01.md")

        assert service.deleted == ["synthesis/batch_01.md"]

    def test_missing_file_is_silent(self):
        service = _FlakyService(WorkspaceFileNotFoundError("File not found: x"))
        agent = _make_agent(service)

        agent.delete_file("synthesis/batch_01.md")  # must not raise

    def test_noop_without_workspace(self):
        agent = _make_agent(_RecordingService([]))
        agent.workspace_id = None
        agent.delete_file("anything.md")
