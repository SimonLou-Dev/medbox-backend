# 📡 MQTT Events & Protocol - MEDBOX

**Date**: Décembre 2025 | **Status**: 🟡 À implémenter dans iotworker

---

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture Topics](#architecture-topics)
3. [ACL & Sécurité](#acl--sécurité)
4. [Events détaillés](#events-détaillés)
5. [Payload formats](#payload-formats)
6. [QoS & Reliability](#qos--reliability)
7. [Implementation Guide](#implementation-guide)

---

## Vue d'ensemble

MEDBOX communique avec les boxes ESP32 via **MQTT 3.1.1** avec:
- ✅ TLS 1.2+ (chiffrement transit)
- ✅ mTLS certificats (authentification box)
- ✅ Topic-based access control (ACL par box_id)
- ✅ QoS adapté par type de message (0, 1, 2)

---

## Architecture Topics

### **Topologie globale**

```
medbox/                           ← Namespace racine
├── box/                          ← Pour les boxes
│   ├── {BOX_UUID}/               ← Instance box spécifique
│   │   ├── evt/                  ← Events: BOX → BACKEND
│   │   │   ├── heartbeat
│   │   │   ├── wheel_inserted
│   │   │   ├── wheel_removed
│   │   │   ├── dispense_started
│   │   │   ├── dispense_confirmed
│   │   │   ├── dispense_missed
│   │   │   ├── dispense_failed
│   │   │   ├── door_opened
│   │   │   ├── door_closed
│   │   │   └── error
│   │   │
│   │   └── cmd/                  ← Commands: BACKEND → BOX
│   │       ├── dispense
│   │       ├── display
│   │       ├── lock
│   │       └── ack
│   │
│   └── {OTHER_BOX_UUID}/...
│
└── system/                       ← Topics système (optionnel)
    ├── heartbeat               (Uptime, version)
    └── metrics                 (Agrégations, KPI)
```

### **Wildcards MQTT**

```
# Backend écoute TOUS les events:
SUBSCRIBE medbox/box/+/evt/#     ← + = un level
                                  ← # = multi-levels

# Exemple messages correspondants:
- medbox/box/box_001/evt/heartbeat
- medbox/box/box_001/evt/dispense_confirmed
- medbox/box/anotherbox/evt/error
```

---

## ACL & Sécurité

### **Certificats mTLS**

Chaque box a un certificat unique:

```
Certificate:
  Common Name (CN): box_001
  Issuer: CA MEDBOX
  Serial: 12345...
  Subject Alt Name: box_001.medbox.local
```

### **ACL (Access Control List) sur broker Mosquitto**

```ini
# /etc/mosquitto/aclfile

# Box peut PUBLISH sur evt seulement:
user box_001
topic write medbox/box/box_001/evt/#

# Box peut SUBSCRIBE sur cmd seulement:
user box_001
topic read medbox/box/box_001/cmd/#

# Backend (certificat special) peut tout:
user backend_service
topic write medbox/box/+/cmd/#
topic read medbox/box/+/evt/#
topic read medbox/box/+/cmd/#

# Autre box ne peut pas accéder box_001:
user box_002
topic write medbox/box/box_002/evt/#
topic read medbox/box/box_002/cmd/#
```

**Résultat**: Isolation stricte par box_id.

---

## Events détaillés

Selon l'image fournie, les events suivants sont identifiés:

### **📤 EVENTS: BOX → BACKEND (PUBLISH)**

Tous les events publiés par la box sur `medbox/box/{box_id}/evt/{event_type}`

#### **1. heartbeat** [BOX] — QoS 0

**Fréquence**: Toutes les 30 secondes  
**Réference**: Toutes les 30s  
**Description**: Metrics de la box (batterie, température, état moteur)

```json
{
  "type": "heartbeat",
  "timestamp": "2025-12-21T14:30:00Z",
  "box_id": "box_001",
  "battery_percent": 87,
  "temperature": 22.5,
  "wheel_position": 3,
  "door_is_open": false,
  "firmware_version": "1.2.3",
  "uptime_seconds": 604800
}
```

**Receiver**: IoT Worker (iotworker/tasks/)  
**DB Write**: `Telemetry` record  
**Actions**:
- [ ] Insérer/update telemetry
- [ ] Check seuils: batterie < 20%? → Alerte
- [ ] Check door_is_open → Événement anomalie si > 5 min

---

#### **2. wheel_inserted** [BOX] — QoS 1

**Référence**: Avant chaque changement de roue  
**Description**: Roue insérée détectée (capteur)

```json
{
  "type": "wheel_inserted",
  "timestamp": "2025-12-21T14:31:00Z",
  "box_id": "box_001",
  "wheel_uid": "wheel_abc123",
  "wheel_position": 0,
  "slot_count": 28
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record + update `Wheel` status → `READY`  
**Actions**:
- [ ] Valider wheel_uid existe en DB
- [ ] Update Wheel.status = "READY"
- [ ] Log audit: "Wheel inserted"

---

#### **3. wheel_removed** [BOX] — QoS 1

**Référence**: À chaque fois que la roue est enlevée  
**Description**: Roue enlevée détectée

```json
{
  "type": "wheel_removed",
  "timestamp": "2025-12-21T14:32:00Z",
  "box_id": "box_001",
  "wheel_uid": "wheel_abc123"
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record + update `Wheel` status → `ABSENT`  
**Actions**:
- [ ] Update Wheel.status = "ABSENT"
- [ ] Log audit: "Wheel removed"
- [ ] Alert: pas de roue → box inactive

---

#### **4. dispense_started** [BOX] — QoS 1

**Référence**: Lorsque la fenêtre de distribution s'ouvre  
**Description**: Dispensation débutée (window opened)

```json
{
  "type": "dispense_started",
  "timestamp": "2025-12-21T14:33:00Z",
  "box_id": "box_001",
  "order_id": "ord_999",
  "prescription_id": "presc_42",
  "patient_id": "pat_10",
  "window_duration_seconds": 30,
  "medications": [
    {
      "medication_id": "med_5",
      "wheel_slot": 3,
      "quantity": 1
    }
  ]
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record, update `Prescription` status → `IN_PROGRESS`  
**Actions**:
- [ ] Insérer event
- [ ] Start timer: 30s (window_duration_seconds)
- [ ] Attendre dispense_confirmed ou dispense_missed/failed

---

#### **5. dispense_confirmed** [BOX] — QoS 1

**Référence**: Lorsque la distribution a été faite  
**Description**: Distribution effectuée avec succès ✓

```json
{
  "type": "dispense_confirmed",
  "timestamp": "2025-12-21T14:33:15Z",
  "box_id": "box_001",
  "order_id": "ord_999",
  "prescription_id": "presc_42",
  "patient_id": "pat_10",
  "medications_delivered": [
    {
      "medication_id": "med_5",
      "wheel_slot": 3,
      "quantity_dispensed": 1
    }
  ]
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record (type=TAKE_SUCCESS), update `Prescription` status → `TAKEN`, `Event` status → `COMPLETED`  
**Actions**:
- [ ] Insérer event status=SUCCESS
- [ ] Update prescription: status = "TAKEN", taken_at = timestamp
- [ ] Log audit: "Medication dispensed successfully"
- [ ] Notification: Patient → "Médication prise ✓"

---

#### **6. dispense_missed** [BOX] — QoS 1

**Référence**: Lorsque la fenêtre de dispense se ferme et que le médicament n'a pas été distribué  
**Description**: Fenêtre fermée, pas distribué ✗

```json
{
  "type": "dispense_missed",
  "timestamp": "2025-12-21T14:33:45Z",
  "box_id": "box_001",
  "order_id": "ord_999",
  "prescription_id": "presc_42",
  "patient_id": "pat_10",
  "reason": "USER_NOT_RESPONDED",
  "window_closed_at": "2025-12-21T14:33:45Z"
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record (type=TAKE_MISSED), update `Prescription` status → `MISSED`, create `Alert`  
**Actions**:
- [ ] Insérer event status=MISSED
- [ ] Update prescription: status = "MISSED", missed_at = timestamp
- [ ] Create Alert: soignant → "Prise manquée"
- [ ] Log: "Patient did not respond within window"

---

#### **7. dispense_failed** [BOX] — QoS 1

**Référence**: Erreur lors de la dispensation ou appuyée hors fenêtre  
**Description**: Erreur dispensation (hardware issue ou unauthorized)

```json
{
  "type": "dispense_failed",
  "timestamp": "2025-12-21T14:34:00Z",
  "box_id": "box_001",
  "order_id": "ord_999",
  "prescription_id": "presc_42",
  "patient_id": "pat_10",
  "error_code": "WHEEL_STUCK",
  "error_message": "Motor timeout: wheel at position 3 cannot rotate",
  "attempted_medications": [
    {
      "medication_id": "med_5",
      "wheel_slot": 3
    }
  ]
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record (type=TAKE_ERROR), update `Prescription` status → `ERROR`, update `Box` status → `MAINTENANCE_NEEDED`, create `Alert`  
**Actions**:
- [ ] Insérer event: status=ERROR, error_code stored
- [ ] Update prescription: status = "ERROR"
- [ ] Update box: status = "MAINTENANCE_NEEDED"
- [ ] Create Critical Alert: maintenance team → "Box XYZ requires maintenance"
- [ ] Log: "Dispense failed: {error_code}"

---

#### **8. door_opened** [BOX] — QoS 1

**Référence**: À chaque fois que la porte principale est ouverte  
**Description**: Porte ouverte détectée

```json
{
  "type": "door_opened",
  "timestamp": "2025-12-21T14:35:00Z",
  "box_id": "box_001"
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record (type=DOOR_OPEN)  
**Actions**:
- [ ] Insérer event
- [ ] Update box: door_is_open = true
- [ ] Log: Door opened

---

#### **9. door_closed** [BOX] — QoS 1

**Référence**: À chaque fois que la porte principale est fermée  
**Description**: Porte fermée détectée

```json
{
  "type": "door_closed",
  "timestamp": "2025-12-21T14:35:15Z",
  "box_id": "box_001"
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record (type=DOOR_CLOSE)  
**Actions**:
- [ ] Insérer event
- [ ] Update box: door_is_open = false
- [ ] Log: Door closed

---

#### **10. error** [BOX] — QoS 1

**Référence**: Générique pour toutes erreurs non catégorisées  
**Description**: Erreur générique (non dispensation)

```json
{
  "type": "error",
  "timestamp": "2025-12-21T14:36:00Z",
  "box_id": "box_001",
  "error_code": "BLUETOOTH_DISCONNECT",
  "error_message": "Bluetooth connection lost to patient device",
  "severity": "WARNING"
}
```

**Receiver**: IoT Worker  
**DB Write**: `Event` record (type=ERROR)  
**Actions**:
- [ ] Insérer event
- [ ] Si severity=CRITICAL → Create Alert
- [ ] Log: "{error_code}: {error_message}"

---

### **📥 COMMANDS: BACKEND → BOX (SUBSCRIBE)**

Tous les commandes envoyées par le backend sur `medbox/box/{box_id}/cmd/{cmd_type}`

#### **1. dispense** [CMD] — QoS 2

**QoS 2**: Exactement une fois (critique)  
**Description**: Ordre de dispensation

```json
{
  "cmd_id": "cmd_001",
  "type": "dispense",
  "timestamp": "2025-12-21T14:30:00Z",
  "order_id": "ord_999",
  "prescription_id": "presc_42",
  "patient_id": "pat_10",
  "medications": [
    {
      "medication_id": "med_5",
      "wheel_slot": 3,
      "quantity": 1
    }
  ],
  "window_duration_seconds": 30,
  "timeout_ms": 5000
}
```

**Sender**: Scheduler Worker (via iotworker publish)  
**Box Action**: Ouvre fenêtre, affiche patient, attend input → dispense_confirmed/missed/failed  

---

#### **2. display** [CMD] — QoS 2

**QoS 2**: Exactement une fois  
**Description**: Mise à jour écran LVGL patient

```json
{
  "cmd_id": "cmd_002",
  "type": "display",
  "timestamp": "2025-12-21T14:29:00Z",
  "screen_type": "HOME",
  "content": {
    "patient_name": "Crypté en c_*",
    "current_time": "14:30",
    "next_medication": {
      "name": "Paracétamol",
      "time": "15:00",
      "dose": "500mg"
    },
    "status": "READY"
  }
}
```

**Sender**: Backend API  
**Box Action**: Update écran avec contenu

---

#### **3. lock** [CMD] — QoS 2

**QoS 2**: Exactement une fois  
**Description**: Contrôle du verrou (actif/inactif)

```json
{
  "cmd_id": "cmd_003",
  "type": "lock",
  "timestamp": "2025-12-21T14:28:00Z",
  "action": "LOCK",  // ou "UNLOCK"
  "reason": "END_OF_SHIFT"
}
```

**Sender**: Backend / Soignant (via API)  
**Box Action**: Active/désactive verrou

---

#### **4. ack** [CMD] — QoS 2

**QoS 2**: Exactement une fois  
**Description**: Accusé réception commande

```json
{
  "cmd_id": "cmd_001",
  "type": "ack",
  "status": "RECEIVED"  // ou "ERROR"
}
```

**Sender**: Box  
**Backend Action**: Confirme réception du command

---

## Payload formats

### **JSON Encoding**

Tous les payloads sont en **UTF-8 JSON**.

```python
import json
payload = {
    "type": "heartbeat",
    "battery_percent": 87,
    ...
}
json_bytes = json.dumps(payload).encode('utf-8')
mqtt_client.publish(topic, json_bytes, qos=0)
```

### **Validation Pydantic**

Backend valide avec Pydantic models:

```python
from pydantic import BaseModel
from typing import Optional

class HeartbeatEvent(BaseModel):
    type: str = "heartbeat"
    timestamp: datetime
    box_id: str
    battery_percent: int
    temperature: float
    wheel_position: int
    door_is_open: bool
    firmware_version: str
    uptime_seconds: int
    
class DispenseConfirmedEvent(BaseModel):
    type: str = "dispense_confirmed"
    timestamp: datetime
    order_id: str
    prescription_id: str
    patient_id: str
    medications_delivered: list[dict]
```

---

## QoS & Reliability

### **QoS Levels**

| QoS | Garantie | Quand? | Exemples |
|-----|----------|--------|----------|
| **0** | At most once | Peut perdre | `heartbeat`, `ping`, `pong` |
| **1** | At least once | Important | `wheel_inserted`, `dispense_started`, `door_opened` |
| **2** | Exactly once | Critique | `dispense`, `lock`, commandes backend |

### **Retries & Timeouts**

```
Commande envoyée: QoS 2
↓
Box ACK reçu dans 5s? ✓
↓
Non reçu après 5s? → Retry (max 3x)
↓
Toujours pas? → Alert: "Box not responding"
```

### **Offline Handling**

```
Box perd connexion MQTT
↓
Backend continue à envoyer commandes
↓
Broker stocke (session persistence) si mTLS actif
↓
Box reconnecte
↓
Box reçoit commandes en attente
```

---

## Implementation Guide

### **1. Setup Mosquitto Broker**

```bash
# Installation
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 8883:8883 \
  -v /path/to/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto:2.0

# Config: mosquitto.conf
listener 1883
protocol mqtt

listener 8883
protocol mqtt
cafile /path/to/ca.crt
certfile /path/to/broker.crt
keyfile /path/to/broker.key
require_certificate true
use_identity_as_username true

acl_file /path/to/aclfile
```

### **2. Generate mTLS Certificates**

```bash
# Créer CA
openssl req -x509 -newkey rsa:2048 -keyout ca.key -out ca.crt -days 365

# Créer certificat broker
openssl req -new -keyout broker.key -out broker.csr -subj "/CN=medbox-broker"
openssl x509 -req -in broker.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out broker.crt -days 365

# Créer certificat pour box_001
openssl req -new -keyout box_001.key -out box_001.csr -subj "/CN=box_001"
openssl x509 -req -in box_001.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out box_001.crt -days 365
```

### **3. Python IoT Worker - MQTT Connection**

```python
# medbox/iotworker/mqtt_client.py

import paho.mqtt.client as mqtt
import asyncio
import json
from typing import Callable

class MQTTClient:
    def __init__(self, broker_host, broker_port, ca_certs, client_cert, client_key):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.handlers = {}
        
        # TLS setup
        self.client.tls_set(
            ca_certs=ca_certs,
            certfile=client_cert,
            keyfile=client_key,
            cert_reqs=mqtt.ssl.CERT_REQUIRED,
            tls_version=mqtt.ssl.TLSv1_2,
            ciphers=None
        )
        
        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT broker")
            # Subscribe à tous les événements boxes
            self.client.subscribe("medbox/box/+/evt/#", qos=1)
        else:
            print(f"Connection failed: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        """
        Reçoit un message MQTT
        topic: medbox/box/box_001/evt/heartbeat
        payload: JSON
        """
        try:
            topic_parts = msg.topic.split("/")
            # topic_parts = ["medbox", "box", "box_001", "evt", "heartbeat"]
            box_id = topic_parts[2]
            event_type = topic_parts[4]
            
            payload = json.loads(msg.payload.decode())
            
            # Appeler handler approprié
            if event_type in self.handlers:
                asyncio.run(self.handlers[event_type](box_id, payload))
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print(f"Disconnected: {reason_code}")
        # Reconnecter automatiquement
        if reason_code != 0:
            asyncio.run(self._reconnect())
    
    async def _reconnect(self):
        await asyncio.sleep(5)
        self.client.reconnect()
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register handler for event_type"""
        self.handlers[event_type] = handler
    
    def connect(self):
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_start()
    
    def publish(self, topic: str, payload: dict, qos: int = 1):
        """Publish command to box"""
        self.client.publish(topic, json.dumps(payload), qos=qos)
```

### **4. Event Handlers**

```python
# medbox/iotworker/tasks/events.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class HeartbeatPayload(BaseModel):
    type: str
    timestamp: datetime
    box_id: str
    battery_percent: int
    temperature: float
    wheel_position: int
    door_is_open: bool
    firmware_version: str
    uptime_seconds: int

async def handle_heartbeat(box_id: str, payload: dict):
    """
    Traite événement heartbeat.
    Écrit telemetry en DB, check seuils.
    """
    validated = HeartbeatPayload(**payload)
    
    # Écrire telemetry
    telemetry = Telemetry(
        box_id=box_id,
        metric="battery_percent",
        value_number=validated.battery_percent,
        tenant_id=get_box_tenant_id(box_id)
    )
    await db.add(telemetry)
    await db.commit()
    
    # Check battery low
    if validated.battery_percent < 20:
        await create_alert(
            box_id=box_id,
            severity="WARNING",
            message=f"Battery low: {validated.battery_percent}%"
        )

# Registrer handler
mqtt_client.register_handler("heartbeat", handle_heartbeat)
```

### **5. Publish Command from Backend**

```python
# Quand Scheduler décide de prescrire une prise:

async def dispatch_prescription_take(prescription_id: str):
    """
    Scheduler déclenche prise via backend.
    Backend publie commande sur MQTT.
    """
    prescription = await db.get(Prescription, prescription_id)
    box = prescription.patient.box
    
    command_payload = {
        "cmd_id": str(uuid4()),
        "type": "dispense",
        "order_id": str(uuid4()),
        "prescription_id": str(prescription.id),
        "patient_id": str(prescription.patient_id),
        "medications": [
            {
                "medication_id": str(item.medication_id),
                "wheel_slot": item.wheel_slot.index,
                "quantity": item.quantity
            }
            for item in prescription.items
        ],
        "window_duration_seconds": 30,
        "timeout_ms": 5000
    }
    
    topic = f"medbox/box/{box.box_uid}/cmd/dispense"
    mqtt_client.publish(topic, command_payload, qos=2)
    
    # Enregistrer commande en DB pour tracking
    await db.add(Command(
        box_id=box.id,
        type="dispense",
        payload=command_payload,
        status="SENT"
    ))
```

---

## Summary

| Component | Status | Timeline |
|-----------|--------|----------|
| MQTT Broker | ✅ Planned | Week 1 |
| mTLS Certs | 🚧 To define | Week 1 |
| Python Client | ❌ To implement | Week 2 |
| Event Handlers | ❌ To implement | Week 2-3 |
| DB Integration | ✅ Models ready | Week 2 |
| Testing | ❌ To add | Week 3 |
| Deployment | ⏳ Later | Week 4+ |

---

**Document créé**: Décembre 2025
