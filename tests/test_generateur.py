"""Étape 8 : la génération de Python et l'exécution de bout en bout."""

import subprocess
import sys
from pathlib import Path

import pytest

from cosmo.compilateur import executer, transpiler
from cosmo.erreurs import ErreurGeneration, ErreursCompilation
from cosmo.generateur import PRELUDE, GenerateurPython, generer
from cosmo.noeuds import (
    Binaire,
    Entier,
    Expression,
    OperateurBinaire,
    Programme,
    Transmets,
)
from cosmo.parser import analyser_expression
from cosmo.tokens import Position

P = Position(1, 1)
RACINE = Path(__file__).parent.parent


def sortie_de(source: str, capsys: pytest.CaptureFixture[str]) -> str:
    executer(source)
    return capsys.readouterr().out


def corps(source: str) -> list[str]:
    """Les lignes générées pour le source, sans le prélude."""
    texte = transpiler(source)
    assert texte.startswith(PRELUDE)
    return texte.removeprefix(PRELUDE).splitlines()


# --- Texte des expressions ---------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("42", "42"),
        ("go", "True"),
        ("nogo", "False"),
        ("x", "c_x"),
        ('"Ada"', "'Ada'"),
        (r'"a\"b\\c\nd"', r"""'a"b\\c\nd'"""),
        ("f()", "c_f()"),
        ("f(1, x)", "c_f(1, c_x)"),
        ("7 / 2", "7 // 2"),
        ("7 % 2", "7 % 2"),
        ("a et b ou c", "c_a and c_b or c_c"),
        ("a != b", "c_a != c_b"),
        # Les parenthèses inutiles disparaissent...
        ("1 + (2 * 3)", "1 + 2 * 3"),
        ("(10 - 3) - 2", "10 - 3 - 2"),
        ("((x))", "c_x"),
        ("(non a) et b", "not c_a and c_b"),
        ("f((1 + 2))", "c_f(1 + 2)"),
        # ... et les parenthèses nécessaires restent.
        ("(1 + 2) * 3", "(1 + 2) * 3"),
        ("10 - (3 - 2)", "10 - (3 - 2)"),
        ("10 / (5 / 2)", "10 // (5 // 2)"),
        ("non (a et b)", "not (c_a and c_b)"),
        ("(a ou b) et c", "(c_a or c_b) and c_c"),
        ("a + (non b)", "c_a + (not c_b)"),
        ("-(a + b)", "-(c_a + c_b)"),
        ("-(non a)", "-(not c_a)"),
        ("- - a", "--c_a"),
        ("non non a", "not not c_a"),
        ("(a < b) < c", "(c_a < c_b) < c_c"),
        ("a < (b < c)", "c_a < (c_b < c_c)"),
        ("(a == b) == c", "(c_a == c_b) == c_c"),
    ],
)
def test_texte_d_une_expression(source: str, attendu: str) -> None:
    assert GenerateurPython().expression(analyser_expression(source)) == attendu


# --- Texte des instructions --------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("module x = 1;", ["c_x = 1"]),
        ("module x = 1; x = 2;", ["c_x = 1", "c_x = 2"]),
        ("transmets;", ["_transmets()"]),
        ("transmets 1, 2;", ["_transmets(1, 2)"]),
        ("orbite go { }", ["while True:", "    pass"]),
        (
            "survole i dans 0..3 { transmets i; }",
            ["for c_i in range(0, 3):", "    _transmets(c_i)"],
        ),
        ("detecte go { }", ["if True:", "    pass"]),
        (
            "detecte go { transmets 1; } sinon { transmets 2; }",
            ["if True:", "    _transmets(1)", "else:", "    _transmets(2)"],
        ),
        (
            "detecte go { } sinon detecte nogo { } sinon { }",
            ["if True:", "    pass", "elif False:", "    pass", "else:", "    pass"],
        ),
        ("mission f() { }", ["def c_f():", "    pass", ""]),
        ("mission f(a, b) { atterris; }", ["def c_f(c_a, c_b):", "    return", ""]),
        ("mission f() { atterris 1; }", ["def c_f():", "    return 1", ""]),
        ("mission f() { } f();", ["def c_f():", "    pass", "", "c_f()"]),
        (
            "orbite go { detecte go { transmets 1; } transmets 2; }\ntransmets 3;",
            [
                "while True:",
                "    if True:",
                "        _transmets(1)",
                "    _transmets(2)",
                "_transmets(3)",
            ],
        ),
    ],
)
def test_texte_d_une_instruction(source: str, attendu: list[str]) -> None:
    assert corps(source) == attendu


def test_programme_vide_ne_contient_que_le_prelude() -> None:
    assert transpiler("") == PRELUDE


def test_missions_sont_generees_avant_le_niveau_principal() -> None:
    assert corps("transmets 1; mission f() { } transmets 2; mission g() { }") == [
        "def c_f():",
        "    pass",
        "",
        "def c_g():",
        "    pass",
        "",
        "_transmets(1)",
        "_transmets(2)",
    ]


# --- Exécution : les règles de la spécification ------------------------------


@pytest.mark.parametrize(
    ("source", "sortie"),
    [
        # Affichage (4.7)
        ("transmets;", "\n"),
        ('transmets "a", 1, go, nogo;', "a 1 go nogo\n"),
        ("mission f() { } transmets f();", "rien\n"),
        ("transmets 0, 1, 1 == 1;", "0 1 go\n"),
        (r'transmets "a\nb", "\"", "\\";', 'a\nb " \\\n'),
        ('transmets "Décollage !";', "Décollage !\n"),
        # Opérateurs (4.2)
        ("transmets 1 + 2 * 3, (1 + 2) * 3;", "7 9\n"),
        ("transmets 10 - 3 - 2, 10 - (3 - 2);", "5 9\n"),
        ("transmets 7 / 2, -7 / 2, 7 % 2, -7 % 2;", "3 -4 1 1\n"),
        ('transmets "a" + "b";', "ab\n"),
        ("transmets 1 == 1, 1 != 1, 1 < 2, 1 <= 1, 1 > 2, 1 >= 2;", "go nogo go go nogo nogo\n"),
        ("transmets non go, non nogo, go et nogo, nogo ou go;", "nogo go nogo go\n"),
        # Une comparaison entre parenthèses n'est pas un enchaînement à la Python.
        ("transmets (3 > 2) > 1, 3 > (2 > 1);", "nogo go\n"),
        # Court-circuit
        ("transmets nogo et 1 / 0, go ou 1 / 0;", "nogo go\n"),
        # Vérité (4.3)
        ('detecte nogo ou 0 ou "" { transmets 1; } sinon { transmets 2; }', "2\n"),
        ("mission f() { } detecte f() { transmets 1; } sinon { transmets 2; }", "2\n"),
        ('detecte 2 et "a" { transmets 1; } sinon { transmets 2; }', "1\n"),
        # Conditions
        ("detecte nogo { transmets 1; } sinon detecte go { transmets 2; }", "2\n"),
        ("detecte nogo { transmets 1; } sinon detecte nogo { transmets 2; }", ""),
        # Boucles (4.6)
        ("module t = 2; orbite t > 0 { transmets t; t = t - 1; }", "2\n1\n"),
        ("orbite nogo { transmets 1; }", ""),
        ("survole i dans 0..3 { transmets i; }", "0\n1\n2\n"),
        ("survole i dans 3..3 { transmets i; }", ""),
        ("survole i dans 5..3 { transmets i; }", ""),
        ("survole i dans -1..1 { transmets i; }", "-1\n0\n"),
        (
            'mission b(v) { transmets v; atterris v; } survole i dans b(0)..b(2) { transmets "t"; }',
            "0\n2\nt\nt\n",
        ),
        (
            "module n = 2; survole i dans 0..n { n = 5; transmets i; }",
            "0\n1\n",
        ),
        # Missions (4.5)
        ("transmets f(); mission f() { atterris 1; }", "1\n"),
        (
            """
            mission p(n) { detecte n == 0 { atterris go; } atterris i(n - 1); }
            mission i(n) { detecte n == 0 { atterris nogo; } atterris p(n - 1); }
            transmets p(4), p(3);
            """,
            "go nogo\n",
        ),
        ("mission f() { atterris; transmets 1; } transmets f();", "rien\n"),
        ("mission f() { survole i dans 0..9 { atterris i; } } transmets f();", "0\n"),
        ("mission f(a) { a = a + 1; atterris a; } module x = 1; transmets f(x), x;", "2 1\n"),
        (
            "module x = 1; mission f() { module x = 2; atterris x; } transmets f(), x;",
            "2 1\n",
        ),
        # Portées (4.4) : un nom libéré par un bloc peut resservir.
        (
            "detecte go { module x = 1; transmets x; } module x = 2; transmets x;",
            "1\n2\n",
        ),
        # Noms (6) : ceux de Python ne gênent pas.
        ("module class = 1; module print = 2; transmets class, print;", "1 2\n"),
        ("module True = 1; module None = 2; transmets True, None;", "1 2\n"),
        ("mission def(if) { atterris if; } transmets def(1);", "1\n"),
        ("module _transmets = 1; module _texte = 2; transmets _transmets, _texte;", "1 2\n"),
        ("mission print() { atterris 1; } transmets print();", "1\n"),
    ],
)
def test_sortie_du_programme(source: str, sortie: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert sortie_de(source, capsys) == sortie


def test_programme_sans_instruction_n_affiche_rien(capsys: pytest.CaptureFixture[str]) -> None:
    assert sortie_de("# rien\n", capsys) == ""


def test_deux_executions_ne_partagent_pas_leurs_variables(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert sortie_de("module x = 1; transmets x;", capsys) == "1\n"
    assert sortie_de("module x = 2; transmets x;", capsys) == "2\n"


# --- Erreurs à l'exécution : celles de Python remontent ----------------------


@pytest.mark.parametrize(
    ("source", "exception"),
    [
        ("transmets 1 / 0;", ZeroDivisionError),
        ("transmets 1 % 0;", ZeroDivisionError),
        ('transmets "a" + 1;', TypeError),
        ('survole i dans "a"..1 { }', TypeError),
        ("mission f() { atterris f(); } f();", RecursionError),
    ],
)
def test_erreur_d_execution_remonte(source: str, exception: type[Exception]) -> None:
    with pytest.raises(exception):
        executer(source)


def test_sortie_affichee_avant_l_erreur_est_conservee(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ZeroDivisionError):
        executer("transmets 1; transmets 1 / 0; transmets 2;")
    assert capsys.readouterr().out == "1\n"


# --- Erreurs de compilation --------------------------------------------------


def test_executer_ne_lance_rien_si_la_compilation_echoue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ErreursCompilation):
        executer("transmets 1; transmets y;")
    assert capsys.readouterr().out == ""


def test_erreur_syntaxique_arrete_avant_l_analyse_semantique() -> None:
    with pytest.raises(ErreursCompilation) as info:
        transpiler("transmets y\ntransmets z;")
    assert str(info.value) == "[1:12] erreur syntaxique : « ; » attendu"


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("orbite go { " * 25 + "}" * 25, id="trop_de_boucles_imbriquees"),
        pytest.param("detecte go { " * 110 + "}" * 110, id="trop_de_niveaux_d_indentation"),
    ],
)
def test_limite_de_python_devient_une_erreur_cosmo(source: str) -> None:
    with pytest.raises(ErreursCompilation) as info:
        transpiler(source)
    erreur = info.value.erreurs[0]
    assert isinstance(erreur, ErreurGeneration)
    assert str(erreur) == (
        "[1:1] erreur de génération : programme trop imbriqué pour être traduit en Python"
    )
    assert isinstance(info.value.__cause__, SyntaxError)


def test_vingt_boucles_imbriquees_restent_acceptees(capsys: pytest.CaptureFixture[str]) -> None:
    profondeur = 20
    assert sortie_de("orbite nogo { " * profondeur + "}" * profondeur, capsys) == ""


def test_arbre_trop_profond_pour_le_generateur() -> None:
    somme: Expression = Entier(1, position=P)
    for _ in range(5000):
        somme = Binaire(OperateurBinaire.PLUS, somme, Entier(1, position=P), position=P)
    programme = Programme((Transmets((somme,), position=P),), position=P)
    with pytest.raises(ErreursCompilation) as info:
        generer(programme)
    assert isinstance(info.value.__cause__, RecursionError)


# --- assert_never et gestionnaire de contexte --------------------------------


def test_instruction_inconnue_est_un_oubli_du_compilateur() -> None:
    with pytest.raises(AssertionError):
        GenerateurPython().instruction(Entier(1, position=P))  # type: ignore[arg-type]


def test_expression_inconnue_est_un_oubli_du_compilateur() -> None:
    with pytest.raises(AssertionError):
        GenerateurPython().expression(Programme((), position=P))  # type: ignore[arg-type]


def test_indentation_restauree_meme_si_le_corps_leve() -> None:
    generateur = GenerateurPython()
    with pytest.raises(ValueError), generateur._indentation():
        raise ValueError
    assert generateur._niveau == 0


# --- Le test le plus important : les programmes du dépôt ---------------------


@pytest.mark.parametrize(
    "chemin", sorted((RACINE / "exemples").glob("*.cosmo")), ids=lambda c: c.stem
)
def test_exemple_produit_sa_sortie_attendue(
    chemin: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    attendu = chemin.with_suffix(".attendu").read_text(encoding="utf-8")
    assert sortie_de(chemin.read_text(encoding="utf-8"), capsys) == attendu


@pytest.mark.parametrize(
    "chemin", sorted((RACINE / "erreurs").glob("*.cosmo")), ids=lambda c: c.stem
)
def test_programme_errone_produit_son_message_attendu(chemin: Path) -> None:
    attendu = chemin.with_suffix(".attendu").read_text(encoding="utf-8").strip()
    with pytest.raises(ErreursCompilation) as info:
        transpiler(chemin.read_text(encoding="utf-8"))
    assert str(info.value) == attendu


def test_python_genere_fonctionne_hors_du_compilateur() -> None:
    source = (RACINE / "exemples" / "02_fibonacci.cosmo").read_text(encoding="utf-8")
    attendu = (RACINE / "exemples" / "02_fibonacci.attendu").read_text(encoding="utf-8")
    resultat = subprocess.run(
        [sys.executable, "-c", transpiler(source)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert resultat.stdout == attendu
