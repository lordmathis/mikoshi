from typing import List, Optional


class AgentPluginBase:
    """Shared class attributes for agent plugin classes."""

    default: bool = False
    name: str = ""
    provider_id: str = ""
    model_id: str = ""
    system_prompt: str = ""
    tool_servers: List[str] = []
    max_iterations: int = 5
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def post_init(self) -> None:
        pass
