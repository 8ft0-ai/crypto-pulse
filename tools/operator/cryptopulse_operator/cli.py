"""Command-line entry point for operator-toolkit/v1."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .commands import auth, candidate, ci, doctor, environment, protection, publication, review_pack, snapshot
from .evidence import EXIT_CODE, Evidence
from .github_read import GitHubReader
from .process import ProcessRunner


def positive_int(value: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def environment_name(value: str) -> str:
    if not value or any(ord(ch) < 32 for ch in value):
        raise argparse.ArgumentTypeError("must be a non-empty printable environment name")
    return value


def _output_options(command: argparse.ArgumentParser) -> None:
    group = command.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", dest="as_json")
    group.add_argument("--evidence", action="store_true")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="cp", description="CryptoPulse read-only operator evidence toolkit")
    sub = result.add_subparsers(dest="command", required=True)

    doctor_command = sub.add_parser("doctor")
    _output_options(doctor_command)

    snapshot_command = sub.add_parser("snapshot")
    _output_options(snapshot_command)
    snapshot_command.add_argument("--repo", type=Path, default=Path.cwd())

    candidate_command = sub.add_parser("candidate")
    candidate_command.add_argument("pr", type=positive_int)
    _output_options(candidate_command)

    ci_command = sub.add_parser("ci")
    ci_command.add_argument("run_id", type=positive_int)
    _output_options(ci_command)

    review_pack_command = sub.add_parser("review-pack")
    review_pack_command.add_argument("pr", type=positive_int)
    _output_options(review_pack_command)

    auth_command = sub.add_parser("auth")
    _output_options(auth_command)

    protection_command = sub.add_parser("protection")
    _output_options(protection_command)

    environment_command = sub.add_parser("environment")
    environment_command.add_argument("name", type=environment_name)
    _output_options(environment_command)

    publication_command = sub.add_parser("publication")
    _output_options(publication_command)

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
    if args.command == "doctor":
        evidence = doctor.run(runner, github)
    elif args.command == "snapshot":
        evidence = snapshot.run(args.repo, runner, github)
    elif args.command == "candidate":
        evidence = candidate.run(args.pr, runner, github)
    elif args.command == "ci":
        evidence = ci.run(args.run_id, runner, github)
    elif args.command == "review-pack":
        evidence = review_pack.run(args.pr, runner, github)
    elif args.command == "auth":
        evidence = auth.run(runner, github)
    elif args.command == "protection":
        evidence = protection.run(runner, github)
    elif args.command == "environment":
        evidence = environment.run(args.name, runner, github)
    else:
        evidence = publication.run(runner, github)
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
