"""Étape 9 : le REPL, une session interactive (SPEC.md, section 7.2).

La boucle est un générateur qu'on pilote avec `send` : il produit l'invite à afficher, et
reçoit en retour la ligne saisie. Il ne sait donc rien du clavier : `lancer_repl` s'occupe
de lire les lignes, et les tests peuvent lui envoyer directement les leurs.
"""

import sys
from collections.abc import Callable, Generator

from cosmo import __version__
from cosmo.compilateur import Session, lire_expression, tokens
from cosmo.erreurs import ErreurCosmo, ErreursCompilation, decrire_erreur_execution
from cosmo.tokens import Token, TypeToken

T = TypeToken

INVITE = "cosmo> "
INVITE_SUITE = "  ... "
BANNIERE = f"Cosmo {__version__} : tapez :aide pour l'aide, :quitter pour sortir."
AIDE = """\
Tapez des instructions Cosmo, ou une expression pour afficher sa valeur.
Une entrée continue sur la ligne suivante tant qu'elle n'est pas finie (invite « ... ») :
  - tant qu'une accolade ou une parenthèse reste ouverte (Ctrl-C pour abandonner) ;
  - sinon, tant qu'elle ne finit pas par « ; » ou « } » (ligne vide pour valider).
Écrivez « sinon » sur la même ligne que le « } » qui le précède.

Commandes :
  :aide      affiche cette aide
  :effacer   oublie toutes les variables et les missions
  :quitter   quitte le REPL (ou Ctrl-D, ou Ctrl-Z puis Entrée sous Windows)"""


def _delimiteurs_ouverts(lus: list[Token]) -> int:
    """Le nombre d'accolades et de parenthèses ouvertes, moins celles fermées."""
    ouvertes = sum(token.type in (T.ACC_OUVRANTE, T.PAR_OUVRANTE) for token in lus)
    fermees = sum(token.type in (T.ACC_FERMANTE, T.PAR_FERMANTE) for token in lus)
    return ouvertes - fermees


def _attend_la_suite(source: str, ligne_vide: bool) -> bool:
    """L'entrée doit-elle continuer sur la ligne suivante ?

    Une erreur lexicale est définitive : aucune suite ne la corrigerait.
    """
    try:
        lus = [token for token in tokens(source) if token.type is not T.FIN]
    except ErreurCosmo:
        return False
    if not lus:
        return False
    ouverts = _delimiteurs_ouverts(lus)
    if ouverts != 0:
        return ouverts > 0
    if ligne_vide or lus[-1].type in (T.POINT_VIRGULE, T.ACC_FERMANTE):
        return False
    return lire_expression(source) is None


def _soumettre(session: Session, source: str) -> None:
    """Exécute une entrée complète. Aucune erreur n'interrompt le REPL."""
    try:
        session.executer(source)
    except ErreursCompilation as erreurs:
        print(erreurs, file=sys.stderr)
    except KeyboardInterrupt:
        print("exécution interrompue", file=sys.stderr)
    except Exception as erreur:  # noqa: BLE001 : un programme peut lever n'importe quoi
        print(decrire_erreur_execution(erreur), file=sys.stderr)


def boucle_repl() -> Generator[str, str, None]:
    """Produit l'invite, reçoit une ligne par `send`, et ainsi de suite jusqu'à `:quitter`.

    Lever KeyboardInterrupt dans le générateur (`throw`) abandonne l'entrée en cours.
    """
    session = Session()
    lignes: list[str] = []
    while True:
        try:
            ligne = yield INVITE_SUITE if lignes else INVITE
        except KeyboardInterrupt:
            lignes.clear()
            continue

        if not lignes:
            commande = ligne.strip()
            if not commande:
                continue
            if commande.startswith(":"):
                match commande:
                    case ":quitter":
                        return
                    case ":effacer":
                        session = Session()
                    case ":aide":
                        print(AIDE)
                    case _:
                        print(f"commande inconnue « {commande} » : voir :aide", file=sys.stderr)
                continue

        lignes.append(ligne)
        source = "\n".join(lignes)
        if not _attend_la_suite(source, ligne_vide=not ligne.strip()):
            lignes.clear()
            _soumettre(session, source)


def lancer_repl(lire: Callable[[str], str] = input) -> None:
    """Fait tourner le REPL jusqu'à `:quitter` ou la fin de l'entrée standard."""
    print(BANNIERE)
    boucle = boucle_repl()
    invite = next(boucle)
    try:
        while True:
            try:
                ligne = lire(invite)
            except KeyboardInterrupt:
                print()
                invite = boucle.throw(KeyboardInterrupt())
                continue
            except EOFError:
                print()
                return
            invite = boucle.send(ligne)
    except StopIteration:  # le générateur s'est terminé : :quitter
        return
