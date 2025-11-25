import subprocess
import sys
from pathlib import Path
from loguru import logger
from rich.console import Console
from rich.panel import Panel

# Warnings that can be safely ignored
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

def find_py_files():
    return [str(p) for p in Path('.').rglob('*.py') if '/site-packages/' not in str(p)]

def running_in_pipenv():
    return Path('Pipfile').exists()

def main():
    use_pipenv = running_in_pipenv()
    files = find_py_files()
    if not files:
        console.print("[yellow]No Python files found.[/yellow]")
        sys.exit(0)

    tools = [
        ("mypy " + " ".join(files), "mypy (static typing)"),
        ("flake8 " + " ".join(files), "flake8 (lint/PEP8)"),
        ("pylint " + " ".join(files) + " --exit-zero", "pylint (code quality/linting)"),
        ("bandit -r . -c", "bandit (security scan)"),
        ("black --check --diff " + " ".join(files), "black (code format)"),
        ("isort --check-only " + " ".join(files), "isort (import order)"),
        ("coverage run -m pytest", "pytest with coverage"),
        ("coverage report -m", "coverage summary"),
    ]
    for cmd, desc in tools:
        run_cmd(cmd, desc, use_pipenv=use_pipenv)
    console.print(Panel.fit("All bulletproofing checks passed on ALL .py files!", style="green"))

if __name__ == "__main__":
    main()
