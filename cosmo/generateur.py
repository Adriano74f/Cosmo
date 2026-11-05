"""Étape 8 : la génération de Python (SPEC.md, section 6).

L'arbre, déjà vérifié par l'analyse sémantique, est traduit en texte Python :

- un `match` par union de nœuds, fermé par `assert_never` : si un nœud est ajouté à une
  union sans être traité ici, mypy le signale ;
- un gestionnaire de contexte pour l'indentation : un `with` par niveau, qu'on ne peut
  pas oublier de refermer ;
- les missions en tête du fichier : en Cosmo, on peut les appeler avant leur déclaration.
"""

from types import CodeType
from typing import assert_never

from cosmo.erreurs import ErreurGeneration, ErreursCompilation
from cosmo.noeuds import (
    Affectation,
    AppelSeul,
    Atterris,
    Bloc,
    Detecte,
    Instruction,
    Mission,
    Module,
    OperateurBinaire,
    OperateurUnaire,
    Orbite,
    Programme,
    Survole,
    Transmets,
)
from cosmo.rendu import GenerateurTexte

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

OPERATEURS_BINAIRES: dict[OperateurBinaire, str] = {
    OperateurBinaire.OU: "or",
    OperateurBinaire.ET: "and",
    OperateurBinaire.DIVISE: "//",
}
"""Les opérateurs qui s'écrivent autrement en Python qu'en Cosmo."""

OPERATEURS_UNAIRES: dict[OperateurUnaire, str] = {
    OperateurUnaire.NON: "not ",
    OperateurUnaire.MOINS: "-",
}


def nom_python(nom: str) -> str:
    """Le nom Python d'un nom Cosmo : `class` devient `c_class`, qui n'a rien de réservé."""
    return f"c_{nom}"


class GenerateurPython(GenerateurTexte):
    """Traduit un arbre en texte Python."""

    def _texte_nom(self, nom: str) -> str:
        return nom_python(nom)

    def _texte_chaine(self, valeur: str) -> str:
        return repr(valeur)

    def _texte_booleen(self, valeur: bool) -> str:
        return repr(valeur)

    def _texte_binaire(self, operateur: OperateurBinaire) -> str:
        return OPERATEURS_BINAIRES.get(operateur, operateur.value)

    def _texte_unaire(self, operateur: OperateurUnaire) -> str:
        return OPERATEURS_UNAIRES[operateur]

    def generer(self, programme: Programme) -> str:
        """Renvoie le texte Python complet : prélude, missions, puis niveau principal."""
        for declaration in programme.declarations:
            if isinstance(declaration, Mission):
                self._mission(declaration)
                self._lignes.append("")
        for declaration in programme.declarations:
            if not isinstance(declaration, Mission):
                self.instruction(declaration)
        return PRELUDE + self._texte_complet()

    def _bloc(self, entete: str, bloc: Bloc) -> None:
        """Écrit `entete` puis les instructions du bloc, indentées."""
        self._ecrire(entete)
        with self._indentation():
            for instruction in bloc.instructions:
                self.instruction(instruction)
            if not bloc.instructions:  # Python refuse un bloc vide
                self._ecrire("pass")

    def _mission(self, mission: Mission) -> None:
        parametres = ", ".join(nom_python(parametre.nom) for parametre in mission.parametres)
        self._bloc(f"def {nom_python(mission.nom)}({parametres}):", mission.corps)

    def instruction(self, noeud: Instruction) -> None:
        """Écrit les lignes Python d'une instruction."""
        match noeud:
            case Module(nom, valeur) | Affectation(nom, valeur):
                self._ecrire(f"{nom_python(nom)} = {self.expression(valeur)}")
            case Transmets(valeurs):
                self._ecrire(f"_transmets({self._liste(valeurs)})")
            case Detecte():
                self._detecte(noeud, "if")
            case Orbite(condition, corps):
                self._bloc(f"while {self.expression(condition)}:", corps)
            case Survole(variable, debut, fin, corps):
                intervalle = f"range({self.expression(debut)}, {self.expression(fin)})"
                self._bloc(f"for {nom_python(variable)} in {intervalle}:", corps)
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


def traduire(programme: Programme) -> tuple[str, CodeType]:
    """Génère le Python d'un programme vérifié : renvoie le texte et le code compilé.

    Un programme valide en Cosmo peut encore dépasser les limites de Python : plus de 20
    boucles imbriquées, par exemple. Ce refus devient une erreur de compilation Cosmo.
    """
    texte = generer(programme)
    try:
        return texte, compile(texte, "<cosmo>", "exec")
    except (SyntaxError, RecursionError, MemoryError) as cause:
        raise ErreursCompilation([trop_imbrique(programme)]) from cause


class BackendPython:
    """Le backend principal : du Python que l'interpréteur accepte à coup sûr."""

    def generer(self, programme: Programme) -> str:
        return traduire(programme)[0]
