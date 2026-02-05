import dramatiq


@dramatiq.actor
def test(message: str):
    print("Lancement de la tâhce test")  # noqa: T201
