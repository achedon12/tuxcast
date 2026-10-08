# Development shortcuts. `make` lists them.
PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

$(BIN)/tuxcast:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -e . ruff pytest "mkdocs<2" mkdocs-material

install: $(BIN)/tuxcast ## Create .venv with tuxcast and the dev tools

lint: install ## Run ruff
	$(BIN)/ruff check src tests .github/scripts

format: install ## Fix what ruff can fix
	$(BIN)/ruff check --fix src tests .github/scripts

test: install ## Run the test suite
	$(BIN)/pytest

docs: install ## Build the website into site/
	$(BIN)/mkdocs build --strict

serve: install ## Preview the website on http://127.0.0.1:8000
	$(BIN)/mkdocs serve

wiki: ## Generate the wiki pages into wiki/
	$(PYTHON) .github/scripts/build-wiki.py . wiki

check: lint test docs ## Everything CI runs

.PHONY: help install lint format test docs serve wiki check
