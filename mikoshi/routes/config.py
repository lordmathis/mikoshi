import logging
import time

from typing import Optional

from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger(__name__)

MODELS_CACHE_TTL = 300  # 5 minutes


@router.get("/config/models")
async def list_models(request: Request):
    """
    List all available models in OpenAI-compatible format.

    Returns both predefined agents from the registry and provider models.
    Format: {agent_name} for predefined agents, {provider}:{model_id} for provider models.
    """
    current_time = time.time()
    cache = getattr(request.app.state, "models_cache", None)
    cache_time = getattr(request.app.state, "models_cache_time", 0.0)

    if cache is not None and (current_time - cache_time) < MODELS_CACHE_TTL:
        return cache

    agent_registry = request.app.state.model_registry
    provider_registry = request.app.state.provider_registry

    models = []

    # Add predefined agents from registry
    agent_names = agent_registry.list_agent_names()
    for model_name in agent_names:
        models.append(
            {
                "id": model_name,
                "object": "model",
                "created": 1234567890,
                "owned_by": "mikoshi",
            }
        )

    # Add provider models
    for provider_name, provider in provider_registry.list_providers().items():
        try:
            model_ids = await provider.get_model_ids()
            if model_ids:
                for model_id in model_ids:
                    models.append(
                        {
                            "id": f"{provider_name}:{model_id}",
                            "object": "model",
                            "created": 1234567890,
                            "owned_by": provider_name,
                        }
                    )
        except Exception as e:
            logger.warning("Could not list models from provider %s: %s", provider_name, e)
            continue

    result = {"object": "list", "data": models}

    request.app.state.models_cache = result
    request.app.state.models_cache_time = current_time

    return result


@router.get("/config/agents")
async def list_agents(request: Request):
    """
    List all predefined agents from the registry with their configurations.
    """
    agent_registry = request.app.state.model_registry

    agents = []
    agent_names = agent_registry.list_agent_names()

    for model_name in agent_names:
        agent_cls = agent_registry.get_agent_class(model_name)
        if agent_cls:
            agents.append(
                {
                    "name": model_name,
                    "system_prompt": agent_cls.system_prompt,
                    "provider": agent_cls.provider_id,
                    "model_id": agent_cls.model_id,
                    "tool_servers": list(agent_cls.tool_servers or []),
                    "temperature": agent_cls.temperature,
                    "max_tokens": agent_cls.max_tokens,
                    "max_iterations": agent_cls.max_iterations,
                }
            )

    return {"agents": agents}


@router.get("/config/default-chat")
async def get_default_chat_config(request: Request, workspace_id: Optional[str] = None):
    """
    Get the default agent plugin (the one with default=True).
    When workspace_id is provided, prefers WorkspaceAgentPlugin defaults.
    """
    agent_registry = request.app.state.model_registry
    default_name = agent_registry.get_default_agent_name(workspace=bool(workspace_id))
    if default_name is None:
        return {"model": None}

    agent_cls = agent_registry.get_agent_class(default_name)

    return {
        "model": default_name,
        "system_prompt": agent_cls.system_prompt,
        "tool_servers": list(agent_cls.tool_servers),
        "model_params": {
            "max_iterations": agent_cls.max_iterations,
            "temperature": agent_cls.temperature,
            "max_tokens": agent_cls.max_tokens,
        },
    }


@router.get("/config/providers")
async def list_providers(request: Request):
    """
    List all configured providers with their available models.
    """
    provider_registry = request.app.state.provider_registry

    providers = []
    for provider_name, provider in provider_registry.list_providers().items():
        try:
            model_ids = await provider.get_model_ids()
            if model_ids is None:
                model_ids = []
        except Exception:
            model_ids = []

        providers.append(
            {
                "name": provider_name,
                "api_base": provider.config.api_base,
                "models": model_ids,
            }
        )

    return {"providers": providers}
