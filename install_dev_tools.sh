#!/bin/bash

# Activate your virtual environment (edit path if needed)
source .venv311/bin/activate

# Upgrade pip, setuptools, and wheel
python -m pip install --upgrade pip setuptools wheel

# Core testing frameworks
pip install pytest
pip install unittest2   # (unittest is built-in, unittest2 for enhancements)
pip install hypothesis
pip install coverage
pip install mock        # (unittest.mock is built-in for Python 3.3+, included here for legacy use)

# Static analysis and code quality tools
pip install pylint
pip install flake8
pip install black
pip install isort
pip install mypy
pip install bandit

# Core web frameworks (security, modernity, validation)
pip install django
pip install fastapi

# Dependency and secret management
pip install python-decouple
pip install python-dotenv

# Good practice: Record versions for reproducibility
pip freeze > requirements_dev.txt

echo "✓ All developer tools and frameworks installed successfully."
