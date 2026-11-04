"""Les erreurs de compilation de Cosmo.

Chaque erreur connaît sa position dans le source : c'est ce qui permet d'afficher
`[1:11] erreur lexicale : chaîne non terminée`.
Les phases suivantes (syntaxique, sémantique) ajouteront leur sous-classe.
"""

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
