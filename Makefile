.PHONY: build deploy sync-catalog optimize-art test book

# Override these for a fresh machine; no SSH alias is required.
DEPLOY_KEY_FILE ?= $(CURDIR)/.deploy/ssh/nsp-deploy
DEPLOY_HOST ?= nsp-deploy@pavpanchekha.com
export DEPLOY_KEY_FILE DEPLOY_HOST

build: deploy

deploy:
	uv run python deploy.py $(if $(SLUG),--slug '$(SLUG)')

sync-catalog:
	uv run python -m bookmaker.catalog

optimize-art:
	uv run python optimize_art.py $(if $(SLUG),--slug '$(SLUG)')

test:
	uv run pytest

book: sync-catalog
	uv run bookmaker run "$(SLUG)" "$(IDEA)" --deploy
