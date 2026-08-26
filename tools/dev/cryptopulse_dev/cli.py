from __future__ import annotations

import argparse
import sys

from .commands import bootstrap, check, doctor
from .environment import PrerequisiteError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cp-dev",
        description="CryptoPulse working-tree developer utilities",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap", help="create or repair .venv")
    bootstrap_parser.add_argument(
        "--recreate",
        action="store_true",
        help="replace only the validated repository-local .venv",
    )
    subparsers.add_parser("doctor", help="diagnose local developer prerequisites")
    subparsers.add_parser("check", help="run the local pre-PR validation mirror")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3

    try:
        if args.command == "bootstrap":
            return bootstrap.run(recreate=args.recreate)
        if args.command == "doctor":
            return doctor.run()
        if args.command == "check":
            return check.run()
        parser.error(f"unknown command: {args.command}")
    except bootstrap.TaskFailure as exc:
        print(f"FAILED {exc}", file=sys.stderr)
        return 2
    except PrerequisiteError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("ERROR interrupted", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"ERROR internal: {exc}", file=sys.stderr)
        return 4
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
