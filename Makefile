.PHONY: install dev test lint format run demo clean

install:        ## Install the package
	pip install -e .

dev:            ## Install with dev tooling (pytest, ruff)
	pip install -e ".[dev]"

test:           ## Run the test suite
	pytest

lint:           ## Lint with ruff
	ruff check .

format:         ## Auto-fix lint issues and format
	ruff check --fix .
	ruff format .

demo:           ## Run the Module 1 limitations demo
	python -m documind.llm --demo

run:            ## Ask DocuMind a question: make run Q="your question"
	python -m documind.llm "$(Q)"

clean:          ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
