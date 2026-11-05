"""Étape 8 : la génération de Python (SPEC.md, section 6).

L'arbre, déjà vérifié par l'analyse sémantique, est traduit en texte Python :

- un `match` par union de nœuds, fermé par `assert_never` : si un nœud est ajouté à une
  union sans être traité ici, mypy le signale ;
- un gestionnaire de contexte pour l'indentation : un `with` par niveau, qu'on ne peut
  pas oublier de refermer ;
- les missions en tête du fichier : en Cosmo, on peut les appeler avant leur déclaration.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import assert_never

from cosmo.erreurs import ErreurGeneration, ErreursCompilation
from cosmo.noeuds import (
    Affectation,
    Appel,
    AppelSeul,
    Atterris,
    Binaire,
    Bloc,
    Booleen,
    Chaine,
    Detecte,
    Entier,
    Expression,
    Instruction,
    Mission,
    Module,
    OperateurBinaire,
    OperateurUnaire,
    Orbite,
    Programme,
    Survole,
    Transmets,
    Unaire,
    Variable,
)
from cosmo.parser import Priorite

INDENTATION = "    "

# Les noms du prélude ne peuvent rien heurter : tout nom Cosmo commence par `c_`.
PRELUDE = """\
# Généré par le compilateur Cosmo.
def _texte(valeur):
    if valeur is True:
        return "go"
    if valeur is False:
        return "nogo"
    if valeur is None:
        return "rien"
    return str(valeur)


def _transmets(*valeurs):
    print(*map(_texte, valeurs))


"""

OPERATEURS_BINAIRES: dict[OperateurBinaire, tuple[str, Priorite]] = {
    OperateurBinaire.OU: ("or", Priorite.OU),
    OperateurBinaire.ET: ("and", Priorite.ET),
    OperateurBinaire.EGAL: ("==", Priorite.COMPARAISON),
    OperateurBinaire.DIFFERENT: ("!=", Priorite.COMPARAISON),
    OperateurBinaire.INFERIEUR: ("<", Priorite.COMPARAISON),
    OperateurBinaire.INFERIEUR_EGAL: ("<=", Priorite.COMPARAISON),
    OperateurBinaire.SUPERIEUR: (">", Priorite.COMPARAISON),
    OperateurBinaire.SUPERIEUR_EGAL: (">=", Priorite.COMPARAISON),
    OperateurBinaire.PLUS: ("+", Priorite.SOMME),
    OperateurBinaire.MOINS: ("-", Priorite.SOMME),
    OperateurBinaire.FOIS: ("*", Priorite.PRODUIT),
    OperateurBinaire.DIVISE: ("//", Priorite.PRODUIT),
    OperateurBinaire.MODULO: ("%", Priorite.PRODUIT),
}
"""Opérateur Cosmo → son texte Python et sa priorité, qui suit le même ordre en Python."""

OPERATEURS_UNAIRES: dict[OperateurUnaire, tuple[str, Priorite]] = {
    OperateurUnaire.NON: ("not ", Priorite.NON),
    OperateurUnaire.MOINS: ("-", Priorite.UNAIRE),
}


def _nom(nom: str) -> str:
    """Le nom Python d'un nom Cosmo : `class` devient `c_class`, qui n'a rien de réservé."""
    return f"c_{nom}"


class GenerateurPython:
    """Traduit un arbre en texte Python."""

    def __init__(self) -> None:
        self._lignes: list[str] = []
        self._niveau = 0

    def generer(self, programme: Programme) -> str:
        """Renvoie le texte Python complet : prélude, missions, puis niveau principal."""
        for declaration in programme.declarations:
            if isinstance(declaration, Mission):
                self._mission(declaration)
                self._lignes.append("")
        for declaration in programme.declarations:
            if not isinstance(declaration, Mission):
                self.instruction(declaration)
        return PRELUDE + "".join(f"{ligne}\n" for ligne in self._lignes)

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

    def _bloc(self, entete: str, bloc: Bloc) -> None:
        """Écrit `entete` puis les instructions du bloc, indentées."""
        self._ecrire(entete)
        with self._indentation():
            for instruction in bloc.instructions:
                self.instruction(instruction)
            if not bloc.instructions:  # Python refuse un bloc vide
                self._ecrire("pass")

    def _mission(self, mission: Mission) -> None:
        parametres = ", ".join(_nom(parametre.nom) for parametre in mission.parametres)
        self._bloc(f"def {_nom(mission.nom)}({parametres}):", mission.corps)

    def instruction(self, noeud: Instruction) -> None:
        """Écrit les lignes Python d'une instruction."""
        match noeud:
            case Module(nom, valeur) | Affectation(nom, valeur):
                self._ecrire(f"{_nom(nom)} = {self.expression(valeur)}")
            case Transmets(valeurs):
                self._ecrire(f"_transmets({self._liste(valeurs)})")
            case Detecte():
                self._detecte(noeud, "if")
            case Orbite(condition, corps):
                self._bloc(f"while {self.expression(condition)}:", corps)
            case Survole(variable, debut, fin, corps):
                intervalle = f"range({self.expression(debut)}, {self.expression(fin)})"
                self._bloc(f"for {_nom(variable)} in {intervalle}:", corps)
            case Atterris(valeur):
                self._ecrire("return" if valeur is None else f"return {self.expression(valeur)}")
            case AppelSeul(appel):
                self._ecrire(self.expression(appel))
            case _:
                assert_never(noeud)

    def _detecte(self, noeud: Detecte, mot_cle: str) -> None:
        self._bloc(f"{mot_cle} {self.expression(noeud.condition)}:", noeud.alors)
        match noeud.sinon:
            case Detecte() as suite:
                self._detecte(suite, "elif")
            case Bloc() as bloc:
                self._bloc("else:", bloc)
            case None:
                pass
            case _ as jamais:
                assert_never(jamais)

    def expression(self, noeud: Expression, minimum: int = Priorite.OU) -> str:
        """Le texte Python d'une expression, entre parenthèses si sa place l'exige.

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
                return repr(valeur), Priorite.PRIMAIRE
            case Booleen(valeur):
                return repr(valeur), Priorite.PRIMAIRE
            case Variable(nom):
                return _nom(nom), Priorite.PRIMAIRE
            case Unaire(operateur, operande):
                texte, priorite = OPERATEURS_UNAIRES[operateur]
                return texte + self.expression(operande, priorite), priorite
            case Binaire(operateur, gauche, droite):
                texte, priorite = OPERATEURS_BINAIRES[operateur]
                # Associativité à gauche : à droite, il faut une priorité strictement plus
                # grande. Une comparaison en exige autant à gauche : Python lirait
                # `a < b < c` comme un enchaînement, qui n'a pas le sens de `(a < b) < c`.
                min_gauche = priorite + 1 if priorite is Priorite.COMPARAISON else priorite
                g = self.expression(gauche, min_gauche)
                d = self.expression(droite, priorite + 1)
                return f"{g} {texte} {d}", priorite
            case Appel(nom, arguments):
                return f"{_nom(nom)}({self._liste(arguments)})", Priorite.PRIMAIRE
            case _:
                assert_never(noeud)

    def _liste(self, expressions: tuple[Expression, ...]) -> str:
        return ", ".join(self.expression(expression) for expression in expressions)


def generer(programme: Programme) -> str:
    """Traduit un programme vérifié en texte Python.

    Lève ErreursCompilation si l'arbre est trop profond pour être parcouru.
    """
    try:
        return GenerateurPython().generer(programme)
    except RecursionError as cause:
        raise ErreursCompilation([trop_imbrique(programme)]) from cause


def trop_imbrique(programme: Programme) -> ErreurGeneration:
    """L'erreur d'un programme valide en Cosmo, mais qui dépasse les limites de Python."""
    return ErreurGeneration(
        "programme trop imbriqué pour être traduit en Python", programme.position
    )
