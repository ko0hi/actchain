.PHONY: format lint typecheck test
format:
	poetry run ruff format . && poetry run ruff . --select I --fix-only
lint:
	poetry run ruff check actchain
lint-test:
	poetry run ruff check tests
lint-sample:
	poetry run ruff check sample
typecheck:
	poetry run mypy --strict actchain
typecheck-test:
	poetry run mypy tests
typecheck-sample:
	poetry run mypy sample
test:
	poetry run pytest tests

