from typing import Dict

from mikoshi.config import ProviderConfig
from mikoshi.providers.provider import Provider


class ProviderRegistry:
    def __init__(self, providers: Dict[str, ProviderConfig]) -> None:
        self._providers: Dict[str, Provider] = {}
        for name, cfg in providers.items():
            self._providers[name] = Provider(cfg, name)

    def get_provider(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def list_providers(self) -> Dict[str, Provider]:
        """List all registered providers."""
        return self._providers.copy()
