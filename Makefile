.PHONY: format lint typecheck test
format:
	poetry run black actchain tests && poetry run isort actchain tests
lint:
	poetry run pflake8 actchain
typecheck:
	poetry run mypy actchain
typecheck-test:
	poetry run mypy tests
test:
	poetry run pytest tests

