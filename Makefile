.PHONY: help setup test lint format seed up down demo clean dev run

PYTHON ?= python
PYTEST ?= pytest
RUFF ?= ruff

help:
	@echo "Argvtix: Enterprise AI Reliability Platform"
	@echo "Available commands:"
	@echo "  make dev       - Run both backend and frontend simultaneously"
	@echo "  make setup     - Install dependencies in virtual environment"
	@echo "  make test      - Run test suite"
	@echo "  make lint      - Run ruff linter & format checker"
	@echo "  make format    - Auto-format code using ruff"
	@echo "  make seed      - Seed business database with synthetic orders & customers"
	@echo "  make up        - Start platform via Docker Compose"
	@echo "  make down      - Stop Docker Compose services"
	@echo "  make demo      - Run end-to-end demo scenario"
	@echo "  make clean     - Remove cache files and build artifacts"

dev:
	$(PYTHON) run.py

run:
	$(PYTHON) run.py

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTEST) tests/ -v --tb=short

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

seed:
	$(PYTHON) -m argvtix.target_app.seed --count 1000

up:
	docker compose up -d

down:
	docker compose down

demo:
	$(PYTHON) -m argvtix.target_app.simulate --ticket "Order 1042 ka refund de do"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
