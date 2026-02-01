"""Dramatiq broker configuration."""

import logging

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, AsyncIO, Retries, TimeLimit
from medbox.core.config.settings import settings

logger = logging.getLogger(__name__)



def configure_broker() -> RedisBroker:
    """Configure and initialize the Dramatiq Redis broker.

    Returns:
        RedisBroker: Configured broker instance

    """
    # Create Redis broker
    broker = RedisBroker(url=settings.redis_url)

    # Add middleware
    broker.add_middleware(AsyncIO())

    # Set as global broker
    dramatiq.set_broker(broker)

    logger.info("✅ Dramatiq broker configured with Redis")

    return broker


# Initialize broker at module import
broker = configure_broker()

# medbox/schedulerworker/broker_config.py
