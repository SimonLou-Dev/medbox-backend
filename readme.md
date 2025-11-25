

```

medbox-back/
│
├── api/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py          # JWT, Keycloak validation
│   │   ├── middleware.py        # tenant + rbac + request ID
│   │   ├── exceptions.py
│   │   └── dependencies.py      # dépendances globales
│   │
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py        # assemble tous les routers
│   │   │   ├── auth.py
│   │   │   ├── tenants.py
│   │   │   ├── users.py
│   │   │   ├── patients.py
│   │   │   ├── prescriptions.py
│   │   │   ├── boxes.py
│   │   │   ├── wheels.py
│   │   │   ├── planning.py
│   │   │   ├── telemetry.py
│   │   │   └── events.py
│   │   └── deps/
│   │       ├── auth.py          # get_current_user
│   │       ├── rbac.py          # check roles
│   │       └── tenant.py        # resolve tenant
│   │
│   ├── db/
│   │   ├── session.py           # async SQLAlchemy session
│   │   ├── base.py              # Base = declarative base
│   │   ├── models/
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── patient.py
│   │   │   ├── prescription.py
│   │   │   ├── wheel.py
│   │   │   ├── box.py
│   │   │   ├── planning.py
│   │   │   ├── telemetry.py
│   │   │   └── event.py
│   │   └── repositories/
│   │       ├── base.py
│   │       ├── tenant_repo.py
│   │       ├── user_repo.py
│   │       ├── patient_repo.py
│   │       ├── prescription_repo.py
│   │       ├── wheel_repo.py
│   │       ├── box_repo.py
│   │       ├── planning_repo.py
│   │       └── telemetry_repo.py
│   │
│   ├── schemas/
│   │   ├── base.py
│   │   ├── user.py
│   │   ├── patient.py
│   │   ├── prescription.py
│   │   ├── wheel.py
│   │   ├── box.py
│   │   ├── planning.py
│   │   ├── telemetry.py
│   │   └── event.py
│   │
│   ├── services/
│   │   ├── patient_service.py
│   │   ├── prescription_service.py
│   │   ├── wheel_service.py
│   │   ├── box_service.py
│   │   ├── planning_service.py   # auto-planification smart
│   │   ├── telemetry_service.py
│   │   ├── event_service.py
│   │   └── security_service.py
│   │
│   ├── utils/
│   │   ├── crypto.py             # chiffrer/déchiffrer c_*
│   │   ├── jwt.py                # outils jwt
│   │   ├── time.py
│   │   ├── hashing.py
│   │   ├── s3.py
│   │   └── pagination.py
│   │
│   └── constants/
│       ├── roles.py
│       ├── tenant.py
│       ├── enums.py
│       └── config_defaults.py
│
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
│
├── tests/
│   ├── api/
│   ├── services/
│   ├── repositories/
│   └── utils/
│
├── requirements.txt
├── docker-compose.yml
└── README.md
```

