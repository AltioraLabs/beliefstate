"""Command-line interface for beliefstate.

Currently exposes a single ``validate-config`` subcommand that lets users
check a TrackerConfig file (in CI/CD, before deploying) without booting the
full tracking pipeline. The parser is structured with subparsers so further
commands can be added alongside it.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from beliefstate.config import TrackerConfig

# Optional third-party dependency required by each non-default store backend,
# as (import_name, pip_extra). sqlite relies on aiosqlite, a core dependency.
_STORE_DEPENDENCIES: Dict[str, Tuple[str, str]] = {
    "redis": ("redis", "redis"),
    "postgres": ("asyncpg", "postgres"),
    "duckdb": ("duckdb", "duckdb"),
}


def _load_config_file(path: Path) -> Dict[str, Any]:
    """Load a JSON or YAML config file into a dict."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "YAML config requires PyYAML. Install with `pip install pyyaml`."
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping/object, got {type(data).__name__}.")
    return data


def _build_store(config: TrackerConfig) -> Any:
    """Construct the configured store, mirroring BeliefTracker's selection."""
    stype = config.store_type.lower()
    if stype == "postgres":
        from beliefstate.store.postgres import PostgreSQLStore

        return PostgreSQLStore(**config.store_kwargs)
    if stype == "redis":
        from beliefstate.store.redis import RedisStore

        if RedisStore is None:
            raise RuntimeError("Redis SDK is not installed.")
        return RedisStore(**config.store_kwargs)
    if stype == "duckdb":
        from beliefstate.store.duckdb import DuckDBStore

        return DuckDBStore(**config.store_kwargs)
    from beliefstate.store.sqlite import SQLiteStore

    return SQLiteStore(db_path=config.store_kwargs.get("db_path", "beliefstate.db"))


def _check_store_dependency(store_type: str) -> Tuple[bool, str]:
    """Verify the optional dependency for the store backend is importable."""
    dep = _STORE_DEPENDENCIES.get(store_type.lower())
    if dep is None:
        return True, f"store_type '{store_type}' needs no extra dependency."
    module_name, extra = dep
    try:
        __import__(module_name)
        return True, f"dependency '{module_name}' is installed."
    except ImportError:
        return (
            False,
            f"missing dependency '{module_name}' for store_type '{store_type}'. "
            f"Install with `pip install beliefstate[{extra}]`.",
        )


async def _health_check_store(config: TrackerConfig) -> Tuple[bool, str]:
    """Best-effort connection check against the configured store."""
    try:
        store = _build_store(config)
    except Exception as exc:
        return False, f"could not construct store: {exc}"

    opener = getattr(store, "open", None)
    closer = getattr(store, "close", None)
    try:
        if opener is not None:
            await opener()
        ok = await store.health_check()
        return (
            (True, "store connection healthy.")
            if ok
            else (False, "store health check returned False.")
        )
    except Exception as exc:
        return False, f"store connection failed: {exc}"
    finally:
        if closer is not None:
            try:
                await closer()
            except Exception:  # pragma: no cover - defensive cleanup
                pass


def _validate_config(config_path: str, check_connection: bool) -> int:
    """Run the validate-config command. Returns a process exit code."""
    path = Path(config_path)
    print(f"Validating config: {path}\n")

    if not path.exists():
        print(f"[FAIL] config file not found: {path}")
        print("\nResult: INVALID")
        return 1

    try:
        data = _load_config_file(path)
    except Exception as exc:
        print(f"[FAIL] could not read config: {exc}")
        print("\nResult: INVALID")
        return 1

    from pydantic import ValidationError

    try:
        config = TrackerConfig(**data)
    except ValidationError as exc:
        print("[FAIL] config failed validation:")
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "(root)"
            print(f"         - {loc}: {err['msg']}")
        print("\nResult: INVALID")
        return 1

    print(f"[PASS] config parsed and validated (store_type={config.store_type})")

    ok = True
    dep_ok, dep_msg = _check_store_dependency(config.store_type)
    print(f"[{'PASS' if dep_ok else 'FAIL'}] {dep_msg}")
    ok = ok and dep_ok

    if check_connection:
        conn_ok, conn_msg = asyncio.run(_health_check_store(config))
        print(f"[{'PASS' if conn_ok else 'FAIL'}] {conn_msg}")
        ok = ok and conn_ok

    print(f"\nResult: {'VALID' if ok else 'INVALID'}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="beliefstate", description="BeliefState command-line interface."
    )
    subparsers = parser.add_subparsers(dest="command")

    validate = subparsers.add_parser(
        "validate-config", help="Validate a TrackerConfig JSON/YAML file."
    )
    validate.add_argument(
        "--config", "-c", required=True, help="Path to a JSON or YAML config file."
    )
    validate.add_argument(
        "--check-connection",
        action="store_true",
        help="Also attempt a store connection health check (may require network).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-config":
        return _validate_config(args.config, args.check_connection)

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
