"""Étape 9 : la ligne de commande (SPEC.md, section 7.1).

Chaque sous-commande est associée à sa fonction par `set_defaults` : `main` n'a pas besoin
de les énumérer pour les lancer.

Codes de sortie : 0 si tout va bien, 1 si le programme Cosmo est erroné ou échoue à
l'exécution, 2 si la commande est mal formée ou qu'un fichier est inaccessible, 130 si
l'utilisateur interrompt l'exécution.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cosmo import __version__, compilateur
from cosmo.affichage import lignes_arbre
from cosmo.erreurs import ErreurCosmo, ErreursCompilation, decrire_erreur_execution
from cosmo.repl import lancer_repl

SUCCES = 0
ECHEC = 1
USAGE = 2
INTERRUPTION = 130


class ErreurFichier(Exception):
    """Un fichier ne peut être ni lu ni écrit."""


def _lire_source(chemin: Path) -> str:
    try:
        return chemin.read_text(encoding="utf-8-sig")  # tolère le BOM de certains éditeurs
    except (OSError, UnicodeDecodeError) as cause:
        raise ErreurFichier(f"impossible de lire « {chemin} » : {cause}") from cause


def _run(args: argparse.Namespace) -> int:
    source = _lire_source(args.fichier)
    try:
        compilateur.executer(source)
    except ErreursCompilation:
        raise
    except KeyboardInterrupt:
        print("exécution interrompue", file=sys.stderr)
        return INTERRUPTION
    except Exception as erreur:  # noqa: BLE001 : un programme peut lever n'importe quoi
        print(decrire_erreur_execution(erreur), file=sys.stderr)
        return ECHEC
    return SUCCES


def _transpile(args: argparse.Namespace) -> int:
    python = compilateur.transpiler(_lire_source(args.fichier))
    if args.sortie is None:
        print(python, end="")
        return SUCCES
    try:
        args.sortie.write_text(python, encoding="utf-8")
    except OSError as cause:
        raise ErreurFichier(f"impossible d'écrire « {args.sortie} » : {cause}") from cause
    return SUCCES


def _verifie(args: argparse.Namespace) -> int:
    compilateur.verifier(_lire_source(args.fichier))
    print(f"{args.fichier} : aucune erreur")
    return SUCCES


def _tokens(args: argparse.Namespace) -> int:
    for token in compilateur.tokens(_lire_source(args.fichier)):
        print(token)
    return SUCCES


def _arbre(args: argparse.Namespace) -> int:
    for ligne in lignes_arbre(compilateur.arbre(_lire_source(args.fichier))):
        print(ligne)
    return SUCCES


def _repl(args: argparse.Namespace) -> int:
    lancer_repl()
    return SUCCES


def construire_parser() -> argparse.ArgumentParser:
    """Décrit la ligne de commande. Sans sous-commande, c'est le REPL qui démarre."""
    parser = argparse.ArgumentParser(
        prog="cosmo", description="Compilateur du langage Cosmo vers Python."
    )
    parser.add_argument("--version", action="version", version=f"cosmo {__version__}")
    parser.set_defaults(action=_repl)
    commandes = parser.add_subparsers(title="commandes", metavar="commande")

    for nom, action, aide in (
        ("run", _run, "exécute un programme"),
        ("transpile", _transpile, "affiche le Python généré"),
        ("verifie", _verifie, "cherche les erreurs de compilation, sans exécuter"),
        ("tokens", _tokens, "affiche les tokens produits par le lexer"),
        ("arbre", _arbre, "affiche l'arbre produit par le parser"),
    ):
        commande = commandes.add_parser(nom, help=aide, description=aide)
        commande.add_argument("fichier", type=Path, help="le fichier source .cosmo")
        commande.set_defaults(action=action)
        if nom == "transpile":
            commande.add_argument(
                "-o", "--sortie", type=Path, help="écrit le Python dans ce fichier"
            )

    repl = commandes.add_parser("repl", help="lance une session interactive")
    repl.set_defaults(action=_repl)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Lance la commande demandée et renvoie son code de sortie."""
    args = construire_parser().parse_args(arguments)
    try:
        code: int = args.action(args)
    except (ErreursCompilation, ErreurCosmo) as erreurs:
        print(erreurs, file=sys.stderr)
        return ECHEC
    except RecursionError:  # seul l'affichage de l'arbre peut encore y arriver ici
        print("erreur : programme trop imbriqué pour être affiché", file=sys.stderr)
        return ECHEC
    except ErreurFichier as erreur:
        print(f"cosmo : {erreur}", file=sys.stderr)
        return USAGE
    return code
