import dramatiq

@dramatiq.actor
def test(message: str):
    print(f"Lancement de la tâhce test")