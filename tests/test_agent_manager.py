from unittest.mock import MagicMock, patch

import pytest

from mikoshi.agents.manager import AgentManager, AgentRegistry
from mikoshi.config import TitleGenerationConfig


def _manager(**overrides):
    defaults = dict(
        db=MagicMock(),
        provider_registry=MagicMock(),
        agent_registry=MagicMock(),
        tool_manager=MagicMock(),
        data_dir="/tmp",
        workspace_config=MagicMock(),
    )
    defaults.update(overrides)
    return AgentManager(**defaults)


class TestResolveAgentParams:
    def test_empty_config(self):
        m = _manager()
        result = m._resolve_agent_params({})
        assert result == {
            "system_prompt": "",
            "tool_servers": [],
            "temperature": None,
            "max_tokens": None,
            "context_window": None,
            "max_iterations": 5,
        }

    def test_config_values_override_defaults(self):
        m = _manager()
        result = m._resolve_agent_params(
            {
                "system_prompt": "custom",
                "tool_servers": ["mcp"],
                "model_params": {"temperature": 0.7, "max_tokens": 100},
            }
        )
        assert result["system_prompt"] == "custom"
        assert result["tool_servers"] == ["mcp"]
        assert result["temperature"] == 0.7
        assert result["max_tokens"] == 100

    def test_defaults_used_when_config_empty(self):
        m = _manager()
        defaults = {
            "system_prompt": "default",
            "temperature": 0.5,
            "max_iterations": 10,
        }
        result = m._resolve_agent_params({}, defaults)
        assert result["system_prompt"] == "default"
        assert result["temperature"] == 0.5
        assert result["max_iterations"] == 10

    def test_config_overrides_defaults(self):
        m = _manager()
        defaults = {"system_prompt": "default", "max_iterations": 10}
        result = m._resolve_agent_params(
            {"system_prompt": "override", "model_params": {"max_iterations": 3}},
            defaults,
        )
        assert result["system_prompt"] == "override"
        assert result["max_iterations"] == 3


class TestResolveTitleParams:
    def test_no_title_config(self):
        m = _manager(title_generation=None)
        assert m._resolve_title_params() == {}

    def test_no_provider_set(self):
        m = _manager(title_generation=TitleGenerationConfig(model="gpt-4"))
        result = m._resolve_title_params()
        assert result == {"title_provider": None, "title_model_id": "gpt-4"}

    def test_provider_found(self):
        mock_provider = MagicMock()
        pr = MagicMock()
        pr.get_provider.return_value = mock_provider
        m = _manager(
            provider_registry=pr,
            title_generation=TitleGenerationConfig(provider="openai", model="gpt-4o"),
        )
        result = m._resolve_title_params()
        assert result["title_provider"] is mock_provider
        assert result["title_model_id"] == "gpt-4o"

    def test_provider_not_found_returns_empty(self):
        pr = MagicMock()
        pr.get_provider.return_value = None
        m = _manager(
            provider_registry=pr,
            title_generation=TitleGenerationConfig(provider="missing"),
        )
        assert m._resolve_title_params() == {}


class TestHydrate:
    def _setup_manager(self):
        m = _manager()
        m.db.get_chat.return_value = MagicMock(workspace_id=None)
        return m

    def test_inline_model_resolves_provider(self):
        m = self._setup_manager()
        mock_provider = MagicMock()
        m.provider_registry.get_provider.return_value = mock_provider
        with patch("mikoshi.agents.manager.ReActAgent") as mock_react:
            m._hydrate("c1", {"model": "openai:gpt-4"})
            kwargs = mock_react.call_args.kwargs
            assert kwargs["provider"] is mock_provider
            assert kwargs["model_id"] == "gpt-4"

    def test_inline_model_provider_not_found(self):
        m = self._setup_manager()
        m.provider_registry.get_provider.return_value = None
        with pytest.raises(ValueError, match="Provider.*not found"):
            m._hydrate("c1", {"model": "bad:model"})

    def test_plugin_agent_path(self):
        m = self._setup_manager()
        mock_cls = MagicMock()
        mock_cls.provider_id = "openai"
        mock_cls.model_id = "gpt-4"
        mock_cls.system_prompt = "agent prompt"
        mock_cls.tool_servers = []
        mock_cls.temperature = None
        mock_cls.max_tokens = None
        mock_cls.max_iterations = None
        m.agent_registry.get_agent_class.return_value = mock_cls
        m.provider_registry.get_provider.return_value = MagicMock()
        agent = m._hydrate("c1", {"model": "my-agent"})
        assert agent is mock_cls.return_value
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["system_prompt"] == "agent prompt"
        assert kwargs["model_id"] == "gpt-4"

    def test_agent_not_found(self):
        m = self._setup_manager()
        m.agent_registry.get_agent_class.return_value = None
        with pytest.raises(ValueError, match="Agent.*not found"):
            m._hydrate("c1", {"model": "missing-agent"})

    def test_no_model_no_default(self):
        m = self._setup_manager()
        m.agent_registry.get_default_agent_name.return_value = None
        with pytest.raises(ValueError, match="Model is required"):
            m._hydrate("c1", {})

    def test_uses_default_agent_when_no_model(self):
        m = self._setup_manager()
        m.agent_registry.get_default_agent_name.return_value = "default-agent"
        mock_cls = MagicMock()
        mock_cls.provider_id = "openai"
        mock_cls.model_id = "gpt-4"
        mock_cls.system_prompt = ""
        mock_cls.tool_servers = []
        mock_cls.temperature = None
        mock_cls.max_tokens = None
        mock_cls.max_iterations = None
        m.agent_registry.get_agent_class.return_value = mock_cls
        m.provider_registry.get_provider.return_value = MagicMock()
        agent = m._hydrate("c1", {})
        assert agent is mock_cls.return_value

    def test_workspace_inline_model_uses_workspace_agent(self):
        m = _manager()
        m.db.get_chat.return_value = MagicMock(workspace_id="ws-1")
        m.db.get_workspace.return_value = MagicMock(connector="github")
        m.provider_registry.get_provider.return_value = MagicMock()

        with patch("mikoshi.agents.manager.WorkspaceAgent") as mock_ws:
            m._hydrate("c1", {"model": "openai:gpt-4"})
            kwargs = mock_ws.call_args.kwargs
            assert kwargs["workspace_id"] == "ws-1"
            assert kwargs["connector_name"] == "github"


class TestCreate:
    def _setup_manager(self):
        m = _manager()
        m.db.get_chat.return_value = MagicMock(workspace_id=None)
        m.provider_registry.get_provider.return_value = MagicMock()
        return m

    def test_missing_model_raises_and_caches_nothing(self):
        m = self._setup_manager()
        # A default agent exists, so _hydrate would succeed — validation
        # must fire first and leave _agents untouched.
        m.agent_registry.get_default_agent_name.return_value = "default-agent"
        with pytest.raises(ValueError, match="Model is required"):
            m.create("c1", {"model": None})
        assert m._agents == {}

    def test_hydrate_failure_raises_and_caches_nothing(self):
        m = self._setup_manager()
        m.provider_registry.get_provider.return_value = None
        with pytest.raises(ValueError, match="Provider.*not found"):
            m.create("c1", {"model": "bad:model"})
        assert m._agents == {}

    def test_missing_chat_raises(self):
        m = _manager()
        m.db.get_chat.return_value = None
        with pytest.raises(ValueError, match="not found"):
            m.create("c1", {"model": "openai:gpt-4"})

    def test_duplicate_agent_raises(self):
        m = self._setup_manager()
        m._agents["c1"] = MagicMock()
        with pytest.raises(ValueError, match="already exists"):
            m.create("c1", {"model": "openai:gpt-4"})

    def test_success_caches_and_persists_config(self):
        m = self._setup_manager()
        agent = MagicMock()
        with patch.object(m, "_hydrate", return_value=agent):
            result = m.create(
                "c1",
                {
                    "model": "openai:gpt-4",
                    "system_prompt": "sys",
                    "tool_servers": ["mcp"],
                    "model_params": {"temperature": 0.5},
                },
            )
        assert result is agent
        assert m._agents["c1"] is agent
        m.db.save_chat_config.assert_called_once_with(
            chat_id="c1",
            model="openai:gpt-4",
            system_prompt="sys",
            tool_servers=["mcp"],
            model_params={"temperature": 0.5},
        )


class TestAgentRegistryDefault:
    def _make_registry(self, classes):
        r = object.__new__(AgentRegistry)
        r._agent_classes = classes
        return r

    def test_no_default(self):
        class NonDefault:
            default = False

        r = self._make_registry({"a": NonDefault})
        assert r.get_default_agent_name() is None

    def test_picks_default(self):
        class DefaultAgent:
            default = True

        r = self._make_registry({"my-agent": DefaultAgent})
        assert r.get_default_agent_name() == "my-agent"

    def test_prefers_workspace_match(self):
        from mikoshi.agents.workspace import WorkspaceAgentPlugin

        class WsDefault(WorkspaceAgentPlugin):
            default = True

        class PlainDefault:
            default = True

        r = self._make_registry({"plain": PlainDefault, "ws": WsDefault})
        assert r.get_default_agent_name(workspace=True) == "ws"
        assert r.get_default_agent_name(workspace=False) == "plain"
