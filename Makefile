SHELL := /bin/bash
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: init env setup dev

init: env setup

env:
	@if [ -f .env ]; then \
		echo ".env already exists — skipping"; \
	else \
		cp .env.example .env; \
		echo "Created .env from .env.example — add your Azure OpenAI credentials"; \
	fi

setup: $(VENV)/.installed

$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	@touch $@

dev:
	@set -a && . ./.env && set +a && \
	$(PYTHON) -m uvicorn app:app --reload --host 127.0.0.1 --port 5012
