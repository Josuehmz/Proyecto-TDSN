.PHONY: help up down logs rebuild test seed eval security ragas clean

help:
	@echo "Comandos disponibles:"
	@echo "  make up        - docker compose up (build + start)"
	@echo "  make down      - detener y remover contenedores"
	@echo "  make logs      - seguir logs del backend"
	@echo "  make rebuild   - rebuild backend + frontend"
	@echo "  make test      - ejecutar pytest en el backend"
	@echo "  make seed      - re-ejecutar seed de tenants"
	@echo "  make eval      - ejecutar banco de preguntas (requiere backend up)"
	@echo "  make ragas     - métricas RAGAS (requiere OPENAI_API_KEY)"
	@echo "  make security  - baterías de seguridad / red-team"
	@echo "  make clean     - eliminar volúmenes y artefactos de evaluación"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f backend

rebuild:
	docker compose build --no-cache backend frontend
	docker compose up -d

test:
	docker compose exec backend pytest -q

seed:
	docker compose exec backend python -m app.scripts.seed_tenants

eval:
	python evaluation/scripts/run_evaluation.py

ragas:
	python evaluation/scripts/ragas_eval.py

security:
	python evaluation/scripts/security_eval.py

clean:
	docker compose down -v
	rm -rf evaluation/results/*.json evaluation/results/*.csv
