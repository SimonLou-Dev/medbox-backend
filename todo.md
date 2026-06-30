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
| ✅ | WebSockets (notifications + live updates) | 95% |
| 🚧 | Tests & Coverage | 55% |
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

### 1. WebSocket — Notifications UX utilisateur ✅

**Responsabilité**: Confirmer les actions du soignant en temps réel (feedback type toast/snackbar) et signaler les alertes importantes.

- ✅ **Setup WebSocket** — `ws://api/v1/ws/notifications?token=<jwt>`
- ✅ **Auth JWT sur handshake** — rejet code 4001 si token invalide / tenant manquant
- ✅ **Connection Manager** (`medbox/api/ws/manager.py`) — registre, notify_user, broadcast_tenant, heartbeat ping/pong
- ✅ **Types de notifications** — ACTION_SUCCESS, ACTION_ERROR, BOX_ALERT, TAKE_EVENT, BOX_STATUS, DISTRIBUTION_UPDATE
- ✅ **Intégration workers** — handle_error_event, handle_take_event, telemetry.py, WheelLoadPlanService.confirm() → Redis pub/sub → WS
- ✅ **Tests** (`tests/test_ws.py` — 24 tests) — auth, isolation tenant, ping/pong, events

---

### 2. WebSocket — Live updates dashboard ✅

- ✅ `ws://api/v1/ws/live?token=<jwt>&box_id=<uuid>` — BOX_STATUS, DISTRIBUTION_UPDATE
- ✅ Infrastructure partagée avec §1 (même Connection Manager)

> ⚠️ À décider avec le front : si polling REST 30s suffit, les events BOX_STATUS/DISTRIBUTION_UPDATE peuvent rester non-câblés côté front.

---

## 🚧 À compléter — PRIORITÉ MOYENNE

### Tests & Coverage — Objectif 80%+

**Coverage actuelle** : ~55% (176 tests)

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
├── test_tenant.py
├── test_api_multi_tenant.py
├── test_wheel_load_plan.py   — moulinette + confirm + list
├── test_preload.py           — job preload + list_upcoming_by_box
└── test_ws.py                — ConnectionManager + events + auth endpoint
```

#### À ajouter
- [ ] Tests services : `security.py`, `tenant_right.py`
- [ ] Tests repositories : CRUD, tenant scoping, soft deletes
- [ ] Tests IoT worker : handle_take_event, handle_error_event (avec mocks Redis/DB)

---

### API — Endpoints ✅

- ✅ `GET /api/v1/wheels?status=in_stock` — roues disponibles
- ✅ `GET /api/v1/alerts` — alertes actives
- ✅ `PATCH /api/v1/alerts/{id}` — acquittement alerte

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
