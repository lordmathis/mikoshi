import pytest

from mikoshi.config import (
    AppConfig,
    ConnectorsConfig,
    ConnectorType,
    LoggingConfig,
    MCPConfig,
    MCPType,
    PluginConfig,
    ProviderConfig,
    ProviderType,
    ServerConfig,
    load_config,
)


class TestAppConfigDefaults:
    def test_empty_config_loads_with_defaults(self, tmp_yaml):
        path = tmp_yaml("{}")
        cfg = load_config(path)
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.port == 8000
        assert cfg.history_db_path == "mikoshi.db"
        assert cfg.mcp_timeout == 60
        assert cfg.file_retention_hours == 24
        assert cfg.workspace.git_user_name == "Mikoshi Agent"

    def test_server_config_override(self, tmp_yaml):
        path = tmp_yaml("server:\n  host: 127.0.0.1\n  port: 3000")
        cfg = load_config(path)
        assert cfg.server.host == "127.0.0.1"
        assert cfg.server.port == 3000


class TestProviderConfig:
    def test_default_type_is_openai(self):
        cfg = ProviderConfig()
        assert cfg.type == ProviderType.OPENAI

    def test_explicit_anthropic(self, tmp_yaml):
        path = tmp_yaml(
            "providers:\n"
            "  claude:\n"
            "    type: anthropic\n"
            "    api_key: sk-test\n"
        )
        cfg = load_config(path)
        assert cfg.providers["claude"].type == ProviderType.ANTHROPIC
        assert cfg.providers["claude"].api_key == "sk-test"

    def test_static_model_ids(self, tmp_yaml):
        path = tmp_yaml(
            "providers:\n"
            "  local:\n"
            "    model_ids:\n"
            "      - gpt-4\n"
            "      - gpt-3.5-turbo\n"
        )
        cfg = load_config(path)
        assert cfg.providers["local"].model_ids == ["gpt-4", "gpt-3.5-turbo"]


class TestMCPConfig:
    def test_stdio_mcp(self, tmp_yaml):
        path = tmp_yaml(
            "mcps:\n"
            "  fs:\n"
            "    command: npx\n"
            "    args:\n"
            "      - -y\n"
            "      - '@mcp/filesystem'\n"
            "    type: stdio\n"
        )
        cfg = load_config(path)
        assert cfg.mcps["fs"].command == "npx"
        assert cfg.mcps["fs"].type == MCPType.STDIO
        assert cfg.mcps["fs"].args == ["-y", "@mcp/filesystem"]


class TestConnectorsConfig:
    def test_github_connector(self, tmp_yaml):
        path = tmp_yaml(
            "connectors:\n"
            "  gh:\n"
            "    type: github\n"
            "    token: ghp_xxx\n"
        )
        cfg = load_config(path)
        assert cfg.connectors["gh"].type == ConnectorType.GITHUB
        assert cfg.connectors["gh"].token == "ghp_xxx"

    def test_forgejo_with_base_url(self, tmp_yaml):
        path = tmp_yaml(
            "connectors:\n"
            "  forge:\n"
            "    type: forgejo\n"
            "    token: tok\n"
            "    base_url: https://git.example.com\n"
        )
        cfg = load_config(path)
        assert cfg.connectors["forge"].base_url == "https://git.example.com"


class TestEnvVarExpansion:
    def test_env_var_in_provider_key(self, tmp_yaml, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "sk-secret-123")
        path = tmp_yaml(
            "providers:\n"
            "  openai:\n"
            "    api_key: ${MY_API_KEY}\n"
        )
        cfg = load_config(path)
        assert cfg.providers["openai"].api_key == "sk-secret-123"

    def test_undefined_env_var_stays_literal(self, tmp_yaml):
        path = tmp_yaml("history_db_path: ${UNDEFINED_VAR_12345}")
        cfg = load_config(path)
        assert cfg.history_db_path == "${UNDEFINED_VAR_12345}"

    def test_env_var_in_nested_value(self, tmp_yaml, monkeypatch):
        monkeypatch.setenv("MY_HOST", "0.0.0.0")
        path = tmp_yaml("server:\n  host: ${MY_HOST}")
        cfg = load_config(path)
        assert cfg.server.host == "0.0.0.0"
