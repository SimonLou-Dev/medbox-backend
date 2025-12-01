import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, Retries

from medbox.schedulerworker.broker import broker

broker = RedisBroker(url="redis://redis:6379")
broker.add_middleware(Retries(max_retries=3))
broker.add_middleware(AgeLimit(max_age=60_000))

from medbox.core.tasks import *

dramatiq.set_broker(broker)


def run():
    print("Scheduler worker started")
