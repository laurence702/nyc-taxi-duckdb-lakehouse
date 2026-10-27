"""Minimal dbt-style runner for DuckDB.

Models are SQL files that reference each other with ``{{ ref('name') }}`` and
the raw layer with ``{{ source('raw', 'trips') }}``. The runner resolves those
references into a dependency graph, materialises models in order, and runs
singular data tests (a test passes when its query returns zero rows).

The SQL is deliberately dbt-compatible so the same files can be handed to
dbt-duckdb unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF_RE = re.compile(r"\{\{\s*ref\(\s*'([a-z0-9_]+)'\s*\)\s*\}\}")
SOURCE_RE = re.compile(r"\{\{\s*source\(\s*'([a-z0-9_]+)'\s*,\s*'([a-z0-9_]+)'\s*\)\s*\}\}")
CONFIG_RE = re.compile(r"^--\s*materialized:\s*(view|table)\s*$", re.MULTILINE)
SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./ -]+$")


class RunnerError(Exception):
    """Raised for invalid project structure or failed SQL."""


def discover_models(models_dir: Path) -> dict[str, Path]:
    """Map model name to file, rejecting duplicate names across folders."""
    models: dict[str, Path] = {}
    for path in sorted(models_dir.rglob("*.sql")):
        if path.stem in models:
            raise RunnerError(f"duplicate model name: {path.stem}")
        models[path.stem] = path
    return models


def dependencies(sql: str) -> set[str]:
    return set(REF_RE.findall(sql))


def order_models(models: dict[str, Path]) -> list[str]:
    """Return model names so every model follows the models it refs."""
    graph: dict[str, set[str]] = {}
    for name, path in models.items():
        deps = dependencies(path.read_text())
        missing = deps - models.keys()
        if missing:
            raise RunnerError(f"{name} refs unknown model(s): {sorted(missing)}")
        graph[name] = deps
    try:
        return list(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        raise RunnerError(f"dependency cycle: {exc.args[1]}") from exc


def render(sql: str) -> str:
    """Replace ref() and source() calls with relation names."""
    sql = REF_RE.sub(lambda m: m.group(1), sql)
    return SOURCE_RE.sub(lambda m: f"{m.group(1)}_{m.group(2)}", sql)


def materialization(sql: str) -> str:
    match = CONFIG_RE.search(sql)
    return match.group(1) if match else "view"


def run_duckdb(db: Path, sql: str, as_json: bool = False) -> str:
    """Execute SQL through the duckdb CLI, feeding it on stdin."""
    if shutil.which("duckdb") is None:
        raise RunnerError("duckdb CLI not found on PATH")
    cmd = ["duckdb", *(["-json"] if as_json else []), str(db)]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RunnerError(proc.stderr.strip() or "duckdb failed")
    return proc.stdout


def ingest(db: Path, csv_path: Path, parquet_path: Path) -> None:
    """Convert the raw CSV to ZSTD Parquet and expose it as ``raw_trips``."""
    for p in (csv_path, parquet_path):
        if not SAFE_PATH_RE.match(str(p)):
            raise RunnerError(f"unsupported characters in path: {p}")
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    run_duckdb(
        db,
        f"COPY (SELECT * FROM read_csv('{csv_path}', header=true, all_varchar=true)) "
        f"TO '{parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD);\n"
        f"CREATE OR REPLACE VIEW raw_trips AS "
        f"SELECT * FROM read_parquet('{parquet_path}', file_row_number=true);",
    )


def build(db: Path, models_dir: Path) -> list[str]:
    models = discover_models(models_dir)
    built = []
    for name in order_models(models):
        sql = models[name].read_text()
        kind = materialization(sql)
        body = render(sql).strip().rstrip(";")
        run_duckdb(db, f"CREATE OR REPLACE {kind.upper()} {name} AS\n{body};")
        built.append(name)
    return built


def run_tests(db: Path, tests_dir: Path) -> dict[str, int]:
    """Run each singular test; value is the number of failing rows."""
    results: dict[str, int] = {}
    for path in sorted(tests_dir.glob("*.sql")):
        body = render(path.read_text()).strip().rstrip(";")
        out = run_duckdb(db, body + ";", as_json=True).strip()
        results[path.stem] = len(json.loads(out)) if out else 0
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lakehouse", description=__doc__)
    parser.add_argument("command", choices=["ingest", "build", "test", "all"])
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "lakehouse.duckdb")
    parser.add_argument("--csv", type=Path, default=ROOT / "data" / "raw" / "yellow_tripdata_2016-01.csv")
    parser.add_argument("--parquet", type=Path, default=ROOT / "data" / "raw" / "trips_raw.parquet")
    parser.add_argument("--models", type=Path, default=ROOT / "models")
    parser.add_argument("--tests", type=Path, default=ROOT / "tests" / "sql")
    args = parser.parse_args(argv)
    args.db.parent.mkdir(parents=True, exist_ok=True)

    try:
        if args.command in ("ingest", "all"):
            ingest(args.db, args.csv, args.parquet)
            print("ingest ok")
        if args.command in ("build", "all"):
            for name in build(args.db, args.models):
                print(f"built {name}")
        if args.command in ("test", "all"):
            results = run_tests(args.db, args.tests)
            for name, failures in results.items():
                print(f"{'PASS' if failures == 0 else 'FAIL'} {name} ({failures} failing rows)")
            if any(results.values()):
                return 1
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
