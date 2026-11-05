"""L'affichage de l'arbre syntaxique, pour voir ce que le parser a compris.

    Module nom='x' [1:8]
      valeur: Entier valeur=1 [1:12]

Le parcours lit les champs des dataclasses : un nœud ajouté plus tard s'affiche sans rien
changer ici.
"""

from collections.abc import Iterator
from dataclasses import fields
from enum import Enum

from cosmo.noeuds import Noeud

INDENTATION = "  "


def lignes_arbre(noeud: Noeud, etiquette: str = "", niveau: int = 0) -> Iterator[str]:
    """Produit une ligne par nœud : son type, ses attributs, sa position, puis ses enfants."""
    attributs: list[str] = []
    enfants: list[tuple[str, Noeud]] = []
    for champ in fields(noeud):
        if champ.name == "position":
            continue
        valeur = getattr(noeud, champ.name)
        match valeur:
            case Noeud():
                enfants.append((champ.name, valeur))
            case tuple():
                enfants += [(f"{champ.name}[{i}]", e) for i, e in enumerate(valeur)]
            case Enum():
                attributs.append(f"{champ.name}={valeur.value!r}")
            case _:
                attributs.append(f"{champ.name}={valeur!r}")

    description = " ".join([type(noeud).__name__, *attributs, f"[{noeud.position}]"])
    prefixe = f"{etiquette}: " if etiquette else ""
    yield f"{INDENTATION * niveau}{prefixe}{description}"
    for nom, enfant in enfants:
        yield from lignes_arbre(enfant, nom, niveau + 1)
