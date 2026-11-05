"""Étape 10 : le formateur, et les backends en `Protocol`."""

import subprocess
import sys
from pathlib import Path

import pytest

from cosmo import compilateur
from cosmo.backend import BACKENDS, Backend
from cosmo.cli import ECHEC, SUCCES, USAGE, main
from cosmo.compilateur import formater, transpiler
from cosmo.erreurs import ErreursCompilation
from cosmo.generateur import BackendPython
from cosmo.noeuds import Orbite, Programme, Transmets
from cosmo.parser import analyser_programme
from cosmo.tokens import Position

RACINE = Path(__file__).parent.parent
EXEMPLES = sorted((RACINE / "exemples").glob("*.cosmo"))
P = Position(1, 1)

type Capture = pytest.CaptureFixture[str]

# Des programmes volontairement mal présentés : chaque propriété est vérifiée sur tous.
SOURCES_DESORDONNEES = [
    "",
    "\n\n\n",
    "# seul\n",
    "# un\n\n\n# deux\n",
    "module   x=1;transmets x ;",
    "module x = 1; module y = 2; # fin\n",
    "module x =\n  1 +\n  # milieu\n  2;\n",
    "mission f(a,b){atterris a+b;}f(1,2);",
    "mission f( ) { }\n\n\n\nmission g( ) { }\ntransmets;",
    "transmets 1;\n\n\n\ntransmets 2;\n\n",
    "detecte a{}sinon detecte b{}sinon{}",
    "detecte a { # entete\n  # dedans\n  x = 1; # fin x\n  # avant accolade\n} # apres\n",
    "detecte a {\n} # avant sinon\n# encore\nsinon {\n  # corps\n}\n",
    "detecte a {\n} sinon detecte b { # c1\n} sinon { # c2\n}\n",
    "orbite a{\n\n\n  x=1;\n\n\n  y=2;\n\n\n}\n",
    "survole i dans 0..8{transmets i;}",
    "survole i dans a+1..f(b)*2 { }",
    "mission f(a, # p1\n  b # p2\n) # p3\n{ # p4\n}\n",
    "# avant\nmission f() {\n}\n# apres\n",
    "x = 1;\n# pour la mission\nmission f() { }\n# la suite\ntransmets 1;\n",
    "mission f() { } # note\ntransmets 1;\n",
    'transmets "a\\"b\\\\c\\nd", "é → #pas un commentaire";',
    "transmets 1 + (2 * 3), (1 + 2) * 3, 10 - (3 - 2), (10 - 3) - 2;",
    "transmets (a < b) < c, a < (b < c), (a == b) != c;",
    "transmets non (a et b), (non a) et b, non a et b, non non a, a ou (b ou c);",
    "transmets - - x, -(a + b), (-a) + b, -(non a), a + (non b), (non a) == b, non (a == b);",
    "transmets f(), f(1), f(g(2), (3));",
    "atterris;\natterris 1;\nf();",
]


def commentaires_de(source: str) -> list[str]:
    return [c.texte for c in analyser_programme(source).mise_en_page.commentaires]


# --- Les trois garanties --------------------------------------------------------


@pytest.mark.parametrize("source", SOURCES_DESORDONNEES)
def test_le_formatage_ne_change_pas_l_arbre(source: str) -> None:
    assert analyser_programme(formater(source)) == analyser_programme(source)


@pytest.mark.parametrize("source", SOURCES_DESORDONNEES)
def test_formater_deux_fois_ne_change_rien_de_plus(source: str) -> None:
    une_fois = formater(source)
    assert formater(une_fois) == une_fois


@pytest.mark.parametrize("source", SOURCES_DESORDONNEES)
def test_aucun_commentaire_n_est_perdu_ni_deplace_dans_l_ordre(source: str) -> None:
    assert commentaires_de(formater(source)) == commentaires_de(source)


@pytest.mark.parametrize("chemin", EXEMPLES, ids=lambda c: c.stem)
def test_les_exemples_sont_deja_au_format_canonique(chemin: Path) -> None:
    source = chemin.read_text(encoding="utf-8")
    assert formater(source) == source


@pytest.mark.parametrize("chemin", EXEMPLES, ids=lambda c: c.stem)
def test_un_exemple_reformate_produit_la_meme_sortie(chemin: Path, capsys: Capture) -> None:
    source = chemin.read_text(encoding="utf-8").replace("\n", "\n\n").replace("    ", "\t")
    compilateur.executer(formater(source))
    attendu = chemin.with_suffix(".attendu").read_text(encoding="utf-8")
    assert capsys.readouterr().out == attendu


# --- Le format canonique ----------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("module   x=1 ;", "module x = 1;\n"),
        ("x=x+1;", "x = x + 1;\n"),
        ("transmets;", "transmets;\n"),
        ("transmets 1,2 , 3;", "transmets 1, 2, 3;\n"),
        ("atterris;", "atterris;\n"),
        ("atterris 1;", "atterris 1;\n"),
        ("f( 1,2 ) ;", "f(1, 2);\n"),
        ("orbite go{}", "orbite go {\n}\n"),
        ("survole i dans 0 .. 8{}", "survole i dans 0..8 {\n}\n"),
        ("mission f(a,b){}", "mission f(a, b) {\n}\n"),
        ("orbite go{x=1;}", "orbite go {\n    x = 1;\n}\n"),
        ("orbite go{orbite nogo{x=1;}}", "orbite go {\n    orbite nogo {\n        x = 1;\n    }\n}\n"),
    ],
)
def test_format_d_une_instruction(source: str, attendu: str) -> None:
    assert formater(source) == attendu


def test_sinon_reste_sur_la_ligne_de_l_accolade_fermante() -> None:
    source = "detecte a { x = 1; }\nsinon detecte b { x = 2; }\nsinon { x = 3; }"
    assert formater(source) == (
        "detecte a {\n"
        "    x = 1;\n"
        "} sinon detecte b {\n"
        "    x = 2;\n"
        "} sinon {\n"
        "    x = 3;\n"
        "}\n"
    )


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("((x))", "x"),
        ("1 + (2 * 3)", "1 + 2 * 3"),
        ("(1 + 2) * 3", "(1 + 2) * 3"),
        ("(10 - 3) - 2", "10 - 3 - 2"),
        ("10 - (3 - 2)", "10 - (3 - 2)"),
        ("(a < b) < c", "(a < b) < c"),
        ("a + (non b)", "a + (non b)"),
        ("(non a) et b", "non a et b"),
        ("non (a et b)", "non (a et b)"),
        ("-(-x)", "--x"),
        ("7 / 2 % 3", "7 / 2 % 3"),
        ("a et b ou c", "a et b ou c"),
        ("a != b", "a != b"),
        ("go", "go"),
        ("nogo", "nogo"),
    ],
)
def test_seules_les_parentheses_necessaires_sont_gardees(source: str, attendu: str) -> None:
    assert formater(f"transmets {source};") == f"transmets {attendu};\n"


@pytest.mark.parametrize(
    "chaine",
    ['"simple"', r'"guillemet \" dedans"', r'"barre \\ oblique"', r'"saut \n de ligne"', '"é → 🚀"'],
)
def test_une_chaine_est_reecrite_a_l_identique(chaine: str) -> None:
    assert formater(f"transmets {chaine};") == f"transmets {chaine};\n"


# --- Lignes vides ---------------------------------------------------------------


def test_les_lignes_vides_multiples_sont_reduites_a_une() -> None:
    assert formater("transmets 1;\n\n\n\ntransmets 2;") == "transmets 1;\n\ntransmets 2;\n"


def test_l_absence_de_ligne_vide_est_respectee() -> None:
    assert formater("transmets 1;\ntransmets 2;") == "transmets 1;\ntransmets 2;\n"


def test_les_lignes_vides_du_debut_et_de_la_fin_disparaissent() -> None:
    assert formater("\n\n\ntransmets 1;\n\n\n") == "transmets 1;\n"


def test_pas_de_ligne_vide_au_debut_ni_a_la_fin_d_un_bloc() -> None:
    assert formater("orbite go {\n\n  x = 1;\n\n}") == "orbite go {\n    x = 1;\n}\n"


def test_une_ligne_vide_dans_un_bloc_est_conservee() -> None:
    source = "orbite go {\n    x = 1;\n\n    y = 2;\n}\n"
    assert formater(source) == source


def test_une_mission_est_entouree_de_lignes_vides() -> None:
    assert formater("x = 1;\nmission f() {\n}\ny = 2;") == (
        "x = 1;\n\nmission f() {\n}\n\ny = 2;\n"
    )


def test_la_ligne_vide_avant_une_mission_precede_son_commentaire() -> None:
    assert formater("x = 1;\n# doc\nmission f() {\n}") == "x = 1;\n\n# doc\nmission f() {\n}\n"


def test_un_commentaire_apres_une_mission_est_separe_d_elle() -> None:
    assert formater("mission f() {\n}\n# fin") == "mission f() {\n}\n\n# fin\n"


def test_un_programme_vide_reste_vide() -> None:
    assert formater("\n\n") == ""


# --- Commentaires ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "# seul\n",
        "# au-dessus\nmodule x = 1;\n",
        "module x = 1;  # à côté\n",
        "module x = 1;\n# en dessous\n",
        "# un\n\n# deux\n",
        "orbite go {  # entête\n    x = 1;\n}\n",
        "orbite go {\n    # au début\n    x = 1;\n}\n",
        "orbite go {\n    x = 1;\n    # à la fin\n}\n",
        "orbite go {\n    # seul dans le bloc\n}\n",
        "orbite go {\n}  # après le bloc\n",
        "detecte a {\n    # alors\n} sinon {\n    # sinon\n}\n",
        "detecte a {\n} sinon {  # sur le sinon\n}\n",
        "mission f() {\n    # doc\n    atterris 1;\n}\n",
    ],
)
def test_un_commentaire_deja_bien_place_ne_bouge_pas(source: str) -> None:
    assert formater(source) == source


def test_un_commentaire_garde_son_texte_exact_sauf_les_espaces_de_fin() -> None:
    assert formater("#sans espace  \t\n#   large\n") == "#sans espace\n#   large\n"


def test_un_commentaire_reprend_l_indentation_du_bloc() -> None:
    assert formater("orbite go {\n# ici\nx = 1;\n}") == "orbite go {\n    # ici\n    x = 1;\n}\n"


def test_un_commentaire_dans_une_instruction_sur_plusieurs_lignes_passe_apres() -> None:
    assert formater("module x = 1 +\n# milieu\n2;") == "module x = 1 + 2;\n# milieu\n"


def test_un_commentaire_entre_l_accolade_et_le_sinon_entre_dans_le_sinon() -> None:
    assert formater("detecte a {\n}\n# c\nsinon {\n}") == "detecte a {\n} sinon {  # c\n}\n"


def test_les_diese_d_une_chaine_ne_sont_pas_des_commentaires() -> None:
    assert commentaires_de('transmets "# non"; # oui') == ["# oui"]


def test_les_commentaires_ne_changent_pas_la_generation_python() -> None:
    assert transpiler("# c\nmodule x = 1;  # d") == transpiler("module x = 1;")


# --- Le formateur ne regarde que la syntaxe ---------------------------------------


def test_on_peut_formater_un_programme_au_sens_encore_faux() -> None:
    assert formater("transmets  inconnue ;") == "transmets inconnue;\n"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("module x = ", "erreur syntaxique"),
        ("{", "erreur syntaxique"),
        ("@", "erreur lexicale"),
    ],
)
def test_une_syntaxe_fausse_est_refusee(source: str, message: str) -> None:
    with pytest.raises(ErreursCompilation, match=message):
        formater(source)


def test_un_arbre_trop_profond_est_signale_proprement() -> None:
    with pytest.raises(ErreursCompilation, match="trop imbriqué pour être formaté"):
        formater("transmets 1" + " + 1" * 5000 + ";")


# --- Un arbre sans mise en page -----------------------------------------------------


def test_un_arbre_construit_a_la_main_se_formate_aussi() -> None:
    programme = Programme((Transmets((), position=P),), position=P)
    assert BACKENDS["cosmo"].generer(programme) == "transmets;\n"


def test_la_mise_en_page_ne_compte_pas_dans_l_egalite_des_arbres() -> None:
    assert analyser_programme("# c\n\ntransmets;") == analyser_programme("transmets;")


def test_la_fin_d_un_bloc_est_sa_position_d_accolade_fermante() -> None:
    orbite = analyser_programme("orbite go {\n\n}").declarations[0]
    assert isinstance(orbite, Orbite)
    assert orbite.corps.fin == Position(3, 1)


# --- Backend : le Protocol et le principe ouvert/fermé --------------------------------


class BackendCompteur:
    """N'hérite de rien : avoir la bonne méthode suffit pour être un Backend."""

    def generer(self, programme: Programme) -> str:
        return f"{len(programme.declarations)} déclarations\n"


def test_une_classe_quelconque_avec_la_bonne_methode_est_un_backend() -> None:
    backend: Backend = BackendCompteur()  # vérifié par mypy --strict
    assert transpiler("transmets 1; transmets 2;", backend) == "2 déclarations\n"


def test_tout_backend_passe_par_l_analyse_semantique() -> None:
    with pytest.raises(ErreursCompilation, match="non déclarée"):
        transpiler("transmets y;", BackendCompteur())


def test_python_est_le_backend_par_defaut() -> None:
    assert transpiler("transmets 1;") == transpiler("transmets 1;", BackendPython())


def test_un_backend_enregistre_est_disponible_sans_toucher_a_la_ligne_de_commande(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: Capture
) -> None:
    monkeypatch.setitem(BACKENDS, "compteur", BackendCompteur())
    chemin = tmp_path / "p.cosmo"
    chemin.write_text("transmets 1;", encoding="utf-8")
    assert main(["transpile", str(chemin), "--backend", "compteur"]) == SUCCES
    assert capsys.readouterr().out == "1 déclarations\n"


# --- La ligne de commande -------------------------------------------------------------


@pytest.fixture
def desordonne(tmp_path: Path) -> Path:
    chemin = tmp_path / "desordonne.cosmo"
    chemin.write_text("module   x=1;\n", encoding="utf-8")
    return chemin


@pytest.fixture
def propre(tmp_path: Path) -> Path:
    chemin = tmp_path / "propre.cosmo"
    chemin.write_text("module x = 1;\n", encoding="utf-8")
    return chemin


def test_formate_affiche_sans_modifier_le_fichier(desordonne: Path, capsys: Capture) -> None:
    assert main(["formate", str(desordonne)]) == SUCCES
    assert capsys.readouterr().out == "module x = 1;\n"
    assert desordonne.read_text(encoding="utf-8") == "module   x=1;\n"


@pytest.mark.parametrize("option", ["-e", "--ecrire"])
def test_formate_ecrire_reecrit_le_fichier(option: str, desordonne: Path, capsys: Capture) -> None:
    assert main(["formate", str(desordonne), option]) == SUCCES
    assert capsys.readouterr().out == ""
    assert desordonne.read_text(encoding="utf-8") == "module x = 1;\n"


def test_formate_ecrire_ne_touche_pas_un_fichier_a_la_syntaxe_fausse(
    tmp_path: Path, capsys: Capture
) -> None:
    chemin = tmp_path / "faux.cosmo"
    chemin.write_text("module   x=", encoding="utf-8")
    assert main(["formate", str(chemin), "--ecrire"]) == ECHEC
    assert chemin.read_text(encoding="utf-8") == "module   x="
    assert "erreur syntaxique" in capsys.readouterr().err


def test_formate_verifie_accepte_un_fichier_propre(propre: Path) -> None:
    assert main(["formate", str(propre), "--verifie"]) == SUCCES


def test_formate_verifie_signale_un_fichier_a_reformater_sans_le_modifier(
    desordonne: Path, capsys: Capture
) -> None:
    assert main(["formate", str(desordonne), "--verifie"]) == ECHEC
    assert capsys.readouterr().err == f"{desordonne} : à reformater\n"
    assert desordonne.read_text(encoding="utf-8") == "module   x=1;\n"


def test_formate_refuse_ecrire_et_verifier_a_la_fois(propre: Path, capsys: Capture) -> None:
    with pytest.raises(SystemExit) as info:
        main(["formate", str(propre), "--ecrire", "--verifie"])
    assert info.value.code == USAGE
    capsys.readouterr()


def test_transpile_vers_cosmo_fait_aussi_l_analyse_semantique(
    desordonne: Path, tmp_path: Path, capsys: Capture
) -> None:
    assert main(["transpile", str(desordonne), "--backend", "cosmo"]) == SUCCES
    assert capsys.readouterr().out == "module x = 1;\n"
    faux = tmp_path / "faux.cosmo"
    faux.write_text("transmets y;", encoding="utf-8")
    assert main(["transpile", str(faux), "--backend", "cosmo"]) == ECHEC
    assert "non déclarée" in capsys.readouterr().err


def test_transpile_refuse_un_backend_inconnu(propre: Path, capsys: Capture) -> None:
    with pytest.raises(SystemExit) as info:
        main(["transpile", str(propre), "--backend", "klingon"])
    assert info.value.code == USAGE
    assert "klingon" in capsys.readouterr().err


def test_python_m_cosmo_formate() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "cosmo", "formate", "exemples/05_portees.cosmo", "--verifie"],
        capture_output=True,
        encoding="utf-8",
        cwd=RACINE,
        check=False,
    )
    assert (resultat.returncode, resultat.stderr) == (SUCCES, "")


# --- Début de bloc ----------------------------------------------------------------------


@pytest.mark.parametrize("entete", ["orbite go {  # note", "orbite go {  # finit par {"])
def test_pas_de_ligne_vide_apres_un_entete_commente(entete: str) -> None:
    source = f"{entete}\n\n    x = 1;\n}}\n"
    assert formater(source) == f"{entete}\n    x = 1;\n}}\n"


def test_une_ligne_vide_apres_un_commentaire_qui_finit_par_accolade_est_conservee() -> None:
    source = "# {\n\ntransmets 1;\n"
    assert formater(source) == source
