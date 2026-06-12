# 📋 TODO MEDBOX - Roadmap & Tâches en cours

**Date**: Juin 2026 | **Version**: 0.1.0

---

## 📊 Vue d'ensemble des tâches

| Statut | Tâches | % Complet |
|--------|--------|----------|
| ✅ | Documentation (architecture, readme) | 100% |
| ✅ | Architecture multi-tenant + Auth (Keycloak/JWT) | 100% |
| ✅ | CRUD entités (Box, Patient, Prescription, Wheel…) | 90% |
| ✅ | IoT Worker (MQTT handlers + telemetry) | 80% |
| ✅ | Scheduler Worker (preload 2x/jour) | 90% |
| ✅ | WheelLoadPlan — moulinette + distributions | 100% |
| 🚧 | WebSockets (notifications + live updates) | 0% |
| 🚧 | Tests & Coverage | 25% |
| ⏳ | Déploiement & DevOps | 0% |
| ⏳ | Admin Dashboard | 0% |

---

## ✅ Implémenté (état réel juin 2026)

### IoT Worker
- ✅ Connexion MQTT async (aiomqtt, mTLS)
- ✅ `handle_take_event` — marque `PrescriptionScheduleItem` → `taken` (confirmé par la medbox)
- ✅ `handle_error_event` — marque item → `error`, box → `maintenance`
- ✅ `telemetry.py` — RTC drift, stockage Telemetry/health, sync_time si drift >10min

### Scheduler Worker
- ✅ `preload_upcoming_distributions` — 2×/jour (08:00 + 20:00 UTC) : envoie les 3 prochaines distributions par box via MQTT `cmd/preload`
- ✅ `cleanup_job` — quotidien 02:00 UTC : expire invitations périmées
- ✅ `monitor_boxes` — toutes les 5 min : surveillance état boxes

### WheelLoadPlan — Moulinette
- ✅ `WheelLoadPlan` model (draft → confirmed → active → exhausted)
- ✅ `WheelLoadPlanPrescription` — association plan ↔ ordonnances (plusieurs prescriptions par plan)
- ✅ `WheelLoadPlanService.create()` — croise les ordonnances, calcule les 21 cases, retourne la liste de remplissage
- ✅ `WheelLoadPlanService.confirm()` — soignant confirme le remplissage physique → crée les `PrescriptionScheduleItem` + monte la roue sur la box
- ✅ `WheelLoadPlanRepository`
- ✅ `PrescriptionScheduleItem` refactorisé : `wheel_slot_id` + `wheel_load_plan_id` (plus de `prescription_item_id` singulier)
- ✅ Statuts PSI simplifiés : `pending | taken | error` (plus de `dispatched` ni `missed`)
- ✅ Migration Alembic : `a1b2c3d4e5f6`

### API REST
- ✅ Auth OAuth2 / Keycloak
- ✅ Tenant, User, Invitation
- ✅ Patient CRUD
- ✅ Box CRUD + stats + telemetry
- ✅ Box Admin (configure, reset)
- ✅ Prescription CRUD
- ✅ Wheel + WheelSlot
- ✅ GlobalMedication
- ✅ Events (audit trail, filterable)
- ✅ Health check
- ✅ `GET /api/v1/wheel-load-plans` — liste des plans du tenant
- ✅ `POST /api/v1/wheel-load-plans` — lance la moulinette, retourne la liste de remplissage
- ✅ `GET /api/v1/wheel-load-plans/{id}` — récupère un plan avec sa liste de remplissage
- ✅ `POST /api/v1/wheel-load-plans/{id}/confirm` — soignant confirme le remplissage physique

### DB / Core
- ✅ Modèles : Tenant, User, Patient, Box, Wheel, WheelSlot, WheelSlotPrescriptionItem, Prescription, PrescriptionItem, PrescriptionScheduleItem, WheelLoadPlan, WheelLoadPlanPrescription, Event, Telemetry, GlobalMedication, Invitation
- ✅ Repositories (15) avec tenant scoping
- ✅ Chiffrement PII (Fernet, champs `c_*`)
- ✅ RBAC (rôles par tenant)

---

## 🚧 À implémenter — PRIORITÉ HAUTE

### 1. WebSocket — Notifications UX utilisateur

**Responsabilité**: Confirmer les actions du soignant en temps réel (feedback type toast/snackbar) et signaler les alertes importantes.

#### Exemples de notifications attendues
- "Plan de chargement créé" / "Roue assignée à la medbox"
- "Sauvegardé" (mise à jour prescription, config box…)
- "Erreur : roue non disponible"
- "Alerte : batterie critique sur Box #42"
- "Alerte : Box #12 en maintenance (roue bloquée)"

#### Sous-tâches

- [ ] **Setup WebSocket** (FastAPI natif)
  - [ ] Endpoint : `ws://api/v1/ws/notifications?token=<jwt>`
  - [ ] Auth JWT sur handshake (rejeter si token invalide)
  - [ ] Tenant isolation : un utilisateur ne reçoit que les events de son tenant

- [ ] **Connection Manager** (`medbox/api/ws/manager.py`)
  - [ ] Registre connexions : `{ tenant_id → { user_id → [ws_connections] } }`
  - [ ] `notify_user(user_id, event)` — notif ciblée
  - [ ] `broadcast_tenant(tenant_id, event)` — tous les soignants du tenant
  - [ ] Gestion déconnexion propre + heartbeat ping/pong

- [ ] **Types de notifications**
  - [ ] `ACTION_SUCCESS` — confirmation action soignant
  - [ ] `ACTION_ERROR` — échec avec message lisible
  - [ ] `BOX_ALERT` — alerte box (offline, batterie critique, maintenance)
  - [ ] `TAKE_EVENT` — distribution confirmée ou en erreur (informatif)

- [ ] **Intégration workers**
  - [ ] `handle_error_event` + `telemetry.py` → Redis pub/sub → WS broadcast
  - [ ] `WheelLoadPlanService.confirm()` → notif "Roue assignée"

- [ ] **Tests**
  - [ ] Test connexion / auth invalide → rejet
  - [ ] Test isolation tenant
  - [ ] Test broadcast après action

**Fichiers** : `medbox/api/ws/manager.py` (à créer), `medbox/api/routes/v1/ws.py` (à créer)

---

### 2. WebSocket — Live updates dashboard

**Responsabilité**: Mise à jour de certaines vues sans re-fetch REST complet.

> ⚠️ À décider avec le front : si polling REST toutes les 30s suffit, déprioriser.

- [ ] État live d'une box : `{status, battery_level, last_seen}` — page détail box
- [ ] Changement statut distribution : `{item_id, status, taken_at}` — page planning
- [ ] Canaux : `ws://api/v1/ws/boxes/{box_id}/live` + `ws://api/v1/ws/distributions/live`
- [ ] Partage infrastructure WS avec §1 (même Connection Manager)
- [ ] SSE en alternative si unidirectionnel suffit

**Fichiers** : partagé avec §1 — `medbox/api/ws/`

---

## 🚧 À compléter — PRIORITÉ MOYENNE

### Tests & Coverage — Objectif 80%+

**Coverage actuelle** : ~25%

#### Tests existants ✅
```
tests/
├── test_crypto.py
├── test_encrypted_type.py
├── test_encrypted_update.py
├── test_patient.py
├── test_global_medication.py
├── test_box.py
├── test_wheel.py
├── test_prescription.py
├── test_admin.py
├── test_invitation.py
└── ... (14 fichiers total, 119 tests)
```

#### À ajouter
- [ ] `test_wheel_load_plan.py` — moulinette (cas nominal, cas saturé >21 cases, prescriptions incompatibles)
- [ ] `test_wheel_load_plan.py` — confirm (PSI créés, roue montée, statut plan)
- [ ] `test_preload.py` — job preload (3 items par box, skip box sans items, mock MQTT)
- [ ] Tests WebSocket (§1 et §2 ci-dessus)
- [ ] Tests services : `security.py`, `tenant.py`, `tenant_right.py`
- [ ] Tests repositories : CRUD, tenant scoping, soft deletes
- [ ] Integration test : multi-tenant isolation end-to-end

---

### API — Endpoints manquants

- [ ] `GET /api/v1/wheels?status=in_stock` — roues disponibles en stock (utilisé avant création WheelLoadPlan)
- [ ] `GET /api/v1/alerts` — alertes actives
- [ ] `PATCH /api/v1/alerts/{id}` — acquittement alerte

---

## ⏳ Backlog — PRIORITÉ BASSE

### Déploiement & DevOps

- [ ] Dockerfiles (API, IoT Worker, Scheduler Worker)
- [ ] docker-compose.yml dev complet (Postgres, Redis, EMQX, Keycloak)
- [ ] CI/CD GitHub Actions (lint, tests, build, push)
- [ ] Pre-commit hooks (ruff format + check)
- [ ] Kubernetes manifests (prod)
- [ ] Monitoring : structured logging corrélé inter-services, Grafana/Prometheus

### Sécurité

- [ ] Audit OWASP Top 10
- [ ] Stratégie rotation clé Fernet
- [ ] Headers CORS stricts vérifiés
- [ ] Retention logs configurée (ex. 90 jours)
- [ ] MQTT : vérifier ACL topics par tenant/box

### Documentation code

- [ ] Docstrings modèles `core/db/models/*.py`
- [ ] Docstrings services `core/services/*.py`
- [ ] README dev : comment ajouter endpoint, modèle, job, handler MQTT

---

## 🐛 Known Issues

### Critical
- [ ] **MQTT mTLS certs** : setup certificats dev (blocker tests iotworker en isolation)

### High
- [ ] **Keycloak** : claim `tenant_id` dans JWT à vérifier conforme
- [ ] **Preload payload** : format exact du JSON `cmd/preload` à aligner avec le firmware

### Medium
- [ ] **API error handling** : format réponse erreur inconsistant
- [ ] **Logging** : pas de correlation IDs entre services
- [ ] **N+1 queries** : à vérifier sur list endpoints avec relations

---

## 🎯 Milestones

### Milestone 1 — MVP (Juillet 2026)
- ✅ Architecture + Auth + CRUD entités
- ✅ IoT Worker (take/error events)
- ✅ WheelLoadPlan + moulinette + distributions
- ✅ Preload 2x/jour vers les medboxes
- 🚧 WebSockets notifications (§1 minimal)
- 🚧 Tests 50%+
- ⏳ Docker Compose dev complet

### Milestone 2 — Beta (Septembre 2026)
- [ ] WebSockets live updates complets (§2)
- [ ] Tests 80%+
- [ ] Kubernetes manifests
- [ ] Monitoring & alerting

### Milestone 3 — Release (Novembre 2026)
- [ ] Security audit
- [ ] Performance optimization
- [ ] CI/CD pipeline complet
- [ ] Admin dashboard
- [ ] Documentation complète

---

## 📞 Questions ouvertes

1. **WebSocket vs SSE** : SSE suffit pour les live updates (unidirectionnel) ? ou besoin de bi-directionnel ?
2. **Preload payload** : format exact du JSON `cmd/preload` à aligner avec firmware medbox
3. **Reconnexion WS** : stocker les events dans Redis pour replay ? quelle durée de rétention ?
4. **Roues en stock** : comment le soignant sélectionne-t-il la roue avant de créer le plan ? (endpoint `/wheels?status=in_stock` à ajouter)
5. **Keycloak tenant_id claim** : custom mapper confirmé ou alternative ?
6. **Admin dashboard** : requis pour MVP ou backlog ?

---

## 🔗 Références

- [`docs/architecture.md`](./docs/architecture.md)
- [`docs/database.md`](./docs/database.md)
- [`docs/readme.md`](./docs/readme.md)
- [`readme.md`](./readme.md)
- [`pyproject.toml`](./pyproject.toml)

---

**Statut** : 🚧 En cours | **Dernière mise à jour** : Juin 2026
