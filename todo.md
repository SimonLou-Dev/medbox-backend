# 📋 TODO MEDBOX - Roadmap & Tâches en cours

**Date**: Décembre 2025 | **Version**: 0.1.0

---

## 📊 Vue d'ensemble des tâches

| Statut | Tâches | % Complet |
|--------|--------|----------|
| ✅ | Documentation (architecture, readme) | 100% |
| 🚧 | IoT Worker | 10% |
| 🚧 | Scheduler Worker | 15% |
| 🚧 | Tests & Coverage | 20% |
| ⏳ | Déploiement & DevOps | 0% |
| ⏳ | Admin Dashboard | 0% |

---

## 🚧 En cours d'implémentation

URGENT : Test de test_patient.py test_global_medication.py

### 1. IoT Worker (MQTT → DB) — **PRIORITÉ: HAUTE**

**Responsabilité**: Subscribe `medbox/box/+/evt/#`, valider, écrire en DB, déclencher actions.

#### Sous-tâches

- [ ] **Connexion MQTT**
  - [ ] Config broker MQTT (host, port, certs mTLS)
  - [ ] Connexion async (paho-mqtt ou aiohttp)
  - [ ] Reconnexion automatique + backoff
  - [ ] Logging connexion/déconnexion

- [ ] **Event Handlers** (créer dans `iotworker/tasks/`)
  - [ ] `handle_take` — Prise effectuée
    - [ ] Valider payload (box_id, prescription_id, timestamp)
    - [ ] Insérer `Event` record
    - [ ] Update `Prescription` status → `taken`
    - [ ] Optionnel: notifier frontend (webhook)
  - [ ] `handle_error` — Erreur prise
    - [ ] Valider error_code (WHEEL_STUCK, TIMEOUT, etc.)
    - [ ] Insérer `Event` record status=error
    - [ ] Update `Box` status → `maintenance_needed`
    - [ ] Alerte soignant (notification, email?)
  - [ ] `handle_door_open` — Porte ouverte détectée
    - [ ] Insérer audit event
    - [ ] Update box status
  - [ ] `handle_medication_fall` — Chute médicament
    - [ ] Insérer event
    - [ ] Alert: checker dispensation précédente
  - [ ] `handle_telemetry` — Telemetry box (batterie, temp, etc.)
    - [ ] Insérer `Telemetry` record
    - [ ] Vérifier seuils (batterie < 20%?)
    - [ ] Alerte si seuil critique

- [ ] **Publishing commandes** (MQTT → box)
  - [ ] Endpoint API: POST `/api/v1/boxes/{box_id}/dispense`
  - [ ] Générer payload commande
  - [ ] Publier `medbox/box/{box_id}/cmd/dispense`
  - [ ] QoS 2 (exactement une fois)
  - [ ] Timeout + retry logic

- [ ] **Tests IoT Worker**
  - [ ] Mock MQTT broker
  - [ ] Test each handler (payload valid/invalid)
  - [ ] Test DB writes
  - [ ] Test error cases

**Fichiers clés**:
- `medbox/iotworker/main.py` — Point d'entrée
- `medbox/iotworker/broker.py` — Config MQTT
- `medbox/iotworker/tasks/` — Handlers événements
- `core/db/models/event.py` — Event model

**Blockers**: ❌ Authentification MQTT (certificats mTLS) pas testée en dev

---

### 2. Scheduler Worker (Tâches planifiées) — **PRIORITÉ: HAUTE**

**Responsabilité**: Calcul plannings, déclenchement prises, nettoyage, surveillance.

#### Sous-tâches

- [ ] **Configuration Dramatiq**
  - [ ] Broker Redis setup + tests
  - [ ] Worker startup/shutdown clean
  - [ ] Logging structure (structlog)
  - [ ] Error handling + retries

- [ ] **Job: Calcul planning prise** (`calculate_prescription_scheduling`)
  - [ ] Lire toutes prescriptions actives
  - [ ] Pour chaque prescription:
    - [ ] Récupérer pattern prise (intervalle heures, days_of_week)
    - [ ] Calculer prochaine prise (T + intervalle)
    - [ ] Créer `PrescriptionScheduleItem` en DB
  - [ ] Idempotence: rappels multiples = même résultat
  - [ ] Fréquence: Chaque heure (ou configurable)
  - [ ] Logs: Compteur items créés

- [ ] **Job: Déclenchement prise** (`dispatch_scheduled_take`)
  - [ ] Requête DB: Prises dues (time <= NOW)
  - [ ] Pour chaque prise:
    - [ ] Récupérer patient, prescription, medications
    - [ ] Générer commande MQTT
    - [ ] Publier `medbox/box/{box_id}/cmd/dispense`
    - [ ] Update statut → `dispatched`
  - [ ] Fréquence: Toutes les 5 minutes
  - [ ] Timeout: 30s (retry si pas ACK)

- [ ] **Job: Surveillance boxes** (`monitor_boxes`)
  - [ ] Requête: Boxes offline (last_heartbeat > 15 min)
  - [ ] Requête: Batterie critique (< 10%)
  - [ ] Requête: Roue bloquée (status maintenance)
  - [ ] Créer `Alert` pour chaque anomalie
  - [ ] Fréquence: Toutes les 5 minutes

- [ ] **Job: Nettoyage** (`cleanup_job`)
  - [ ] Supprimer invitations expirées (> 30 jours)
  - [ ] Archiver events anciens (> 1 an? configurable)
  - [ ] Nettoyer sessions expirées
  - [ ] Fréquence: Quotidien 02:00 UTC

- [ ] **Job: Agrégation métriques** (`aggregate_metrics`)
  - [ ] Résumé journalier prises par tenant
  - [ ] Compteur erreurs par type
  - [ ] Taux succès box (%)
  - [ ] Batterie moyenne boxes
  - [ ] Persister dans table `DailyMetric`
  - [ ] Fréquence: Quotidien 03:00 UTC

- [ ] **Tests Scheduler**
  - [ ] Mock Dramatiq broker
  - [ ] Test job execution (DB side effects)
  - [ ] Test idempotence
  - [ ] Test error/retry scenarios
  - [ ] Integration test avec vrai Redis? (CI env)

**Fichiers clés**:
- `medbox/schedulerworker/main.py` — Point d'entrée
- `medbox/schedulerworker/broker.py` — Config Dramatiq
- `medbox/schedulerworker/tasks/` — Job definitions
- `core/db/models/prescription.py` — Prescription model
- `core/services/tenant.py` — Tenant context

**Blockers**: ❌ Schema DB pour schedule_items pas clear (voir `docs/database.md`)

---

## 🧪 Tests & Coverage — **PRIORITÉ: HAUTE**

**Objectif**: 80%+ couverture code

### Tests existants ✅

```
tests/
├── test_crypto.py          — Chiffrement/déchiffrement
├── test_encrypted_type.py  — Type SQLAlchemy custom
└── test_encrypted_update.py — Update champs chiffrés
```

**Coverage**: ~15% (surtout crypto/utils)

### À ajouter

#### API Tests

- [ ] **Health endpoint**
  - [ ] GET /health → 200 OK

- [ ] **Tenant endpoints**
  - [ ] POST /api/v1/tenants — Create tenant
  - [ ] GET /api/v1/tenants/{id} — Get tenant (auth)
  - [ ] PATCH /api/v1/tenants/{id} — Update tenant

- [ ] **Patient endpoints**
  - [ ] GET /api/v1/patients — List patients (tenant filtered)
  - [ ] POST /api/v1/patients — Create patient
  - [ ] GET /api/v1/patients/{id} — Get patient
  - [ ] PATCH /api/v1/patients/{id} — Update patient
  - [ ] DELETE /api/v1/patients/{id} — Soft delete

- [ ] **Prescription endpoints**
  - [ ] POST /api/v1/prescriptions — Create prescription
  - [ ] GET /api/v1/prescriptions/{id} — Get with schedule
  - [ ] PATCH /api/v1/prescriptions/{id} — Update
  - [ ] GET /api/v1/prescriptions/{id}/schedule — Get computed schedule

- [ ] **Box endpoints**
  - [ ] GET /api/v1/boxes — List tenant boxes
  - [ ] POST /api/v1/boxes/{id}/dispense — Trigger prise
  - [ ] GET /api/v1/boxes/{id}/telemetry — Recent telemetry

#### Service Tests

- [ ] `core/services/security.py`
  - [ ] validate_jwt (valid/invalid tokens)
  - [ ] get_current_user (auth flow)
  - [ ] get_current_tenant

- [ ] `core/services/tenant.py`
  - [ ] create_tenant
  - [ ] add_user_to_tenant
  - [ ] validate_tenant_access

- [ ] `core/services/tenant_right.py`
  - [ ] check_user_permission
  - [ ] RBAC logic

#### Repository Tests

- [ ] Base repository patterns (CRUD, filters, pagination)
- [ ] Tenant scoping (all queries filtered by tenant_id)
- [ ] Soft deletes

#### Middleware Tests

- [ ] Auth middleware (JWT extraction, validation)
- [ ] Tenant context injection
- [ ] Request logging

#### Integration Tests

- [ ] Database transaction rollback on error
- [ ] Multi-tenant isolation (user A can't read tenant B data)
- [ ] Keycloak token validation (mock)

**Tools**:
- `pytest` + `pytest-asyncio` (async DB)
- `httpx` (async HTTP client)
- Mock/patch pour Keycloak, MQTT

**Target**: 
- API: 85%
- Services: 90%
- Repositories: 95%
- Utils: 95%

---

## 📚 Documentation code — **PRIORITÉ: MOYENNE**

**Convention**: Docstrings & commentaires EN FRANÇAIS (cf. `pyproject.toml` Ruff rules)

### À compléter

- [ ] **Docstrings modèles** (`core/db/models/*.py`)
  - [ ] `Tenant` — Multi-tenant entity
  - [ ] `Box` — Hardware entity
  - [ ] `Prescription` — Prescription logic
  - [ ] `Patient` — PII fields
  - [ ] `Event` — Audit trail
  - [ ] Etc.

- [ ] **Docstrings services** (`core/services/*.py`)
  - [ ] Chaque fonction publique
  - [ ] Args, Returns, Raises
  - [ ] Exemples usage

- [ ] **Docstrings repositories** (`core/db/repositories/*.py`)
  - [ ] Query methods
  - [ ] Filters, pagination

- [ ] **Comments complexes**
  - [ ] Logique chiffrement/déchiffrement (`core/utils/crypto.py`)
  - [ ] Calcul planning prescription (`core/services/prescription.py`)
  - [ ] MQTT payload validation (`iotworker/tasks/*.py`)

- [ ] **README technique** (pour devs)
  - [ ] Comment ajouter endpoint API
  - [ ] Comment ajouter modèle DB
  - [ ] Comment traiter événement MQTT
  - [ ] Comment ajouter job Scheduler

**Format docstring**:
```python
def ma_fonction(arg1: str, arg2: int) -> dict:
    """
    Description courte en français (1-2 lignes).
    
    Description longue si nécessaire, expliquer pourquoi
    cette fonction existe, quels side effects, etc.
    
    Args:
        arg1: Description du premier argument
        arg2: Description du second argument
        
    Returns:
        Description de la valeur retournée
        
    Raises:
        ValueError: Si condition X
        CustomException: Si condition Y
        
    Note:
        Informations additionnelles importantes
        (ex: appelée par quoi, avec quelle fréquence)
        
    Example:
        >>> result = ma_fonction("test", 42)
        >>> print(result)
        {'status': 'ok'}
    """
```

---

## 🚀 Déploiement & DevOps — **PRIORITÉ: MOYENNE**

### Infrastructure

- [ ] **Docker**
  - [ ] Dockerfile API
  - [ ] Dockerfile IoT Worker
  - [ ] Dockerfile Scheduler Worker
  - [ ] docker-compose.yml (dev)
  - [ ] docker-compose.prod.yml (prod)

- [ ] **Kubernetes** (optionnel, pour prod)
  - [ ] k8s deployment API
  - [ ] k8s deployment workers
  - [ ] k8s services
  - [ ] k8s configmaps (secrets)
  - [ ] k8s PVC PostgreSQL

- [ ] **Database**
  - [ ] PostgreSQL setup (dev, staging, prod)
  - [ ] Backup strategy
  - [ ] Migration automation
  - [ ] Performance tuning (indexes, etc.)

- [ ] **MQTT Broker**
  - [ ] Mosquitto setup + TLS
  - [ ] mTLS certificates setup
  - [ ] Topic ACL configuration
  - [ ] Persistence config

- [ ] **Redis**
  - [ ] Redis setup (dev, staging, prod)
  - [ ] Persistence (RDB/AOF)
  - [ ] Replication? (pour prod)

- [ ] **Keycloak**
  - [ ] Realm setup
  - [ ] Client creation
  - [ ] User mapping
  - [ ] OIDC flows

### CI/CD

- [ ] **GitHub Actions**
  - [ ] Lint check (ruff)
  - [ ] Run tests (pytest)
  - [ ] Build Docker images
  - [ ] Push to registry (DockerHub/ECR)
  - [ ] Deploy staging
  - [ ] Deploy prod (manual approval)

- [ ] **Pre-commit hooks**
  - [ ] ruff format
  - [ ] ruff check
  - [ ] pytest (local subset?)

### Monitoring & Logging

- [ ] **Structured logging** (structlog est déjà setup)
  - [ ] API logs (requests, responses)
  - [ ] Worker logs (job execution, errors)
  - [ ] DB query logs (slow queries)
  - [ ] MQTT message logs (high-level, pas PII)

- [ ] **Metrics**
  - [ ] API response times
  - [ ] Worker job durations
  - [ ] DB connection pool stats
  - [ ] Box online/offline status
  - [ ] Prise success/error rates

- [ ] **Alerting**
  - [ ] Worker downtime
  - [ ] Database errors
  - [ ] MQTT broker offline
  - [ ] Box maintenance alerts
  - [ ] High error rate

- [ ] **Tracing** (optionnel)
  - [ ] Jaeger / OpenTelemetry?

---

## 🔐 Sécurité — **PRIORITÉ: MOYENNE**

### Code

- [ ] **Secret management**
  - [ ] ❌ Jamais hardcoder secrets
  - [ ] ✅ Utiliser variables d'environnement (cf `.env`)
  - [ ] ❌ Jamais commiter `.env`
  - [ ] Optionnel: Vault pour prod

- [ ] **Input validation**
  - [ ] Pydantic models pour tous les inputs
  - [ ] Validation côté DB (constraints)
  - [ ] MQTT payload validation

- [ ] **SQL Injection**
  - [ ] ✅ SQLAlchemy ORM résiste (pas de string concat)
  - [ ] Vérifier: Pas de `execute(f"SELECT ...")`

- [ ] **CSRF**
  - [ ] API stateless (JWT) = pas de CSRF token nécessaire
  - [ ] Vérifier: Headers CORS strictes

### Infrastructure

- [ ] **TLS/SSL**
  - [ ] API: HTTPS partout (même dev?)
  - [ ] MQTT: TLS 1.2+ + mTLS certs
  - [ ] Certificats valides (pas auto-signed en prod)

- [ ] **Authentication**
  - [ ] ✅ Keycloak OIDC setup
  - [ ] ✅ JWT validation
  - [ ] Session timeouts

- [ ] **Authorization (RBAC)**
  - [ ] ✅ Tenant isolation
  - [ ] ✅ Per-endpoint checks
  - [ ] Audit qui a accès quoi

- [ ] **Encryption**
  - [ ] ✅ PII au repos (Fernet champs `c_*`)
  - [ ] ✅ Clé d'encryption forte (Fernet)
  - [ ] Rotation clé? (stratégie?)

- [ ] **Audit**
  - [ ] ✅ Event table complète
  - [ ] ✅ Logs structurés
  - [ ] Retention logs (ex: 90 jours?)

**Audit de sécurité**: À planifier (OWASP Top 10 review)

---

## 📦 API Endpoints — **PRIORITÉ: MOYENNE**

Actuellement implémenté:
- ✅ Health check
- ✅ Keycloak OAuth2 flows (partial)
- ✅ Tenant management (partial)
- ✅ Patient CRUD (partial)
- ✅ Invitation system (partial)

À compléter:
- [ ] **Prescriptions**
  - [ ] POST /api/v1/prescriptions
  - [ ] GET /api/v1/prescriptions/{id}
  - [ ] PATCH /api/v1/prescriptions/{id}
  - [ ] GET /api/v1/prescriptions/{id}/schedule

- [ ] **Boxes**
  - [ ] GET /api/v1/boxes
  - [ ] POST /api/v1/boxes
  - [ ] GET /api/v1/boxes/{id}
  - [ ] POST /api/v1/boxes/{id}/dispense (Trigger prise)
  - [ ] GET /api/v1/boxes/{id}/telemetry
  - [ ] PATCH /api/v1/boxes/{id}/config

- [ ] **Wheels & Slots**
  - [ ] GET /api/v1/wheels
  - [ ] POST /api/v1/wheels (assign to box)
  - [ ] GET /api/v1/wheels/{id}/slots
  - [ ] PATCH /api/v1/wheels/{id}/slots/{slot_id}

- [ ] **Telemetry & Events**
  - [ ] GET /api/v1/events (audit trail, filterable)
  - [ ] GET /api/v1/boxes/{id}/telemetry (time series)

- [ ] **Alerts & Supervision**
  - [ ] GET /api/v1/alerts (active alerts)
  - [ ] PATCH /api/v1/alerts/{id} (acknowledge)
  - [ ] GET /api/v1/dashboard (KPIs, overview)

Voir `docs/readme.md` pour specs détaillées.

---

## 🐛 Known Issues & Bugs

### Critical

- [ ] **MQTT mTLS certs**: Pas de setup certificats en dev (blocker pour iotworker)
- [ ] **Database schema**: Relation Prescription ↔ Box unclear (voir `docs/database.md`)

### High

- [ ] **Keycloak setup**: Token claim tenant_id pas conforme?
- [ ] **Scheduler persistence**: Pas clear comment persister job state si worker crash

### Medium

- [ ] **API error handling**: Format réponse inconsistent
- [ ] **Logging**: Pas de correlation IDs entre services
- [ ] **Performance**: N+1 queries possibles (ORM)

### Low

- [ ] **Type hints**: Quelques `Any` à remplacer
- [ ] **Documentation**: README outdated en certains endroits

---

## 🎯 Milestones

### Milestone 1: MVP (Fin Décembre 2025)

- ✅ Architecture documentée
- 🚧 API endpoints de base (CRUD entités)
- 🚧 IoT Worker fonctionnel
- 🚧 Scheduler minimal
- ⏳ Tests 50%+
- ⏳ Docker Compose dev

### Milestone 2: Beta (Janvier 2026)

- [ ] API endpoints complets
- [ ] IoT Worker production-ready
- [ ] Scheduler complet (all jobs)
- [ ] Tests 80%+
- [ ] Kubernetes manifests
- [ ] Monitoring & logging

### Milestone 3: Release (Février 2026)

- [ ] Security audit
- [ ] Performance optimization
- [ ] Documentation complète
- [ ] CI/CD pipeline
- [ ] Admin dashboard
- [ ] Production deployment

---

## 📞 Questions ouvertes

1. **Keycloak tenant_id claim**: Comment injecter dans JWT? Custom mapper?
2. **MQTT certificats dev**: Utiliser self-signed pour dev? Comment loader en Python?
3. **Database schema Prescription**: Lier directement à Box ou via Order?
4. **Scheduler persistence**: Event sourcing ou simple job queue suffisant?
5. **Alertes**: Push notifications? Email? In-app only?
6. **Admin dashboard**: Requis pour MVP ou backlog?

---

## 🔗 Références utiles

- [`docs/architecture.md`](./docs/architecture.md) — Design système complet
- [`docs/database.md`](./docs/database.md) — Schéma DB
- [`docs/readme.md`](./docs/readme.md) — API endpoints (français)
- [`readme.md`](./readme.md) — Quick start
- [`pyproject.toml`](./pyproject.toml) — Dépendances & config

---

## 📝 Notes

- **Convention code**: Docstrings & comments français (voir Ruff config)
- **Linting**: `poetry run ruff check medbox/`
- **Format**: `poetry run ruff format medbox/`
- **Tests**: `pytest tests/` ou `pytest tests/test_XXXX.py -v`

---

**Statut**: 🚧 En cours | **Dernière mise à jour**: Décembre 2025
