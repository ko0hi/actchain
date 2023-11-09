.PHONY: format lint typecheck test
format:
	poetry run black actchain sample tests && poetry run isort actchain sample tests
lint:
	poetry run pflake8 actchain
lint-test:
	poetry run pflake8 tests
lint-sample:
	poetry run pflake8 sample
typecheck:
	poetry run mypy actchain
typecheck-test:
	poetry run mypy tests
typecheck-sample:
	poetry run mypy sample
test:
	poetry run pytest tests

