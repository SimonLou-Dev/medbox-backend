# 🚀 Guide de démarrage MEDBOX

**Bienvenue dans MEDBOX!** Ce guide vous aidera à configurer l'environnement de développement et comprendre la structure du projet.

---

## 📚 Lire en premier

1. **[`readme.md`](../readme.md)** — Vue d'ensemble du projet (5 min)
2. **[`docs/architecture.md`](./architecture.md)** — Comprendre les 4 composants (15 min)
3. **Ce fichier** — Setup dev (10 min)

---

## 🛠️ Setup développement (15 min)

### Prérequis

```bash
# Vérifier Python 3.11+
python --version

# Installer Poetry (si absent)
curl -sSL https://install.python-poetry.org | python3 -
```

### Installation

```bash
# 1. Cloner repo
git clone https://github.com/SimonLou-Dev/medbox-backend.git
cd medbox-backend

# 2. Installer dépendances
poetry install

# 3. Activer virtualenv
poetry shell

# 4. Vérifier installation
poetry run ruff --version
```

### Variables d'environnement

Créer `.env` à la racine (copier du template):

```bash
# Database (PostgreSQL local)
DATABASE_URL=postgresql+asyncpg://medbox:medbox@localhost:5432/medbox_dev
SQLALCHEMY_ECHO=false

# Keycloak (dev)
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=medbox
KEYCLOAK_CLIENT_ID=backend-client
KEYCLOAK_CLIENT_SECRET=changeme

# MQTT (dev)
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=medbox
MQTT_PASSWORD=medbox

# Redis (dev)
REDIS_URL=redis://localhost:6379/0

# Crypto
ENCRYPTION_KEY=your_fernet_key_here

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
```

### Base de données

```bash
# 1. Démarrer PostgreSQL (Docker)
docker run -d \
  --name medbox_db \
  -e POSTGRES_USER=medbox \
  -e POSTGRES_PASSWORD=medbox \
  -e POSTGRES_DB=medbox_dev \
  -p 5432:5432 \
  postgres:15

# 2. Appliquer migrations
alembic upgrade head

# 3. Vérifier
psql postgresql://medbox:medbox@localhost:5432/medbox_dev -c "SELECT COUNT(*) FROM tenant"
```

### Services externes (Docker Compose)

```bash
# Démarrer tous les services (PostgreSQL, Redis, MQTT, Keycloak)
docker-compose up -d

# Vérifier
docker-compose ps
```

**Services accessibles**:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MQTT (Mosquitto): `localhost:1883`
- Keycloak: `http://localhost:8080`

---

## 🎯 Premiers pas

### 1. Lancer API

```bash
# Terminal 1: API server
poetry run api-dev

# Tester
curl http://localhost:8000/health
# → {"status": "ok"}

# Docs: http://localhost:8000/docs (Swagger)
```

### 2. Lancer Workers (optionnel pour dev)

```bash
# Terminal 2: IoT Worker
poetry run iot-worker

# Terminal 3: Scheduler Worker  
poetry run scheduler-worker
```

### 3. Lancer tests

```bash
# Tous les tests
pytest

# Avec couverture
pytest --cov=medbox

# Un fichier spécifique
pytest tests/test_crypto.py -v
```

### 4. Linter & formater

```bash
# Check
poetry run ruff check medbox/

# Format (auto-fix)
poetry run ruff format medbox/

# Combo
poetry run ruff format medbox/ && poetry run ruff check medbox/
```

---

## 📁 Structure du projet (résumé)

```
medbox/
├── api/              ← FastAPI app & routes
│   ├── main.py       (Point d'entrée)
│   ├── routes/       (Endpoints v1)
│   ├── deps/         (Dépendances FastAPI)
│   └── middlewares/  (Auth, etc.)
│
├── core/             ← Business logic
│   ├── db/           (Models, repositories, session)
│   ├── services/     (Business services)
│   ├── dto/          (Data transfer objects)
│   ├── utils/        (Utilities: crypto, etc.)
│   ├── constants/    (Enums, constants)
│   ├── exceptions/   (Custom exceptions)
│   └── tasks/        (Async background tasks)
│
├── iotworker/        ← MQTT worker (incomplete)
├── schedulerworker/  ← Scheduler worker (incomplete)
├── migrations/       ← Alembic DB migrations
├── tests/            ← Pytest test suite
├── docs/             ← Documentation (ce dossier)
│   ├── architecture.md  ← LIRE CETTE PREMIÈRE!
│   ├── database.md      (Schema DB)
│   ├── readme.md        (API endpoints)
│   └── GETTING_STARTED.md (Ce fichier)
│
├── pyproject.toml    ← Poetry config + dépendances
├── pytest.ini        ← Pytest config
├── alembic.ini       ← Alembic config
├── readme.md         ← README racine
└── todo.md           ← Tâches & roadmap
```

👉 Voir [`architecture.md#structure-du-projet`](./architecture.md#structure-du-projet) pour détails complets.

---

## 🔑 Concepts clés

### Multi-tenant

- Chaque entité a un `tenant_id`
- Utilisateur authentifié via Keycloak → `tenant_id` dans JWT
- API filtre automatiquement par tenant (middleware)
- Zéro cross-tenant possible

### Authentification

- **Utilisateurs**: Keycloak OIDC (SSO)
- **Boxes**: Certificats mTLS MQTT (pas encore implémenté en dev)

### Architecture asynchrone

- API: FastAPI async endpoints
- DB: SQLAlchemy 2.0 async ORM (asyncpg driver)
- MQTT: Async MQTT client (iotworker)
- Jobs: Dramatiq async task queue (schedulerworker)

### Chiffrement

- Champs sensibles: `c_patient_name`, `c_medication_name`, etc.
- Algo: Fernet (AES-128 + HMAC)
- Utils: `core/utils/crypto.py`
- Tests: `tests/test_crypto.py`

---

## 🐛 Troubleshooting

### `poetry: command not found`

```bash
# Solution: Ajouter Poetry au PATH
export PATH="$HOME/.local/bin:$PATH"
```

### `ModuleNotFoundError: No module named 'medbox'`

```bash
# Solution: Réinstaller en mode dev
poetry install
```

### `psycopg2.OperationalError: could not connect to database`

```bash
# Vérifier PostgreSQL
docker ps | grep postgres

# Redémarrer
docker-compose restart db

# Check connexion
psql postgresql://medbox:medbox@localhost:5432/medbox_dev -c "SELECT 1"
```

### `redis.exceptions.ConnectionError`

```bash
# Vérifier Redis
docker ps | grep redis

# Redémarrer
docker-compose restart redis

# Test
redis-cli ping
```

### Ruff errors

```bash
# Check quels problèmes
poetry run ruff check medbox/

# Fix automatiquement
poetry run ruff format medbox/
```

---

## ✅ Checklist développeur

Avant de commencer à coder:

- [ ] `git clone` + `cd medbox-backend`
- [ ] `poetry install`
- [ ] Créer `.env` (cf template)
- [ ] `docker-compose up -d` (ou PostgreSQL local)
- [ ] `alembic upgrade head`
- [ ] `pytest` (tous tests passent?)
- [ ] `poetry run api-dev` (API démarre?)
- [ ] `curl http://localhost:8000/health` (OK?)
- [ ] Lire [`docs/architecture.md`](./architecture.md)

---

## 🎯 Next steps

### Pour ajouter nouvel endpoint API

1. Créer DTOs → `core/dto/mon_domaine.py`
2. Créer service → `core/services/mon_domaine.py`
3. Créer route → `api/routes/v1/mon_domaine.py`
4. Importer dans router → `api/routes/router_v1.py`
5. Ajouter tests → `tests/test_mon_domaine.py`

Exemple complet: `api/routes/v1/patient.py` + `core/services/tenant.py`

### Pour ajouter nouvel modèle DB

1. Créer modèle → `core/db/models/ma_table.py`
2. Générer migration → `alembic revision --autogenerate -m "Add ma_table"`
3. Vérifier migration → `alembic history`
4. Appliquer → `alembic upgrade head`
5. Optionnel: Créer repository → `core/db/repositories/ma_table.py`

### Pour ajouter événement MQTT

1. Créer handler → `iotworker/tasks/mon_event.py`
2. Valider payload avec Pydantic
3. Écrire en DB via repository
4. Déclencher action métier si besoin
5. Tester avec mock MQTT broker

👉 Voir [`todo.md`](../todo.md) pour liste détaillée tâches.

---

## 📞 Questions?

- **Architecture**: Voir [`docs/architecture.md`](./architecture.md)
- **API endpoints**: Voir [`docs/readme.md`](./readme.md)
- **Database schema**: Voir [`docs/database.md`](./database.md)
- **Roadmap**: Voir [`todo.md`](../todo.md)
- **Keycloak setup**: TBD (voir notes ouvertes dans `todo.md`)
- **MQTT dev**: TBD (certificats mTLS)

---

## 🔗 Ressources utiles

- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy 2.0 async**: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Pydantic**: https://docs.pydantic.dev/
- **Dramatiq**: https://dramatiq.io/
- **Keycloak**: https://www.keycloak.org/docs/
- **MQTT spec**: http://mqtt.org/

---

**Prêt à coder?** 🚀 Consultez la [checklist développeur](#-checklist-développeur) et c'est parti!
