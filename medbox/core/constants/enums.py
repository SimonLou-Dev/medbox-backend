"""Définitions des énumérations."""

from enum import Enum


class UserStatus(Enum):
    """Statut représentant l'état du comtpe de l'utilsiateur."""

    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    DISABLED = "disabled"


class UserRoles(Enum):
    """Statut représentant les rôles au sein du tenant."""

    PATIENT = "patient"
    CAREGIVER = "caregiver"
    TENANT_ADMIN = "tenant_admin"
    DEFAULT = "default"
    SUPER_ADMIN = "super_admin"


class InviteStatus(Enum):
    """Etat possibles d'une invitation d'un user dans un tenant."""

    PENDING = "pending"
    CLAIMED = "claimed"
    EXPIRED = "expired"
    CANCELED = "canceled"
