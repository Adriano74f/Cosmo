"""La façade du compilateur : un point d'entrée unique vers toute la chaîne.

source → lexer → parser → analyse sémantique → backend

La ligne de commande et le REPL ne connaissent que ce module : ils n'ont pas à savoir dans
quel ordre s'enchaînent les phases.
"""

from collections.abc import Iterator

from cosmo.backend import BACKEND_PAR_DEFAUT, BACKENDS, Backend
from cosmo.erreurs import ErreurCosmo
from cosmo.generateur import nom_python, traduire
from cosmo.lexer import analyser
from cosmo.noeuds import Expression, Programme, Transmets
from cosmo.parser import analyser_expression, analyser_programme
from cosmo.semantique import AnalyseurSemantique, analyser_semantique
from cosmo.tokens import Token


def _analyser(source: str) -> Programme:
    """Fait passer le source par les phases communes à tous les backends."""
    programme = analyser_programme(source)
    analyser_semantique(programme)
    return programme


def tokens(source: str) -> Iterator[Token]:
    """Les tokens du source, produits un par un. Lève ErreurLexicale au premier invalide."""
    return analyser(source)


def arbre(source: str) -> Programme:
    """L'arbre syntaxique du source, sans analyse sémantique. Lève ErreursCompilation."""
    return analyser_programme(source)


def verifier(source: str) -> None:
    """Compile le source sans l'exécuter. Lève ErreursCompilation s'il est erroné."""
    traduire(_analyser(source))


def transpiler(source: str, backend: Backend = BACKENDS[BACKEND_PAR_DEFAUT]) -> str:
    """Traduit un source Cosmo avec ce backend. Lève ErreursCompilation s'il est erroné."""
    return backend.generer(_analyser(source))


def formater(source: str) -> str:
    """Le source réécrit au format canonique. Lève ErreursCompilation si sa syntaxe est fausse.

    Il n'y a pas d'analyse sémantique : on peut formater un programme encore inachevé.
    """
    return BACKENDS["cosmo"].generer(analyser_programme(source))


def executer(source: str) -> None:
    """Compile et exécute un source Cosmo.

    Lève ErreursCompilation s'il est erroné. Les erreurs d'exécution (division par zéro,
    types incompatibles) sont les exceptions de Python, qui remontent telles quelles.
    """
    _, code = traduire(_analyser(source))
    exec(code, {"__name__": "__cosmo__"})  # noqa: S102 : le code vient de notre compilateur


def lire_expression(source: str) -> Expression | None:
    """L'expression que forme le source à lui seul, ou None s'il n'en forme pas une."""
    try:
        return analyser_expression(source)
    except (ErreurCosmo, RecursionError):
        return None


class Session:
    """Plusieurs entrées exécutées l'une après l'autre, qui partagent leurs déclarations.

    C'est le cœur du REPL. Le texte des entrées précédentes n'est jamais recompilé (leurs
    `transmets` seraient rejoués) : on garde l'état de l'analyse sémantique, et les valeurs
    dans un espace de noms Python. Les deux doivent rester d'accord sur ce qui existe.
    """

    def __init__(self) -> None:
        self._analyseur = AnalyseurSemantique()
        self._espace: dict[str, object] = {"__name__": "__cosmo__"}

    def executer(self, source: str) -> None:
        """Exécute une entrée : des instructions, ou une expression dont on affiche la valeur.

        Lève ErreursCompilation si elle est erronée : la session reste alors inchangée.
        Les erreurs d'exécution remontent ; ce qui a été exécuté avant elles est conservé.
        """
        expression = lire_expression(source)
        if expression is None:
            programme = analyser_programme(source)
        else:
            position = expression.position
            afficher = Transmets((expression,), position=position)
            programme = Programme((afficher,), position=position)
        self._analyseur.verifier_entree(programme)
        try:
            _, code = traduire(programme)
            exec(code, self._espace)  # noqa: S102 : le code vient de notre compilateur
        except BaseException:  # KeyboardInterrupt compris : Ctrl-C arrête l'exécution en cours
            self._analyseur.retenir(lambda nom: nom_python(nom) in self._espace)
            raise
        finally:
            self._oublier_variables_de_blocs()

    def _oublier_variables_de_blocs(self) -> None:
        """Retire de l'espace Python les variables dont la portée Cosmo est terminée.

        Un bloc Python n'ouvre pas de portée : sans cela, une valeur périmée pourrait passer
        pour celle d'une déclaration ultérieure qui a échoué.
        """
        vivants = {nom_python(nom) for nom in self._analyseur.noms_du_niveau_principal()}
        for nom in [nom for nom in self._espace if nom.startswith("c_") and nom not in vivants]:
            del self._espace[nom]
