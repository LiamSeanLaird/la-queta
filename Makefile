# La Queta — common local commands (conda env `la-queta` should be active).
# On the production VM, prefer: make deploy

.PHONY: run test seed migrate upgrade deploy

PORT ?= 5001

run:
	poetry run python -m flask --app wsgi run -p $(PORT)

test:
	poetry run python -m pytest -q

seed:
	poetry run python scripts/seed.py

migrate:
	poetry run python -m flask --app wsgi db migrate

upgrade:
	poetry run python -m flask --app wsgi db upgrade

# Production VM only: pull → install → backup → migrate → seed → restart → health
deploy:
	./scripts/deploy.sh
