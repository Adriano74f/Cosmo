"""Étape 5 : le parser des expressions, par la méthode de Pratt.

Plutôt qu'une fonction par niveau de la grammaire, on associe à chaque token une règle,
enregistrée par un décorateur paramétré, qui dit comment l'analyser :

- `@prefixe` : le token commence une expression (`42`, `x`, `(`, `non`, `-`) ;
- `@infixe` : le token continue une expression déjà lue (`+`, `et`, `<`...).

`Parser.expression` enchaîne ces règles en les cherchant dans deux tables. Ajouter un
opérateur revient à ajouter une règle : la boucle principale ne change pas.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import IntEnum

from cosmo.erreurs import ErreurSyntaxique
from cosmo.lexer import FluxTokens, analyser
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
from cosmo.tokens import Position, Token, TypeToken

T = TypeToken


class Priorite(IntEnum):
    """Les niveaux de priorité, du moins au plus prioritaire (SPEC.md, section 3.3)."""

    OU = 1
    ET = 2
    NON = 3
    COMPARAISON = 4
    SOMME = 5
    PRODUIT = 6
    UNAIRE = 7
    PRIMAIRE = 8


COMPARAISONS = (
    T.EGAL_EGAL,
    T.DIFFERENT,
    T.INFERIEUR,
    T.INFERIEUR_EGAL,
    T.SUPERIEUR,
    T.SUPERIEUR_EGAL,
)

# Les règles sont de simples fonctions, rangées dans des tables (fonctions de 1ʳᵉ classe).
type AnalyseurPrefixe = Callable[[Parser, Token], Expression]
type AnalyseurInfixe = Callable[[Parser, Expression, Token, Priorite], Expression]


@dataclass(frozen=True)
class ReglePrefixe:
    """Comment analyser un token qui commence une expression.

    La priorité indique où ce token est permis : la grammaire accepte `a et non b`,
    mais pas `a + non b`, où il faut écrire `a + (non b)`.
    """

    priorite: Priorite
    analyser: AnalyseurPrefixe


@dataclass(frozen=True)
class RegleInfixe:
    """Comment analyser un token placé entre deux expressions, et sa priorité."""

    priorite: Priorite
    analyser: AnalyseurInfixe


REGLES_PREFIXES: dict[TypeToken, ReglePrefixe] = {}
REGLES_INFIXES: dict[TypeToken, RegleInfixe] = {}


def prefixe(
    *types: TypeToken, priorite: Priorite = Priorite.PRIMAIRE
) -> Callable[[AnalyseurPrefixe], AnalyseurPrefixe]:
    """Enregistre la fonction décorée comme règle préfixe de ces types de token."""

    def decorateur(fn: AnalyseurPrefixe) -> AnalyseurPrefixe:
        for type_token in types:
            REGLES_PREFIXES[type_token] = ReglePrefixe(priorite, fn)
        return fn

    return decorateur


def infixe(*types: TypeToken, priorite: Priorite) -> Callable[[AnalyseurInfixe], AnalyseurInfixe]:
    """Enregistre la fonction décorée comme règle infixe de ces types de token."""

    def decorateur(fn: AnalyseurInfixe) -> AnalyseurInfixe:
        for type_token in types:
            REGLES_INFIXES[type_token] = RegleInfixe(priorite, fn)
        return fn

    return decorateur


class Parser:
    """Construit l'arbre syntaxique à partir d'une suite de tokens."""

    def __init__(self, tokens: Iterable[Token]) -> None:
        self.flux = FluxTokens(tokens)

    def expression(self, minimum: int = Priorite.OU) -> Expression:
        """Analyse une expression dont les opérateurs ont au moins la priorité `minimum`.

        C'est le cœur de la méthode de Pratt : on lit le début de l'expression, puis on
        l'étend tant que l'opérateur suivant est assez prioritaire. Sinon, on s'arrête et
        cet opérateur revient à l'appelant, qui l'appliquera au résultat complet.
        """
        token = self.flux.regarder()
        regle_prefixe = REGLES_PREFIXES.get(token.type)
        if regle_prefixe is None or regle_prefixe.priorite < minimum:
            raise ErreurSyntaxique("expression attendue", token.position)
        self.flux.avancer()
        gauche = regle_prefixe.analyser(self, token)

        while True:
            regle_infixe = REGLES_INFIXES.get(self.flux.regarder().type)
            if regle_infixe is None or regle_infixe.priorite < minimum:
                return gauche
            operateur = self.flux.avancer()
            gauche = regle_infixe.analyser(self, gauche, operateur, regle_infixe.priorite)

    def attendre(self, type_token: TypeToken) -> Token:
        """Consomme un token de ce type, ou lève une erreur juste après le token précédent.

        C'est là que le token manque : un « ; » oublié se signale en fin de ligne, et non
        sur la ligne suivante.
        """
        token = self.flux.accepter(type_token)
        if token is None:
            raise ErreurSyntaxique(f"« {type_token.value} » attendu", self._apres_le_precedent())
        return token

    def _apres_le_precedent(self) -> Position:
        """La position juste après le dernier token consommé (un token tient sur une ligne)."""
        precedent = self.flux.precedent
        if precedent is None:
            return self.flux.regarder().position
        return Position(precedent.position.ligne, precedent.position.colonne + len(precedent.texte))


# --- Règles préfixes : ce qui peut commencer une expression ------------------


@prefixe(T.ENTIER)
def _entier(parser: Parser, token: Token) -> Expression:
    assert isinstance(token.valeur, int)
    return Entier(token.valeur, position=token.position)


@prefixe(T.CHAINE)
def _chaine(parser: Parser, token: Token) -> Expression:
    assert isinstance(token.valeur, str)
    return Chaine(token.valeur, position=token.position)


@prefixe(T.GO, T.NOGO)
def _booleen(parser: Parser, token: Token) -> Expression:
    return Booleen(token.type is T.GO, position=token.position)


@prefixe(T.IDENT)
def _variable_ou_appel(parser: Parser, token: Token) -> Expression:
    if parser.flux.accepter(T.PAR_OUVRANTE) is None:
        return Variable(token.texte, position=token.position)
    arguments: list[Expression] = []
    if not parser.flux.est(T.PAR_FERMANTE):
        arguments.append(parser.expression())
        while parser.flux.accepter(T.VIRGULE) is not None:
            arguments.append(parser.expression())
    parser.attendre(T.PAR_FERMANTE)
    return Appel(token.texte, tuple(arguments), position=token.position)


@prefixe(T.PAR_OUVRANTE)
def _parentheses(parser: Parser, token: Token) -> Expression:
    interieur = parser.expression()
    parser.attendre(T.PAR_FERMANTE)
    return interieur


@prefixe(T.NON, priorite=Priorite.NON)
def _non(parser: Parser, token: Token) -> Expression:
    operande = parser.expression(Priorite.NON)
    return Unaire(OperateurUnaire.NON, operande, position=token.position)


@prefixe(T.MOINS, priorite=Priorite.UNAIRE)
def _moins(parser: Parser, token: Token) -> Expression:
    operande = parser.expression(Priorite.UNAIRE)
    return Unaire(OperateurUnaire.MOINS, operande, position=token.position)


# --- Règles infixes : ce qui peut continuer une expression -------------------


@infixe(T.OU, priorite=Priorite.OU)
@infixe(T.ET, priorite=Priorite.ET)
@infixe(T.PLUS, T.MOINS, priorite=Priorite.SOMME)
@infixe(T.FOIS, T.DIVISE, T.MODULO, priorite=Priorite.PRODUIT)
def _binaire(
    parser: Parser, gauche: Expression, operateur: Token, priorite: Priorite
) -> Expression:
    # Associativité à gauche : à droite, on exige une priorité strictement plus grande. Dans
    # `a - b - c`, l'opérande droit s'arrête donc à `b`, et la boucle applique ensuite `- c`.
    droite = parser.expression(priorite + 1)
    return Binaire(OperateurBinaire(operateur.texte), gauche, droite, position=operateur.position)


@infixe(*COMPARAISONS, priorite=Priorite.COMPARAISON)
def _comparaison(
    parser: Parser, gauche: Expression, operateur: Token, priorite: Priorite
) -> Expression:
    resultat = _binaire(parser, gauche, operateur, priorite)
    suivant = parser.flux.regarder()
    if suivant.type in COMPARAISONS:
        raise ErreurSyntaxique(
            "comparaisons enchaînées : ajoutez des parenthèses", suivant.position
        )
    return resultat


def analyser_expression(source: str) -> Expression:
    """Analyse un texte qui contient exactement une expression, et rien d'autre."""
    parser = Parser(analyser(source))
    expression = parser.expression()
    suivant = parser.flux.regarder()
    if suivant.type is not T.FIN:
        raise ErreurSyntaxique(
            f"« {suivant.texte} » inattendu après l'expression", suivant.position
        )
    return expression
