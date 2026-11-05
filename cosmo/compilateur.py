"""La chaîne de compilation complète : du texte Cosmo au programme Python exécuté.

source → lexer → parser → analyse sémantique → génération → compilation Python
"""

from types import CodeType

from cosmo.erreurs import ErreursCompilation
from cosmo.generateur import generer, trop_imbrique
from cosmo.parser import analyser_programme
from cosmo.semantique import analyser_semantique


def _compiler(source: str) -> tuple[str, CodeType]:
    """Fait passer le source par toutes les phases : renvoie le Python, en texte et compilé.

    Un programme valide en Cosmo peut encore dépasser les limites de Python : plus de 20
    boucles imbriquées, par exemple. Ce refus devient une erreur de compilation Cosmo.
    """
    programme = analyser_programme(source)
    analyser_semantique(programme)
    texte = generer(programme)
    try:
        return texte, compile(texte, "<cosmo>", "exec")
    except (SyntaxError, RecursionError, MemoryError) as cause:
        raise ErreursCompilation([trop_imbrique(programme)]) from cause


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
