"""Étape 6 : le parser des instructions et la récupération d'erreurs."""

from pathlib import Path

import pytest

from cosmo.erreurs import ErreurLexicale, ErreursCompilation, ErreurSyntaxique
from cosmo.lexer import analyser
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
    Instruction,
    Mission,
    Module,
    OperateurBinaire,
    Orbite,
    Parametre,
    Programme,
    Survole,
    Transmets,
    Variable,
)
from cosmo.parser import Parser, analyser_programme
from cosmo.tokens import Position

P = Position(1, 1)
RACINE = Path(__file__).parent.parent


def une_declaration(source: str) -> Declaration:
    programme = analyser_programme(source)
    assert len(programme.declarations) == 1
    return programme.declarations[0]


def erreurs_de(source: str) -> list[str]:
    """Les erreurs du source, au format de la spécification."""
    with pytest.raises(ErreursCompilation) as info:
        analyser_programme(source)
    return [str(erreur) for erreur in info.value.erreurs]


def entier(valeur: int) -> Entier:
    return Entier(valeur, position=P)


def variable(nom: str) -> Variable:
    return Variable(nom, position=P)


def bloc(*instructions: Instruction) -> Bloc:
    return Bloc(instructions, position=P)


def transmets(*valeurs: int) -> Transmets:
    return Transmets(tuple(entier(v) for v in valeurs), position=P)


# --- Programme ---------------------------------------------------------------


@pytest.mark.parametrize("source", ["", "   \n\n", "# un commentaire seul\n"])
def test_programme_sans_declaration(source: str) -> None:
    assert analyser_programme(source) == Programme((), position=P)


def test_programme_garde_ses_declarations_dans_l_ordre() -> None:
    programme = analyser_programme("transmets 1; mission f() { } transmets 2;")
    assert programme.declarations == (
        transmets(1),
        Mission("f", (), bloc(), position=P),
        transmets(2),
    )


def test_programme_a_la_position_de_son_premier_token() -> None:
    assert analyser_programme("\n\n  transmets;").position == Position(3, 3)


# --- Une instruction de chaque sorte -----------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("module x = 5;", Module("x", entier(5), position=P)),
        ("x = 5;", Affectation("x", entier(5), position=P)),
        ("transmets;", Transmets((), position=P)),
        ("transmets 1;", transmets(1)),
        ("transmets 1, 2, 3;", transmets(1, 2, 3)),
        ("atterris;", Atterris(None, position=P)),
        ("atterris 1;", Atterris(entier(1), position=P)),
        ("orbite go { }", Orbite(Booleen(True, position=P), bloc(), position=P)),
        (
            "survole i dans 0..3 { transmets 1; }",
            Survole("i", entier(0), entier(3), bloc(transmets(1)), position=P),
        ),
        ("f();", AppelSeul(Appel("f", (), position=P), position=P)),
        (
            'f(1, "a");',
            AppelSeul(
                Appel("f", (entier(1), Chaine("a", position=P)), position=P),
                position=P,
            ),
        ),
    ],
)
def test_instruction(source: str, attendu: Declaration) -> None:
    assert une_declaration(source) == attendu


def test_module_et_affectation_acceptent_une_expression_complete() -> None:
    somme = Binaire(OperateurBinaire.PLUS, variable("a"), entier(1), position=P)
    assert une_declaration("module x = a + 1;") == Module("x", somme, position=P)
    assert une_declaration("x = a + 1;") == Affectation("x", somme, position=P)


def test_bornes_de_survole_sont_des_expressions() -> None:
    somme = Binaire(OperateurBinaire.PLUS, variable("a"), entier(1), position=P)
    assert une_declaration("survole i dans a + 1..a + 1 { }") == Survole(
        "i", somme, somme, bloc(), position=P
    )


# --- detecte -----------------------------------------------------------------

CONDITION = Variable("c", position=P)


def test_detecte_sans_sinon() -> None:
    attendu = Detecte(CONDITION, bloc(transmets(1)), None, position=P)
    assert une_declaration("detecte c { transmets 1; }") == attendu


def test_detecte_sinon() -> None:
    attendu = Detecte(CONDITION, bloc(transmets(1)), bloc(transmets(2)), position=P)
    assert une_declaration("detecte c { transmets 1; } sinon { transmets 2; }") == attendu


def test_sinon_detecte_s_enchaine_sans_accolades() -> None:
    source = "detecte c { transmets 1; } sinon detecte c { transmets 2; } sinon { transmets 3; }"
    deuxieme = Detecte(CONDITION, bloc(transmets(2)), bloc(transmets(3)), position=P)
    assert une_declaration(source) == Detecte(CONDITION, bloc(transmets(1)), deuxieme, position=P)


# --- Missions ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "noms"),
    [
        ("mission f() { }", ()),
        ("mission f(a) { }", ("a",)),
        ("mission f(a, b, c) { }", ("a", "b", "c")),
    ],
)
def test_parametres_de_mission(source: str, noms: tuple[str, ...]) -> None:
    parametres = tuple(Parametre(nom, position=P) for nom in noms)
    assert une_declaration(source) == Mission("f", parametres, bloc(), position=P)


def test_corps_de_mission_contient_ses_instructions() -> None:
    attendu = Mission(
        "f", (), bloc(transmets(1), Atterris(entier(2), position=P)), position=P
    )
    assert une_declaration("mission f() { transmets 1; atterris 2; }") == attendu


# --- Positions (SPEC, docstring de Noeud) ------------------------------------


@pytest.mark.parametrize(
    ("source", "position"),
    [
        ("  module x = 1;", Position(1, 10)),  # le nom déclaré
        ("  x = 1;", Position(1, 3)),  # le nom affecté
        ("  mission f() { }", Position(1, 11)),  # le nom de la mission
        ("  survole i dans 0..1 { }", Position(1, 11)),  # le nom de la variable
        ("  transmets 1;", Position(1, 3)),  # le mot-clé
        ("  detecte go { }", Position(1, 3)),
        ("  orbite go { }", Position(1, 3)),
        ("  atterris;", Position(1, 3)),
        ("  f();", Position(1, 3)),
    ],
)
def test_position_de_l_instruction(source: str, position: Position) -> None:
    assert une_declaration(source).position == position


def test_position_des_parametres_et_du_bloc() -> None:
    mission = une_declaration("mission f(a,\n  b) {\n}")
    assert isinstance(mission, Mission)
    assert [p.position for p in mission.parametres] == [Position(1, 11), Position(2, 3)]
    assert mission.corps.position == Position(2, 6)


def test_position_d_un_sinon_detecte_est_son_mot_cle() -> None:
    detecte = une_declaration("detecte a { } sinon detecte b { }")
    assert isinstance(detecte, Detecte)
    assert isinstance(detecte.sinon, Detecte)
    assert detecte.sinon.position == Position(1, 21)


# --- Erreurs, une à la fois --------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("module x = 1", "[1:13] erreur syntaxique : « ; » attendu"),
        ("x = 1", "[1:6] erreur syntaxique : « ; » attendu"),
        ("transmets 1", "[1:12] erreur syntaxique : « ; » attendu"),
        ("atterris 1", "[1:11] erreur syntaxique : « ; » attendu"),
        ("f()", "[1:4] erreur syntaxique : « ; » attendu"),
        ("module = 1;", "[1:7] erreur syntaxique : « identifiant » attendu"),
        ("module x 1;", "[1:9] erreur syntaxique : « = » attendu"),
        ("module x = ;", "[1:12] erreur syntaxique : expression attendue"),
        ("transmets 1,;", "[1:13] erreur syntaxique : expression attendue"),
        ("detecte { }", "[1:9] erreur syntaxique : expression attendue"),
        ("detecte go", "[1:11] erreur syntaxique : « { » attendu"),
        ("orbite go", "[1:10] erreur syntaxique : « { » attendu"),
        ("survole dans 0..1 { }", "[1:8] erreur syntaxique : « identifiant » attendu"),
        ("survole i 0..1 { }", "[1:10] erreur syntaxique : « dans » attendu"),
        ("survole i dans 0 { }", "[1:17] erreur syntaxique : « .. » attendu"),
        ("mission (a) { }", "[1:8] erreur syntaxique : « identifiant » attendu"),
        ("mission f { }", "[1:10] erreur syntaxique : « ( » attendu"),
        ("mission f(a { }", "[1:12] erreur syntaxique : « ) » attendu"),
        ("mission f(1) { }", "[1:11] erreur syntaxique : « identifiant » attendu"),
        ("mission f(a,) { }", "[1:13] erreur syntaxique : « identifiant » attendu"),
        ("mission f()", "[1:12] erreur syntaxique : « { » attendu"),
        ("1 + 2;", "[1:1] erreur syntaxique : instruction attendue"),
        ("(f());", "[1:1] erreur syntaxique : instruction attendue"),
        ("sinon { }", "[1:1] erreur syntaxique : instruction attendue"),
        ("}", "[1:1] erreur syntaxique : instruction attendue"),
        ("x;", "[1:2] erreur syntaxique : « = » ou « ( » attendu après « x »"),
        ("x + 1;", "[1:2] erreur syntaxique : « = » ou « ( » attendu après « x »"),
        ("f() + 1;", "[1:4] erreur syntaxique : « ; » attendu"),
        (
            "transmets a < b < c;",
            "[1:17] erreur syntaxique : comparaisons enchaînées : ajoutez des parenthèses",
        ),
    ],
)
def test_erreur_signalee_avec_sa_position(source: str, attendu: str) -> None:
    assert erreurs_de(source) == [attendu]


def test_point_virgule_oublie_signale_en_fin_de_ligne() -> None:
    assert erreurs_de("module x = 1   \n\ntransmets x;") == [
        "[1:13] erreur syntaxique : « ; » attendu"
    ]


def test_mission_dans_un_bloc_est_refusee() -> None:
    assert erreurs_de("detecte go {\n  mission f() { atterris; }\n}") == [
        "[2:3] erreur syntaxique : une mission ne se déclare qu'au niveau principal"
    ]


def test_accolade_fermante_manquante_signalee_une_seule_fois() -> None:
    source = "mission f() {\n  detecte go {\n    orbite go {\n      transmets 1;\n"
    assert erreurs_de(source) == ["[4:19] erreur syntaxique : « } » attendu"]


# --- Récupération : plusieurs erreurs en une compilation ---------------------


def test_erreurs_de_plusieurs_instructions_toutes_signalees_dans_l_ordre() -> None:
    source = "module = 1;\ntransmets 1\nmodule y = ;\nx + 1;\n"
    assert erreurs_de(source) == [
        "[1:7] erreur syntaxique : « identifiant » attendu",
        "[2:12] erreur syntaxique : « ; » attendu",
        "[3:12] erreur syntaxique : expression attendue",
        "[4:2] erreur syntaxique : « = » ou « ( » attendu après « x »",
    ]


def test_erreur_dans_un_bloc_n_empeche_pas_d_analyser_la_suite_du_bloc() -> None:
    source = "mission f() {\n  module = 1;\n  transmets 2\n  atterris;\n}\nmodule y;\n"
    assert erreurs_de(source) == [
        "[2:9] erreur syntaxique : « identifiant » attendu",
        "[3:14] erreur syntaxique : « ; » attendu",
        "[6:9] erreur syntaxique : « = » attendu",
    ]


def test_arbre_partiel_garde_les_instructions_valides() -> None:
    parser = Parser(analyser("transmets 1; module = 2; transmets 3;"))
    programme = parser.programme()
    assert programme.declarations == (transmets(1), transmets(3))
    assert len(parser.erreurs) == 1


def test_bloc_garde_ses_instructions_valides_autour_d_une_erreur() -> None:
    parser = Parser(analyser("orbite go { transmets 1; module = 2; transmets 3; }"))
    programme = parser.programme()
    orbite = Orbite(Booleen(True, position=P), bloc(transmets(1), transmets(3)), position=P)
    assert programme.declarations == (orbite,)


@pytest.mark.parametrize(
    "source",
    [
        "detecte { transmets 1; }",  # le bloc d'une condition cassée est sauté d'un coup
        "detecte { transmets 1; } sinon { transmets 2; }",  # pas de « sinon » orphelin
        "mission (a) { transmets 1; }",
        "survole i 0..3 { detecte go { } transmets 1; }",  # accolades imbriquées
        "{ transmets 1; }",  # un bloc seul n'est pas une instruction
    ],
)
def test_bloc_abime_n_entraine_pas_d_erreur_en_cascade(source: str) -> None:
    assert len(erreurs_de(source + "\ntransmets 2;")) == 1


def test_reprise_a_l_instruction_suivante_apres_un_bloc_abime() -> None:
    assert len(erreurs_de("detecte { } module = 1;")) == 2


def test_sinon_detecte_reprend_apres_une_condition_cassee() -> None:
    # Le deuxième `detecte` est analysé normalement, son erreur est donc trouvée aussi.
    assert erreurs_de("detecte { } sinon detecte { }") == [
        "[1:9] erreur syntaxique : expression attendue",
        "[1:27] erreur syntaxique : expression attendue",
    ]


@pytest.mark.parametrize(
    "source",
    ["}", "} } }", "sinon", ")", ";", ",,,,", "1 2 3", "mission", "detecte", "= = ="],
)
def test_parser_se_termine_toujours(source: str) -> None:
    assert erreurs_de(source)


def test_accolade_en_trop_ne_masque_pas_la_suite() -> None:
    assert erreurs_de("}\nmodule = 1;") == [
        "[1:1] erreur syntaxique : instruction attendue",
        "[2:7] erreur syntaxique : « identifiant » attendu",
    ]


# --- Erreurs fatales ---------------------------------------------------------


def test_erreur_lexicale_arrete_l_analyse_sans_perdre_les_precedentes() -> None:
    assert erreurs_de('module = 1;\ntransmets "abc;\nmodule = 2;') == [
        "[1:7] erreur syntaxique : « identifiant » attendu",
        "[2:11] erreur lexicale : chaîne non terminée",
    ]


def test_erreur_lexicale_dans_un_bloc_est_collectee() -> None:
    assert erreurs_de("orbite go {\n  transmets @;\n}") == [
        "[2:13] erreur lexicale : caractère inattendu « @ »"
    ]


def test_erreur_lexicale_sur_le_premier_token_est_collectee() -> None:
    assert erreurs_de("@") == ["[1:1] erreur lexicale : caractère inattendu « @ »"]


def test_erreur_lexicale_vue_par_le_regard_en_avant_est_collectee() -> None:
    assert erreurs_de("x @") == ["[1:3] erreur lexicale : caractère inattendu « @ »"]


@pytest.mark.parametrize(
    "source",
    [
        "transmets " + "(" * 5000 + "1",
        "transmets " + "-" * 5000 + "1;",
        "detecte go { " * 5000,
    ],
)
def test_imbrication_trop_profonde_devient_une_erreur_cosmo(source: str) -> None:
    with pytest.raises(ErreursCompilation) as info:
        analyser_programme(source)
    assert len(info.value.erreurs) == 1
    erreur = info.value.erreurs[0]
    assert isinstance(erreur, ErreurSyntaxique)
    assert erreur.message == "imbrication trop profonde"
    assert isinstance(erreur.__cause__, RecursionError)


# --- ErreursCompilation : collecte et chaînage -------------------------------


def test_erreurs_compilation_est_causee_par_la_premiere_erreur() -> None:
    with pytest.raises(ErreursCompilation) as info:
        analyser_programme("module = 1; module = 2;")
    assert info.value.__cause__ is info.value.erreurs[0]


def test_erreurs_compilation_affiche_une_erreur_par_ligne() -> None:
    with pytest.raises(ErreursCompilation) as info:
        analyser_programme("module = 1;\nmodule = 2;")
    assert str(info.value).splitlines() == [
        "[1:7] erreur syntaxique : « identifiant » attendu",
        "[2:7] erreur syntaxique : « identifiant » attendu",
    ]


def test_erreurs_collectees_gardent_leur_type() -> None:
    with pytest.raises(ErreursCompilation) as info:
        analyser_programme('module = 1;\ntransmets "')
    assert [type(e) for e in info.value.erreurs] == [ErreurSyntaxique, ErreurLexicale]


# --- Les programmes du dépôt -------------------------------------------------


@pytest.mark.parametrize(
    "chemin", sorted((RACINE / "exemples").glob("*.cosmo")), ids=lambda c: c.stem
)
def test_exemple_analyse_sans_erreur(chemin: Path) -> None:
    assert analyser_programme(chemin.read_text(encoding="utf-8")).declarations


@pytest.mark.parametrize("nom", ["01_chaine_non_terminee", "02_point_virgule_oublie"])
def test_programme_errone_donne_le_message_attendu(nom: str) -> None:
    dossier = RACINE / "erreurs"
    source = (dossier / f"{nom}.cosmo").read_text(encoding="utf-8")
    attendu = (dossier / f"{nom}.attendu").read_text(encoding="utf-8").strip()
    assert erreurs_de(source) == [attendu]


@pytest.mark.parametrize(
    "nom", ["03_variable_non_declaree", "04_mission_isolee", "05_nombre_arguments"]
)
def test_erreur_semantique_passe_le_parser(nom: str) -> None:
    source = (RACINE / "erreurs" / f"{nom}.cosmo").read_text(encoding="utf-8")
    assert analyser_programme(source).declarations
