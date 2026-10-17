#!/usr/bin/env python
"""Finite regression for the demo inspector's new-evidence output boundary.

Run with Python -B, --record <accepted six-file record>, and a never-used
--evidence-root under data/reviews. Only this test's copied nine files are
injected; the source record and its envelope are never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "scripts/run_runtime_demo.py"
SIX = ("expectations.json", "judgment_result.json", "manifest.json",
       "materials.json", "prior_history.json", "submission.json")
THREE = ("context.json", "receipt.json", "started.json")
CONFLICT_BYTES = b"own conflict sentinel; must not be overwritten\n"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    raw = path.read_bytes()
    return {"byte_size": len(raw), "file_sha256": hashlib.sha256(raw).hexdigest()}


def envelope(record):
    return ROOT / "data/runtime" / record.parent.parent.name / "normal.initial"


def input_paths(record):
    return [record / name for name in SIX] + [envelope(record) / name for name in THREE]


def identities(paths):
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}


def load_demo():
    spec = importlib.util.spec_from_file_location("demo_output_safety_control", DEMO)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def control(args):
    module = load_demo()
    target = Path(args.target)
    observed = {"control": args.control, "injected": False}
    if args.control == "conflict":
        original = module.os.open

        def create_conflict(path, flags, mode=0o777, **kwargs):
            if Path(path) == target:
                target.write_bytes(CONFLICT_BYTES)
                observed.update(injected=True, actual_flags=flags,
                                exclusive_flag=bool(flags & os.O_EXCL))
            return original(path, flags, mode, **kwargs)

        module.os.open = create_conflict
    else:
        original = module.write_inspect_output
        changed = envelope(Path(args.record)) / "context.json"

        def mutate_after_output(path, value):
            stream = original(path, value)
            changed.write_bytes(changed.read_bytes() + b"\n")
            observed.update(injected=True, changed=changed.relative_to(ROOT).as_posix(),
                            changed_identity=digest(changed))
            return stream

        module.write_inspect_output = mutate_after_output
    try:
        code = module.main(["--inspect-record", args.record, "--inspect-out", str(target)])
    except Exception as exc:
        observed.update(exception_type=type(exc).__name__, message=str(exc))
        print(json.dumps(observed, ensure_ascii=False))
        return 1
    observed["main_returned"] = code
    print(json.dumps(observed, ensure_ascii=False))
    return code


def run(args):
    source = Path(args.record).resolve()
    evidence = Path(args.evidence_root).absolute()
    if not evidence.is_relative_to(ROOT / "data/reviews") or evidence.exists():
        raise ValueError("evidence root must be a never-used path under data/reviews")
    evidence.mkdir(parents=True)
    scene_name = "task042_gpt_fix_output_" + evidence.name
    record = ROOT / "data/human_initial_judgment_records" / scene_name / "bound/rec_0001"
    record.mkdir(parents=True)
    own_envelope = envelope(record)
    own_envelope.mkdir(parents=True)
    source_before = identities(input_paths(source))
    copied = []
    for name in SIX:
        shutil.copyfile(source / name, record / name)
        copied.append(record / name)
    for name in THREE:
        shutil.copyfile(envelope(source) / name, own_envelope / name)
        copied.append(own_envelope / name)
    own_before = identities(copied)
    checks, calls = [], []

    def check(name, condition, **details):
        checks.append({"name": name, "pass": bool(condition), **details})

    def command(name, output=None, mode=None):
        if mode:
            argv = [sys.executable, "-B", str(Path(__file__).resolve()), "--control", mode,
                    "--record", str(record), "--target", str(output)]
        else:
            argv = [sys.executable, "-B", str(DEMO), "--inspect-record", str(record)]
            if output is not None:
                argv += ["--inspect-out", str(output)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        (evidence / (name + ".stdout.txt")).write_text(result.stdout, encoding="utf-8")
        (evidence / (name + ".stderr.txt")).write_text(result.stderr, encoding="utf-8")
        calls.append({"name": name, "argv": argv, "returncode": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr})
        return result

    result = command("stdout_only")
    summary = json.loads(result.stdout)
    check("stdout mode succeeds and is read only",
          result.returncode == 0 and summary["zero_write"] is True
          and identities(copied) == own_before)

    invalid = [
        ("context", own_envelope / "context.json"),
        ("receipt", own_envelope / "receipt.json"),
        ("record_file", record / "materials.json"),
        ("namespace_new", record.parent / "new.json"),
        ("other_runtime", own_envelope.parent / "new.json"),
        ("protected_code", DEMO),
        ("dotdot", str(evidence / "..") + "/bypass.json"),
        ("ads", str(evidence / "result.json") + ":stream"),
        ("reserved", evidence / "NUL.json"),
        ("trailing_dot", evidence / "ambiguous.json."),
        ("device_path", "\\\\?\\" + str(evidence / "device.json")),
        ("missing_parent", evidence / "not_created/result.json"),
    ]
    original_demo = digest(DEMO)
    for name, target in invalid:
        result = command("reject_" + name, target)
        check("reject " + name, result.returncode != 0 and identities(copied) == own_before
              and digest(DEMO) == original_demo, exit_code=result.returncode)
    sentinel = evidence / "existing.json"
    sentinel.write_bytes(CONFLICT_BYTES)
    result = command("reject_existing", sentinel)
    check("existing evidence file preserved", result.returncode != 0
          and sentinel.read_bytes() == CONFLICT_BYTES)

    allowed = evidence / "allowed.json"
    result = command("allowed_new", allowed)
    saved = json.loads(allowed.read_bytes())
    stdout = json.loads(result.stdout)
    check("new evidence output succeeds", result.returncode == 0
          and saved["zero_write"] is True and stdout["zero_write"] is True
          and saved["watch_snapshot_before"] == saved["watch_snapshot_after"]
          and identities(copied) == own_before)
    check("saved and returned fingerprints agree",
          saved["record_fingerprint"] == stdout["record_fingerprint"]
          and saved["manifest_file_sha256"] == stdout["manifest_file_sha256"])

    conflict = evidence / "raced_output.json"
    result = command("exclusive_conflict", conflict, "conflict")
    observed = json.loads(result.stdout)
    check("actual exclusive create conflict governs main failure", result.returncode == 1
          and observed.get("injected") is True and observed.get("exclusive_flag") is True
          and observed.get("exception_type") == "FileExistsError"
          and conflict.read_bytes() == CONFLICT_BYTES)

    context = own_envelope / "context.json"
    original_context = context.read_bytes()
    result = command("final_snapshot_control", evidence / "late_control.json", "late_change")
    observed = json.loads(result.stdout)
    bad = context.read_bytes()
    (evidence / "own_context_bad.bin").write_bytes(bad)
    check("post-output snapshot governs main failure", result.returncode == 1
          and observed.get("injected") is True and observed.get("exception_type") == "DemoFailure"
          and bad != original_context)
    rejected_summary = json.loads((evidence / "late_control.json").read_bytes())
    check("failed output records actual final snapshot", rejected_summary["zero_write"] is False
          and rejected_summary["watch_snapshot_before"] != rejected_summary["watch_snapshot_after"])
    context.write_bytes(original_context)
    check("own context exactly restored", identities(copied) == own_before)

    # Exercise a real reparse point where Windows permissions permit it; no cleanup.
    link = evidence / "directory_alias"
    try:
        os.symlink(evidence, link, target_is_directory=True)
    except OSError as exc:
        reparse = {"executed": False, "exception_type": type(exc).__name__, "reason": str(exc)}
    else:
        result = command("reject_reparse", link / "via_alias.json")
        reparse = {"executed": True, "returncode": result.returncode}
        check("real directory symlink rejected", result.returncode != 0
              and not (evidence / "via_alias.json").exists())
    source_after = identities(input_paths(source))
    check("source nine files unchanged", source_before == source_after)
    check("own nine files unchanged after exact restoration", own_before == identities(copied))
    result = {"status": "PASS" if all(item["pass"] for item in checks) else "FAIL",
              "checks": checks, "counts": {"total": len(checks),
              "passed": sum(item["pass"] for item in checks)}, "calls": calls,
              "source_before": source_before, "source_after": source_after,
              "own_before": own_before, "own_after": identities(copied),
              "reparse_control": reparse, "copied_files": [str(path) for path in copied],
              "scope_note": "Standalone store verification only; no runtime chain or algorithms built."}
    dump(evidence / "result.json", result)
    print(json.dumps({"status": result["status"], "checks": result["counts"],
                      "evidence": str(evidence)}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", required=True)
    parser.add_argument("--evidence-root")
    parser.add_argument("--control", choices=("conflict", "late_change"))
    parser.add_argument("--target")
    args = parser.parse_args()
    return control(args) if args.control else run(args)


if __name__ == "__main__":
    raise SystemExit(main())
