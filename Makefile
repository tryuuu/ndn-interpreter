S ?= examples/hello.ndn

.PHONY: all build up down run logs

all: build up

build:
	docker compose build

up:
	docker compose up -d nfd producer

down:
	docker compose down

run:
	docker compose run --rm consumer ndnc run $(S)

logs:
	docker compose logs -f