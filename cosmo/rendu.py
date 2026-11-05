"""Ce que partagent les backends qui écrivent du texte : l'indentation et les expressions.

Python et Cosmo ont les mêmes priorités d'opérateurs : seuls les mots changent. Le placement
des parenthèses, facile à rater, n'est donc écrit qu'une fois, ici. Chaque backend indique
seulement comment s'écrivent les noms, les littéraux et les opérateurs.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import assert_never

from cosmo.noeuds import (
    Appel,
    Binaire,
    Booleen,
    Chaine,
    Entier,
    Expression,
    OperateurBinaire,
    OperateurUnaire,
    Unaire,
    Variable,
)
from cosmo.parser import Priorite

INDENTATION = "    "

PRIORITES_BINAIRES: dict[OperateurBinaire, Priorite] = {
    OperateurBinaire.OU: Priorite.OU,
    OperateurBinaire.ET: Priorite.ET,
    OperateurBinaire.EGAL: Priorite.COMPARAISON,
    OperateurBinaire.DIFFERENT: Priorite.COMPARAISON,
    OperateurBinaire.INFERIEUR: Priorite.COMPARAISON,
    OperateurBinaire.INFERIEUR_EGAL: Priorite.COMPARAISON,
    OperateurBinaire.SUPERIEUR: Priorite.COMPARAISON,
    OperateurBinaire.SUPERIEUR_EGAL: Priorite.COMPARAISON,
    OperateurBinaire.PLUS: Priorite.SOMME,
    OperateurBinaire.MOINS: Priorite.SOMME,
    OperateurBinaire.FOIS: Priorite.PRODUIT,
    OperateurBinaire.DIVISE: Priorite.PRODUIT,
    OperateurBinaire.MODULO: Priorite.PRODUIT,
}

PRIORITES_UNAIRES: dict[OperateurUnaire, Priorite] = {
    OperateurUnaire.NON: Priorite.NON,
    OperateurUnaire.MOINS: Priorite.UNAIRE,
}


class GenerateurTexte(ABC):
    """Écrit des lignes indentées, et le texte des expressions."""

    def __init__(self) -> None:
        self._lignes: list[str] = []
        self._niveau = 0

    # --- Ce que chaque backend doit préciser -----------------------------------

    @abstractmethod
    def _texte_nom(self, nom: str) -> str:
        """Comment s'écrit un nom de variable ou de mission."""

    @abstractmethod
    def _texte_chaine(self, valeur: str) -> str:
        """Comment s'écrit une chaîne littérale."""

    @abstractmethod
    def _texte_booleen(self, valeur: bool) -> str:
        """Comment s'écrit un booléen."""

    @abstractmethod
    def _texte_binaire(self, operateur: OperateurBinaire) -> str:
        """Comment s'écrit un opérateur binaire."""

    @abstractmethod
    def _texte_unaire(self, operateur: OperateurUnaire) -> str:
        """Comment s'écrit un opérateur unaire, espace comprise s'il en faut une."""

    # --- L'écriture des lignes -------------------------------------------------

    @contextmanager
    def _indentation(self) -> Iterator[None]:
        """Les lignes écrites pendant le `with` ont un niveau d'indentation de plus."""
        self._niveau += 1
        try:
            yield
        finally:
            self._niveau -= 1

    def _ecrire(self, ligne: str) -> None:
        self._lignes.append(INDENTATION * self._niveau + ligne)

    def _texte_complet(self) -> str:
        return "".join(f"{ligne}\n" for ligne in self._lignes)

    # --- Les expressions -------------------------------------------------------

    def expression(self, noeud: Expression, minimum: int = Priorite.OU) -> str:
        """Le texte d'une expression, entre parenthèses si sa place l'exige.

        `minimum` est la priorité que le contexte exige : `(1 + 2) * 3` garde ainsi ses
        parenthèses, et `1 + (2 * 3)` les perd.
        """
        texte, priorite = self._rendre(noeud)
        return f"({texte})" if priorite < minimum else texte

    def _rendre(self, noeud: Expression) -> tuple[str, Priorite]:
        """Le texte d'une expression, sans parenthèses autour, et sa priorité."""
        match noeud:
            case Entier(valeur):
                return str(valeur), Priorite.PRIMAIRE
            case Chaine(valeur):
                return self._texte_chaine(valeur), Priorite.PRIMAIRE
            case Booleen(valeur):
                return self._texte_booleen(valeur), Priorite.PRIMAIRE
            case Variable(nom):
                return self._texte_nom(nom), Priorite.PRIMAIRE
            case Unaire(operateur, operande):
                priorite = PRIORITES_UNAIRES[operateur]
                return self._texte_unaire(operateur) + self.expression(operande, priorite), priorite
            case Binaire(operateur, gauche, droite):
                priorite = PRIORITES_BINAIRES[operateur]
                # Associativité à gauche : à droite, il faut une priorité strictement plus
                # grande. Une comparaison en exige autant à gauche : Python lirait
                # `a < b < c` comme un enchaînement, et Cosmo le refuserait.
                min_gauche = priorite + 1 if priorite is Priorite.COMPARAISON else priorite
                g = self.expression(gauche, min_gauche)
                d = self.expression(droite, priorite + 1)
                return f"{g} {self._texte_binaire(operateur)} {d}", priorite
            case Appel(nom, arguments):
                return f"{self._texte_nom(nom)}({self._liste(arguments)})", Priorite.PRIMAIRE
            case _:
                assert_never(noeud)

    def _liste(self, expressions: tuple[Expression, ...]) -> str:
        return ", ".join(self.expression(expression) for expression in expressions)
