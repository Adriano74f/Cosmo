"""Les erreurs de compilation de Cosmo.

Chaque erreur connaît sa position dans le source : c'est ce qui permet d'afficher
`[1:11] erreur lexicale : chaîne non terminée`.
Une phase qui sait continuer après une erreur les collecte, puis les lève toutes d'un
coup dans une `ErreursCompilation`.
"""

from collections.abc import Iterable

from cosmo.tokens import Position


class ErreurCosmo(Exception):
    """Classe de base de toutes les erreurs de compilation."""

    phase = "de compilation"

    def __init__(self, message: str, position: Position) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:
        return f"[{self.position}] erreur {self.phase} : {self.message}"


class ErreurLexicale(ErreurCosmo):
    """Le texte contient quelque chose qui ne forme aucun token valide."""

    phase = "lexicale"


class ErreurSyntaxique(ErreurCosmo):
    """Les tokens sont valides, mais leur enchaînement ne respecte pas la grammaire."""

    phase = "syntaxique"


class ErreurSemantique(ErreurCosmo):
    """La grammaire est respectée, mais le programme n'a pas de sens (nom inconnu, doublon...)."""

    phase = "sémantique"


class ErreurGeneration(ErreurCosmo):
    """Le programme est valide en Cosmo, mais sa traduction dépasse les limites de Python."""

    phase = "de génération"


class ErreursCompilation(Exception):
    """Toutes les erreurs collectées par une phase de compilation.

    Elle est levée avec `raise ... from` : la première erreur en est la cause.
    Sa représentation texte contient une erreur par ligne.
    """

    def __init__(self, erreurs: Iterable[ErreurCosmo]) -> None:
        self.erreurs = tuple(erreurs)
        super().__init__("\n".join(str(erreur) for erreur in self.erreurs))
