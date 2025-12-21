import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import AgeLimit, Retries

broker = RedisBroker(url="redis://redis:6379")
broker.add_middleware(Retries(max_retries=3))
broker.add_middleware(AgeLimit(max_age=60_000))

dramatiq.set_broker(broker)
