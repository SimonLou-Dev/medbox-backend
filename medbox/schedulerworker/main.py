# medbox/schedulerworker/main.py


from medbox.core import tasks  # noqa: F401
from medbox.schedulerworker import broker_config  # noqa: F401


def run():
    print("Scheduler worker started")
