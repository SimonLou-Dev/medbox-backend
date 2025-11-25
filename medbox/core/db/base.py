from datetime import datetime
import uuid

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass