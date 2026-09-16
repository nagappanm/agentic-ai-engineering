.PHONY: install dev test lint format run demo clean signals signals-dry

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

signals:        ## Weekly QE signal digest: fetch → rank → ideate → deliver (spends LLM tokens)
	python -m qe_signals.run $(ARGS)

signals-dry:    ## Fetch + rank only, no LLM spend; prints clusters and projected call count
	python -m qe_signals.run --dry-run $(ARGS)

stlc-demo:      ## Run all six STLC phases live against ParaBank (0 GO · 10 HOLD · 20 NO-GO)
	bash pr_gate/stlc_demo.sh

clean:          ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
