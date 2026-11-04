"""Étape 4 : les nœuds de l'arbre syntaxique.

Le parser transforme la suite de tokens en un arbre, qui représente la structure du
programme. `1 + 2 * 3` devient par exemple :

    Binaire(PLUS, Entier(1), Binaire(FOIS, Entier(2), Entier(3)))

Chaque sorte de nœud est une dataclass immuable. Les unions `Expression`, `Instruction`
et `Declaration` disent ce qui est permis à chaque endroit de l'arbre : les phases
suivantes les parcourent avec `match`.
"""

from dataclasses import dataclass, field
from enum import Enum

from cosmo.tokens import Position

# Un alias `type` est évalué à la demande : il peut citer des classes définies plus bas,
# et ces classes peuvent à leur tour l'utiliser dans leurs champs (l'arbre est récursif).
type Expression = Entier | Chaine | Booleen | Variable | Unaire | Binaire | Appel
type Instruction = (
    Module | Affectation | Transmets | Detecte | Orbite | Survole | Atterris | AppelSeul
)
type Declaration = Mission | Instruction
type Sinon = Detecte | Bloc | None


class OperateurUnaire(Enum):
    """Les opérateurs à un opérande. La valeur est le texte du token."""

    NON = "non"
    MOINS = "-"


class OperateurBinaire(Enum):
    """Les opérateurs à deux opérandes. La valeur est le texte du token."""

    OU = "ou"
    ET = "et"
    EGAL = "=="
    DIFFERENT = "!="
    INFERIEUR = "<"
    INFERIEUR_EGAL = "<="
    SUPERIEUR = ">"
    SUPERIEUR_EGAL = ">="
    PLUS = "+"
    MOINS = "-"
    FOIS = "*"
    DIVISE = "/"
    MODULO = "%"


@dataclass(frozen=True)
class Noeud:
    """Classe de base de tous les nœuds.

    `position` est l'endroit à signaler si ce nœud provoque une erreur :
    - le nom déclaré ou affecté pour Module, Affectation, Mission, Parametre et Survole ;
    - l'opérateur pour Unaire et Binaire ;
    - le premier token dans tous les autres cas.

    Elle est obligatoire, mais ne compte ni dans l'égalité ni dans le repr : deux arbres de
    même structure sont égaux, où qu'ils soient écrits dans le source.
    """

    position: Position = field(kw_only=True, compare=False, repr=False)


# --- Expressions -------------------------------------------------------------


@dataclass(frozen=True)
class Entier(Noeud):
    """Un entier littéral : `42`."""

    valeur: int


@dataclass(frozen=True)
class Chaine(Noeud):
    """Une chaîne littérale, échappements déjà traduits : `"Ada"`."""

    valeur: str


@dataclass(frozen=True)
class Booleen(Noeud):
    """`go` (True) ou `nogo` (False)."""

    valeur: bool


@dataclass(frozen=True)
class Variable(Noeud):
    """La lecture d'une variable : `altitude`."""

    nom: str


@dataclass(frozen=True)
class Unaire(Noeud):
    """Un opérateur appliqué à une seule expression : `non a`, `-x`."""

    operateur: OperateurUnaire
    operande: Expression


@dataclass(frozen=True)
class Binaire(Noeud):
    """Un opérateur entre deux expressions : `a + b`, `a et b`."""

    operateur: OperateurBinaire
    gauche: Expression
    droite: Expression


@dataclass(frozen=True)
class Appel(Noeud):
    """L'appel d'une mission : `f(a, b)`."""

    nom: str
    arguments: tuple[Expression, ...]


# --- Instructions ------------------------------------------------------------


@dataclass(frozen=True)
class Bloc(Noeud):
    """Des instructions entre accolades : `{ … }`. Ouvre une nouvelle portée."""

    instructions: tuple[Instruction, ...]


@dataclass(frozen=True)
class Module(Noeud):
    """La déclaration d'une variable : `module x = 5;`."""

    nom: str
    valeur: Expression


@dataclass(frozen=True)
class Affectation(Noeud):
    """La réaffectation d'une variable déjà déclarée : `x = x + 1;`."""

    nom: str
    valeur: Expression


@dataclass(frozen=True)
class Transmets(Noeud):
    """L'affichage de zéro, une ou plusieurs valeurs : `transmets a, b;`."""

    valeurs: tuple[Expression, ...]


@dataclass(frozen=True)
class Detecte(Noeud):
    """Une condition. `sinon` est un autre Detecte pour écrire `sinon detecte`."""

    condition: Expression
    alors: Bloc
    sinon: Sinon


@dataclass(frozen=True)
class Orbite(Noeud):
    """La boucle « tant que » : `orbite cond { … }`."""

    condition: Expression
    corps: Bloc


@dataclass(frozen=True)
class Survole(Noeud):
    """La boucle sur un intervalle, `fin` exclue : `survole i dans a..b { … }`."""

    variable: str
    debut: Expression
    fin: Expression
    corps: Bloc


@dataclass(frozen=True)
class Atterris(Noeud):
    """Le retour d'une mission. `valeur` vaut None pour `atterris;`."""

    valeur: Expression | None


@dataclass(frozen=True)
class AppelSeul(Noeud):
    """Un appel utilisé comme instruction, sa valeur est ignorée : `salue("Ada");`."""

    appel: Appel


# --- Niveau principal --------------------------------------------------------


@dataclass(frozen=True)
class Parametre(Noeud):
    """Un paramètre de mission.

    C'est un nœud pour garder sa position : l'analyse sémantique doit pouvoir signaler
    un paramètre en double.
    """

    nom: str


@dataclass(frozen=True)
class Mission(Noeud):
    """La déclaration d'une mission : `mission f(a, b) { … }`."""

    nom: str
    parametres: tuple[Parametre, ...]
    corps: Bloc


@dataclass(frozen=True)
class Programme(Noeud):
    """La racine de l'arbre : tout le contenu d'un fichier source."""

    declarations: tuple[Declaration, ...]
