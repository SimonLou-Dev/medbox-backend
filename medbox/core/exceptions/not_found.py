"""Définitions des exception 'Not Found'."""


class ModelNotFoundError(Exception):
    """Erreure lorsqu'un modèle n'a pas plus être trouvé."""

    def __init__(self, model: str, id: str) -> None:
        """Constructeur.

        Arguments:
        ---------
        model: str
            Nom du modèle
        id : str
            Identifiant du modèle

        """
        super().__init__(
            f"Impossible de trouver le modèle {model} avec l'identifiant {id}",
        )
