import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        dist = root / "webui" / "dist"
        if not dist.exists():
            if shutil.which("npm") is None:
                raise RuntimeError(
                    "webui/dist is missing and npm was not found on PATH. "
                    "Install Node.js (and ensure npm is on PATH), or build the "
                    "frontend yourself first: cd webui && npm ci && npm run build"
                )
            for cmd in (["npm", "ci"], ["npm", "run", "build"]):
                subprocess.run(cmd, cwd=root / "webui", check=True)
        build_data["force_include"]["webui/dist"] = "mikoshi/static"
