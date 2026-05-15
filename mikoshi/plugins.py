import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

logger = logging.getLogger(__name__)


def discover_plugins(
    directory: str,
    base_class: type | tuple[type, ...],
    *,
    exclude_bases: Optional[tuple[type, ...]] = None,
    required_attrs: Optional[List[str]] = None,
) -> Dict[str, Type]:
    """Discover plugin classes from Python files in a directory.

    Args:
        directory: Path to scan for *.py files.
        base_class: Class or tuple of classes to filter by.
        exclude_bases: Classes to exclude from results (e.g. the base itself).
        required_attrs: Attribute names that must have truthy values.

    Returns:
        Dict mapping class name (or obj.name) to the class.
    """
    plugins: Dict[str, Type] = {}
    seen_classes: set = set()
    dir_path = Path(directory)

    if not dir_path.exists() or not dir_path.is_dir():
        logger.warning(f"Plugin directory '{directory}' does not exist or is not a directory")
        return plugins

    exclude = exclude_bases or ()

    for file_path in dir_path.glob("*.py"):
        if file_path.name.startswith("_"):
            continue

        try:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec is None or spec.loader is None:
                logger.warning(f"Could not load spec for module: {file_path}")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if not issubclass(obj, base_class) or obj in exclude:
                    continue
                if obj in seen_classes:
                    continue
                seen_classes.add(obj)

                if required_attrs:
                    missing = [a for a in required_attrs if not getattr(obj, a, "")]
                    if missing:
                        plugin_name = getattr(obj, "name", None) or name.lower()
                        logger.warning(
                            f"Plugin '{plugin_name}' missing required attributes: {', '.join(missing)}, skipping"
                        )
                        continue

                plugin_name = getattr(obj, "name", None) or name.lower()
                plugins[plugin_name] = obj
                logger.info(f"Registered plugin: {plugin_name} from {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to load module from {file_path}: {e}", exc_info=True)

    logger.info(f"Discovered {len(plugins)} plugin(s) from '{directory}'")
    return plugins
