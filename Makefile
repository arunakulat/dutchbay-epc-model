.PHONY: setup lint type security test cov html package freeze lock clean

PY?=python
PIP?=pip

setup:
	{
		python -m pip install --upgrade pip
		pip install -e .[dev,test]
	}

lint:
	black --check .
	ruff check .
	flake8 .

type:
	mypy --install-types --non-interactive dutchbay_v13

security:
	bandit -r dutchbay_v13 -x tests

test:
	coverage run -m unittest discover -s tests -p "test_*_unittest.py"

cov:
	coverage report -m

html:
	coverage html && echo "Open htmlcov/index.html"

package:
	python -m build || true
	mkdir -p dist_zip
	git ls-files | zip -@ dist_zip/DutchBay_Model_V13.1.0.zip

freeze:
	# Generate constraints from the current venv (deterministic pin set)
	pip freeze --all | sort > constraints.txt

lock:
	# Write an explicit lock file used by CI/Prod
	pip freeze --all | sort > requirements.lock

clean:
	rm -rf build dist *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
