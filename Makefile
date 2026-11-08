.PHONY: build deploy sync-catalog optimize-art test book

# Override these for a fresh machine; no SSH alias is required.
DEPLOY_KEY ?= $(CURDIR)/.deploy/ssh/nsp-deploy
DEPLOY_HOST ?= nsp-deploy@pavpanchekha.com
export DEPLOY_KEY DEPLOY_HOST

build: deploy

deploy:
	python3 deploy.py $(if $(SLUG),--slug '$(SLUG)')

sync-catalog:
	python3 -m bookmaker.catalog

optimize-art:
	python3 optimize_art.py $(if $(SLUG),--slug '$(SLUG)')

test:
	uv run pytest

book: sync-catalog
	uv run bookmaker run "$(SLUG)" "$(IDEA)" --deploy
