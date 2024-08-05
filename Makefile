USER=$(shell id -u):$(shell id -g)

.PHONY: build
build:
	docker-compose build base
	docker-compose build dev
	docker-compose build service
	docker-compose build client

.PHONY: package
package:
	docker-compose run --user $(USER) --rm dev poetry build

.PHONY: test-unit
test-unit:
	docker-compose run --user $(USER) --rm dev py.test $${TEST_ARGS:-"tests/unit"}

.PHONY: emulate-client
emulate-client: build teardown
	docker-compose run --user $(USER) --rm client python tests/integration/emulate_client.py

.PHONY: lint
lint:
	docker-compose run --rm --user $(USER) dev pylint src/ tests/

.PHONY: format
format:
	docker-compose run --rm --user $(USER) dev isort src/ tests/
	docker-compose run --rm --user $(USER) dev black src/ tests/

.PHONY: bash-dev
bash-dev:
	docker-compose run --user $(USER) --rm dev bash

.PHONY: bash-client
bash-client:
	docker-compose run --user $(USER) --rm client bash

.PHONY: bash-service
bash-service:
	docker-compose run --user $(USER) --rm service bash

.PHONY: service
service:
	docker-compose up service

.PHONY: redis
redis:
	docker-compose up redis

.PHONY: teardown
teardown:
	docker-compose down -v --remove-orphans
