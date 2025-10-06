# Variables
REGISTRY ?= ghcr.io/your-org
DMP_IMAGE ?= $(REGISTRY)/delineo-dmp:latest
SIM_IMAGE ?= $(REGISTRY)/delineo-simulator:latest
COMPOSE ?= docker compose

.PHONY: build up down logs ps push clean

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

down:
	$(COMPOSE) down

push:
	docker tag simulation_dmp $(DMP_IMAGE) || true
	docker tag simulation_simulator $(SIM_IMAGE) || true
	docker push $(DMP_IMAGE)
	docker push $(SIM_IMAGE)

clean:
	$(COMPOSE) down -v --remove-orphans
	docker image prune -f
