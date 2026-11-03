"""Étape 2 : les types de token et la classe Token.

Un token est le plus petit morceau qui a un sens dans un programme Cosmo :
un mot-clé (`module`), un nom (`altitude`), un nombre (`42`), un symbole (`<=`)...
Le lexer (étape 3) découpe le texte source en une suite de tokens.
"""

from dataclasses import dataclass
from enum import Enum


class TypeToken(Enum):
    """Toutes les sortes de tokens de Cosmo.

    Pour les mots-clés et les symboles, la valeur est le texte exact du token :
    `TypeToken("<=")` retrouve donc `TypeToken.INFERIEUR_EGAL`.
    Pour les autres, c'est un nom lisible, utilisé dans les messages d'erreur.
    """

    # Littéraux et identifiants : leur texte varie d'un token à l'autre.
    ENTIER = "entier"
    CHAINE = "chaîne"
    IDENT = "identifiant"

    # Mots-clés
    MODULE = "module"
    MISSION = "mission"
    ATTERRIS = "atterris"
    DETECTE = "detecte"
    SINON = "sinon"
    ORBITE = "orbite"
    SURVOLE = "survole"
    DANS = "dans"
    TRANSMETS = "transmets"
    GO = "go"
    NOGO = "nogo"
    ET = "et"
    OU = "ou"
    NON = "non"

    # Opérateurs
    PLUS = "+"
    MOINS = "-"
    FOIS = "*"
    DIVISE = "/"
    MODULO = "%"
    EGAL_EGAL = "=="
    DIFFERENT = "!="
    INFERIEUR = "<"
    INFERIEUR_EGAL = "<="
    SUPERIEUR = ">"
    SUPERIEUR_EGAL = ">="
    EGAL = "="

    # Ponctuation
    PAR_OUVRANTE = "("
    PAR_FERMANTE = ")"
    ACC_OUVRANTE = "{"
    ACC_FERMANTE = "}"
    VIRGULE = ","
    POINT_VIRGULE = ";"
    POINT_POINT = ".."

    # Fin du texte source : le parser s'arrête quand il la rencontre.
    FIN = "fin de fichier"


MOTS_CLES: dict[str, TypeToken] = {
    t.value: t
    for t in (
        TypeToken.MODULE,
        TypeToken.MISSION,
        TypeToken.ATTERRIS,
        TypeToken.DETECTE,
        TypeToken.SINON,
        TypeToken.ORBITE,
        TypeToken.SURVOLE,
        TypeToken.DANS,
        TypeToken.TRANSMETS,
        TypeToken.GO,
        TypeToken.NOGO,
        TypeToken.ET,
        TypeToken.OU,
        TypeToken.NON,
    )
}
"""Texte d'un mot réservé → son type de token."""

SYMBOLES: dict[str, TypeToken] = {
    t.value: t
    for t in TypeToken
    if t not in MOTS_CLES.values()
    and t not in (TypeToken.ENTIER, TypeToken.CHAINE, TypeToken.IDENT, TypeToken.FIN)
}
"""Texte d'un symbole → son type de token (tout ce qui n'est ni mot-clé ni littéral)."""


@dataclass(frozen=True)
class Position:
    """Une position dans le texte source. Ligne et colonne commencent à 1."""

    ligne: int
    colonne: int

    def __str__(self) -> str:
        return f"{self.ligne}:{self.colonne}"


@dataclass(frozen=True)
class Token:
    """Un token : son type, le texte exact lu dans la source, et sa position.

    `valeur` contient la valeur Python du littéral : l'entier pour ENTIER,
    la chaîne décodée (échappements traduits) pour CHAINE, None sinon.
    """

    type: TypeToken
    texte: str
    position: Position
    valeur: int | str | None = None

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.texte!r}, {self.position})"
