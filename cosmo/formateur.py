"""Étape 10 : le formateur, qui réécrit un programme Cosmo au format canonique (SPEC.md, 7.3).

C'est un backend comme un autre : il reçoit un arbre et renvoie du texte, sauf que ce texte
est du Cosmo. Deux garanties, vérifiées par les tests :

- le programme formaté a exactement le même arbre que l'original ;
- formater un programme déjà formaté ne change rien.

L'arbre ne connaît pas les commentaires. Ils sont dans `Programme.mise_en_page`, triés par
position : à chaque instruction, on écrit ceux que le parcours vient de dépasser.
"""

from collections import deque
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

ECHAPPEMENTS = {"\\": "\\\\", '"': '\\"', "\n": "\\n"}


class FormateurCosmo(GenerateurTexte):
    """Réécrit un arbre en texte Cosmo. Une instance ne sert qu'à un seul programme."""

    def __init__(self, programme: Programme) -> None:
        super().__init__()
        self._programme = programme
        self._commentaires = deque(programme.mise_en_page.commentaires)
        self._vides = programme.mise_en_page.lignes_vides
        # Le nombre de lignes juste après l'ouverture du dernier bloc. Regarder si la ligne
        # finit par « { » ne suffirait pas : un commentaire peut la suivre, ou en finir par un.
        self._taille_a_l_ouverture = -1

    def _texte_nom(self, nom: str) -> str:
        return nom

    def _texte_chaine(self, valeur: str) -> str:
        echappee = "".join(ECHAPPEMENTS.get(c, c) for c in valeur)
        return f'"{echappee}"'

    def _texte_booleen(self, valeur: bool) -> str:
        return "go" if valeur else "nogo"

    def _texte_binaire(self, operateur: OperateurBinaire) -> str:
        return operateur.value

    def _texte_unaire(self, operateur: OperateurUnaire) -> str:
        return "non " if operateur is OperateurUnaire.NON else operateur.value

    def formater(self) -> str:
        """Renvoie le texte complet. Une mission est toujours entourée de lignes vides."""
        apres_mission = False
        for declaration in self._programme.declarations:
            est_mission = isinstance(declaration, Mission)
            self._avant_instruction(declaration.position.ligne, apres_mission or est_mission)
            apres_mission = est_mission
            if isinstance(declaration, Mission):
                self._mission(declaration)
            else:
                self.instruction(declaration)
        if self._commentaires:
            derniere = self._commentaires[-1].position.ligne
            self._commentaires_avant(derniere + 1, separer=apres_mission)
        return self._texte_complet()

    # --- Commentaires et lignes vides --------------------------------------------

    def _ligne_vide(self) -> None:
        """Ajoute une ligne vide, sauf au début d'un bloc ou après une autre ligne vide."""
        debut_de_bloc = len(self._lignes) == self._taille_a_l_ouverture
        if self._lignes and self._lignes[-1] and not debut_de_bloc:
            self._lignes.append("")

    def _commentaires_avant(self, ligne: int, separer: bool = False) -> bool:
        """Écrit les commentaires situés avant cette ligne. Renvoie True s'il y en avait."""
        ecrit = False
        while self._commentaires and self._commentaires[0].position.ligne < ligne:
            commentaire = self._commentaires.popleft()
            if (separer and not ecrit) or commentaire.position.ligne - 1 in self._vides:
                self._ligne_vide()
            self._ecrire(commentaire.texte)
            ecrit = True
        return ecrit

    def _avant_instruction(self, ligne: int, separer: bool = False) -> None:
        """Prépare une instruction : ses commentaires, et la ligne vide qui la précède."""
        ecrit = self._commentaires_avant(ligne, separer)
        if (separer and not ecrit) or ligne - 1 in self._vides:
            self._ligne_vide()

    def _commentaires_en_fin_de_ligne(self, ligne: int) -> None:
        """Le premier commentaire, jusqu'à cette ligne, finit la dernière ligne écrite.

        Les suivants viennent de l'intérieur d'une instruction écrite sur plusieurs lignes :
        chacun garde sa propre ligne.
        """
        premier = True
        while self._commentaires and self._commentaires[0].position.ligne <= ligne:
            commentaire = self._commentaires.popleft()
            if premier:
                self._lignes[-1] += f"  {commentaire.texte}"
                premier = False
            else:
                self._ecrire(commentaire.texte)

    # --- Les blocs -------------------------------------------------------------

    def _ouvrir(self, entete: str, bloc: Bloc) -> None:
        """Écrit l'en-tête et le contenu du bloc, mais pas l'accolade fermante.

        Elle peut partager sa ligne avec un `sinon` : c'est à l'appelant de l'écrire.
        """
        self._ecrire(f"{entete} {{")
        with self._indentation():
            self._commentaires_en_fin_de_ligne(bloc.position.ligne)
            self._taille_a_l_ouverture = len(self._lignes)
            for instruction in bloc.instructions:
                self._avant_instruction(instruction.position.ligne)
                self.instruction(instruction)
            if bloc.fin is not None:
                self._commentaires_avant(bloc.fin.ligne)

    def _fermer(self, bloc: Bloc) -> None:
        self._ecrire("}")
        if bloc.fin is not None:
            self._commentaires_en_fin_de_ligne(bloc.fin.ligne)

    def _bloc(self, entete: str, bloc: Bloc) -> None:
        self._ouvrir(entete, bloc)
        self._fermer(bloc)

    def _mission(self, mission: Mission) -> None:
        parametres = ", ".join(parametre.nom for parametre in mission.parametres)
        self._bloc(f"mission {mission.nom}({parametres})", mission.corps)

    def _detecte(self, noeud: Detecte, debut: str) -> None:
        self._ouvrir(f"{debut} {self.expression(noeud.condition)}", noeud.alors)
        match noeud.sinon:
            case Detecte() as suite:
                self._detecte(suite, "} sinon detecte")
            case Bloc() as bloc:
                self._bloc("} sinon", bloc)
            case None:
                self._fermer(noeud.alors)
            case _ as jamais:
                assert_never(jamais)

    # --- Les instructions --------------------------------------------------------

    def _simple(self, noeud: Instruction, texte: str) -> None:
        self._ecrire(f"{texte};")
        self._commentaires_en_fin_de_ligne(noeud.position.ligne)

    def instruction(self, noeud: Instruction) -> None:
        """Écrit les lignes d'une instruction."""
        match noeud:
            case Module(nom, valeur):
                self._simple(noeud, f"module {nom} = {self.expression(valeur)}")
            case Affectation(nom, valeur):
                self._simple(noeud, f"{nom} = {self.expression(valeur)}")
            case Transmets(valeurs):
                texte = f"transmets {self._liste(valeurs)}" if valeurs else "transmets"
                self._simple(noeud, texte)
            case Detecte():
                self._detecte(noeud, "detecte")
            case Orbite(condition, corps):
                self._bloc(f"orbite {self.expression(condition)}", corps)
            case Survole(variable, debut, fin, corps):
                intervalle = f"{self.expression(debut)}..{self.expression(fin)}"
                self._bloc(f"survole {variable} dans {intervalle}", corps)
            case Atterris(valeur):
                texte = "atterris" if valeur is None else f"atterris {self.expression(valeur)}"
                self._simple(noeud, texte)
            case AppelSeul(appel):
                self._simple(noeud, self.expression(appel))
            case _:
                assert_never(noeud)


class BackendCosmo:
    """Le backend du formateur : du Cosmo au format canonique."""

    def generer(self, programme: Programme) -> str:
        """Renvoie le texte formaté. Lève ErreursCompilation si l'arbre est trop profond."""
        try:
            return FormateurCosmo(programme).formater()
        except RecursionError as cause:
            erreur = ErreurGeneration("programme trop imbriqué pour être formaté", programme.position)
            raise ErreursCompilation([erreur]) from cause
