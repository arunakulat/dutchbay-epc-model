import subprocess
import sys
from loguru import logger
from rich.console import Console
from rich.panel import Panel

IGNORABLE = [
    'mypy_extensions',
    'note: A user-defined top-level module with name "mypy_extensions"',
]

console = Console()

def skip_warnings(output):
    lines = output.split("\n")
    return "\n".join(
        line for line in lines
        if not any(msg in line for msg in IGNORABLE)
    )

def run_cmd(cmd, desc, use_pipenv=False):
    display_cmd = f"pipenv run {cmd}" if use_pipenv else cmd
    try:
        logger.info(f">> {desc}")
        proc = subprocess.run(
            display_cmd, shell=True, capture_output=True, text=True
        )
        filtered = skip_warnings(proc.stdout + proc.stderr)
        if proc.returncode == 0:
            console.print(Panel.fit(f"✓ Passed: {desc}", style="green"))
        else:
            console.print(Panel(filtered, title=f"Failure: {desc}", style="bold red"))
            sys.exit(proc.returncode)
    except Exception as e:
        logger.exception(f"Exception running {desc}")
        console.print(Panel(str(e), title=f"Exception: {desc}", style="bold red"))
        sys.exit(1)

def running_in_pipenv():
    from pathlib import Path
    return Path('Pipfile').exists()

def get_staged_py_files():
    proc = subprocess.run(
        "git diff --cached --name-only --diff-filter=ACM | grep '.py$'",
        shell=True, capture_output=True, text=True)
    files = [f.strip() for f in proc.stdout.splitlines() if f.strip()]
    return files

def main():
    use_pipenv = running_in_pipenv()
    py_files = get_staged_py_files()
    if not py_files:
        console.print("[yellow]No staged/modified Python files found. Skipping checks.[/yellow]")
        sys.exit(0)

    tools = [
        ("mypy " + " ".join(py_files), "mypy (static typing)"),
        ("flake8 " + " ".join(py_files), "flake8 (lint/PEP8)"),
        ("pylint " + " ".join(py_files) + " --exit-zero", "pylint (code quality/linting)"),
        ("black --check --diff " + " ".join(py_files), "black (code format)"),
        ("isort --check-only " + " ".join(py_files), "isort (import order)"),
        ("bandit -r . -c", "bandit (security scan)"),
    ]
    for cmd, desc in tools:
        run_cmd(cmd, desc, use_pipenv=use_pipenv)

    if any('test' in f for f in py_files):
        run_cmd("coverage run -m pytest", "pytest with coverage")
        run_cmd("coverage report -m", "coverage summary")
    console.print(Panel.fit("All bulletproofing checks passed on STAGED .py files!", style="green"))

if __name__ == "__main__":
    main()
