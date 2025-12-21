# 📡 MQTT Events & Protocol - MEDBOX

**Date**: Décembre 2025 | **Status**: 🟢 Stable

---

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture Topics](#architecture-topics)
3. [ACL & Sécurité](#acl--sécurité)
4. [Events détaillés](#events-détaillés)
5. [Commandes](#commandes)
6. [QoS & Reliability](#qos--reliability)

---

## Vue d'ensemble

MEDBOX communique avec les boxes ESP32 via **MQTT 3.1.1** avec :
- ✅ **Broker recommandé** : **EMQX** (gestion ACL, mTLS, haute disponibilité).
- ✅ **Sécurité** : TLS 1.2+ et certificats mTLS pour authentification.
- ✅ **Contrôle d'accès** : ACL par `box_id` pour isolation stricte.
- ✅ **Fiabilité** : QoS adapté par type de message (0, 1, 2).

---

## Architecture Topics

### Topologie globale

```
medbox/                           ← Namespace racine
├── box/                          ← Pour les boxes
│   ├── {BOX_UUID}/               ← Instance box spécifique
│   │   ├── evt/                  ← Events: BOX → BACKEND
│   │   └── cmd/                  ← Commands: BACKEND → BOX

```

### Wildcards MQTT

- **Backend écoute tous les events** : `medbox/box/+/evt/#`
- **Exemples** :
  - `medbox/box/box_001/evt/heartbeat`
  - `medbox/box/box_001/evt/dispense_confirmed`

---

## ACL & Sécurité

### Certificats mTLS

Chaque box utilise un certificat unique pour l'authentification. Exemple :

```
Certificate:
  Common Name (CN): box_001
  Issuer: CA MEDBOX
  Serial: 12345...
```

### Exemple d'ACL EMQX

```yaml
# Box peut publier uniquement sur evt
username: box_001
publish: medbox/box/box_001/evt/#

# Box peut souscrire uniquement sur cmd
subscribe: medbox/box/box_001/cmd/#
```

---

## Events détaillés

Les events publiés par la box doivent être concis et suivre le pattern `medbox/box/{box_id}/evt/{event_type}`.

### Principes généraux
- **Payload minimal** : inclure uniquement les identifiants nécessaires (`planned_dose_id`, `wheel_uid`, etc.).
- **Données sensibles** : ne jamais transmettre de données personnelles non chiffrées.

### Exemples d'events

#### heartbeat — QoS 0
```json
{
  "type": "heartbeat",
  "timestamp": "2025-12-21T14:30:00Z",
  "box_id": "box_001",
  "battery_percent": 87,
  "firmware_version": "1.2.3"
}
```

#### wheel_inserted — QoS 1
```json
{
  "type": "wheel_inserted",
  "timestamp": "2025-12-21T14:31:00Z",
  "box_id": "box_001",
  "wheel_uid": "wheel_abc123"
}
```

#### dispense_confirmed — QoS 1
```json
{
  "type": "dispense_confirmed",
  "timestamp": "2025-12-21T14:33:15Z",
  "box_id": "box_001",
  "planned_dose_id": "dose_999"
}
```

---

## Commandes

Les commandes sont publiées sur `medbox/box/{box_id}/cmd/{cmd_type}`.

### Commandes principales

#### scheduling_update — QoS 1
```json
{
  "cmd_id": "cmd_sched_001",
  "type": "scheduling_update",
  "timestamp": "2025-12-21T00:00:00Z",
  "prescriptions": [
    {
      "planned_dose_id": "dose_1001",
      "scheduled_at": "2025-12-22T08:00:00Z",
      "wheel_slot": 3,
      "quantity": 1
    }
  ]
}
```

#### wheel_reset — QoS 2
```json
{
  "cmd_id": "cmd_reset_001",
  "type": "wheel_reset",
  "timestamp": "2025-12-21T14:40:00Z",
}
```

#### ping — QoS 0
```json
{
  "cmd_id": "cmd_ping_001",
  "type": "ping",
  "timestamp": "2025-12-21T14:41:00Z"
}
```

---

## QoS & Reliability

### Niveaux de QoS

| QoS | Garantie            | Exemples                  |
|-----|---------------------|---------------------------|
| 0   | At most once        | `heartbeat`, `ping`       |
| 1   | At least once       | `wheel_inserted`, `dispense_confirmed` |
| 2   | Exactly once        | `scheduling_update`, `wheel_reset` |

### Bonnes pratiques
- **Timeouts** : Configurer des délais pour les commandes critiques.
- **Retries** : Réessayer les commandes QoS 1/2 en cas d'échec.
- **Session persistence** : Activer la persistance pour les boxes déconnectées.

---

**Document mis à jour**: Décembre 2025
