"""La façade du compilateur : un point d'entrée unique vers toute la chaîne.

source → lexer → parser → analyse sémantique → génération → compilation Python

La ligne de commande et le REPL ne connaissent que ce module : ils n'ont pas à savoir dans
quel ordre s'enchaînent les phases.
"""

from collections.abc import Iterator
from types import CodeType

from cosmo.erreurs import ErreurCosmo, ErreursCompilation
from cosmo.generateur import generer, nom_python, trop_imbrique
from cosmo.lexer import analyser
from cosmo.noeuds import Expression, Programme, Transmets
from cosmo.parser import analyser_expression, analyser_programme
from cosmo.semantique import AnalyseurSemantique, analyser_semantique
from cosmo.tokens import Token


def _traduire(programme: Programme) -> tuple[str, CodeType]:
    """Génère le Python d'un programme vérifié : renvoie le texte et le code compilé.

    Un programme valide en Cosmo peut encore dépasser les limites de Python : plus de 20
    boucles imbriquées, par exemple. Ce refus devient une erreur de compilation Cosmo.
    """
    texte = generer(programme)
    try:
        return texte, compile(texte, "<cosmo>", "exec")
    except (SyntaxError, RecursionError, MemoryError) as cause:
        raise ErreursCompilation([trop_imbrique(programme)]) from cause


def _compiler(source: str) -> tuple[str, CodeType]:
    """Fait passer le source par toutes les phases."""
    programme = analyser_programme(source)
    analyser_semantique(programme)
    return _traduire(programme)


def tokens(source: str) -> Iterator[Token]:
    """Les tokens du source, produits un par un. Lève ErreurLexicale au premier invalide."""
    return analyser(source)


def arbre(source: str) -> Programme:
    """L'arbre syntaxique du source, sans analyse sémantique. Lève ErreursCompilation."""
    return analyser_programme(source)


def verifier(source: str) -> None:
    """Compile le source sans l'exécuter. Lève ErreursCompilation s'il est erroné."""
    _compiler(source)


def transpiler(source: str) -> str:
    """Traduit un source Cosmo en texte Python. Lève ErreursCompilation s'il est erroné."""
    return _compiler(source)[0]


def executer(source: str) -> None:
    """Compile et exécute un source Cosmo.

    Lève ErreursCompilation s'il est erroné. Les erreurs d'exécution (division par zéro,
    types incompatibles) sont les exceptions de Python, qui remontent telles quelles.
    """
    _, code = _compiler(source)
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
            _, code = _traduire(programme)
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
