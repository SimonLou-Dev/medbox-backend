# 📋 TODO MEDBOX - Roadmap & Tâches en cours

**Date**: Juin 2026 | **Version**: 0.1.0

---

## 📊 Vue d'ensemble des tâches

| Statut | Tâches | % Complet |
|--------|--------|----------|
| ✅ | Documentation (architecture, readme) | 100% |
| ✅ | Architecture multi-tenant + Auth (Keycloak/JWT) | 100% |
| ✅ | CRUD entités (Box, Patient, Prescription, Wheel…) | 90% |
| ✅ | IoT Worker (MQTT handlers + telemetry) | 75% |
| ✅ | Scheduler Worker (dispatch + scheduling) | 70% |
| 🚧 | WebSockets (notifications + live updates) | 0% |
| 🚧 | Tâches métier manquantes (pre-load + prescription→distribution) | 0% |
| 🚧 | Tests & Coverage | 25% |
| ⏳ | Déploiement & DevOps | 0% |
| ⏳ | Admin Dashboard | 0% |

---

## ✅ Implémenté (état réel juin 2026)

### IoT Worker
- ✅ Connexion MQTT async (aiomqtt, mTLS)
- ✅ `send_dispense_command` — publie `medbox/box/{uid}/cmd/dispense` QoS 2
- ✅ `handle_take_event` — marque `PrescriptionScheduleItem` → `taken`
- ✅ `handle_error_event` — marque item → `error`, box → `maintenance`
- ✅ `telemetry.py` — RTC drift, stockage Telemetry/health, sync_time si drift >10min

### Scheduler Worker
- ✅ `calculate_prescription_scheduling` — génère PrescriptionScheduleItems pour les 24h suivantes (fréquence times_per_day)
- ✅ `dispatch_scheduled_takes` — toutes les 5 min, dispatch via Celery les items dus
- ✅ `cleanup_job` — quotidien 02:00 UTC : expire invites, marque items missed, archive events

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

### DB / Core
- ✅ Modèles : Tenant, User, Patient, Box, Wheel, WheelSlot, Prescription, PrescriptionItem, PrescriptionScheduleItem, Event, Telemetry, GlobalMedication, Invitation
- ✅ 13 repositories avec tenant scoping
- ✅ Chiffrement PII (Fernet, champs `c_*`)
- ✅ RBAC (rôles par tenant)

---

## 🚧 À implémenter — PRIORITÉ HAUTE

### 1. Pre-load distributions vers les medboxes — **NOUVEAU**

**Responsabilité**: 2× par jour, envoyer à chaque medbox les 3 prochaines distributions prévues, pour qu'elle puisse fonctionner en mode offline.

#### Sous-tâches

- [ ] **Job Scheduler** `preload_upcoming_distributions`
  - [ ] Requête : pour chaque box active, récupérer les 3 prochains `PrescriptionScheduleItem` (status=`pending`, scheduled_at > now, triés ASC)
  - [ ] Formatter payload MQTT (liste des 3 prochaines : prescription_id, slot_id, scheduled_at, medications)
  - [ ] Publier `medbox/box/{box_id}/cmd/preload` avec QoS 1
  - [ ] Logger le résultat par box
  - [ ] Fréquence : 2× par jour (ex. 08:00 et 20:00 UTC)
  - [ ] Gérer les boxes offline (skip + log, pas d'erreur critique)

- [ ] **Payload MQTT** format `preload`
  - [ ] Définir schéma JSON du payload (à aligner avec firmware)
  - [ ] Validation Pydantic avant envoi

- [ ] **Tests**
  - [ ] Test calcul des 3 prochains items par box
  - [ ] Test skip box offline
  - [ ] Test publication MQTT (mock)

**Fichiers** : `medbox/schedulerworker/tasks/preload.py` (à créer), `medbox/iotworker/tasks/` (payload helpers)

---

### 2. Tâche asynchrone : Prescription → Distributions — **NOUVEAU**

**Responsabilité**: **Seul moyen de créer des distributions.** Le soignant sélectionne des ordonnances, le système choisit une roue en stock, le soignant choisit la medbox cible, puis le système calcule les `PrescriptionScheduleItem` en tenant compte des 22 cases (21 utiles) de la medbox.

> ⚠️ Le job `calculate_prescription_scheduling` existant NE crée PAS de distributions — il est à revoir/supprimer ou cantonner à un rôle différent. Toutes les distributions passent obligatoirement par ce flux.

#### Flux métier

```
Soignant sélectionne ordonnances
        ↓
API valide + identifie roues disponibles en stock
        ↓
Soignant choisit la medbox cible
        ↓
Tâche Celery : calcule les distributions
  - 21 cases utiles dans la medbox
  - Chaque case = 1 médicament sur 1 créneau horaire
  - Répartition selon fréquence prescription (times_per_day)
        ↓
PrescriptionScheduleItems créés en DB
        ↓
Notification WS → soignant : "Distributions générées"
```

#### Sous-tâches

- [ ] **Endpoint API** `POST /api/v1/prescriptions/generate-distributions`
  - [ ] Body : `{ prescription_ids: [], box_id: uuid }`
  - [ ] Auth : soignant authentifié, tenant scoping obligatoire
  - [ ] Vérifier que la box appartient au tenant
  - [ ] Identifier les roues disponibles en stock pour ces prescriptions
  - [ ] Retour immédiat `{ task_id }` — traitement async Celery
  - [ ] Notification WS à la fin (voir §3)

- [ ] **Endpoint API** `GET /api/v1/prescriptions/available-wheels`
  - [ ] Retourne les roues en stock compatibles avec les prescriptions sélectionnées
  - [ ] Utilisé par le front pour présenter le choix à l'utilisateur avant soumission

- [ ] **Tâche Celery** `generate_distributions_for_prescriptions(prescription_ids, box_id, wheel_id, tenant_id)`
  - [ ] Valider appartenance tenant (prescriptions, box, roue)
  - [ ] Récupérer les 21 cases utiles de la medbox
  - [ ] Calculer la répartition des prises selon fréquence (times_per_day × durée prescription)
  - [ ] Mapper chaque prise → case disponible (slot assignment)
  - [ ] Créer les `PrescriptionScheduleItem` (idempotent : skip si créneau déjà occupé)
  - [ ] Assigner la roue à la box en DB
  - [ ] Retourner : nb items créés, nb cases utilisées / 21, conflits éventuels
  - [ ] Publier event Redis → WS notification soignant

- [ ] **Logique cases (21 utiles sur 22)**
  - [ ] Modéliser "capacité restante" d'une medbox (cases libres)
  - [ ] Gérer conflits si cases insuffisantes pour toutes les prescriptions
  - [ ] Alerter si remplissage > 90% des cases

- [ ] **Revoir `calculate_prescription_scheduling`**
  - [ ] Clarifier son rôle si les distributions ne passent plus par lui
  - [ ] Option A : le supprimer
  - [ ] Option B : le garder pour re-planifier les items `missed` automatiquement

- [ ] **Tests**
  - [ ] Test flux complet (prescriptions → roue → box → items créés)
  - [ ] Test calcul répartition 21 cases (cas nominal, cas saturé)
  - [ ] Test idempotence (appel 2× = même résultat, pas de doublons)
  - [ ] Test prescription d'un autre tenant → 403
  - [ ] Test box inexistante → 404
  - [ ] Test capacité dépassée → erreur métier claire

**Fichiers** :
- `medbox/api/routes/v1/prescription.py` — nouveaux endpoints
- `medbox/schedulerworker/tasks/distributions.py` (à créer) — logique calcul
- `medbox/core/services/distribution.py` (à créer) — slot assignment, capacité

---

### 3. WebSocket — Notifications UX utilisateur — **NOUVEAU**

**Responsabilité**: Confirmer les actions du soignant en temps réel (feedback immédiat type toast/snackbar) et signaler les alertes importantes. **Usage principal : retour d'action, pas monitoring continu.**

#### Exemples de notifications attendues
- "Distributions générées avec succès" (fin §2)
- "Medbox assignée" (roue chargée confirmée)
- "Sauvegardé" (mise à jour prescription, config box…)
- "Erreur : case insuffisante" (échec génération distributions)
- "Alerte : batterie critique sur Box #42"
- "Alerte : Box #12 hors ligne"

#### Sous-tâches

- [ ] **Setup WebSocket** (FastAPI natif — suffisant pour ce cas d'usage)
  - [ ] Endpoint : `ws://api/v1/ws/notifications?token=<jwt>`
  - [ ] Auth JWT sur handshake (rejeter si token invalide)
  - [ ] Tenant isolation : un utilisateur ne reçoit que les events de son tenant

- [ ] **Connection Manager**
  - [ ] Registre connexions actives : `{ tenant_id → { user_id → [ws_connections] } }`
  - [ ] `notify_user(user_id, event)` — notif ciblée 1 utilisateur
  - [ ] `broadcast_tenant(tenant_id, event)` — broadcast tous les soignants du tenant
  - [ ] Gestion déconnexion propre + heartbeat

- [ ] **Types de notifications**
  - [ ] `ACTION_SUCCESS` — confirmation action soignant (distributions créées, box assignée, sauvegarde)
  - [ ] `ACTION_ERROR` — échec action soignant avec message d'erreur lisible
  - [ ] `BOX_ALERT` — alerte box (offline, batterie critique, maintenance)
  - [ ] `TAKE_EVENT` — prise effectuée ou en erreur (informatif, pas bloquant)

- [ ] **Intégration**
  - [ ] Celery tasks (§2) → publie sur Redis channel → WS broadcast
  - [ ] IoT Worker (`handle_error_event`, `telemetry.py`) → Redis → WS broadcast

- [ ] **Tests**
  - [ ] Test connexion / auth invalide → rejet
  - [ ] Test isolation tenant
  - [ ] Test réception notification après action (mock Celery → WS)

**Fichiers** : `medbox/api/ws/` (à créer), `medbox/api/ws/manager.py`, `medbox/api/routes/v1/ws.py`

---

### 4. WebSocket — Live updates dashboard — **NOUVEAU**

**Responsabilité**: Flux pour mettre à jour certaines vues du dashboard sans re-fetch complet (état box, liste distributions). Secondaire par rapport à §3 — évaluer si SSE suffit.

#### Périmètre (à affiner selon besoins front)

- [ ] État live d'une box : `{box_id, status, battery_level, last_seen}` — utile sur la page détail box
- [ ] Changement statut distribution : `{item_id, status, taken_at}` — utile sur le planning
- [ ] Events récents d'une box — utile sur le détail box

> **Note** : si le front fait juste du polling REST toutes les 30s, ce §4 peut être dépriorisé / mis en backlog. À décider avec l'équipe front.

- [ ] Canaux : `ws://api/v1/ws/boxes/{box_id}/live` et `ws://api/v1/ws/distributions/live`
- [ ] Partage de l'infrastructure WS avec §3 (même Connection Manager)
- [ ] SSE en alternative si unidirectionnel suffit

**Fichiers** : partagé avec §3 — `medbox/api/ws/`

---

## 🚧 À compléter — PRIORITÉ MOYENNE

### Tests & Coverage — Objectif 80%+

**Coverage actuelle** : ~25% (crypto, API multi-tenant, modèles de base)

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
└── ... (14 fichiers total)
```

#### À ajouter
- [ ] Tests endpoints WebSocket (§3 et §4)
- [ ] Tests tâche `generate_distributions_for_prescriptions` (§2)
- [ ] Tests job `preload_upcoming_distributions` (§1)
- [ ] Tests services : `security.py`, `tenant.py`, `tenant_right.py`
- [ ] Tests repositories : base CRUD, tenant scoping, soft deletes
- [ ] Integration test : multi-tenant isolation end-to-end
- [ ] Tests schedulerworker : idempotence, error/retry

---

### API — Endpoints manquants

- [ ] `POST /api/v1/prescriptions/generate-distributions` (voir §2)
- [ ] `GET /api/v1/tasks/{task_id}/status` — polling état tâche Celery
- [ ] `GET /api/v1/alerts` — alertes actives
- [ ] `PATCH /api/v1/alerts/{id}` — acquittement alerte
- [ ] `POST /api/v1/boxes/{id}/dispense` — déclenchement manuel prise

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
- [ ] **Scheduler persistence** : état job si worker crash non géré

### Medium
- [ ] **API error handling** : format réponse erreur inconsistant
- [ ] **Logging** : pas de correlation IDs entre services
- [ ] **N+1 queries** : à vérifier sur list endpoints avec relations

---

## 🎯 Milestones

### Milestone 1 — MVP (Juillet 2026)
- ✅ Architecture + Auth + CRUD entités
- ✅ IoT Worker + Scheduler Worker de base
- 🚧 WebSockets notifications (§3 minimal)
- 🚧 Pre-load distributions (§1)
- 🚧 Tests 50%+
- ⏳ Docker Compose dev complet

### Milestone 2 — Beta (Septembre 2026)
- [ ] WebSockets live updates complets (§4)
- [ ] Tâche prescription→distributions (§2)
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
2. **Pre-load payload** : format exact du payload `preload` à aligner avec le firmware des medboxes
3. **Celery task status** : polling REST ou WebSocket pour informer le front de l'avancement de `generate_distributions` ?
4. **Reconnexion WS** : stocker les events dans Redis pour replay ? quelle durée de rétention ?
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
