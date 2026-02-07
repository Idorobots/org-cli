SHELL := /bin/bash

init:
	python -m venv dev
	source dev/bin/activate
	pip install -r requirements.txt

check:
	source dev/bin/activate
	ruff format --check src/ tests/
	ruff check --fix src/ tests/
	mypy src/
	pytest --cov=src/ --cov-report=term-missing
