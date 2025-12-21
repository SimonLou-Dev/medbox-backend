# 💊 MEDBOX - Système de Distribution Automatisée de Médicaments

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](./pyproject.toml)
[![Python](https://img.shields.io/badge/python-^3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688)](https://fastapi.tiangolo.com/)

Plateforme sécurisée de distribution automatisée de médicaments avec orchestration backend, boîtiers IoT connectés et synchronisation temps réel MQTT.

---

## 📖 Documentation

**➡️ Toute la documentation se trouve dans [`docs/`](./docs/)**

- **Nouveaux développeurs**: Commencer par [`docs/GETTING_STARTED.md`](./docs/GETTING_STARTED.md)
- **Architecture système**: [`docs/architecture.md`](./docs/architecture.md)
- **Patterns de code**: [`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md)
- **Index complet**: [`docs/INDEX.md`](./docs/INDEX.md)

---

## 🚀 Quick Start

```bash
# Clone + setup
git clone https://github.com/SimonLou-Dev/medbox-backend.git
cd medbox-backend

# Install dépendances
poetry install

# Run tests
poetry run pytest ./tests -v

# Format code
poetry run ruff format .

# Check linting
poetry run ruff check .
```

---

## 🧠 Vue d'ensemble

**MEDBOX** = **Backend + Workers + IoT Boxes**

```
Soignant → [API] → Calcul planning (Scheduler) → Commande box
                ↓
            [MQTT Broker] ← Remontée événements (IoT Worker)
                ↓
         📦 Physical Box (ESP32)
```

### Clés d'architecture

- ✅ **Multi-tenant strict** — Chaque établissement = tenant isolé
- 🔐 **Sécurité** — Keycloak auth + chiffrement PII + audit trail
- ⚡ **Async/await** — FastAPI + SQLAlchemy async + Dramatiq
- 🔄 **Temps réel** — MQTT pub/sub pour box ↔ backend
- 📊 **Worker paradigme** — Orchestration distribuée (API + Scheduler + IoT)

---

## 🛠 Stack technique

| Composant | Tech | Version |
|-----------|------|---------|
| API | FastAPI | 0.110.0 |
| ORM | SQLAlchemy | 2.0.25 |
| Database | PostgreSQL | 13+ |
| Auth | Keycloak | 2.9.0 |
| Task Queue | Dramatiq | 1.15.0 |
| Validation | Pydantic | 2.12.4 |
| Testing | pytest | 8.0+ |
| Linting | Ruff | 0.6+ |

**Infrastructure**: Python 3.11+, PostgreSQL 13+, Redis 6+, Keycloak, MQTT broker

---

## 📝 Status du projet

| Component | Status |
|-----------|--------|
| API multi-tenant | ✅ Complet (80%) |
| Routes standardisées | ✅ Fixé |
| Tests multi-tenant | ✅ 10 tests |
| Logging structuré | ✅ Créé |
| Pagination générique | ✅ PagedResponse<T> |
| Erreurs standardisées | ✅ ErrorResponse |
| MQTT Protocol | ⏳ Prochaine sprint |

👉 **Détails complets**: [`docs/audit.md`](./docs/audit.md)
KEYCLOAK_REALM=medbox
KEYCLOAK_CLIENT_ID=backend-client
KEYCLOAK_CLIENT_SECRET=your_secret_here

# MQTT
MQTT_BROKER_HOST=mqtt.example.com
MQTT_BROKER_PORT=8883
MQTT_USERNAME=medbox_user
MQTT_PASSWORD=mqtt_password
MQTT_CA_CERT=/path/to/ca.crt
MQTT_CLIENT_CERT=/path/to/client.crt
MQTT_CLIENT_KEY=/path/to/client.key

# Redis (Dramatiq)
REDIS_URL=redis://localhost:6379/0

# Crypto
ENCRYPTION_KEY=your_fernet_key_here

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
```

### 3. Migration DB

```bash
# Créer tables
alembic upgrade head

# Vérifier statut
alembic current
```

### 4. Lancer services

```bash
# Terminal 1: API (http://localhost:8000)
poetry run api-dev

# Terminal 2: IoT Worker (MQTT subscriber)
poetry run iot-worker

# Terminal 3: Scheduler Worker (Async jobs)
poetry run scheduler-worker
```

### 5. Vérifier santé

```bash
# Health check
curl http://localhost:8000/health

# Swagger docs
open http://localhost:8000/docs

# ReDoc docs
open http://localhost:8000/redoc
```

---

## 📌 Commandes principales

### API

```bash
# Production
poetry run api

# Dev avec hot-reload
poetry run api-dev

# Vérifier santé
curl http://localhost:8000/health
```

### Workers

```bash
# IoT Worker (subscribe MQTT, écrit DB)
poetry run iot-worker

# Scheduler Worker (tâches planifiées, jobs Dramatiq)
poetry run scheduler-worker
```

### Database

```bash
# Créer nouvelle migration
alembic revision --autogenerate -m "Add new_table"

# Appliquer migrations
alembic upgrade head

# Revert dernière migration
alembic downgrade -1

# Voir statut
alembic current
```

### Tests & Linting

```bash
# Lancer tous tests
pytest

# Tests avec couverture
pytest --cov=medbox tests/

# Linter (check)
poetry run ruff check medbox/

# Formater code
poetry run ruff format medbox/

# Linter + format
poetry run ruff check medbox/ && poetry run ruff format medbox/
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [`docs/architecture.md`](./docs/architecture.md) | **Lire d'abord**: Design système, 4 composants, flux données, MQTT, sécurité, diagrammes Mermaid |
| [`docs/database.md`](./docs/database.md) | Schéma DB, ERD, champs chiffrés, relations |
| [`docs/readme.md`](./docs/readme.md) | Endpoints API détaillés, flows métier (multi-tenant, invitations, prescriptions) |
| [`todo.md`](./todo.md) | Tâches en cours, implémentations incomplètes, roadmap |
| [`pyproject.toml`](./pyproject.toml) | Dépendances, scripts CLI, config Ruff |

### Quick links

- **API Swagger**: http://localhost:8000/docs (après `poetry run api-dev`)
- **API ReDoc**: http://localhost:8000/redoc
- **Keycloak Admin**: https://keycloak.example.com/admin
- **MQTT Topics**: Voir [`docs/architecture.md#protocole-mqtt`](./docs/architecture.md#protocole-mqtt)

---

## 🧪 Tests

```bash
# Lancer tests
pytest

# Tests d'un fichier spécifique
pytest tests/test_crypto.py -v

# Tests avec pattern
pytest -k "encrypt" -v

# Avec couverture
pytest --cov=medbox --cov-report=html

# Ouverture rapport HTML
open htmlcov/index.html
```

### Coverage

Tests existants couvrent:
- ✅ Chiffrement/déchiffrement PII (`test_crypto.py`)
- ✅ Types SQLAlchemy custom (`test_encrypted_type.py`)
- ✅ Update champs chiffrés (`test_encrypted_update.py`)

**À compléter**: Voir [`todo.md`](./todo.md) pour gaps tests API, workers, MQTT.

---

## 🔐 Sécurité

### Authentification

- **Utilisateurs**: OIDC via Keycloak (SSO)
- **Boxes**: Certificats mTLS MQTT
- **JWT**: Validation signature + expiration
- **RBAC**: Droits par tenant

### Chiffrement

- **PII au repos**: Fernet (AES-128 + HMAC), champs `c_*`
- **Transit API**: TLS 1.2+
- **Transit MQTT**: TLS 1.2+ + mTLS certs

### Audit

- **Event log**: Tous changements tracked en DB (`event` table)
- **MQTT events**: Trace complète prises/erreurs/telemetry
- **Tenant isolation**: Cloisonnement strict au niveau DB

---

## 📦 Structure projet

```
medbox/
├── api/                 ← FastAPI app & routes
├── core/                ← Business logic, models, services
├── iotworker/           ← MQTT worker (events → DB)
├── schedulerworker/     ← Scheduler worker (async jobs)
│
docs/
├── architecture.md      ← Design système (LIRE CETTE PREMIÈRE!)
├── database.md         ← Schéma DB & ERD
└── readme.md           ← API endpoints détaillés
│
migrations/             ← Alembic DB migrations
tests/                  ← Pytest test suite
│
pyproject.toml          ← Poetry config
pytest.ini              ← Pytest config
alembic.ini            ← Alembic config
todo.md                ← Tâches & roadmap
readme.md              ← Ce fichier
```

👉 Voir [`docs/architecture.md#structure-du-projet`](./docs/architecture.md#structure-du-projet) pour détails complets.

---

## 🚀 Déploiement

**Statut**: ⚠️ À documenter (voir [`todo.md`](./todo.md))

Prévu:
- Docker Compose dev/prod
- Kubernetes manifests
- Environment setup (PostgreSQL, Redis, Keycloak, MQTT)
- CI/CD pipeline (GitHub Actions)

---

## 🐛 Troubleshooting

### `ModuleNotFoundError: No module named 'medbox'`

```bash
# Solution: installer en mode dev
poetry install
poetry shell
```

### `SQLAlchemy: No engine available`

```bash
# Vérifier DATABASE_URL en .env
# Vérifier PostgreSQL connectible
psql $DATABASE_URL -c "SELECT 1"
```

### MQTT connection refused

```bash
# Vérifier broker accessible
mosquitto_sub -h $MQTT_BROKER_HOST -p $MQTT_BROKER_PORT -t "test"

# Vérifier certificats mTLS
openssl x509 -in $MQTT_CLIENT_CERT -text -noout
```

### Ruff errors

```bash
# Fix automatiquement
poetry run ruff format medbox/

# Puis checker
poetry run ruff check medbox/
```

---

## 🤝 Support & Contributions

### Rapport bug

Créer issue GitHub avec:
- Description du problème
- Steps to reproduce
- Logs (terminal output, server logs)
- Environnement (OS, Python version, etc.)

### Code style

- **Format**: Ruff (double quotes, 88 chars)
- **Docstrings**: Français (conformité équipe)
- **Tests**: Obligatoires pour nouveau code
- **Commits**: Squash + messages clairs

Avant pull request:

```bash
poetry run ruff format medbox/
poetry run ruff check medbox/
pytest tests/
```

---

## 📄 License

MIT License - Voir [`LICENSE`](./LICENSE) (si présent)

---

## 👥 Auteurs

**Simon** — Lead Developer

---

## 📞 Contact

Pour questions: Slack #medbox ou issues GitHub

---

## 🗺️ Roadmap

- ✅ Architecture système documentée
- 🚧 IoT Worker implémentation complète
- 🚧 Scheduler Worker complet
- 🚧 Tests coverage 80%+
- ⏳ Déploiement Kubernetes
- ⏳ Admin dashboard (maintenance boxes)
- ⏳ Mobile app patient

Voir [`todo.md`](./todo.md) pour détails.

---

**Version**: 0.1.0 | **Mise à jour**: Décembre 2025
