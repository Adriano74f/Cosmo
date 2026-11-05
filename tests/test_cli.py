"""Étape 9 : la ligne de commande."""

import subprocess
import sys
from pathlib import Path

import pytest

from cosmo import __version__
from cosmo.cli import ECHEC, SUCCES, USAGE, main

RACINE = Path(__file__).parent.parent
EXEMPLES = sorted((RACINE / "exemples").glob("*.cosmo"))
ERREURS = sorted((RACINE / "erreurs").glob("*.cosmo"))

type Capture = pytest.CaptureFixture[str]


@pytest.fixture
def fichier(tmp_path: Path) -> Path:
    chemin = tmp_path / "programme.cosmo"
    chemin.write_text("module x = 1;\ntransmets x;\n", encoding="utf-8")
    return chemin


def ecrire(dossier: Path, source: str) -> str:
    chemin = dossier / "source.cosmo"
    chemin.write_text(source, encoding="utf-8")
    return str(chemin)


# --- run -----------------------------------------------------------------------


@pytest.mark.parametrize("chemin", EXEMPLES, ids=lambda c: c.stem)
def test_run_affiche_la_sortie_attendue_de_chaque_exemple(chemin: Path, capsys: Capture) -> None:
    assert main(["run", str(chemin)]) == SUCCES
    assert capsys.readouterr().out == chemin.with_suffix(".attendu").read_text(encoding="utf-8")


@pytest.mark.parametrize("chemin", ERREURS, ids=lambda c: c.stem)
def test_run_signale_les_erreurs_de_compilation_sur_stderr(chemin: Path, capsys: Capture) -> None:
    assert main(["run", str(chemin)]) == ECHEC
    capture = capsys.readouterr()
    assert capture.out == ""
    assert capture.err == chemin.with_suffix(".attendu").read_text(encoding="utf-8")


def test_run_signale_toutes_les_erreurs_collectees(tmp_path: Path, capsys: Capture) -> None:
    assert main(["run", ecrire(tmp_path, "transmets a;\ntransmets b;\n")]) == ECHEC
    assert capsys.readouterr().err == (
        "[1:11] erreur sémantique : variable « a » non déclarée\n"
        "[2:11] erreur sémantique : variable « b » non déclarée\n"
    )


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("transmets 1 / 0;", "erreur d'exécution : division par zéro\n"),
        ("transmets 1 % 0;", "erreur d'exécution : division par zéro\n"),
        ("mission f() { atterris f(); }\nf();", "erreur d'exécution : trop d'appels"),
        ('transmets "a" + 1;', "erreur d'exécution : types incompatibles"),
    ],
)
def test_run_decrit_les_erreurs_d_execution_sans_trace_python(
    source: str, message: str, tmp_path: Path, capsys: Capture
) -> None:
    assert main(["run", ecrire(tmp_path, source)]) == ECHEC
    erreur = capsys.readouterr().err
    assert erreur.startswith(message)
    assert "Traceback" not in erreur


def test_run_garde_ce_qui_est_affiche_avant_l_erreur_d_execution(
    tmp_path: Path, capsys: Capture
) -> None:
    assert main(["run", ecrire(tmp_path, "transmets 1;\ntransmets 1 / 0;")]) == ECHEC
    assert capsys.readouterr().out == "1\n"


def test_run_tolere_le_bom_d_un_fichier_windows(tmp_path: Path, capsys: Capture) -> None:
    assert main(["run", ecrire(tmp_path, "﻿transmets 1;")]) == SUCCES
    assert capsys.readouterr().out == "1\n"


def test_run_comprend_les_fins_de_ligne_windows(tmp_path: Path, capsys: Capture) -> None:
    chemin = tmp_path / "crlf.cosmo"
    chemin.write_bytes(b"module x = 1;\r\ntransmets y;\r\n")
    assert main(["run", str(chemin)]) == ECHEC
    assert capsys.readouterr().err.startswith("[2:11] ")


# --- Fichiers inaccessibles ----------------------------------------------------


@pytest.mark.parametrize(
    "commande", ["run", "transpile", "formate", "verifie", "tokens", "arbre"]
)
def test_fichier_absent_signale_proprement(
    commande: str, tmp_path: Path, capsys: Capture
) -> None:
    assert main([commande, str(tmp_path / "absent.cosmo")]) == USAGE
    capture = capsys.readouterr()
    assert capture.err.startswith("cosmo : impossible de lire")
    assert "absent.cosmo" in capture.err
    assert "Traceback" not in capture.err


def test_un_dossier_n_est_pas_un_fichier_source(tmp_path: Path, capsys: Capture) -> None:
    assert main(["run", str(tmp_path)]) == USAGE
    assert "impossible de lire" in capsys.readouterr().err


def test_fichier_qui_n_est_pas_en_utf8_signale_proprement(tmp_path: Path, capsys: Capture) -> None:
    chemin = tmp_path / "latin1.cosmo"
    chemin.write_bytes('transmets "é";'.encode("latin-1"))
    assert main(["run", str(chemin)]) == USAGE
    assert "impossible de lire" in capsys.readouterr().err


# --- transpile -----------------------------------------------------------------


def test_transpile_affiche_le_python(fichier: Path, capsys: Capture) -> None:
    assert main(["transpile", str(fichier)]) == SUCCES
    sortie = capsys.readouterr().out
    assert "c_x = 1\n_transmets(c_x)\n" in sortie


def test_transpile_n_execute_pas_le_programme(tmp_path: Path, capsys: Capture) -> None:
    assert main(["transpile", ecrire(tmp_path, "transmets 1 / 0;")]) == SUCCES
    assert "_transmets(1 // 0)" in capsys.readouterr().out


@pytest.mark.parametrize("option", ["-o", "--sortie"])
def test_transpile_ecrit_un_fichier_python_executable(
    option: str, fichier: Path, tmp_path: Path, capsys: Capture
) -> None:
    sortie = tmp_path / "sortie.py"
    assert main(["transpile", str(fichier), option, str(sortie)]) == SUCCES
    assert capsys.readouterr().out == ""
    resultat = subprocess.run(
        [sys.executable, str(sortie)], capture_output=True, text=True, check=True
    )
    assert resultat.stdout == "1\n"


def test_transpile_signale_un_fichier_de_sortie_inaccessible(
    fichier: Path, tmp_path: Path, capsys: Capture
) -> None:
    sortie = tmp_path / "absent" / "sortie.py"
    assert main(["transpile", str(fichier), "-o", str(sortie)]) == USAGE
    assert "impossible d'écrire" in capsys.readouterr().err


def test_transpile_d_un_programme_errone_n_ecrit_rien(tmp_path: Path, capsys: Capture) -> None:
    sortie = tmp_path / "sortie.py"
    assert main(["transpile", ecrire(tmp_path, "transmets y;"), "-o", str(sortie)]) == ECHEC
    assert not sortie.exists()
    assert "non déclarée" in capsys.readouterr().err


# --- verifie -------------------------------------------------------------------


def test_verifie_confirme_un_programme_correct_sans_l_executer(
    tmp_path: Path, capsys: Capture
) -> None:
    chemin = ecrire(tmp_path, "transmets 1 / 0;")
    assert main(["verifie", chemin]) == SUCCES
    assert capsys.readouterr().out == f"{chemin} : aucune erreur\n"


@pytest.mark.parametrize("chemin", ERREURS, ids=lambda c: c.stem)
def test_verifie_signale_les_erreurs_de_chaque_phase(chemin: Path, capsys: Capture) -> None:
    assert main(["verifie", str(chemin)]) == ECHEC
    assert capsys.readouterr().err == chemin.with_suffix(".attendu").read_text(encoding="utf-8")


def test_verifie_refuse_un_programme_trop_imbrique_pour_python(
    tmp_path: Path, capsys: Capture
) -> None:
    ouvertures = "".join(f"survole i{n} dans 0..1 {{ " for n in range(25))
    assert main(["verifie", ecrire(tmp_path, ouvertures + "}" * 25)]) == ECHEC
    assert "erreur de génération" in capsys.readouterr().err


# --- tokens --------------------------------------------------------------------


def test_tokens_affiche_un_token_par_ligne(tmp_path: Path, capsys: Capture) -> None:
    assert main(["tokens", ecrire(tmp_path, "go;")]) == SUCCES
    assert capsys.readouterr().out.splitlines() == [
        "Token(GO, 'go', 1:1)",
        "Token(POINT_VIRGULE, ';', 1:3)",
        "Token(FIN, '', 1:4)",
    ]


def test_tokens_affiche_ceux_qui_precedent_une_erreur_lexicale(
    tmp_path: Path, capsys: Capture
) -> None:
    assert main(["tokens", ecrire(tmp_path, "go @")]) == ECHEC
    capture = capsys.readouterr()
    assert capture.out == "Token(GO, 'go', 1:1)\n"
    assert capture.err == "[1:4] erreur lexicale : caractère inattendu « @ »\n"


# --- arbre ---------------------------------------------------------------------


def test_arbre_affiche_les_noeuds_indentes_avec_leur_position(
    tmp_path: Path, capsys: Capture
) -> None:
    assert main(["arbre", ecrire(tmp_path, "module x = 1 + 2;")]) == SUCCES
    assert capsys.readouterr().out.splitlines() == [
        "Programme [1:1]",
        "  declarations[0]: Module nom='x' [1:8]",
        "    valeur: Binaire operateur='+' [1:14]",
        "      gauche: Entier valeur=1 [1:12]",
        "      droite: Entier valeur=2 [1:16]",
    ]


def test_arbre_affiche_les_champs_vides(tmp_path: Path, capsys: Capture) -> None:
    assert main(["arbre", ecrire(tmp_path, "atterris;")]) == SUCCES
    assert "Atterris valeur=None" in capsys.readouterr().out


def test_arbre_ne_fait_pas_d_analyse_semantique(tmp_path: Path, capsys: Capture) -> None:
    assert main(["arbre", ecrire(tmp_path, "transmets inconnue;")]) == SUCCES
    assert "Variable nom='inconnue'" in capsys.readouterr().out


def test_arbre_signale_les_erreurs_de_syntaxe(tmp_path: Path, capsys: Capture) -> None:
    assert main(["arbre", ecrire(tmp_path, "module x = 1")]) == ECHEC
    assert capsys.readouterr().err == "[1:13] erreur syntaxique : « ; » attendu\n"


def test_arbre_trop_profond_pour_etre_affiche_signale_proprement(
    tmp_path: Path, capsys: Capture
) -> None:
    source = "transmets 1" + " + 1" * 5000 + ";"
    assert main(["arbre", ecrire(tmp_path, source)]) == ECHEC
    assert "trop imbriqué" in capsys.readouterr().err


# --- argparse ------------------------------------------------------------------


def test_version(capsys: Capture) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert capsys.readouterr().out == f"cosmo {__version__}\n"


@pytest.mark.parametrize(
    "arguments",
    [["inconnue"], ["run"], ["run", "a", "b"], ["run", "a", "-o", "b"], ["repl", "a"]],
)
def test_ligne_de_commande_mal_formee_sort_avec_le_code_d_usage(
    arguments: list[str], capsys: Capture
) -> None:
    with pytest.raises(SystemExit) as info:
        main(arguments)
    assert info.value.code == USAGE
    assert "usage" in capsys.readouterr().err


@pytest.mark.parametrize(
    "commande", ["run", "transpile", "formate", "verifie", "tokens", "arbre", "repl"]
)
def test_l_aide_cite_chaque_commande(commande: str, capsys: Capture) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert commande in capsys.readouterr().out


# --- python -m cosmo, dans un vrai processus -----------------------------------


def lancer(*arguments: str, entree: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cosmo", *arguments],
        capture_output=True,
        encoding="utf-8",
        input=entree,
        cwd=RACINE,
        check=False,
    )


def test_python_m_cosmo_run_execute_un_exemple() -> None:
    resultat = lancer("run", "exemples/02_fibonacci.cosmo")
    attendu = (RACINE / "exemples" / "02_fibonacci.attendu").read_text(encoding="utf-8")
    assert (resultat.returncode, resultat.stdout) == (SUCCES, attendu)


def test_python_m_cosmo_transmet_le_code_de_sortie_d_une_erreur() -> None:
    resultat = lancer("run", "erreurs/03_variable_non_declaree.cosmo")
    assert resultat.returncode == ECHEC
    assert resultat.stderr == "[2:11] erreur sémantique : variable « y » non déclarée\n"


def test_python_m_cosmo_affiche_tous_les_caracteres_hors_d_un_terminal(tmp_path: Path) -> None:
    resultat = lancer("run", ecrire(tmp_path, 'transmets "décollage → 🚀";'))
    assert resultat.stdout == "décollage → 🚀\n"


@pytest.mark.parametrize("arguments", [(), ("repl",)], ids=["sans_commande", "repl"])
def test_python_m_cosmo_lance_le_repl_qui_lit_l_entree_standard(
    arguments: tuple[str, ...],
) -> None:
    resultat = lancer(*arguments, entree="module x = 41;\nx + 1\n")
    assert resultat.returncode == SUCCES
    assert "42\n" in resultat.stdout
    assert resultat.stderr == ""
