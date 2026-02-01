"""Redis lock utility for distributed task locking."""

import logging
from datetime import datetime

import redis

from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)

# Redis client
redis_client = redis.Redis.from_url(
    settings.redis_url or "redis://redis:6379/0",
    decode_responses=True,
)


class RedisLock:
    """Distributed lock using Redis."""

    def __init__(
        self,
        lock_key: str,
        timeout: int = 3600,
        expire_after: int = 3600,
    ):
        """Initialize Redis lock.

        Args:
            lock_key: Unique key for the lock
            timeout: How long to wait for the lock (seconds)
            expire_after: Auto-expire the lock after this many seconds

        """
        self.lock_key = lock_key
        self.timeout = timeout
        self.expire_after = expire_after
        self.acquired = False

    def acquire(self) -> bool:
        """Try to acquire the lock.

        Returns:
            bool: True if lock acquired, False if already locked

        """
        try:
            # Set lock with NX (only if not exists) and EX (expire after)
            result = redis_client.set(
                self.lock_key,
                datetime.utcnow().isoformat(),
                nx=True,
                ex=self.expire_after,
            )
            self.acquired = bool(result)
            return self.acquired
        except Exception as e:
            logger.error(f"Error acquiring lock {self.lock_key}: {e}")
            return False

    def release(self) -> bool:
        """Release the lock.

        Returns:
            bool: True if released, False if lock doesn't exist

        """
        try:
            result = redis_client.delete(self.lock_key)
            self.acquired = False
            return bool(result)
        except Exception as e:
            logger.error(f"Error releasing lock {self.lock_key}: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise RuntimeError(
                f"Could not acquire lock {self.lock_key}. Another task may be running.",
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


def get_task_lock(task_name: str, max_age_minutes: int = 60) -> RedisLock:
    """Get a lock for a task with rate limiting.

    Args:
        task_name: Name of the task
        max_age_minutes: Minimum minutes between executions (rate limit)

    Returns:
        RedisLock: Lock object

    """
    lock_key = f"task_lock:{task_name}"
    expire_after = max_age_minutes * 60  # Convert to seconds

    return RedisLock(
        lock_key=lock_key,
        timeout=5,
        expire_after=expire_after,
    )
