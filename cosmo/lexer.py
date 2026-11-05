"""Étape 3 : le lexer, et un flux de tokens avec regard en avant.

Le lexer lit le texte caractère par caractère et produit les tokens un par un,
grâce à un générateur (`yield`). Le flux enveloppe ce générateur pour que le
parser puisse regarder les tokens suivants sans les consommer.
"""

from collections import deque
from collections.abc import Iterable, Iterator

from cosmo.erreurs import ErreurLexicale
from cosmo.tokens import MOTS_CLES, SYMBOLES, Commentaire, Position, Token, TypeToken

CHIFFRES = "0123456789"
LETTRES = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
ESPACES = " \t\r"
ECHAPPEMENTS = {'"': '"', "\\": "\\", "n": "\n"}

# Les symboles les plus longs d'abord : on essaie "<=" avant "<".
SYMBOLES_PAR_LONGUEUR = sorted(SYMBOLES, key=len, reverse=True)


def analyser(source: str, commentaires: list[Commentaire] | None = None) -> Iterator[Token]:
    """Découpe `source` en tokens, produits un par un, et termine par FIN.

    Les commentaires ne sont pas des tokens : ils sont ajoutés à la liste `commentaires`,
    si elle est fournie, pour le formateur (étape 10).

    Lève ErreurLexicale, avec sa position, au premier caractère invalide.
    Comme c'est un générateur, les tokens qui précèdent l'erreur ont déjà été produits.
    """
    i = 0  # indice du caractère courant dans source
    ligne = 1
    debut_ligne = 0  # indice du premier caractère de la ligne courante

    while i < len(source):
        c = source[i]
        position = Position(ligne, i - debut_ligne + 1)

        # Saut de ligne : on change de ligne, la colonne repartira à 1.
        if c == "\n":
            i += 1
            ligne += 1
            debut_ligne = i

        # Espaces : ignorés.
        elif c in ESPACES:
            i += 1

        # Commentaire : on saute jusqu'à la fin de la ligne (sans consommer le \n).
        elif c == "#":
            debut = i
            while i < len(source) and source[i] != "\n":
                i += 1
            if commentaires is not None:
                commentaires.append(Commentaire(source[debut:i].rstrip(), position))

        # Entier : une suite de chiffres.
        elif c in CHIFFRES:
            debut = i
            while i < len(source) and source[i] in CHIFFRES:
                i += 1
            texte = source[debut:i]
            try:
                valeur = int(texte)
            except ValueError as cause:  # Python limite la taille d'un entier écrit en texte
                raise ErreurLexicale("entier trop grand", position) from cause
            yield Token(TypeToken.ENTIER, texte, position, valeur)

        # Identifiant ou mot-clé : une lettre, puis des lettres ou des chiffres.
        elif c in LETTRES:
            debut = i
            while i < len(source) and (source[i] in LETTRES or source[i] in CHIFFRES):
                i += 1
            texte = source[debut:i]
            type_token = MOTS_CLES.get(texte, TypeToken.IDENT)
            yield Token(type_token, texte, position)

        # Chaîne : entre guillemets, sur une seule ligne.
        elif c == '"':
            i, token = _lire_chaine(source, i, position)
            yield token

        # Symbole : on prend le plus long qui correspond.
        else:
            for symbole in SYMBOLES_PAR_LONGUEUR:
                if source.startswith(symbole, i):
                    i += len(symbole)
                    yield Token(SYMBOLES[symbole], symbole, position)
                    break
            else:  # aucun break : aucun symbole ne correspond
                raise ErreurLexicale(f"caractère inattendu « {c} »", position)

    yield Token(TypeToken.FIN, "", Position(ligne, i - debut_ligne + 1))


def _lire_chaine(source: str, i: int, position: Position) -> tuple[int, Token]:
    """Lit la chaîne qui commence au guillemet source[i].

    Renvoie l'indice juste après le guillemet fermant, et le token.
    """
    debut = i
    i += 1  # on passe le guillemet ouvrant
    morceaux: list[str] = []
    while True:
        if i >= len(source) or source[i] == "\n":
            raise ErreurLexicale("chaîne non terminée", position)
        c = source[i]
        if c == '"':
            i += 1
            texte = source[debut:i]
            return i, Token(TypeToken.CHAINE, texte, position, "".join(morceaux))
        if c == "\\":
            suivant = source[i + 1] if i + 1 < len(source) else ""
            if suivant not in ECHAPPEMENTS:
                colonne = position.colonne + (i - debut)
                raise ErreurLexicale(
                    f"échappement inconnu « \\{suivant} »",
                    Position(position.ligne, colonne),
                )
            morceaux.append(ECHAPPEMENTS[suivant])
            i += 2
        else:
            morceaux.append(c)
            i += 1


class FluxTokens:
    """Un flux de tokens qui permet de regarder en avant sans consommer.

    Le parser en a besoin : face à un identifiant, il regarde le token suivant
    pour savoir s'il lit une affectation (`x = ...`) ou un appel (`f(...)`).

    Les tokens sont lus à la demande dans le générateur, et gardés dans un tampon
    tant qu'ils n'ont pas été consommés. Une fois FIN atteint, le flux renvoie
    FIN indéfiniment : le parser n'a jamais à gérer « plus de token du tout ».
    """

    def __init__(self, tokens: Iterable[Token]) -> None:
        self._source = iter(tokens)
        self._tampon: deque[Token] = deque()
        self._fin: Token | None = None
        self.precedent: Token | None = None  # le dernier token consommé

    def regarder(self, decalage: int = 0) -> Token:
        """Renvoie le token situé `decalage` positions plus loin, sans le consommer."""
        while len(self._tampon) <= decalage:
            self._tampon.append(self._lire())
        return self._tampon[decalage]

    def avancer(self) -> Token:
        """Consomme et renvoie le token courant."""
        token = self.regarder()
        self._tampon.popleft()
        self.precedent = token
        return token

    def est(self, *types: TypeToken) -> bool:
        """Le token courant est-il de l'un de ces types ?"""
        return self.regarder().type in types

    def accepter(self, *types: TypeToken) -> Token | None:
        """Consomme le token courant s'il est de l'un de ces types, sinon renvoie None."""
        if self.est(*types):
            return self.avancer()
        return None

    def _lire(self) -> Token:
        """Lit le token suivant dans le générateur, ou répète FIN s'il est épuisé."""
        if self._fin is not None:
            return self._fin
        token = next(self._source)
        if token.type is TypeToken.FIN:
            self._fin = token
        return token
