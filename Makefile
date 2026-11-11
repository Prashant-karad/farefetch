# One-command workflow. Run `make help`.
SHELL := /bin/bash
ROOT  := $(shell git rev-parse --show-toplevel 2>/dev/null || pwd)
API   := $(shell grep '^DEMO_AGENT_API_KEY=' .env 2>/dev/null | cut -d= -f2)
TOKEN := $(shell grep '^INTERNAL_TOKEN=' .env 2>/dev/null | cut -d= -f2)
P     := http://127.0.0.1:8001

.PHONY: help install up down keys migrate seed setup dev agent agent-sloppy settle topup wallet ledger-check test

help:            ## Show commands
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*## /\t/'

install:         ## Create venvs and install dependencies for all services
	cd platform && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	cd gateway  && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
	cd agent    && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

up:              ## Start PostgreSQL and Redis
	docker compose up -d && docker compose ps

down:            ## Stop PostgreSQL and Redis (data is kept)
	docker compose down

keys:            ## Generate the ES256 pass-signing key pair (once)
	mkdir -p keys && [ -f keys/pass_private.pem ] || ( \
	  openssl ecparam -name prime256v1 -genkey -noout -out keys/pass_private.pem && \
	  openssl ec -in keys/pass_private.pem -pubout -out keys/pass_public.pem )

migrate:         ## Apply database migrations
	cd platform && .venv/bin/alembic upgrade head

seed:            ## Load demo data (prints the agent API key once)
	cd platform && .venv/bin/python -m scripts.seed

setup:           ## Add paid API resource + set publisher PayPal emails from .env
	cd platform && .venv/bin/python -m scripts.setup_demo

dev:             ## Run origin + platform + gateway together
	./scripts/dev.sh

agent:           ## Run the research agent (Q="your question")
	cd agent && .venv/bin/python -m app.main "$(or $(Q),When should I sow soybean in Pune and how do I test my soil first?)"

agent-sloppy:    ## Run the agent in copy-paste mode to demo the license guard
	cd agent && .venv/bin/python -m app.main "$(or $(Q),How do I test my soil before sowing?)" --sloppy

topup:           ## Start a $5 PayPal sandbox top-up (open the approve_url)
	curl -s -X POST $(P)/v1/topups -H "Authorization: Bearer $(API)" -H "Content-Type: application/json" -d '{"amount":"5.00"}' | python3 -m json.tool

wallet:          ## Show wallet balance and recent ledger entries
	curl -s -H "Authorization: Bearer $(API)" $(P)/v1/wallet | python3 -m json.tool

settle:          ## Pay publishers via PayPal Payouts
	curl -s -X POST $(P)/v1/admin/payouts/settle -H "X-Admin-Token: $(TOKEN)" | python3 -m json.tool

ledger-check:    ## Every transaction must sum to zero (expect 0 rows)
	docker compose exec postgres psql -U app -d agentgate -c "SELECT transaction_id, SUM(amount) FROM ledger_entries GROUP BY transaction_id HAVING SUM(amount) <> 0;"

test:            ## Unit tests for the license guard core (no services needed)
	cd platform && .venv/bin/python -m unittest discover -s tests -v
