"""Étape 4 : les nœuds de l'arbre syntaxique."""

import dataclasses
from typing import get_args

import pytest

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
    Survole,
    Transmets,
    Unaire,
    Variable,
)
from cosmo.tokens import Position

P = Position(1, 1)
AILLEURS = Position(9, 9)


def ent(valeur: int = 1) -> Entier:
    return Entier(valeur, position=P)


def var(nom: str = "x") -> Variable:
    return Variable(nom, position=P)


def bloc(*instructions: Instruction) -> Bloc:
    return Bloc(instructions, position=P)


def decrire(expression: Expression) -> str:
    """Un parcours avec `match`, comme le feront les phases suivantes."""
    match expression:
        case Entier(valeur):
            return f"entier {valeur}"
        case Chaine(valeur):
            return f"chaîne {valeur}"
        case Booleen(valeur):
            return f"booléen {valeur}"
        case Variable(nom):
            return f"variable {nom}"
        case Unaire(operateur, _):
            return f"unaire {operateur.value}"
        case Binaire(operateur, _, _):
            return f"binaire {operateur.value}"
        case Appel(nom, arguments):
            return f"appel {nom}/{len(arguments)}"


# --- Comportement commun -----------------------------------------------------


def test_la_position_est_obligatoire() -> None:
    with pytest.raises(TypeError):
        Entier(1)  # type: ignore[call-arg]


def test_la_position_ne_se_passe_que_par_son_nom() -> None:
    with pytest.raises(TypeError):
        Entier(P, 1)  # type: ignore[call-arg, arg-type]


def test_un_noeud_garde_sa_position() -> None:
    assert Variable("x", position=AILLEURS).position == AILLEURS


def test_la_position_ne_compte_pas_dans_l_egalite() -> None:
    assert Entier(1, position=P) == Entier(1, position=AILLEURS)


def test_deux_valeurs_differentes_ne_sont_pas_egales() -> None:
    assert ent(1) != ent(2)


def test_deux_sortes_de_noeuds_ne_sont_jamais_egales() -> None:
    declaration: object = Module("x", ent(), position=P)
    assert declaration != Affectation("x", ent(), position=P)


def test_le_repr_montre_la_structure_sans_la_position() -> None:
    assert repr(Unaire(OperateurUnaire.MOINS, ent(), position=P)) == (
        "Unaire(operateur=<OperateurUnaire.MOINS: '-'>, operande=Entier(valeur=1))"
    )


def test_un_noeud_est_immuable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ent().valeur = 2  # type: ignore[misc]


def test_deux_appels_egaux_ont_le_meme_hash_quelle_que_soit_leur_position() -> None:
    ici = Appel("f", (ent(), var()), position=P)
    la_bas = Appel("f", (ent(), var()), position=AILLEURS)
    assert hash(ici) == hash(la_bas)


# --- Les unions --------------------------------------------------------------


def test_contenu_de_l_union_des_expressions() -> None:
    assert set(get_args(Expression.__value__)) == {
        Entier,
        Chaine,
        Booleen,
        Variable,
        Unaire,
        Binaire,
        Appel,
    }


def test_contenu_de_l_union_des_instructions() -> None:
    assert set(get_args(Instruction.__value__)) == {
        Module,
        Affectation,
        Transmets,
        Detecte,
        Orbite,
        Survole,
        Atterris,
        AppelSeul,
    }


def test_une_declaration_est_une_mission_ou_une_instruction() -> None:
    assert set(get_args(Declaration.__value__)) == {Mission, Instruction}


@pytest.mark.parametrize(
    ("expression", "attendu"),
    [
        (Entier(42, position=P), "entier 42"),
        (Chaine("Ada", position=P), "chaîne Ada"),
        (Booleen(True, position=P), "booléen True"),
        (Variable("x", position=P), "variable x"),
        (Unaire(OperateurUnaire.NON, ent(), position=P), "unaire non"),
        (Binaire(OperateurBinaire.ET, ent(), ent(), position=P), "binaire et"),
        (Appel("f", (ent(), ent()), position=P), "appel f/2"),
    ],
)
def test_match_reconnait_chaque_expression(expression: Expression, attendu: str) -> None:
    assert decrire(expression) == attendu


@pytest.mark.parametrize(
    ("operateur", "texte"),
    [(OperateurUnaire.NON, "non"), (OperateurBinaire.MODULO, "%"), (OperateurBinaire.OU, "ou")],
)
def test_un_operateur_a_pour_valeur_le_texte_de_son_token(
    operateur: OperateurUnaire | OperateurBinaire, texte: str
) -> None:
    assert operateur.value == texte


# --- Construire de vrais morceaux de programme -------------------------------


def test_les_expressions_s_imbriquent() -> None:
    """`1 + 2 * 3` : le produit est un enfant de la somme."""
    produit = Binaire(OperateurBinaire.FOIS, ent(2), ent(3), position=P)
    somme = Binaire(OperateurBinaire.PLUS, ent(1), produit, position=P)
    assert somme.droite == produit


def test_sinon_accepte_un_bloc_un_detecte_ou_rien() -> None:
    sans_sinon = Detecte(ent(), bloc(), None, position=P)
    avec_bloc = Detecte(ent(), bloc(), bloc(), position=P)
    en_chaine = Detecte(ent(), bloc(), avec_bloc, position=P)
    assert sans_sinon.sinon is None
    assert avec_bloc.sinon == bloc()
    assert en_chaine.sinon == avec_bloc


def test_atterris_accepte_une_valeur_ou_rien() -> None:
    assert Atterris(None, position=P).valeur is None
    assert Atterris(ent(), position=P).valeur == ent()


def test_un_programme_se_construit_a_la_main() -> None:
    """`mission fibo(n) { detecte n < 2 { atterris n; } }` suivi d'instructions."""
    condition = Binaire(OperateurBinaire.INFERIEUR, var("n"), ent(2), position=P)
    corps = bloc(Detecte(condition, bloc(Atterris(var("n"), position=P)), None, position=P))
    appel = Appel("fibo", (ent(),), position=P)
    programme = Programme(
        (
            Mission("fibo", (Parametre("n", position=P),), corps, position=P),
            Survole("k", ent(0), ent(8), bloc(Transmets((var("k"),), position=P)), position=P),
            Orbite(Booleen(False, position=P), bloc(), position=P),
            AppelSeul(appel, position=P),
        ),
        position=P,
    )
    mission, *instructions = programme.declarations
    assert isinstance(mission, Mission)
    assert mission.parametres[0].nom == "n"
    assert [type(i) for i in instructions] == [Survole, Orbite, AppelSeul]
