"""Étape 5 : le parser des expressions (Pratt)."""

import pytest

import cosmo.parser as module_parser
from cosmo.erreurs import ErreurLexicale, ErreurSyntaxique
from cosmo.lexer import analyser
from cosmo.noeuds import (
    Appel,
    Binaire,
    Booleen,
    Chaine,
    Entier,
    Expression,
    OperateurBinaire,
    Unaire,
    Variable,
)
from cosmo.parser import (
    REGLES_INFIXES,
    REGLES_PREFIXES,
    Parser,
    Priorite,
    analyser_expression,
    infixe,
)
from cosmo.tokens import Position, Token
from cosmo.tokens import TypeToken as T

P = Position(1, 1)


def parentheser(expression: Expression) -> str:
    """Réécrit l'arbre avec toutes ses parenthèses : la structure se lit d'un coup d'œil."""
    match expression:
        case Entier(valeur):
            return str(valeur)
        case Chaine(valeur):
            return f'"{valeur}"'
        case Booleen(valeur):
            return "go" if valeur else "nogo"
        case Variable(nom):
            return nom
        case Unaire(operateur, operande):
            return f"({operateur.value} {parentheser(operande)})"
        case Binaire(operateur, gauche, droite):
            return f"({parentheser(gauche)} {operateur.value} {parentheser(droite)})"
        case Appel(nom, arguments):
            return f"{nom}({', '.join(parentheser(a) for a in arguments)})"


def structure(source: str) -> str:
    return parentheser(analyser_expression(source))


# --- Valeurs simples ---------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("42", Entier(42, position=P)),
        ('"Ada"', Chaine("Ada", position=P)),
        (r'"a\nb"', Chaine("a\nb", position=P)),
        ("go", Booleen(True, position=P)),
        ("nogo", Booleen(False, position=P)),
        ("altitude", Variable("altitude", position=P)),
        ("f()", Appel("f", (), position=P)),
        ("f(x)", Appel("f", (Variable("x", position=P),), position=P)),
    ],
)
def test_valeurs_simples(source: str, attendu: Expression) -> None:
    assert analyser_expression(source) == attendu


# --- Priorités et associativité ----------------------------------------------


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        # Les exemples de la spécification
        ("1 + 2 * 3", "(1 + (2 * 3))"),
        ("non a et b", "((non a) et b)"),
        ("10 - 3 - 2", "((10 - 3) - 2)"),
        # Chaque niveau face au suivant
        ("a ou b et c", "(a ou (b et c))"),
        ("a et b ou c", "((a et b) ou c)"),
        ("non a == b", "(non (a == b))"),
        ("a == b + c", "(a == (b + c))"),
        ("a + b == c", "((a + b) == c)"),
        ("a + b * c", "(a + (b * c))"),
        ("a * b + c", "((a * b) + c)"),
        ("-a * b", "((- a) * b)"),
        ("a * -b", "(a * (- b))"),
        ("-f(x)", "(- f(x))"),
        # Associativité à gauche
        ("a ou b ou c", "((a ou b) ou c)"),
        ("a et b et c", "((a et b) et c)"),
        ("a + b - c", "((a + b) - c)"),
        ("a * b / c % d", "(((a * b) / c) % d)"),
        # Tous les opérateurs de comparaison
        ("a == b", "(a == b)"),
        ("a != b", "(a != b)"),
        ("a < b", "(a < b)"),
        ("a <= b", "(a <= b)"),
        ("a > b", "(a > b)"),
        ("a >= b", "(a >= b)"),
        # Comparaisons reliées par la logique : ce n'est pas un enchaînement
        ("a < b et c < d", "((a < b) et (c < d))"),
        # Parenthèses
        ("(1 + 2) * 3", "((1 + 2) * 3)"),
        ("10 - (3 - 2)", "(10 - (3 - 2))"),
        ("((x))", "x"),
        ("(a < b) < c", "((a < b) < c)"),
        ("a < (b < c)", "(a < (b < c))"),
        # Opérateurs préfixes
        ("non non a", "(non (non a))"),
        ("- - a", "(- (- a))"),
        ("a et non b", "(a et (non b))"),
        ("a ou non b", "(a ou (non b))"),
        ("-(non a)", "(- (non a))"),
        ("1 + (non a)", "(1 + (non a))"),
        # Appels
        ("f(1, 2 + 3, g(4))", "f(1, (2 + 3), g(4))"),
        ("f(a) + g(b) * 2", "(f(a) + (g(b) * 2))"),
        # Lignes tirées des programmes d'exemple
        ("-7 / 2", "((- 7) / 2)"),
        ("non (3 < 5)", "(non (3 < 5))"),
        ("t % 2 == 0", "((t % 2) == 0)"),
        ("non go ou go", "((non go) ou go)"),
        ("carburant > 50 et moteurs_ok", "((carburant > 50) et moteurs_ok)"),
        ("fibo(n - 1) + fibo(n - 2)", "(fibo((n - 1)) + fibo((n - 2)))"),
        ('"Capitaine " + nom + " à bord"', '(("Capitaine " + nom) + " à bord")'),
    ],
)
def test_structure_de_l_arbre(source: str, attendu: str) -> None:
    assert structure(source) == attendu


def test_un_operateur_garde_sa_sorte() -> None:
    expression = analyser_expression("a % b")
    assert isinstance(expression, Binaire)
    assert expression.operateur is OperateurBinaire.MODULO


# --- Positions ---------------------------------------------------------------


def test_un_binaire_est_positionne_sur_son_operateur() -> None:
    assert analyser_expression("a +\n  b").position == Position(1, 3)


def test_un_unaire_est_positionne_sur_son_operateur() -> None:
    assert analyser_expression("  non a").position == Position(1, 3)


def test_un_appel_est_positionne_sur_son_nom() -> None:
    assert analyser_expression("\n  f(1)").position == Position(2, 3)


def test_des_parentheses_ne_comptent_pas_dans_la_position() -> None:
    assert analyser_expression("(x)").position == Position(1, 2)


def test_les_enfants_gardent_leur_propre_position() -> None:
    expression = analyser_expression("f(1,\n   y)")
    assert isinstance(expression, Appel)
    assert [a.position for a in expression.arguments] == [Position(1, 3), Position(2, 4)]


# --- Erreurs -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "ligne", "colonne", "message"),
    [
        # Il manque une expression : on signale le token qui gêne
        ("", 1, 1, "expression attendue"),
        ("1 +", 1, 4, "expression attendue"),
        ("1 + ;", 1, 5, "expression attendue"),
        ("* 2", 1, 1, "expression attendue"),
        ("module", 1, 1, "expression attendue"),
        ("()", 1, 2, "expression attendue"),
        ("f(1,)", 1, 5, "expression attendue"),
        ("f(,1)", 1, 3, "expression attendue"),
        # `non` n'est permis que là où la grammaire le prévoit
        ("1 + non a", 1, 5, "expression attendue"),
        ("2 * non a", 1, 5, "expression attendue"),
        ("a == non b", 1, 6, "expression attendue"),
        ("- non a", 1, 3, "expression attendue"),
        # Il manque un token : on signale juste après le précédent
        ("(1 + 2", 1, 7, "« ) » attendu"),
        ("(1 + 2\n\n;", 1, 7, "« ) » attendu"),
        ("f(1, 2", 1, 7, "« ) » attendu"),
        ("f(1 2)", 1, 4, "« ) » attendu"),
        ('("abc" 1', 1, 7, "« ) » attendu"),
        # Les comparaisons ne s'enchaînent pas
        ("a < b < c", 1, 7, "comparaisons enchaînées : ajoutez des parenthèses"),
        ("a == b != c", 1, 8, "comparaisons enchaînées : ajoutez des parenthèses"),
        ("a < b + 1 >= c", 1, 11, "comparaisons enchaînées : ajoutez des parenthèses"),
        # Du texte reste après l'expression
        ("1 2", 1, 3, "« 2 » inattendu après l'expression"),
        ("a = 1", 1, 3, "« = » inattendu après l'expression"),
        ("0..10", 1, 2, "« .. » inattendu après l'expression"),
        # Seul un nom peut être appelé
        ("5(1)", 1, 2, "« ( » inattendu après l'expression"),
        ("f(1)(2)", 1, 5, "« ( » inattendu après l'expression"),
        ("(f)(1)", 1, 4, "« ( » inattendu après l'expression"),
    ],
)
def test_erreur_syntaxique(source: str, ligne: int, colonne: int, message: str) -> None:
    with pytest.raises(ErreurSyntaxique) as erreur:
        analyser_expression(source)
    assert erreur.value.message == message
    assert erreur.value.position == Position(ligne, colonne)


def test_format_du_message_d_erreur() -> None:
    with pytest.raises(ErreurSyntaxique) as erreur:
        analyser_expression("1 +")
    assert str(erreur.value) == "[1:4] erreur syntaxique : expression attendue"


def test_une_erreur_lexicale_traverse_le_parser() -> None:
    with pytest.raises(ErreurLexicale) as erreur:
        analyser_expression("1 + @")
    assert erreur.value.position == Position(1, 5)


def test_attendre_sans_token_precedent_signale_le_token_courant() -> None:
    parser = Parser(analyser("  x"))
    with pytest.raises(ErreurSyntaxique) as erreur:
        parser.attendre(T.POINT_VIRGULE)
    assert erreur.value.position == Position(1, 3)


# --- Le parser dans une instruction ------------------------------------------


def test_l_expression_s_arrete_au_premier_token_qui_ne_la_continue_pas() -> None:
    """Le parser des instructions (étape 6) trouvera le `;` encore à lire."""
    parser = Parser(analyser("1 + 2; x"))
    assert parentheser(parser.expression()) == "(1 + 2)"
    assert parser.attendre(T.POINT_VIRGULE).texte == ";"
    assert parser.flux.regarder().texte == "x"


def test_le_minimum_arrete_les_operateurs_moins_prioritaires() -> None:
    parser = Parser(analyser("a * b + c"))
    assert parentheser(parser.expression(Priorite.PRODUIT)) == "(a * b)"
    assert parser.flux.est(T.PLUS)


# --- Les tables de règles ----------------------------------------------------


@pytest.mark.parametrize(
    ("types", "priorite"),
    [
        ((T.OU,), Priorite.OU),
        ((T.ET,), Priorite.ET),
        (
            (
                T.EGAL_EGAL,
                T.DIFFERENT,
                T.INFERIEUR,
                T.INFERIEUR_EGAL,
                T.SUPERIEUR,
                T.SUPERIEUR_EGAL,
            ),
            Priorite.COMPARAISON,
        ),
        ((T.PLUS, T.MOINS), Priorite.SOMME),
        ((T.FOIS, T.DIVISE, T.MODULO), Priorite.PRODUIT),
    ],
)
def test_priorite_des_operateurs_infixes(types: tuple[T, ...], priorite: Priorite) -> None:
    for type_token in types:
        assert REGLES_INFIXES[type_token].priorite is priorite


def test_tous_les_debuts_d_expression_ont_une_regle() -> None:
    assert set(REGLES_PREFIXES) == {
        T.ENTIER,
        T.CHAINE,
        T.GO,
        T.NOGO,
        T.IDENT,
        T.PAR_OUVRANTE,
        T.NON,
        T.MOINS,
    }


def test_ajouter_une_regle_etend_le_parser_sans_toucher_a_la_boucle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`..` devient temporairement un opérateur : seule la table change."""
    monkeypatch.setattr(module_parser, "REGLES_INFIXES", dict(REGLES_INFIXES))

    @infixe(T.POINT_POINT, priorite=Priorite.SOMME)
    def intervalle(
        parser: Parser, gauche: Expression, operateur: Token, priorite: Priorite
    ) -> Expression:
        return Appel("intervalle", (gauche, parser.expression(priorite + 1)), position=P)

    assert structure("1..2 * 3") == "intervalle(1, (2 * 3))"


def test_le_decorateur_renvoie_la_fonction_telle_quelle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module_parser, "REGLES_INFIXES", {})

    def regle(
        parser: Parser, gauche: Expression, operateur: Token, priorite: Priorite
    ) -> Expression:
        return gauche

    assert infixe(T.POINT_POINT, priorite=Priorite.SOMME)(regle) is regle
