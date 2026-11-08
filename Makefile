.PHONY: build deploy optimize-art test book

DEPLOY_KEY := $(CURDIR)/.deploy/ssh/nsp-deploy
DEPLOY_SSH := ssh -i '$(DEPLOY_KEY)' -o IdentitiesOnly=yes -o BatchMode=yes
DEPLOY_HOST := nsp-deploy@server

build: deploy

# Remote paths are relative to the directory enforced by rrsync.
deploy: optimize-art
	rsync -az -e "$(DEPLOY_SSH)" .deploy/art/ $(DEPLOY_HOST):art/
	rsync -az -e "$(DEPLOY_SSH)" *.html book.css book.js $(DEPLOY_HOST):./
	# Retire server originals only after the compressed art and pages are live.
	rsync -az --delete -e "$(DEPLOY_SSH)" .deploy/art/ $(DEPLOY_HOST):art/

optimize-art:
	python3 optimize_art.py

test:
	uv run pytest

# Usage: make book SLUG=space-cats IDEA='Nicholas meets cats on the moon'
book:
	uv run bookmaker run "$(SLUG)" "$(IDEA)" --deploy
