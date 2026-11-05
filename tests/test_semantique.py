"""Étape 7 : l'analyse sémantique."""

from pathlib import Path

import pytest

from cosmo.erreurs import ErreursCompilation, ErreurSemantique
from cosmo.noeuds import Noeud
from cosmo.parser import analyser_programme
from cosmo.semantique import AnalyseurSemantique, analyser_semantique
from cosmo.tokens import Position

RACINE = Path(__file__).parent.parent


def verifier(source: str) -> None:
    analyser_semantique(analyser_programme(source))


def erreurs_de(source: str) -> list[str]:
    """Les erreurs du source, sans le préfixe commun à toutes."""
    with pytest.raises(ErreursCompilation) as info:
        verifier(source)
    return [str(erreur).replace(" erreur sémantique :", "") for erreur in info.value.erreurs]


# --- Programmes corrects -----------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("", id="programme_vide"),
        pytest.param("module x = 1; x = x + 1; transmets x;", id="lecture_et_reaffectation"),
        pytest.param("module x = 1; orbite x < 2 { x = x + 1; }", id="bloc_voit_l_englobante"),
        pytest.param(
            "detecte go { module x = 1; } detecte go { module x = 2; }",
            id="meme_nom_dans_deux_blocs_voisins",
        ),
        pytest.param("detecte go { module x = 1; } module x = 2;", id="nom_libere_par_le_bloc"),
        pytest.param(
            "survole i dans 0..2 { } survole i dans 0..2 { }", id="deux_boucles_meme_variable"
        ),
        pytest.param("survole i dans 0..2 { transmets i; }", id="variable_de_boucle_lisible"),
        pytest.param("survole i dans 0..2 { i = 1; }", id="variable_de_boucle_reaffectable"),
        pytest.param("f(); mission f() { }", id="appel_avant_la_declaration"),
        pytest.param("mission f(n) { atterris f(n); }", id="recursivite"),
        pytest.param(
            "mission a() { atterris b(); } mission b() { atterris a(); }",
            id="recursivite_croisee",
        ),
        pytest.param("mission f(a, b) { transmets a, b; } f(1, 2);", id="parametres_lisibles"),
        pytest.param("mission f(a) { a = 1; }", id="parametre_reaffectable"),
        pytest.param("mission f(a) { module x = a; atterris x; }", id="variable_locale"),
        pytest.param("mission f() { detecte go { atterris; } }", id="atterris_dans_un_bloc"),
        pytest.param(
            "module x = 1; mission f() { module x = 2; }",
            id="mission_isolee_peut_reutiliser_un_nom_global",
        ),
        pytest.param("module a = 1; mission f(a) { }", id="parametre_peut_reprendre_un_nom_global"),
        pytest.param(
            "mission f(a) { } mission g(a) { module b = 1; } module b = 2;",
            id="missions_voisines_independantes",
        ),
    ],
)
def test_programme_correct_passe(source: str) -> None:
    verifier(source)


# --- Déclaration des variables -----------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("transmets y;", "[1:11] variable « y » non déclarée"),
        ("y = 1;", "[1:1] variable « y » non déclarée"),
        ("transmets y; module y = 1;", "[1:11] variable « y » non déclarée"),
        ("module x = x;", "[1:12] variable « x » non déclarée"),
        ("transmets -y;", "[1:12] variable « y » non déclarée"),
        ("transmets non y;", "[1:15] variable « y » non déclarée"),
        ("transmets 1 + y;", "[1:15] variable « y » non déclarée"),
        ("transmets y + 1;", "[1:11] variable « y » non déclarée"),
        ("x = y;\n", "[1:5] variable « y » non déclarée"),
        ("detecte y { }", "[1:9] variable « y » non déclarée"),
        ("orbite y { }", "[1:8] variable « y » non déclarée"),
        ("survole i dans y..1 { }", "[1:16] variable « y » non déclarée"),
        ("survole i dans 0..y { }", "[1:19] variable « y » non déclarée"),
        ("mission f() { } f(y);", "[1:19] variable « y » non déclarée"),
    ],
)
def test_lecture_d_un_nom_non_declare(source: str, attendu: str) -> None:
    assert attendu in erreurs_de(source)


def test_variable_d_un_bloc_n_existe_plus_apres_le_bloc() -> None:
    source = "detecte go {\n  module x = 1;\n}\ntransmets x;"
    assert erreurs_de(source) == ["[4:11] variable « x » non déclarée"]


def test_variable_d_un_alors_invisible_dans_le_sinon() -> None:
    source = "detecte go { module x = 1; } sinon { transmets x; }"
    assert erreurs_de(source) == ["[1:48] variable « x » non déclarée"]


def test_variable_de_boucle_n_existe_plus_apres_la_boucle() -> None:
    assert erreurs_de("survole i dans 0..2 { } transmets i;") == [
        "[1:35] variable « i » non déclarée"
    ]


def test_bornes_de_survole_ne_voient_pas_la_variable_de_boucle() -> None:
    assert erreurs_de("survole i dans 0..i { }") == ["[1:19] variable « i » non déclarée"]


# --- Doublons et masquage ----------------------------------------------------


def test_double_declaration_dans_la_meme_portee() -> None:
    assert erreurs_de("module x = 1;\nmodule x = 2;") == [
        "[2:8] variable « x » déjà déclarée à la ligne 1"
    ]


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        (
            "module x = 1;\ndetecte go {\n  module x = 2;\n}",
            "[3:10] la variable « x » masquerait celle de la ligne 1",
        ),
        (
            "module x = 1;\ndetecte go { orbite go {\n  module x = 2;\n} }",
            "[3:10] la variable « x » masquerait celle de la ligne 1",
        ),
        (
            "module i = 1;\nsurvole i dans 0..2 { }",
            "[2:9] la variable « i » masquerait celle de la ligne 1",
        ),
        (
            "survole i dans 0..2 {\n  module i = 1;\n}",
            "[2:10] la variable « i » masquerait celle de la ligne 1",
        ),
        (
            "survole i dans 0..2 {\n  survole i dans 0..2 { }\n}",
            "[2:11] la variable « i » masquerait celle de la ligne 1",
        ),
        (
            "mission f(a) {\n  module a = 1;\n}",
            "[2:10] la variable « a » masquerait celle de la ligne 1",
        ),
    ],
)
def test_masquage_refuse(source: str, attendu: str) -> None:
    assert erreurs_de(source) == [attendu]


def test_declaration_refusee_garde_la_premiere_declaration() -> None:
    assert erreurs_de("module x = 1; module x = 2; transmets x;") == [
        "[1:22] variable « x » déjà déclarée à la ligne 1"
    ]


# --- Noms de missions --------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("mission f() { } module f = 1;", "[1:24] « f » est déjà le nom d'une mission"),
        ("module f = 1; mission f() { }", "[1:8] « f » est déjà le nom d'une mission"),
        ("mission f(f) { }", "[1:11] « f » est déjà le nom d'une mission"),
        ("mission f() { } survole f dans 0..1 { }", "[1:25] « f » est déjà le nom d'une mission"),
        ("mission f() { module f = 1; }", "[1:22] « f » est déjà le nom d'une mission"),
        ("mission f() { } transmets f;", "[1:27] « f » est une mission, pas une variable"),
        ("mission f() { } f = 1;", "[1:17] « f » est une mission, pas une variable"),
    ],
)
def test_nom_de_mission_ne_sert_pas_de_variable(source: str, attendu: str) -> None:
    assert erreurs_de(source) == [attendu]


def test_variable_refusee_ne_provoque_pas_d_erreur_en_cascade() -> None:
    assert erreurs_de("mission f() { } module f = 1; transmets f; f = 2;") == [
        "[1:24] « f » est déjà le nom d'une mission"
    ]


def test_mission_declaree_deux_fois() -> None:
    assert erreurs_de("mission f() { }\nmission f(a) { }") == [
        "[2:9] la mission « f » est déjà déclarée à la ligne 1"
    ]


def test_corps_d_une_mission_en_double_est_quand_meme_analyse() -> None:
    assert erreurs_de("mission f() { }\nmission f() { transmets y; }") == [
        "[2:9] la mission « f » est déjà déclarée à la ligne 1",
        "[2:25] variable « y » non déclarée",
    ]


def test_parametres_en_double() -> None:
    assert erreurs_de("mission f(a, a) { }") == ["[1:14] paramètre « a » déjà déclaré"]


# --- Appels ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        (
            "mission f() { } f(1);",
            "[1:17] la mission « f » attend 0 argument, 1 reçu",
        ),
        (
            "mission f(a) { } f();",
            "[1:18] la mission « f » attend 1 argument, 0 reçu",
        ),
        (
            "mission f(a) { } f(1, 2);",
            "[1:18] la mission « f » attend 1 argument, 2 reçus",
        ),
        (
            "mission f(a, b) { } f(1);",
            "[1:21] la mission « f » attend 2 arguments, 1 reçu",
        ),
        (
            "f(1); mission f() { }",
            "[1:1] la mission « f » attend 0 argument, 1 reçu",
        ),
        (
            "mission f(n) { atterris f(); }",
            "[1:25] la mission « f » attend 1 argument, 0 reçu",
        ),
    ],
)
def test_nombre_d_arguments(source: str, attendu: str) -> None:
    assert erreurs_de(source) == [attendu]


def test_mission_inconnue() -> None:
    assert erreurs_de("f(1);") == ["[1:1] mission « f » inconnue"]
    assert erreurs_de("transmets f();") == ["[1:11] mission « f » inconnue"]


def test_variable_appelee_comme_une_mission() -> None:
    assert erreurs_de("module x = 1; x();") == ["[1:15] mission « x » inconnue"]


def test_arguments_d_un_appel_sont_verifies_meme_si_l_appel_est_faux() -> None:
    assert erreurs_de("f(y);") == [
        "[1:1] mission « f » inconnue",
        "[1:3] variable « y » non déclarée",
    ]


# --- Isolation des missions --------------------------------------------------


def test_mission_ne_voit_pas_le_niveau_principal() -> None:
    assert erreurs_de("module x = 1;\nmission f() {\n  transmets x;\n}") == [
        "[3:13] variable « x » non déclarée"
    ]


def test_mission_ne_peut_pas_reaffecter_le_niveau_principal() -> None:
    assert erreurs_de("module x = 1;\nmission f() {\n  x = 2;\n}") == [
        "[3:3] variable « x » non déclarée"
    ]


def test_niveau_principal_ne_voit_pas_les_variables_d_une_mission() -> None:
    assert erreurs_de("mission f(a) { module b = 1; } transmets a, b;") == [
        "[1:42] variable « a » non déclarée",
        "[1:45] variable « b » non déclarée",
    ]


def test_niveau_principal_retrouve_ses_variables_apres_une_mission() -> None:
    verifier("module x = 1; mission f() { } transmets x;")


# --- atterris ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("atterris;", "[1:1] « atterris » en dehors d'une mission"),
        ("atterris 1;", "[1:1] « atterris » en dehors d'une mission"),
        ("detecte go { atterris; }", "[1:14] « atterris » en dehors d'une mission"),
        ("mission f() { } atterris;", "[1:17] « atterris » en dehors d'une mission"),
    ],
)
def test_atterris_hors_mission(source: str, attendu: str) -> None:
    assert erreurs_de(source) == [attendu]


def test_valeur_d_un_atterris_mal_place_est_verifiee() -> None:
    assert erreurs_de("atterris y;") == [
        "[1:1] « atterris » en dehors d'une mission",
        "[1:10] variable « y » non déclarée",
    ]


# --- Collecte ----------------------------------------------------------------


def test_toutes_les_erreurs_sont_signalees_dans_l_ordre_du_source() -> None:
    # La mission en double est trouvée dès la première passe, mais reste à sa place.
    source = "transmets a;\nmission f() { }\nb = 1;\nmission f() { }\ng();\n"
    assert erreurs_de(source) == [
        "[1:11] variable « a » non déclarée",
        "[3:1] variable « b » non déclarée",
        "[4:9] la mission « f » est déjà déclarée à la ligne 2",
        "[5:1] mission « g » inconnue",
    ]


def test_erreurs_compilation_est_causee_par_la_premiere_erreur() -> None:
    with pytest.raises(ErreursCompilation) as info:
        verifier("transmets a; transmets b;")
    assert info.value.__cause__ is info.value.erreurs[0]
    assert all(isinstance(e, ErreurSemantique) for e in info.value.erreurs)


def test_arbre_trop_profond_devient_une_erreur_cosmo() -> None:
    # Le parser lit cette somme en boucle : c'est le parcours de l'arbre qui déborde.
    source = "transmets 1;\ntransmets " + " + ".join(["1"] * 5000) + ";"
    with pytest.raises(ErreursCompilation) as info:
        verifier(source)
    assert len(info.value.erreurs) == 1
    erreur = info.value.erreurs[0]
    assert erreur.message == "imbrication trop profonde"
    assert erreur.position == Position(2, 1)
    assert isinstance(erreur.__cause__, RecursionError)


# --- Les portées, gestionnaires de contexte ----------------------------------


def test_portee_est_refermee_meme_si_le_corps_leve() -> None:
    analyseur = AnalyseurSemantique()
    with pytest.raises(ValueError), analyseur.portee():
        analyseur._declarer("x", Position(1, 1))
        raise ValueError
    assert analyseur._portees == []


def test_corps_de_mission_restaure_les_portees_meme_si_le_corps_leve() -> None:
    analyseur = AnalyseurSemantique()
    with analyseur.portee():
        analyseur._declarer("x", Position(1, 1))
        with pytest.raises(ValueError), analyseur.corps_de_mission():
            assert analyseur._chercher("x") is None
            raise ValueError
        assert analyseur._chercher("x") == Position(1, 1)
        assert analyseur._dans_une_mission is False


def test_noeud_sans_methode_est_un_oubli_du_compilateur() -> None:
    with pytest.raises(TypeError, match="Noeud"):
        AnalyseurSemantique().visiter(Noeud(position=Position(1, 1)))


# --- Les programmes du dépôt -------------------------------------------------


@pytest.mark.parametrize(
    "chemin", sorted((RACINE / "exemples").glob("*.cosmo")), ids=lambda c: c.stem
)
def test_exemple_passe_l_analyse(chemin: Path) -> None:
    verifier(chemin.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "nom", ["03_variable_non_declaree", "04_mission_isolee", "05_nombre_arguments"]
)
def test_programme_errone_donne_le_message_attendu(nom: str) -> None:
    source = (RACINE / "erreurs" / f"{nom}.cosmo").read_text(encoding="utf-8")
    attendu = (RACINE / "erreurs" / f"{nom}.attendu").read_text(encoding="utf-8").strip()
    with pytest.raises(ErreursCompilation) as info:
        verifier(source)
    assert str(info.value) == attendu
