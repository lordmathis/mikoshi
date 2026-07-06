import asyncio
import logging
import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mikoshi.agents import AgentManager, AgentRegistry
from mikoshi.config import AppConfig
from mikoshi.connectors.registry import ConnectorRegistry
from mikoshi.db import Database
from mikoshi.middleware import InFlightRequests
from mikoshi.providers.registry import ProviderRegistry
from mikoshi.skills import SkillRegistry
from mikoshi.tools.manager import ToolManager
from mikoshi.workspace import WorkspaceService

logger = logging.getLogger(__name__)


async def _orphan_file_cleanup_task(app: FastAPI):
    """Background task to clean up orphan files"""
    logger.info("Starting orphan file cleanup task")
    try:
        while True:
            try:
                db: Database = app.state.database
                app_config: AppConfig = app.state.app_config

                retention_hours = app_config.file_retention_hours
                deleted_ids = db.delete_orphan_files(retention_hours)

                for file_id in deleted_ids:
                    upload_dir = os.path.join("uploads", file_id)
                    if os.path.exists(upload_dir):
                        shutil.rmtree(upload_dir, ignore_errors=True)

                if deleted_ids:
                    logger.info(f"Cleaned up {len(deleted_ids)} orphan files")
            except Exception as e:
                logger.error(f"Orphan cleanup error: {e}")

            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Orphan cleanup task cancelled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup: Initialize tool manager and other resources
    logger.info("Initializing application...")
    app_config: AppConfig = app.state.app_config

    # Initialize database
    logger.info("Initializing database...")
    database = Database(app_config.history_db_path)
    app.state.database = database

    # Initialize provider registry
    logger.info("Initializing provider registry...")
    provider_registry = ProviderRegistry(app_config.providers)
    app.state.provider_registry = provider_registry

    # Initialize and start tool manager
    try:
        tool_manager = ToolManager(
            app_config=app_config,
            provider_registry=provider_registry,
            db=database,
        )
        await tool_manager.start()
        app.state.tool_manager = tool_manager
    except Exception as e:
        logger.error(f"Failed to start tool manager: {e}", exc_info=True)
        # Clean up already initialized resources
        database.close()
        raise

    # Initialize agent registry
    logger.info("Initializing agent registry...")
    model_registry = AgentRegistry(
        provider_registry, tool_manager, app_config.plugins.agents_dir
    )
    app.state.model_registry = model_registry

    # Initialize skill registry
    logger.info("Initializing skill registry...")
    skill_registry = SkillRegistry(app_config.plugins.skills_dir)
    app.state.skill_registry = skill_registry

    logger.info("Initializing connectors...")
    connector_registry = await ConnectorRegistry.create(app_config.connectors)
    app.state.connector_registry = connector_registry

    # Initialize workspace service
    logger.info("Initializing workspace service...")
    workspace_service = WorkspaceService(
        data_dir=app_config.data_dir,
        connectors_config=app_config.connectors,
    )
    app.state.workspace_service = workspace_service

    # Initialize agent manager
    logger.info("Initializing agent manager...")
    agent_manager = AgentManager(
        db=database,
        provider_registry=provider_registry,
        agent_registry=model_registry,
        tool_manager=tool_manager,
        data_dir=app_config.data_dir,
        workspace_config=app_config.workspace,
        skill_registry=skill_registry,
        title_generation=app_config.title_generation,
        workspace_service=workspace_service,
    )
    app.state.agent_manager = agent_manager

    # Initialize model cache
    app.state.models_cache = None
    app.state.models_cache_time = 0.0

    logger.info("Server started successfully")

    # Start orphan file cleanup task
    cleanup_task = asyncio.create_task(_orphan_file_cleanup_task(app))

    yield

    # Drain in-flight requests before shutting down
    in_flight: InFlightRequests = app.state.in_flight
    await in_flight.drain()

    # Cancel background tasks
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Shutdown: Clean up resources
    logger.info("Shutting down server...")

    try:
        await tool_manager.stop()
    except Exception as e:
        logger.error(f"Error during tool manager shutdown: {e}", exc_info=True)

    try:
        database.close()
    except Exception as e:
        logger.error(f"Error during database shutdown: {e}", exc_info=True)

    logger.info("Server shutdown complete")
