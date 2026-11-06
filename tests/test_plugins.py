import importlib
import uuid

import pytest

from mikoshi.plugins import discover_plugins


@pytest.fixture
def plugin_env(tmp_path, monkeypatch):
    """Fresh plugin directory with a unique importable base class.

    The base module gets a per-test name so sys.modules caching can never
    leak one test's class into another's.
    """
    monkeypatch.syspath_prepend(str(tmp_path))
    mod_name = f"fake_base_{uuid.uuid4().hex[:8]}"
    (tmp_path / f"{mod_name}.py").write_text("class FakePluginBase:\n    name = ''\n")
    base = importlib.import_module(mod_name).FakePluginBase
    return tmp_path, mod_name, base


class TestDiscoverPlugins:
    def test_registers_subclass_keyed_by_name(self, plugin_env):
        tmp_path, mod_name, base = plugin_env
        (tmp_path / "good.py").write_text(
            f"from {mod_name} import FakePluginBase\n\n"
            "class Thing(FakePluginBase):\n"
            '    name = "my-thing"\n'
        )

        plugins = discover_plugins(
            str(tmp_path), base, exclude_bases=(base,)
        )

        assert "my-thing" in plugins
        assert plugins["my-thing"].__name__ == "Thing"

    def test_skips_class_missing_required_attrs(self, plugin_env):
        tmp_path, mod_name, base = plugin_env
        (tmp_path / "lazy.py").write_text(
            f"from {mod_name} import FakePluginBase\n\n"
            "class Lazy(FakePluginBase):\n"
            "    pass\n"
        )

        plugins = discover_plugins(
            str(tmp_path), base, exclude_bases=(base,), required_attrs=["name"]
        )

        assert "lazy" not in plugins
        assert not any(cls.__name__ == "Lazy" for cls in plugins.values())

    def test_exclude_bases_keeps_base_out_of_results(self, plugin_env):
        tmp_path, _, base = plugin_env

        plugins = discover_plugins(str(tmp_path), base, exclude_bases=(base,))

        assert plugins == {}

    def test_broken_module_does_not_stop_discovery(self, plugin_env):
        tmp_path, mod_name, base = plugin_env
        (tmp_path / "broken.py").write_text("raise RuntimeError('boom')\n")
        (tmp_path / "good.py").write_text(
            f"from {mod_name} import FakePluginBase\n\n"
            "class Thing(FakePluginBase):\n"
            '    name = "my-thing"\n'
        )

        plugins = discover_plugins(
            str(tmp_path), base, exclude_bases=(base,)
        )

        assert "my-thing" in plugins

    def test_missing_directory_returns_empty(self, tmp_path, plugin_env):
        _, _, base = plugin_env

        assert discover_plugins(str(tmp_path / "nope"), base) == {}
