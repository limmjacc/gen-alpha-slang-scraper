from __future__ import annotations

import argparse
import json
from pathlib import Path

from gen_alpha_slang_scraper.collectors import COLLECTOR_TYPES
from gen_alpha_slang_scraper.config import DEFAULT_CONFIG_PATH, load_config
from gen_alpha_slang_scraper.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track emerging slang from public social sources.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Collect, score, and render a report.")
    run_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to JSON config override.")

    doctor_parser = subparsers.add_parser("doctor", help="Show which collectors are available and enabled.")
    doctor_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to JSON config override.")

    subparsers.add_parser("list-sources", help="List built-in collectors.")
    return parser


def command_run(config_path: str) -> int:
    config = load_config(config_path)
    result = run_pipeline(config, config_path=config_path)
    print(json.dumps(result, indent=2))
    return 0


def command_doctor(config_path: str) -> int:
    config = load_config(config_path)
    enabled = config.get("collectors", {})
    for name in sorted(COLLECTOR_TYPES):
        collector_config = enabled.get(name, {})
        status = "enabled" if collector_config.get("enabled") else "disabled"
        print(f"{name:22} {status}")
    print(f"\nConfig: {Path(config_path).resolve()}")
    return 0


def command_list_sources() -> int:
    for name in sorted(COLLECTOR_TYPES):
        print(name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return command_run(args.config)
    if args.command == "doctor":
        return command_doctor(args.config)
    if args.command == "list-sources":
        return command_list_sources()
    parser.print_help()
    return 1
