"""Discover strategy metadata from files under the repo ``strategies/`` package."""
from __future__ import annotations

import ast
import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT

STRATEGIES_DIR = REPO_ROOT / "strategies"


@dataclass(frozen=True)
class DiscoveredStrategy:
    slug: str
    name: str
    description: str | None
    module: str
    class_name: str
    config_class: str
    default_config: dict[str, Any]
    requires_market_data: bool


def _normalize_filename(filename: str) -> str:
    name = filename.strip().replace("\\", "/").split("/")[-1]
    if name.endswith(".py"):
        name = name[:-3]
    if not name or name.startswith("_") or not name.isidentifier():
        raise ValueError(
            f"Invalid strategy filename '{filename}'. "
            "Pass a module name like 'running_ping' or 'running_ping.py'.",
        )
    return name


def discover_strategy_from_file(filename: str) -> DiscoveredStrategy:
    """
    Load ``strategies/<name>.py`` and extract Strategy + StrategyConfig classes.

    Does not require Nautilus at import time for the class *names* (uses AST
    first); falls back to live import when Nautilus is available for defaults.
    """
    slug = _normalize_filename(filename)
    path = STRATEGIES_DIR / f"{slug}.py"
    if not path.is_file():
        raise FileNotFoundError(
            f"Strategy file not found: strategies/{slug}.py "
            f"(expected under {STRATEGIES_DIR})",
        )

    module_name = f"strategies.{slug}"
    source = path.read_text(encoding="utf-8")
    class_name, config_class = _find_classes_via_ast(source, slug)
    description = _module_docstring(source)

    default_config: dict[str, Any] = _defaults_from_ast(source, config_class)
    requires_market_data = _ast_requires_market_data(source, config_class)

    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        mod = importlib.import_module(module_name)
        strategy_cls = getattr(mod, class_name)
        config_cls = getattr(mod, config_class)
        defaults, needs_md = _defaults_from_config(config_cls)
        if defaults:
            default_config = defaults
        requires_market_data = requires_market_data or needs_md
        class_name = strategy_cls.__name__
        config_class = config_cls.__name__
        if strategy_cls.__doc__ and not description:
            description = inspect.cleandoc(strategy_cls.__doc__).split("\n\n")[0]
    except Exception:
        pass

    return DiscoveredStrategy(
        slug=slug,
        name=class_name,
        description=description,
        module=module_name,
        class_name=class_name,
        config_class=config_class,
        default_config=default_config,
        requires_market_data=requires_market_data,
    )


def _module_docstring(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    doc = ast.get_docstring(tree)
    if not doc:
        return None
    return doc.strip().split("\n\n")[0].strip()


def _find_classes_via_ast(source: str, slug: str) -> tuple[str, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Cannot parse strategies/{slug}.py: {exc}") from exc

    strategy_classes: list[str] = []
    config_classes: list[str] = []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {_base_name(b) for b in node.bases}
        if "Strategy" in base_names:
            strategy_classes.append(node.name)
        if "StrategyConfig" in base_names:
            config_classes.append(node.name)

    if not strategy_classes:
        raise ValueError(
            f"No Strategy subclass found in strategies/{slug}.py",
        )
    if not config_classes:
        # Convention: ClassName + Config
        config_classes = [f"{strategy_classes[0]}Config"]

    strategy_name = strategy_classes[0]
    # Prefer matching Config for the strategy class
    preferred = f"{strategy_name}Config"
    config_name = preferred if preferred in config_classes else config_classes[0]
    return strategy_name, config_name


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return ""


def _ast_requires_market_data(source: str, config_class: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == config_class:
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if item.target.id in {"instrument_id", "bar_type"}:
                        return True
    return False


def _defaults_from_config(config_cls: type) -> tuple[dict[str, Any], bool]:
    """Build a JSON-serializable default_config from StrategyConfig fields."""
    defaults: dict[str, Any] = {}
    annotations = getattr(config_cls, "__annotations__", {}) or {}
    requires_market_data = any(
        name in {"instrument_id", "bar_type"} for name in annotations
    )

    fields = getattr(config_cls, "model_fields", None)
    if fields:
        for name, field in fields.items():
            if name in {"instrument_id", "bar_type"}:
                requires_market_data = True
                continue
            if field.is_required():
                continue
            value = field.default
            if value is None and field.default_factory is not None:
                try:
                    value = field.default_factory()
                except Exception:
                    continue
            serialized = _jsonable(value)
            if serialized is not None:
                defaults[name] = serialized
        return defaults, requires_market_data

    # msgspec / plain annotated classes — only keep JSON-safe literal defaults
    for name in annotations:
        if name in {"instrument_id", "bar_type"}:
            continue
        if not hasattr(config_cls, name):
            continue
        value = getattr(config_cls, name)
        # Skip msgspec / descriptor members (not real defaults)
        if type(value).__name__ in {"Member", "FieldInfo"} or "member" in repr(type(value)).lower():
            continue
        if inspect.isdatadescriptor(value) or inspect.ismemberdescriptor(value):
            continue
        serialized = _jsonable(value)
        if serialized is not None and not str(serialized).startswith("<member"):
            defaults[name] = serialized

    return defaults, requires_market_data


def _defaults_from_ast(source: str, config_class: str) -> dict[str, Any]:
    """Pull simple literal defaults from the config class AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    defaults: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != config_class:
            continue
        for item in node.body:
            if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                continue
            name = item.target.id
            if name in {"instrument_id", "bar_type"} or item.value is None:
                continue
            try:
                defaults[name] = ast.literal_eval(item.value)
            except Exception:
                # Decimal("0.001") etc.
                if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name):
                    if item.value.func.id == "Decimal" and item.value.args:
                        try:
                            defaults[name] = str(ast.literal_eval(item.value.args[0]))
                        except Exception:
                            pass
    return defaults


def _jsonable(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        out = [_jsonable(v) for v in value]
        if any(v is None and orig is not None for v, orig in zip(out, value)):
            return None
        return out
    # Decimal, enums, etc.
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            return str(value)
    except Exception:
        pass
    try:
        return str(value)
    except Exception:
        return None
