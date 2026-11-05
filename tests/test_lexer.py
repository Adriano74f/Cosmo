"""Étape 3 : le lexer et le flux de tokens."""

from pathlib import Path

import pytest

from cosmo.erreurs import ErreurLexicale
from cosmo.lexer import FluxTokens, analyser
from cosmo.tokens import Position
from cosmo.tokens import TypeToken as T

RACINE = Path(__file__).parent.parent


def types(source: str) -> list[T]:
    """Les types des tokens de `source`, sans le FIN final."""
    return [token.type for token in analyser(source)][:-1]


# --- Découpage ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("module x = 5;", [T.MODULE, T.IDENT, T.EGAL, T.ENTIER, T.POINT_VIRGULE]),
        ("a <= b", [T.IDENT, T.INFERIEUR_EGAL, T.IDENT]),
        ("a < = b", [T.IDENT, T.INFERIEUR, T.EGAL, T.IDENT]),
        ("a == b", [T.IDENT, T.EGAL_EGAL, T.IDENT]),
        ("a != b", [T.IDENT, T.DIFFERENT, T.IDENT]),
        ("0..10", [T.ENTIER, T.POINT_POINT, T.ENTIER]),
        ("-7", [T.MOINS, T.ENTIER]),
        ("f(a, b)", [T.IDENT, T.PAR_OUVRANTE, T.IDENT, T.VIRGULE, T.IDENT, T.PAR_FERMANTE]),
        ("{ }", [T.ACC_OUVRANTE, T.ACC_FERMANTE]),
        ("+ - * / %", [T.PLUS, T.MOINS, T.FOIS, T.DIVISE, T.MODULO]),
        ("non go et nogo ou go", [T.NON, T.GO, T.ET, T.NOGO, T.OU, T.GO]),
    ],
)
def test_decoupage_en_tokens(source: str, attendu: list[T]) -> None:
    assert types(source) == attendu


@pytest.mark.parametrize("mot", ["modules", "Module", "orbite2", "_go", "nogo_"])
def test_un_mot_qui_ressemble_a_un_mot_cle_est_un_identifiant(mot: str) -> None:
    assert types(mot) == [T.IDENT]


def test_un_entier_porte_sa_valeur() -> None:
    token = next(analyser("1965"))
    assert token.valeur == 1965


def test_les_espaces_et_commentaires_sont_ignores() -> None:
    source = "# un commentaire\n  x   # un autre\n\t;"
    assert types(source) == [T.IDENT, T.POINT_VIRGULE]


def test_un_texte_vide_ne_contient_que_fin() -> None:
    assert [token.type for token in analyser("")] == [T.FIN]


def test_le_dernier_token_est_toujours_fin() -> None:
    assert list(analyser("x;"))[-1].type is T.FIN


# --- Chaînes -----------------------------------------------------------------


def test_une_chaine_garde_son_texte_et_sa_valeur() -> None:
    token = next(analyser('"Ada"'))
    assert token.type is T.CHAINE
    assert token.texte == '"Ada"'
    assert token.valeur == "Ada"


def test_une_chaine_peut_contenir_des_accents_et_des_mots_cles() -> None:
    assert next(analyser('"détecte module"')).valeur == "détecte module"


@pytest.mark.parametrize(
    ("source", "valeur"),
    [(r'"a\"b"', 'a"b'), (r'"a\\b"', "a\\b"), (r'"a\nb"', "a\nb")],
)
def test_les_echappements_sont_traduits(source: str, valeur: str) -> None:
    assert next(analyser(source)).valeur == valeur


# --- Positions ---------------------------------------------------------------


def test_les_positions_commencent_a_un() -> None:
    assert next(analyser("x")).position == Position(1, 1)


def test_les_positions_suivent_lignes_et_colonnes() -> None:
    source = "module x = 5;\n  transmets x;"
    positions = [(t.texte, t.position) for t in analyser(source)]
    assert positions[0] == ("module", Position(1, 1))
    assert positions[3] == ("5", Position(1, 12))
    assert positions[5] == ("transmets", Position(2, 3))
    assert positions[6] == ("x", Position(2, 13))


def test_la_position_de_fin_est_apres_le_dernier_caractere() -> None:
    assert list(analyser("ab\ncd"))[-1].position == Position(2, 3)


# --- Erreurs -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("x = @;", "[1:5] erreur lexicale : caractère inattendu « @ »"),
        ("x\n  é", "[2:3] erreur lexicale : caractère inattendu « é »"),
        ('transmets "bonjour;', "[1:11] erreur lexicale : chaîne non terminée"),
        ('"ab\ncd"', "[1:1] erreur lexicale : chaîne non terminée"),
        (r'x = "a\tb";', "[1:7] erreur lexicale : échappement inconnu « \\t »"),
        ("a ! b", "[1:3] erreur lexicale : caractère inattendu « ! »"),
        ("1.5", "[1:2] erreur lexicale : caractère inattendu « . »"),
    ],
)
def test_les_erreurs_lexicales_indiquent_leur_position(source: str, message: str) -> None:
    with pytest.raises(ErreurLexicale) as erreur:
        list(analyser(source))
    assert str(erreur.value) == message


def test_un_entier_trop_grand_devient_une_erreur_lexicale() -> None:
    with pytest.raises(ErreurLexicale) as erreur:
        list(analyser("x = " + "9" * 5000))
    assert str(erreur.value) == "[1:5] erreur lexicale : entier trop grand"
    assert isinstance(erreur.value.__cause__, ValueError)


def test_le_lexer_est_paresseux() -> None:
    """Les tokens avant l'erreur sont produits : l'erreur n'arrive qu'en l'atteignant."""
    tokens = analyser("x = @")
    assert next(tokens).texte == "x"
    assert next(tokens).texte == "="
    with pytest.raises(ErreurLexicale):
        next(tokens)


# --- Programmes du projet ----------------------------------------------------


@pytest.mark.parametrize(
    "fichier", sorted((RACINE / "exemples").glob("*.cosmo")), ids=lambda p: p.stem
)
def test_les_programmes_d_exemple_n_ont_pas_d_erreur_lexicale(fichier: Path) -> None:
    tokens = list(analyser(fichier.read_text(encoding="utf-8")))
    assert tokens[-1].type is T.FIN


def test_le_programme_d_erreur_lexicale_produit_le_message_attendu() -> None:
    dossier = RACINE / "erreurs"
    source = (dossier / "01_chaine_non_terminee.cosmo").read_text(encoding="utf-8")
    attendu = (dossier / "01_chaine_non_terminee.attendu").read_text(encoding="utf-8").strip()
    with pytest.raises(ErreurLexicale) as erreur:
        list(analyser(source))
    assert str(erreur.value) == attendu


# --- Flux avec regard en avant -----------------------------------------------


def test_regarder_ne_consomme_pas() -> None:
    flux = FluxTokens(analyser("x = 1;"))
    assert flux.regarder().texte == "x"
    assert flux.regarder().texte == "x"


def test_regarder_plus_loin() -> None:
    flux = FluxTokens(analyser("f(1);"))
    assert flux.regarder(1).type is T.PAR_OUVRANTE
    assert flux.avancer().texte == "f"


def test_avancer_consomme_dans_l_ordre() -> None:
    flux = FluxTokens(analyser("a b"))
    assert [flux.avancer().texte, flux.avancer().texte] == ["a", "b"]
    assert flux.avancer().type is T.FIN


def test_apres_la_fin_le_flux_renvoie_toujours_fin() -> None:
    flux = FluxTokens(analyser("x"))
    flux.avancer()
    assert flux.avancer().type is T.FIN
    assert flux.avancer().type is T.FIN
    assert flux.regarder(5).type is T.FIN


def test_est_et_accepter() -> None:
    flux = FluxTokens(analyser("x = 1"))
    assert flux.est(T.IDENT)
    assert flux.est(T.ENTIER, T.IDENT)
    assert flux.accepter(T.EGAL) is None  # le courant est x : rien n'est consommé
    assert flux.accepter(T.IDENT) is not None
    assert flux.accepter(T.EGAL) is not None
    assert flux.est(T.ENTIER)


def test_precedent_est_le_dernier_token_consomme() -> None:
    flux = FluxTokens(analyser("a b"))
    assert flux.precedent is None
    flux.regarder(1)  # regarder ne consomme pas
    assert flux.precedent is None
    flux.avancer()
    flux.accepter(T.IDENT)
    assert flux.precedent is not None
    assert flux.precedent.texte == "b"


def test_le_flux_lit_le_lexer_a_la_demande() -> None:
    """Regarder le premier token ne déclenche pas l'erreur située plus loin."""
    flux = FluxTokens(analyser("x @"))
    assert flux.regarder().texte == "x"
    with pytest.raises(ErreurLexicale):
        flux.regarder(1)
