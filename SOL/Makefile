.PHONY: venv install fmt lint test train backtest grid live clean

venv:
	python3 -m venv venv

install:
	pip install --upgrade pip
	pip install -r requirements.txt

fmt:
	black src/ scripts/ tests/
	ruff check --fix src/ scripts/ tests/

lint:
	black --check src/ scripts/ tests/
	ruff check src/ scripts/ tests/

test:
	python -m pytest tests/ -v

train:
	python scripts/train_runner.py

backtest:
	python scripts/backtest_runner.py

grid:
	python scripts/gridsearch_runner.py

live:
	python scripts/live_demo_runner.py

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
