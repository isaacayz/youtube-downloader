from typing import Optional, List
from app.source_adapters.base import BaseSourceAdapter
from app.source_adapters.youtube import YouTubeSourceAdapter
from app.source_adapters.generic import GenericMediaAdapter


class SourceAdapterRegistry:
    def __init__(self):
        self.adapters: List[BaseSourceAdapter] = [
            YouTubeSourceAdapter(),
            GenericMediaAdapter(),
        ]

    def get_adapter(self, url: str) -> Optional[BaseSourceAdapter]:
        for adapter in self.adapters:
            if adapter.identify(url):
                return adapter
        return None

    def list_capabilities(self) -> List[str]:
        return [adapter.health()["adapter"] for adapter in self.adapters]


registry = SourceAdapterRegistry()
