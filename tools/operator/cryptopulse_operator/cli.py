"""Command-line entry point for operator-toolkit/v1 Slice A."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .commands import doctor, snapshot
from .evidence import EXIT_CODE, Evidence
from .github_read import GitHubReader
from .process import ProcessRunner


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="cp", description="CryptoPulse read-only operator evidence toolkit")
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("doctor", "snapshot"):
        command = sub.add_parser(name)
        group = command.add_mutually_exclusive_group()
        group.add_argument("--json", action="store_true", dest="as_json")
        group.add_argument("--evidence", action="store_true")
        if name == "snapshot":
            command.add_argument("--repo", type=Path, default=Path.cwd())
    return result


def render_human(evidence: Evidence) -> str:
    payload = evidence.payload()
    lines = [f"{payload['command']}: {payload['status']}"]
    for item in payload["assertions"]:
        lines.append(f"- {'PASS' if item['holds'] else 'FAIL'} {item['name']}")
    for item in payload["findings"]:
        lines.append(f"- {item['code']}")
    lines.append(f"evidence_sha256: {payload['evidence_sha256']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    runner = ProcessRunner()
    github = GitHubReader(runner)
    evidence = doctor.run(runner, github) if args.command == "doctor" else snapshot.run(args.repo, runner, github)
    if args.evidence:
        sys.stdout.write(evidence.envelope())
    elif args.as_json:
        sys.stdout.write(evidence.json_text() + "\n")
    else:
        sys.stdout.write(render_human(evidence))
    return EXIT_CODE[evidence.status]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(4)
    except Exception:
        sys.stderr.write("cp: unexpected internal error\n")
        raise SystemExit(5)
