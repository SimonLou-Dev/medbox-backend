from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from medbox.core.db.models import User
from medbox.core.db.session import async_session_local
from medbox.core.services.security import UserContext


class UserService:
    async def get_user_from_subject(self, subject_id: str) -> User | None:
        """
        Charge un utilisateur Medbox via son subject Keycloak (sub).
        """
        async with async_session_local() as session:
            result = await session.execute(
                select(User).where(User.keycloak_subject == subject_id)
            )
            user = result.scalars().first()

            return user

    async def register_user(self, user_context: UserContext) -> User:
        if usr := await self.get_user_from_subject(user_context.subject):
            return usr

        user = User(
            tenant_id=None,
            keycloak_subject=user_context.subject,
            email=user_context.email,
            c_full_name=user_context.full_name
        )

        async with async_session_local() as session:
            session.add(user)

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                raise HTTPException(400, "User already exists")

            await session.refresh(user)
            return user



def get_user_service() -> UserService:
    return UserService()