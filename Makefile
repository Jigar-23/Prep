PYTHON_BIN := .venv/bin/python
PIP_BIN := .venv/bin/pip

.PHONY: backend-install backend-install-turso frontend-install mobile-install backend-dev frontend-dev frontend-build frontend-start mobile-dev mobile-typecheck

backend-install:
	python3 -m venv .venv
	$(PIP_BIN) install -r backend/requirements.txt

backend-install-turso:
	$(PIP_BIN) install -r backend/requirements-turso.txt

frontend-install:
	cd frontend && npm install

mobile-install:
	cd mobile && npm install

backend-dev:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-start:
	cd frontend && npm start -- --hostname 127.0.0.1 --port 3000

mobile-dev:
	cd mobile && npm start

mobile-typecheck:
	cd mobile && npm run typecheck
