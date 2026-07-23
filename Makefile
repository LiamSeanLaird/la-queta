# La Queta — common local commands (conda env `la-queta` should be active).

.PHONY: run test seed migrate upgrade

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
