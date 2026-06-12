# 🔌 WebSocket — Notifications temps réel

**Date**: Juin 2026 | **Status**: 🟢 Stable

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Connexion](#connexion)
4. [Canaux](#canaux)
5. [Événements](#événements)
6. [Heartbeat](#heartbeat)
7. [Codes de fermeture](#codes-de-fermeture)
8. [Exemples client](#exemples-client)

---

## Vue d'ensemble

Le backend expose deux endpoints WebSocket pour pousser des événements en temps réel vers le front :

| Endpoint | Usage |
|---|---|
| `GET /v1/ws/notifications` | Notifications UX (confirmations, alertes) |
| `GET /v1/ws/live` | État live du dashboard (boxes, distributions) |

Les deux canaux utilisent le **même bus Redis pub/sub** pour relayer les messages des workers Celery (IoT, Scheduler) vers les clients connectés.

---

## Architecture

```
Workers Celery                     Process API                    Client browser
─────────────────────              ──────────────────             ──────────────
IoT worker                         ConnectionManager              WS client
  handle_take_event()   ──────►   ws:tenant:{tid}    ──────────► /ws/notifications
  handle_error_event()             ws:user:{tid}:{uid}            /ws/live

Scheduler worker
  monitor_boxes()       ──────►   Redis pub/sub
  preload (futur)
```

**Flux d'un événement :**

1. Un worker Celery appelle `publish_to_tenant(tenant_id, event)` ou `publish_to_user(tenant_id, user_id, event)`.
2. Le worker publie le JSON de l'événement sur un canal Redis (`ws:tenant:…` ou `ws:user:…`).
3. Chaque connexion WS active a une coroutine `redis_listener` qui écoute ces deux canaux.
4. À réception, `redis_listener` forward le message brut au client via `ws.send_text()`.

**Pourquoi Redis et pas une diffusion directe ?**
Les workers Celery tournent dans des processus séparés du process API FastAPI. Ils ne peuvent pas accéder directement au `ConnectionManager` en mémoire. Redis sert de bus inter-processus.

---

## Connexion

L'authentification se fait via le JWT Keycloak passé en **query param** (les navigateurs ne supportent pas les headers custom sur les WebSocket).

```
wss://api/v1/ws/notifications?token=<JWT>
wss://api/v1/ws/live?token=<JWT>
wss://api/v1/ws/live?token=<JWT>&box_id=<UUID>   # filtrage optionnel
```

Le token est validé au moment de l'upgrade HTTP → WebSocket. Si invalide, la connexion est fermée immédiatement avec le code `4001`.

**Claims JWT requis :**

| Claim | Description |
|---|---|
| `sub` | UUID de l'utilisateur (Keycloak subject) |
| `tenant_id` ou `tenantId` | UUID du tenant |

---

## Canaux

### `/ws/notifications`

Reçoit les événements liés aux **actions utilisateur** et aux **alertes boxes** :

- `ACTION_SUCCESS` — confirmation d'une action soignant (ex : plan chargé)
- `ACTION_ERROR` — échec d'une action
- `BOX_ALERT` — alerte sur une box (hors ligne, maintenance)
- `TAKE_EVENT` — distribution confirmée ou en erreur

### `/ws/live`

Reçoit les événements de **mise à jour live du dashboard** :

- `BOX_STATUS` — changement d'état d'une box
- `DISTRIBUTION_UPDATE` — changement de statut d'une distribution

> Note : les deux canaux reçoivent actuellement les mêmes messages Redis. Le paramètre `box_id` sur `/ws/live` est exposé pour un filtrage futur côté serveur.

---

## Événements

Tous les messages ont la même enveloppe JSON :

```json
{
  "type": "NOM_EVENEMENT",
  "payload": { ... },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

### ACTION_SUCCESS

Confirmation d'une action soignant (envoyé uniquement à l'utilisateur qui a déclenché l'action).

```json
{
  "type": "ACTION_SUCCESS",
  "payload": {
    "message": "Roue chargée et assignée à la medbox",
    "plan_id": "uuid",
    "box_id": "uuid",
    "distributions_created": 21
  },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

**Émis par :** `WheelLoadPlanService.confirm()`

---

### ACTION_ERROR

Échec d'une action.

```json
{
  "type": "ACTION_ERROR",
  "payload": {
    "message": "Impossible de confirmer le plan",
    "code": "PLAN_ALREADY_ACTIVE"
  },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

---

### BOX_ALERT

Alerte sur une box, diffusée à **tous les soignants connectés du tenant**.

```json
{
  "type": "BOX_ALERT",
  "payload": {
    "box_id": "uuid",
    "alert_type": "offline",
    "detail": "Box BOX-001 hors ligne depuis 10 min"
  },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

`alert_type` : `offline` | `maintenance` | `error`

**Émis par :** `monitor_boxes` (offline), `handle_error_event` (maintenance/error)

---

### TAKE_EVENT

Résultat d'une distribution (confirmée par la medbox ou en erreur).

```json
{
  "type": "TAKE_EVENT",
  "payload": {
    "box_uid": "BOX-ABC123",
    "item_id": "uuid-du-psi",
    "status": "taken"
  },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

`status` : `taken` | `error`

**Émis par :** `handle_take_event`, `handle_error_event`

---

### BOX_STATUS

Changement d'état d'une box.

```json
{
  "type": "BOX_STATUS",
  "payload": {
    "box_id": "uuid",
    "status": "active",
    "battery_level": 78.5
  },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

---

### DISTRIBUTION_UPDATE

Mise à jour d'une distribution planifiée.

```json
{
  "type": "DISTRIBUTION_UPDATE",
  "payload": {
    "item_id": "uuid-du-psi",
    "status": "taken",
    "taken_at": "2026-06-12T08:02:00Z"
  },
  "timestamp": "2026-06-12T10:30:00Z"
}
```

---

## Heartbeat

Le serveur envoie un ping toutes les **30 secondes** si aucun message n'est reçu. Le client doit répondre avec un pong, sinon la connexion est fermée.

**Ping serveur → client :**
```json
{"type": "ping"}
```

**Pong client → serveur :**
```json
{"type": "pong"}
```

ou la chaîne littérale `"ping"` (les deux formes sont acceptées).

---

## Codes de fermeture

| Code | Raison | Description |
|---|---|---|
| `4001` | `invalid_token` | JWT invalide ou expiré |
| `4001` | `missing_tenant_or_user` | Claims `tenant_id` / `sub` absents |
| `1000` | — | Fermeture normale (client déconnecté) |

---

## Exemples client

### JavaScript (browser)

```javascript
const token = await getAccessToken(); // via Keycloak JS adapter

const ws = new WebSocket(
  `wss://api.medbox.local/v1/ws/notifications?token=${token}`
);

ws.onopen = () => console.log("WS connecté");

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case "ACTION_SUCCESS":
      showToast("success", msg.payload.message);
      break;
    case "ACTION_ERROR":
      showToast("error", msg.payload.message);
      break;
    case "BOX_ALERT":
      showAlert(msg.payload);
      break;
    case "TAKE_EVENT":
      refreshDistributionList();
      break;
    case "ping":
      ws.send(JSON.stringify({ type: "pong" }));
      break;
  }
};

ws.onclose = (event) => {
  if (event.code === 4001) {
    // Token expiré → re-authentifier puis reconnecter
    redirectToLogin();
  } else {
    // Reconnexion avec backoff exponentiel
    scheduleReconnect();
  }
};
```

### Python (tests / scripts)

```python
import asyncio
import websockets
import json

async def listen():
    token = "..."
    uri = f"ws://localhost:8000/v1/ws/notifications?token={token}"

    async with websockets.connect(uri) as ws:
        async for raw in ws:
            event = json.loads(raw)
            print(event["type"], event["payload"])

asyncio.run(listen())
```

---

## Publication depuis un worker

Pour envoyer un événement depuis un worker Celery :

```python
from medbox.api.ws.events import action_success, box_alert, take_event
from medbox.api.ws.manager import publish_to_tenant, publish_to_user

# Diffuser à tous les soignants d'un tenant
await publish_to_tenant(tenant_id, box_alert(box_id, "offline", "Box hors ligne"))

# Cibler un utilisateur spécifique
await publish_to_user(
    tenant_id,
    user_id,
    action_success("Plan confirmé", {"plan_id": str(plan.id)}),
)
```

Ces fonctions ouvrent une connexion Redis éphémère, publient, puis ferment. L'erreur Redis est non-bloquante : entourer l'appel d'un `try/except` pour ne pas planter le worker.

---

**Document mis à jour** : Juin 2026
