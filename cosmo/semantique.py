"""Étape 7 : l'analyse sémantique, déclarations et portées (SPEC.md, sections 4.4 à 4.6).

Le parser a vérifié la forme du programme ; on vérifie ici son sens : chaque nom utilisé
existe-t-il à cet endroit ? L'analyse se fait en deux passes, car une mission peut être
appelée avant sa déclaration :

1. on relève toutes les missions du niveau principal ;
2. on parcourt l'arbre en suivant les portées.

Le parcours repose sur `singledispatchmethod` : `visiter` choisit la méthode à exécuter
d'après le type du nœud. Les portées sont des gestionnaires de contexte : un `with` garantit
que chaque portée ouverte est refermée.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import singledispatchmethod

from cosmo.erreurs import ErreurCosmo, ErreursCompilation, ErreurSemantique
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
    Mission,
    Module,
    Noeud,
    Orbite,
    Parametre,
    Programme,
    Survole,
    Transmets,
    Unaire,
    Variable,
)
from cosmo.tokens import Position


def _accord(nombre: int, mot: str) -> str:
    """`_accord(2, "reçu")` donne « 2 reçus ». En français, 0 reste au singulier."""
    return f"{nombre} {mot}{'s' if nombre > 1 else ''}"


class AnalyseurSemantique:
    """Parcourt l'arbre et collecte les erreurs, sans s'arrêter à la première."""

    def __init__(self) -> None:
        self.erreurs: list[ErreurCosmo] = []
        self._missions: dict[str, Mission] = {}
        # Les portées visibles, de la plus englobante à la plus locale : nom → déclaration.
        self._portees: list[dict[str, Position]] = []
        self._dans_une_mission = False

    def analyser(self, programme: Programme) -> None:
        """Analyse tout le programme.

        Lève ErreurSemantique si l'arbre est trop profond pour être parcouru.
        """
        self._relever_missions(programme)
        with self.portee():
            for declaration in programme.declarations:
                try:
                    self.visiter(declaration)
                except RecursionError as cause:
                    # `1 + 1 + … + 1` est lu en boucle par le parser, mais donne un arbre
                    # très profond : cette limite peut n'être atteinte qu'ici.
                    raise ErreurSemantique(
                        "imbrication trop profonde", declaration.position
                    ) from cause

    def _relever_missions(self, programme: Programme) -> None:
        for declaration in programme.declarations:
            if not isinstance(declaration, Mission):
                continue
            premiere = self._missions.setdefault(declaration.nom, declaration)
            if premiere is not declaration:
                self._erreur(
                    f"la mission « {declaration.nom} » est déjà déclarée "
                    f"à la ligne {premiere.position.ligne}",
                    declaration.position,
                )

    # --- Les portées ---------------------------------------------------------

    @contextmanager
    def portee(self) -> Iterator[None]:
        """Ouvre une portée le temps du `with` : ses variables disparaissent à la sortie."""
        self._portees.append({})
        try:
            yield
        finally:
            self._portees.pop()

    @contextmanager
    def corps_de_mission(self) -> Iterator[None]:
        """Isole une mission : elle ne voit aucune des portées qui l'entourent."""
        englobantes, self._portees = self._portees, []
        self._dans_une_mission = True
        try:
            with self.portee():
                yield
        finally:
            self._portees = englobantes
            self._dans_une_mission = False

    def _chercher(self, nom: str) -> Position | None:
        """La position de la déclaration visible de ce nom, s'il y en a une."""
        for portee in reversed(self._portees):
            if nom in portee:
                return portee[nom]
        return None

    def _declarer(self, nom: str, position: Position) -> None:
        """Déclare une variable dans la portée courante, si les règles le permettent."""
        if nom in self._missions:
            self._erreur(f"« {nom} » est déjà le nom d'une mission", position)
        precedente = self._chercher(nom)
        if precedente is None:
            # Même refusé à cause d'une mission, le nom est retenu : ses utilisations
            # suivantes ne provoqueront pas une erreur « non déclarée » trompeuse.
            self._portees[-1][nom] = position
        elif nom in self._portees[-1]:
            self._erreur(
                f"variable « {nom} » déjà déclarée à la ligne {precedente.ligne}", position
            )
        else:
            self._erreur(
                f"la variable « {nom} » masquerait celle de la ligne {precedente.ligne}",
                position,
            )

    def _verifier_variable(self, nom: str, position: Position) -> None:
        """Vérifie qu'on peut lire ou réaffecter ce nom ici."""
        if self._chercher(nom) is not None:
            return
        if nom in self._missions:
            self._erreur(f"« {nom} » est une mission, pas une variable", position)
        else:
            self._erreur(f"variable « {nom} » non déclarée", position)

    def _erreur(self, message: str, position: Position) -> None:
        self.erreurs.append(ErreurSemantique(message, position))

    # --- Le parcours : une méthode par sorte de nœud --------------------------

    @singledispatchmethod
    def visiter(self, noeud: Noeud) -> None:
        """Vérifie un nœud et ses enfants. Un nœud sans méthode est un oubli du compilateur."""
        raise TypeError(f"nœud inconnu de l'analyse sémantique : {type(noeud).__name__}")

    @visiter.register(Entier)
    @visiter.register(Chaine)
    @visiter.register(Booleen)
    def _visiter_litteral(self, noeud: Noeud) -> None:
        pass  # une valeur écrite en toutes lettres ne peut rien contredire

    @visiter.register
    def _visiter_variable(self, noeud: Variable) -> None:
        self._verifier_variable(noeud.nom, noeud.position)

    @visiter.register
    def _visiter_unaire(self, noeud: Unaire) -> None:
        self.visiter(noeud.operande)

    @visiter.register
    def _visiter_binaire(self, noeud: Binaire) -> None:
        self.visiter(noeud.gauche)
        self.visiter(noeud.droite)

    @visiter.register
    def _visiter_appel(self, noeud: Appel) -> None:
        mission = self._missions.get(noeud.nom)
        if mission is None:
            self._erreur(f"mission « {noeud.nom} » inconnue", noeud.position)
        elif len(noeud.arguments) != len(mission.parametres):
            attendus = _accord(len(mission.parametres), "argument")
            recus = _accord(len(noeud.arguments), "reçu")
            self._erreur(f"la mission « {noeud.nom} » attend {attendus}, {recus}", noeud.position)
        for argument in noeud.arguments:
            self.visiter(argument)

    @visiter.register
    def _visiter_bloc(self, noeud: Bloc) -> None:
        with self.portee():
            for instruction in noeud.instructions:
                self.visiter(instruction)

    @visiter.register
    def _visiter_module(self, noeud: Module) -> None:
        # La valeur d'abord : dans `module x = x;`, le `x` de droite n'existe pas encore.
        self.visiter(noeud.valeur)
        self._declarer(noeud.nom, noeud.position)

    @visiter.register
    def _visiter_affectation(self, noeud: Affectation) -> None:
        self.visiter(noeud.valeur)
        self._verifier_variable(noeud.nom, noeud.position)

    @visiter.register
    def _visiter_transmets(self, noeud: Transmets) -> None:
        for valeur in noeud.valeurs:
            self.visiter(valeur)

    @visiter.register
    def _visiter_detecte(self, noeud: Detecte) -> None:
        self.visiter(noeud.condition)
        self.visiter(noeud.alors)
        if noeud.sinon is not None:
            self.visiter(noeud.sinon)

    @visiter.register
    def _visiter_orbite(self, noeud: Orbite) -> None:
        self.visiter(noeud.condition)
        self.visiter(noeud.corps)

    @visiter.register
    def _visiter_survole(self, noeud: Survole) -> None:
        # Les bornes sont évaluées avant la boucle : elles ne voient pas sa variable.
        self.visiter(noeud.debut)
        self.visiter(noeud.fin)
        with self.portee():
            self._declarer(noeud.variable, noeud.position)
            self.visiter(noeud.corps)

    @visiter.register
    def _visiter_atterris(self, noeud: Atterris) -> None:
        if not self._dans_une_mission:
            self._erreur("« atterris » en dehors d'une mission", noeud.position)
        if noeud.valeur is not None:
            self.visiter(noeud.valeur)

    @visiter.register
    def _visiter_appel_seul(self, noeud: AppelSeul) -> None:
        self.visiter(noeud.appel)

    @visiter.register
    def _visiter_mission(self, noeud: Mission) -> None:
        with self.corps_de_mission():
            for parametre in noeud.parametres:
                self.visiter(parametre)
            self.visiter(noeud.corps)

    @visiter.register
    def _visiter_parametre(self, noeud: Parametre) -> None:
        precedent = self._portees[-1].get(noeud.nom)
        if precedent is None:
            self._declarer(noeud.nom, noeud.position)
        else:
            self._erreur(f"paramètre « {noeud.nom} » déjà déclaré", noeud.position)


def analyser_semantique(programme: Programme) -> None:
    """Vérifie le programme.

    Lève ErreursCompilation avec toutes les erreurs trouvées, dans l'ordre du source,
    causée par la première.
    """
    analyseur = AnalyseurSemantique()
    try:
        analyseur.analyser(programme)
    except ErreurSemantique as fatale:
        analyseur.erreurs.append(fatale)
    if analyseur.erreurs:
        erreurs = sorted(analyseur.erreurs, key=lambda e: (e.position.ligne, e.position.colonne))
        raise ErreursCompilation(erreurs) from erreurs[0]
