.PHONY: build harness repro eir all up down

build:
	./scripts/build-bluez.sh

harness:
	./scripts/build-harness.sh

repro: harness
	./scripts/repro-eir.sh

eir: build
	./scripts/repro-eir.sh

all: build
	./scripts/repro-all.sh

up:
	docker compose up --build

down:
	docker compose down
