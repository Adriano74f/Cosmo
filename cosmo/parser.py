"""Étapes 5 et 6 : le parser des expressions (Pratt) et celui des instructions.

Plutôt qu'une fonction par niveau de la grammaire, on associe à chaque token une règle,
enregistrée par un décorateur paramétré, qui dit comment l'analyser :

- `@prefixe` : le token commence une expression (`42`, `x`, `(`, `non`, `-`) ;
- `@infixe` : le token continue une expression déjà lue (`+`, `et`, `<`...).

`Parser.expression` enchaîne ces règles en les cherchant dans deux tables. Ajouter un
opérateur revient à ajouter une règle : la boucle principale ne change pas.

Les instructions suivent la même idée : `@instruction` associe une règle au token qui
commence l'instruction. Une erreur dans une instruction est collectée, le parser se
resynchronise au début de l'instruction suivante, et `analyser_programme` signale d'un
seul coup toutes les erreurs trouvées.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import IntEnum

from cosmo.erreurs import ErreurCosmo, ErreursCompilation, ErreurSyntaxique
from cosmo.lexer import FluxTokens, analyser
from cosmo.noeuds import (
    Affectation,
    Appel,
    AppelSeul,
    Atterris,
    Binaire,
    Bloc,
    Booleen,
    Chaine,
    Declaration,
    Detecte,
    Entier,
    Expression,
    Instruction,
    Mission,
    Module,
    OperateurBinaire,
    OperateurUnaire,
    Orbite,
    Parametre,
    Programme,
    Sinon,
    Survole,
    Transmets,
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

# Les mots-clés où le parser peut reprendre après une erreur. Pas IDENT : un identifiant
# peut très bien se trouver au milieu de l'expression qui vient d'échouer.
DEBUTS_INSTRUCTION = (
    T.MODULE,
    T.MISSION,
    T.TRANSMETS,
    T.DETECTE,
    T.ORBITE,
    T.SURVOLE,
    T.ATTERRIS,
)

# Les règles sont de simples fonctions, rangées dans des tables (fonctions de 1ʳᵉ classe).
type AnalyseurPrefixe = Callable[[Parser, Token], Expression]
type AnalyseurInfixe = Callable[[Parser, Expression, Token, Priorite], Expression]
type AnalyseurInstruction = Callable[[Parser], Instruction]


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
REGLES_INSTRUCTIONS: dict[TypeToken, AnalyseurInstruction] = {}


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


def instruction(*types: TypeToken) -> Callable[[AnalyseurInstruction], AnalyseurInstruction]:
    """Enregistre la fonction décorée comme règle des instructions commençant par ces tokens."""

    def decorateur(fn: AnalyseurInstruction) -> AnalyseurInstruction:
        for type_token in types:
            REGLES_INSTRUCTIONS[type_token] = fn
        return fn

    return decorateur


class Parser:
    """Construit l'arbre syntaxique à partir d'une suite de tokens."""

    def __init__(self, tokens: Iterable[Token]) -> None:
        self.flux = FluxTokens(tokens)
        self.erreurs: list[ErreurCosmo] = []  # collectées au fil de l'analyse

    def programme(self) -> Programme:
        """Analyse tout le source. Ne lève pas : les erreurs sont dans `self.erreurs`.

        Deux erreurs arrêtent l'analyse, faute de pouvoir reprendre :
        - une erreur lexicale : le générateur du lexer s'est terminé en la levant, il ne
          produira plus aucun token ;
        - une imbrication trop profonde : la pile d'appels de Python est épuisée.
        """
        position = Position(1, 1)
        declarations: list[Declaration] = []
        try:
            position = self.flux.regarder().position
            self._lire_declarations(declarations)
        except ErreurCosmo as erreur:
            self._signaler(erreur)
        return Programme(tuple(declarations), position=position)

    def _lire_declarations(self, declarations: list[Declaration]) -> None:
        """Ajoute à `declarations` celles du niveau principal, jusqu'à la fin du source."""
        try:
            while not self.flux.est(T.FIN):
                declaration = self._avec_recuperation(self._declaration)
                if declaration is not None:
                    declarations.append(declaration)
        except RecursionError as cause:
            # On traduit l'erreur de Python en erreur de Cosmo, sans perdre son origine.
            raise ErreurSyntaxique(
                "imbrication trop profonde", self._apres_le_precedent()
            ) from cause

    def _declaration(self) -> Declaration:
        if self.flux.est(T.MISSION):
            return self._mission()
        return self.instruction()

    def _mission(self) -> Mission:
        self.flux.avancer()  # mission
        nom = self.attendre(T.IDENT)
        self.attendre(T.PAR_OUVRANTE)
        parametres: list[Parametre] = []
        if not self.flux.est(T.PAR_FERMANTE):
            parametres.append(self._parametre())
            while self.flux.accepter(T.VIRGULE) is not None:
                parametres.append(self._parametre())
        self.attendre(T.PAR_FERMANTE)
        return Mission(nom.texte, tuple(parametres), self.bloc(), position=nom.position)

    def _parametre(self) -> Parametre:
        nom = self.attendre(T.IDENT)
        return Parametre(nom.texte, position=nom.position)

    def bloc(self) -> Bloc:
        """Analyse `{ … }`. Une instruction erronée n'empêche pas de lire les suivantes."""
        ouvrante = self.attendre(T.ACC_OUVRANTE)
        instructions: list[Instruction] = []
        while not self.flux.est(T.ACC_FERMANTE, T.FIN):
            lue = self._avec_recuperation(self.instruction)
            if lue is not None:
                instructions.append(lue)
        self.attendre(T.ACC_FERMANTE)
        return Bloc(tuple(instructions), position=ouvrante.position)

    def instruction(self) -> Instruction:
        """Analyse une instruction, avec la règle associée à son premier token."""
        token = self.flux.regarder()
        if token.type is T.MISSION:
            raise ErreurSyntaxique(
                "une mission ne se déclare qu'au niveau principal", token.position
            )
        regle = REGLES_INSTRUCTIONS.get(token.type)
        if regle is None:
            raise ErreurSyntaxique("instruction attendue", token.position)
        return regle(self)

    def _avec_recuperation[N](self, analyse: Callable[[], N]) -> N | None:
        """Lance `analyse`. En cas d'erreur, la collecte, resynchronise et renvoie None."""
        avant = self.flux.precedent
        try:
            return analyse()
        except ErreurSyntaxique as erreur:
            self._signaler(erreur)
            self._synchroniser(aucun_progres=self.flux.precedent is avant)
            return None

    def _signaler(self, erreur: ErreurCosmo) -> None:
        """Collecte une erreur, sauf si la même position vient déjà d'en signaler une.

        Sans cela, un « } » manquant en fin de fichier serait signalé une fois par bloc
        encore ouvert, toujours au même endroit.
        """
        if not self.erreurs or self.erreurs[-1].position != erreur.position:
            self.erreurs.append(erreur)

    def _synchroniser(self, aucun_progres: bool) -> None:
        """Saute des tokens jusqu'à un endroit où une instruction peut commencer.

        On s'arrête après un « ; » ou après le « } » d'un bloc sauté en entier, et avant un
        mot-clé d'instruction ou le « } » du bloc englobant. Les accolades sont comptées pour
        ne pas prendre le contenu d'un bloc abîmé pour une suite d'instructions.

        Si l'instruction n'a consommé aucun token (`aucun_progres`), le premier est sauté
        d'office : sinon, le parser buterait indéfiniment sur le même.
        """
        profondeur = 0
        while not self.flux.est(T.FIN):
            reprise_possible = self.flux.est(*DEBUTS_INSTRUCTION, T.ACC_FERMANTE)
            if reprise_possible and profondeur == 0 and not aucun_progres:
                return
            aucun_progres = False
            token = self.flux.avancer()
            if token.type is T.ACC_OUVRANTE:
                profondeur += 1
            elif token.type is T.ACC_FERMANTE:
                profondeur = max(0, profondeur - 1)
                # Le « sinon » qui suit appartient encore à l'instruction abîmée.
                if profondeur == 0 and not self.flux.est(T.SINON):
                    return
            elif token.type is T.POINT_VIRGULE and profondeur == 0:
                return

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


# --- Règles d'instruction : chacune consomme tout, du premier token au dernier -------


@instruction(T.MODULE)
def _module(parser: Parser) -> Instruction:
    parser.flux.avancer()
    nom = parser.attendre(T.IDENT)
    parser.attendre(T.EGAL)
    valeur = parser.expression()
    parser.attendre(T.POINT_VIRGULE)
    return Module(nom.texte, valeur, position=nom.position)


@instruction(T.IDENT)
def _affectation_ou_appel(parser: Parser) -> Instruction:
    # Le regard en avant : les deux instructions commencent par un identifiant.
    nom = parser.flux.regarder()
    suivant = parser.flux.regarder(1)
    if suivant.type is T.EGAL:
        parser.flux.avancer()
        parser.flux.avancer()
        valeur = parser.expression()
        parser.attendre(T.POINT_VIRGULE)
        return Affectation(nom.texte, valeur, position=nom.position)
    if suivant.type is T.PAR_OUVRANTE:
        # À cette priorité, aucun opérateur ne peut prolonger l'appel : `f() + 1;` est refusé.
        appel = parser.expression(Priorite.PRIMAIRE)
        assert isinstance(appel, Appel)
        parser.attendre(T.POINT_VIRGULE)
        return AppelSeul(appel, position=nom.position)
    parser.flux.avancer()
    raise ErreurSyntaxique(
        f"« = » ou « ( » attendu après « {nom.texte} »", parser._apres_le_precedent()
    )


@instruction(T.TRANSMETS)
def _transmets(parser: Parser) -> Instruction:
    mot = parser.flux.avancer()
    valeurs: list[Expression] = []
    if not parser.flux.est(T.POINT_VIRGULE):
        valeurs.append(parser.expression())
        while parser.flux.accepter(T.VIRGULE) is not None:
            valeurs.append(parser.expression())
    parser.attendre(T.POINT_VIRGULE)
    return Transmets(tuple(valeurs), position=mot.position)


@instruction(T.DETECTE)
def _instruction_detecte(parser: Parser) -> Instruction:
    return _detecte(parser)


def _detecte(parser: Parser) -> Detecte:
    mot = parser.flux.avancer()
    condition = parser.expression()
    alors = parser.bloc()
    sinon: Sinon = None
    if parser.flux.accepter(T.SINON) is not None:
        sinon = _detecte(parser) if parser.flux.est(T.DETECTE) else parser.bloc()
    return Detecte(condition, alors, sinon, position=mot.position)


@instruction(T.ORBITE)
def _orbite(parser: Parser) -> Instruction:
    mot = parser.flux.avancer()
    condition = parser.expression()
    return Orbite(condition, parser.bloc(), position=mot.position)


@instruction(T.SURVOLE)
def _survole(parser: Parser) -> Instruction:
    parser.flux.avancer()
    variable = parser.attendre(T.IDENT)
    parser.attendre(T.DANS)
    debut = parser.expression()
    parser.attendre(T.POINT_POINT)
    fin = parser.expression()
    return Survole(variable.texte, debut, fin, parser.bloc(), position=variable.position)


@instruction(T.ATTERRIS)
def _atterris(parser: Parser) -> Instruction:
    mot = parser.flux.avancer()
    valeur = None if parser.flux.est(T.POINT_VIRGULE) else parser.expression()
    parser.attendre(T.POINT_VIRGULE)
    return Atterris(valeur, position=mot.position)


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


def analyser_programme(source: str) -> Programme:
    """Analyse un programme complet.

    Lève ErreursCompilation avec toutes les erreurs trouvées, causée par la première.
    """
    parser = Parser(analyser(source))
    programme = parser.programme()
    if parser.erreurs:
        raise ErreursCompilation(parser.erreurs) from parser.erreurs[0]
    return programme
