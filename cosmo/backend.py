"""Étape 10 : les backends, ou comment ajouter une sortie sans toucher à la chaîne.

Un backend transforme un arbre en texte. `Backend` est un `Protocol` : le typage est
structurel, si bien qu'une classe en est un dès qu'elle a la bonne méthode, sans en hériter
ni même connaître ce module. mypy le vérifie à l'endroit où elle est utilisée comme telle,
par exemple dans le registre ci-dessous.

C'est le principe ouvert/fermé : pour une nouvelle sortie, on écrit une classe et on
l'enregistre ici. Ni la façade ni la ligne de commande ne changent.
"""

from typing import Protocol

from cosmo.formateur import BackendCosmo
from cosmo.generateur import BackendPython
from cosmo.noeuds import Programme


class Backend(Protocol):
    """Ce qui sait écrire un programme sous forme de texte."""

    def generer(self, programme: Programme) -> str:
        """Le texte du programme. Lève ErreursCompilation s'il ne peut pas être écrit."""
        ...


BACKENDS: dict[str, Backend] = {
    "python": BackendPython(),
    "cosmo": BackendCosmo(),
}

BACKEND_PAR_DEFAUT = "python"
