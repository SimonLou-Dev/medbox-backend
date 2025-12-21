# 👥 Guide de Contribution - MEDBOX

Ce document consolide les directives de travail, patterns de code, et checklist pour collaborer sur MEDBOX.

---

## 🎯 Commencer

### 1. Setup environnement

```bash
# Cloner le repo
git clone https://github.com/SimonLou-Dev/medbox-backend.git
cd medbox-backend

# Installer dépendances
poetry install

# Vérifier setup
poetry run pytest ./tests -v
poetry run ruff check .
```

### 2. Lire la documentation

- **[`docs/GETTING_STARTED.md`](./GETTING_STARTED.md)** — Setup détaillé
- **[`docs/architecture.md`](./architecture.md)** — Design système
- **[`docs/audit.md`](./audit.md)** — État du code et issues identifiées

---

## 🏗️ Architecture & Patterns

### Multi-tenant scoping

**Règle d'or**: Toute requête doit toujours scoper par `tenant_id`.

```python
# ✅ BON
repo = UserRepository(tenant_id=tenant_id)
users = await repo.list()

# ❌ MAUVAIS
users = await session.execute(select(User))  # Pas scopé!
```

### Repository pattern

Tous les accès données passent par des repositories avec tenant scoping:

```python
class UserRepository(BaseRepository[User]):
    def __init__(self, tenant_id: str | None = None):
        super().__init__(User)
        self.tenant_id = tenant_id
    
    async def get_by_subject(self, subject_id: str) -> User | None:
        # Scope automatiquement par tenant_id si fourni
        ...
```

### Pydantic v2 migration

Tous les modèles doivent utiliser la syntaxe v2:

```python
# ✅ BON
class MyDTO(BaseModel):
    model_config = ConfigDict(json_schema_extra={...})
    field: str

# ❌ VIEUX
class MyDTO(BaseModel):
    class Config:
        json_schema_extra = {...}
```

---

## 📝 Style de code

### Import organization

```python
# Standard library
import asyncio
from datetime import datetime

# Third-party
from fastapi import FastAPI
from sqlalchemy import select

# Local
from medbox.core.db.models import User
from medbox.core.dto import UserDTO
```

### Type annotations

Toujours annoter les types:

```python
# ✅ BON
async def get_user(user_id: UUID) -> User | None:
    ...

# ❌ MAUVAIS
async def get_user(user_id):
    ...
```

### Docstrings

Utiliser docstrings NumPy-style:

```python
async def create_invitation(
    tenant_id: str,
    email: str,
) -> Invitation:
    """Crée une invitation pour un utilisateur.

    Parameters
    ----------
    tenant_id : str
        Identifiant unique du tenant.
    email : str
        Email cible de l'invitation.

    Returns
    -------
    Invitation
        L'invitation créée.

    Raises
    ------
    HTTPException
        Si l'email existe déjà.

    """
    ...
```

### Trailing commas

Utiliser trailing commas dans les fonctions multi-ligne:

```python
# ✅ BON
response = await client.post(
    "/api/v1/users",
    json={
        "email": "user@example.com",
        "name": "John",
    },
)

# ❌ MAUVAIS
response = await client.post(
    "/api/v1/users",
    json={
        "email": "user@example.com",
        "name": "John"
    }
)
```

---

## 🧪 Tests

### Exécuter les tests

```bash
# Tous les tests
poetry run pytest ./tests -v

# Un fichier spécifique
poetry run pytest ./tests/test_api_multi_tenant.py -v

# Avec coverage
poetry run pytest ./tests --cov=medbox -v
```

### Écrire des tests

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
class TestUserRepository:
    """Tests du repository User."""
    
    async def test_list_respects_tenant_scope(
        self,
        db_session: AsyncSession,
    ) -> None:
        """❌ FAIL si les users d'autres tenants sont visibles."""
        # Setup
        tenant_1 = Tenant(id=uuid4(), name="Tenant 1")
        user_1 = User(
            id=uuid4(),
            tenant_id=tenant_1.id,
            email="user1@test.com",
        )
        db_session.add_all([tenant_1, user_1])
        await db_session.commit()
        
        # Act
        stmt = select(User).where(User.tenant_id == tenant_1.id)
        result = await db_session.execute(stmt)
        users = result.scalars().all()
        
        # Assert
        assert len(users) == 1
        assert users[0].id == user_1.id
```

### Fixtures disponibles

Dans `tests/conftest.py`:

- **`event_loop`** — Event loop session-scoped pour async tests
- **`db_session`** — AsyncSession SQLite in-memory avec schema
- **`async_client`** — AsyncClient avec overrides de dépendances

---

## ✅ Checklist avant commit

- [ ] Code formé avec `poetry run ruff format .`
- [ ] Linting passé `poetry run ruff check .`
- [ ] Tests passent `poetry run pytest ./tests -v`
- [ ] Docstrings NumPy-style ajoutées
- [ ] Type annotations complètes
- [ ] Imports triés et formés
- [ ] Trailing commas utilisées
- [ ] Aucune données hardcodées (secrets, tokens)
- [ ] Tenant scoping vérifié dans toutes les requêtes

---

## 🔄 Workflow de contribution

### 1. Créer une branche

```bash
git checkout -b feature/nom-feature
```

### 2. Développer

```bash
# Développer code
# Ajouter tests
# Linter/formatter

poetry run ruff format .
poetry run ruff check .
poetry run pytest ./tests -v
```

### 3. Commit & Push

```bash
git add .
git commit -m "feat: description courte et claire"
git push origin feature/nom-feature
```

### 4. Soumettre PR

- Description claire du changement
- Référencer les issues si applicable
- S'assurer que tous les tests passent

---

## 📚 Ressources

- **[docs/GETTING_STARTED.md](./GETTING_STARTED.md)** — Setup complet
- **[docs/architecture.md](./architecture.md)** — Design système
- **[docs/database.md](./database.md)** — Schéma DB
- **[docs/mqtt_protocol.md](./mqtt_protocol.md)** — MQTT spec
- **[../todo.md](../todo.md)** — Roadmap et tâches

---

## ❓ Questions?

Consultez la documentation complète dans `docs/` ou créez une issue sur GitHub.

**Bonne contribution!** 🚀
