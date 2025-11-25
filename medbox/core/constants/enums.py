from enum import Enum


class UserStatus(Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    DISABLED = "disabled"

class UserRoles(Enum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    TENANT_ADMIN = "tenant_admin"
    GLOBAL_ADMIN = "global_admin"
    DEFAULT = "default"

class InviteStatus(Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    EXPIRED = "expired"
    CANCELED = "canceled"
