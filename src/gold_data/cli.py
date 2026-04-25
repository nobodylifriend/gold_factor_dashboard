from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

from .catalog import refresh_indicator_directory
from .pipeline import build_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch and update gold-related FRED indicators.")
    parser.add_argument("command", choices=["init", "update", "catalog"])
    parser.add_argument("--base-dir", default=".", help="Project root directory.")
    parser.add_argument("--config", default=None, help="Path to indicators.yml.")
    parser.add_argument("--env-file", default=None, help="Path to .env file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    base_dir = Path(args.base_dir).resolve()
    config_path = Path(args.config).resolve() if args.config else None
    env_path = Path(args.env_file).resolve() if args.env_file else None

    if args.command == "catalog":
        try:
            refresh_indicator_directory(base_dir=base_dir, config_path=config_path)
        except Exception as exc:
            logging.error("%s", exc)
            return 1
        logging.info("Refreshed indicator directory.")
        return 0

    try:
        pipeline = build_pipeline(base_dir=base_dir, config_path=config_path, env_path=env_path)
        result = pipeline.run(args.command)
    except Exception as exc:
        logging.error("%s", exc)
        return 1

    if result.success:
        logging.info("Completed %s successfully.", args.command)
        return 0

    logging.error("Completed %s with %s error(s).", args.command, len(result.errors))
    for error in result.errors:
        logging.error(" - %s", error)
    return 1


if __name__ == "__main__":
    sys.exit(main())
