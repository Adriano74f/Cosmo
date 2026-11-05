"""Étape 9 : le REPL, et la session qui garde l'état d'une entrée à l'autre."""

from collections.abc import Callable, Iterable, Iterator

import pytest

from cosmo.compilateur import Session
from cosmo.erreurs import ErreursCompilation
from cosmo.repl import AIDE, BANNIERE, INVITE, INVITE_SUITE, boucle_repl, lancer_repl

type Capture = pytest.CaptureFixture[str]


def sortie_de(capsys: Capture, session: Session, source: str) -> str:
    session.executer(source)
    return capsys.readouterr().out


def dialogue(*lignes: str) -> list[str]:
    """Envoie les lignes au générateur, et renvoie l'invite produite après chacune."""
    boucle = boucle_repl()
    next(boucle)
    return [boucle.send(ligne) for ligne in lignes]


# --- Session : l'état partagé entre les entrées ----------------------------------


def test_une_variable_survit_d_une_entree_a_l_autre(capsys: Capture) -> None:
    session = Session()
    session.executer("module x = 1;")
    assert sortie_de(capsys, session, "transmets x;") == "1\n"


def test_une_reaffectation_survit_d_une_entree_a_l_autre(capsys: Capture) -> None:
    session = Session()
    session.executer("module x = 1;")
    session.executer("x = x + 1;")
    assert sortie_de(capsys, session, "transmets x;") == "2\n"


def test_une_mission_survit_d_une_entree_a_l_autre(capsys: Capture) -> None:
    session = Session()
    session.executer("mission double(n) { atterris n * 2; }")
    assert sortie_de(capsys, session, "transmets double(21);") == "42\n"


def test_les_entrees_precedentes_ne_sont_pas_rejouees(capsys: Capture) -> None:
    session = Session()
    session.executer('transmets "une fois";')
    capsys.readouterr()
    assert sortie_de(capsys, session, "transmets 2;") == "2\n"


def test_deux_sessions_sont_independantes() -> None:
    premiere = Session()
    premiere.executer("module x = 1;")
    with pytest.raises(ErreursCompilation, match="« x » non déclarée"):
        Session().executer("transmets x;")


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("1 + 2", "3\n"),
        ("go", "go\n"),
        ('"Ada"', "Ada\n"),
        ("non go", "nogo\n"),
    ],
)
def test_une_expression_seule_affiche_sa_valeur(
    source: str, attendu: str, capsys: Capture
) -> None:
    assert sortie_de(capsys, Session(), source) == attendu


def test_une_mission_sans_valeur_affiche_rien_comme_transmets(capsys: Capture) -> None:
    session = Session()
    session.executer("mission f() { }")
    assert sortie_de(capsys, session, "f()") == "rien\n"


def test_un_appel_termine_par_un_point_virgule_n_affiche_pas_sa_valeur(capsys: Capture) -> None:
    session = Session()
    session.executer("mission f() { atterris 1; }")
    assert sortie_de(capsys, session, "f();") == ""


def test_une_expression_est_verifiee_comme_le_reste() -> None:
    with pytest.raises(ErreursCompilation, match="« y » non déclarée"):
        Session().executer("y + 1")


@pytest.mark.parametrize(
    ("entree", "message"),
    [
        ("module x = 2;", "déjà déclarée"),
        ("mission x() { }", "déjà le nom d'une variable"),
        ("detecte go { module x = 2; }", "masquerait"),
    ],
)
def test_les_regles_de_portee_valent_d_une_entree_a_l_autre(entree: str, message: str) -> None:
    session = Session()
    session.executer("module x = 1;")
    with pytest.raises(ErreursCompilation, match=message):
        session.executer(entree)


def test_une_mission_ne_voit_pas_les_variables_des_entrees_precedentes() -> None:
    session = Session()
    session.executer("module x = 1;")
    with pytest.raises(ErreursCompilation, match="« x » non déclarée"):
        session.executer("mission f() { atterris x; }")


def test_une_variable_de_bloc_disparait_a_la_fin_de_l_entree() -> None:
    session = Session()
    session.executer("detecte go { module x = 1; }")
    with pytest.raises(ErreursCompilation, match="« x » non déclarée"):
        session.executer("transmets x;")


# --- Session : une entrée qui échoue ne laisse pas de trace ------------------------


def test_une_entree_refusee_n_a_rien_declare(capsys: Capture) -> None:
    session = Session()
    with pytest.raises(ErreursCompilation):
        session.executer("module x = 1; transmets y;")
    session.executer("module x = 2;")  # pas de « déjà déclarée »
    assert sortie_de(capsys, session, "x") == "2\n"


def test_une_mission_refusee_n_a_rien_declare(capsys: Capture) -> None:
    session = Session()
    with pytest.raises(ErreursCompilation):
        session.executer("mission f() { atterris y; }")
    session.executer("mission f() { atterris 1; }")
    assert sortie_de(capsys, session, "f()") == "1\n"


def test_une_entree_refusee_n_a_rien_execute(capsys: Capture) -> None:
    with pytest.raises(ErreursCompilation):
        Session().executer("transmets 1; transmets y;")
    assert capsys.readouterr().out == ""


def test_une_variable_dont_la_valeur_a_echoue_n_est_pas_declaree() -> None:
    session = Session()
    with pytest.raises(ZeroDivisionError):
        session.executer("module x = 1 / 0;")
    with pytest.raises(ErreursCompilation, match="« x » non déclarée"):
        session.executer("transmets x;")


def test_ce_qui_precede_une_erreur_d_execution_est_conserve(capsys: Capture) -> None:
    session = Session()
    with pytest.raises(ZeroDivisionError):
        session.executer("module a = 1; module b = 1 / 0; module c = 3;")
    assert sortie_de(capsys, session, "a") == "1\n"
    for nom in "bc":
        with pytest.raises(ErreursCompilation, match="non déclarée"):
            session.executer(nom)


def test_une_valeur_de_bloc_perimee_ne_ressuscite_pas_apres_un_echec() -> None:
    session = Session()
    session.executer("detecte go { module x = 1; }")
    with pytest.raises(ZeroDivisionError):
        session.executer("module x = 1 / 0;")
    with pytest.raises(ErreursCompilation, match="« x » non déclarée"):
        session.executer("transmets x;")


def test_une_reaffectation_qui_echoue_garde_l_ancienne_valeur(capsys: Capture) -> None:
    session = Session()
    session.executer("module x = 1;")
    with pytest.raises(ZeroDivisionError):
        session.executer("x = 1 / 0;")
    assert sortie_de(capsys, session, "x") == "1\n"


def test_une_entree_trop_imbriquee_pour_python_n_a_rien_declare(capsys: Capture) -> None:
    session = Session()
    boucles = "".join(f"survole i{n} dans 0..1 {{ " for n in range(25)) + "}" * 25
    with pytest.raises(ErreursCompilation, match="erreur de génération"):
        session.executer(f"mission f() {{ {boucles} }} module x = 1;")
    session.executer("module x = 2;")
    session.executer("mission f() { atterris 1; }")
    assert sortie_de(capsys, session, "f() + x") == "3\n"


# --- Le générateur : invites et entrées sur plusieurs lignes -----------------------


def test_le_generateur_produit_d_abord_l_invite() -> None:
    assert next(boucle_repl()) == INVITE


@pytest.mark.parametrize(
    "ligne",
    [
        "module x = 1;",
        "1 + 2",
        "mission f() { }",
        "detecte go { }",
        "@",
        '"pas fini',
        ")",
        "}",
        "   ",
        "# un commentaire",
        "",
    ],
)
def test_une_entree_complete_redonne_l_invite_principale(ligne: str) -> None:
    assert dialogue(ligne) == [INVITE]


@pytest.mark.parametrize(
    "ligne",
    [
        "mission f() {",
        "detecte go {",
        "transmets (1 +",
        "module x = 1",
        "module x = 1 +",
        "transmets 1",
        "detecte go",
        "detecte go { } sinon",
        "module",
    ],
)
def test_une_entree_inachevee_demande_la_suite(ligne: str) -> None:
    assert dialogue(ligne) == [INVITE_SUITE]


def test_une_mission_sur_plusieurs_lignes_est_executee_une_fois_fermee(capsys: Capture) -> None:
    invites = dialogue("mission f(n) {", "  atterris n + 1;", "}", "f(1)")
    assert invites == [INVITE_SUITE, INVITE_SUITE, INVITE, INVITE]
    assert capsys.readouterr().out == "2\n"


def test_une_instruction_peut_continuer_sur_la_ligne_suivante(capsys: Capture) -> None:
    assert dialogue("transmets 1 +", "2;") == [INVITE_SUITE, INVITE]
    assert capsys.readouterr().out == "3\n"


def test_une_ligne_vide_valide_une_instruction_sans_point_virgule(capsys: Capture) -> None:
    assert dialogue("module x = 1", "") == [INVITE_SUITE, INVITE]
    assert capsys.readouterr().err == "[1:13] erreur syntaxique : « ; » attendu\n"


def test_une_ligne_vide_n_interrompt_pas_un_bloc_ouvert(capsys: Capture) -> None:
    assert dialogue("detecte go {", "", "transmets 1;", "}") == [
        INVITE_SUITE,
        INVITE_SUITE,
        INVITE_SUITE,
        INVITE,
    ]
    capture = capsys.readouterr()
    assert (capture.out, capture.err) == ("1\n", "")


def test_les_positions_d_une_entree_sur_plusieurs_lignes_sont_les_siennes(capsys: Capture) -> None:
    dialogue("detecte go {", "transmets y;", "}")
    assert capsys.readouterr().err == "[2:11] erreur sémantique : variable « y » non déclarée\n"


def test_keyboard_interrupt_abandonne_l_entree_en_cours(capsys: Capture) -> None:
    boucle = boucle_repl()
    next(boucle)
    assert boucle.send("detecte go {") == INVITE_SUITE
    assert boucle.throw(KeyboardInterrupt()) == INVITE
    assert boucle.send("1") == INVITE
    capture = capsys.readouterr()
    assert (capture.out, capture.err) == ("1\n", "")


# --- Le générateur : aucune erreur n'arrête la session -----------------------------


@pytest.mark.parametrize(
    ("ligne", "message"),
    [
        ("@", "[1:1] erreur lexicale : caractère inattendu « @ »\n"),
        ("1 + ;", "[1:1] erreur syntaxique : instruction attendue\n"),
        ("y", "[1:1] erreur sémantique : variable « y » non déclarée\n"),
        ("1 / 0", "erreur d'exécution : division par zéro\n"),
    ],
)
def test_une_erreur_est_signalee_et_la_session_continue(
    ligne: str, message: str, capsys: Capture
) -> None:
    invites = dialogue("module x = 1;", ligne, "x")
    assert invites[-2:] == [INVITE, INVITE]
    capture = capsys.readouterr()
    assert capture.err == message
    assert capture.out == "1\n"


def test_une_recursion_infinie_ne_termine_pas_la_session(capsys: Capture) -> None:
    dialogue("mission f() { atterris f(); }", "f()", "1")
    capture = capsys.readouterr()
    assert "trop d'appels" in capture.err
    assert capture.out == "1\n"


def test_ctrl_c_interrompt_le_programme_mais_pas_la_session(
    monkeypatch: pytest.MonkeyPatch, capsys: Capture
) -> None:
    executer = Session.executer

    def interrompre(session: Session, source: str) -> None:
        if source == "boucle":
            raise KeyboardInterrupt
        executer(session, source)

    monkeypatch.setattr(Session, "executer", interrompre)
    assert dialogue("boucle", "1") == [INVITE, INVITE]
    capture = capsys.readouterr()
    assert capture.err == "exécution interrompue\n"
    assert capture.out == "1\n"


def test_ctrl_c_pendant_l_execution_conserve_ce_qui_precede(capsys: Capture) -> None:
    session = Session()

    def interrompre() -> None:
        raise KeyboardInterrupt

    # Un programme Cosmo ne peut pas appeler de fonction Python : on en glisse une dans l'espace.
    session.executer("mission attendre() { }")
    session._espace["c_attendre"] = interrompre
    with pytest.raises(KeyboardInterrupt):
        session.executer("module a = 1; attendre(); module b = 2;")
    assert sortie_de(capsys, session, "a") == "1\n"
    with pytest.raises(ErreursCompilation, match="« b » non déclarée"):
        session.executer("b")


# --- Les commandes -----------------------------------------------------------------


def test_aide_affiche_l_aide(capsys: Capture) -> None:
    assert dialogue(":aide") == [INVITE]
    assert capsys.readouterr().out == AIDE + "\n"


def test_effacer_oublie_les_variables_et_les_missions(capsys: Capture) -> None:
    dialogue("module x = 1;", "mission f() { }", ":effacer", "module x = 2;", "mission f() { }")
    assert capsys.readouterr().err == ""


def test_effacer_oublie_vraiment_les_valeurs(capsys: Capture) -> None:
    dialogue("module x = 1;", ":effacer", "x")
    assert "« x » non déclarée" in capsys.readouterr().err


def test_commande_inconnue_est_signalee(capsys: Capture) -> None:
    assert dialogue(":nimportequoi") == [INVITE]
    assert capsys.readouterr().err == "commande inconnue « :nimportequoi » : voir :aide\n"


def test_quitter_termine_le_generateur() -> None:
    boucle = boucle_repl()
    next(boucle)
    with pytest.raises(StopIteration):
        boucle.send(":quitter")


def test_une_commande_tolere_les_espaces_autour() -> None:
    boucle = boucle_repl()
    next(boucle)
    with pytest.raises(StopIteration):
        boucle.send("  :quitter  ")


def test_au_milieu_d_une_entree_les_deux_points_ne_sont_pas_une_commande(capsys: Capture) -> None:
    assert dialogue("detecte go {", ":quitter", "}") == [INVITE_SUITE, INVITE, INVITE]
    assert "caractère inattendu « : »" in capsys.readouterr().err


# --- lancer_repl : la lecture des lignes ---------------------------------------------


def lecteur(lignes: Iterable[str | BaseException]) -> Callable[[str], str]:
    """Remplace `input` : renvoie les lignes une à une, ou lève les exceptions de la liste."""
    suite: Iterator[str | BaseException] = iter(lignes)

    def lire(_invite: str) -> str:
        ligne = next(suite)
        if isinstance(ligne, BaseException):
            raise ligne
        return ligne

    return lire


def test_lancer_repl_affiche_la_banniere_et_s_arrete_sur_quitter(capsys: Capture) -> None:
    lancer_repl(lecteur([":quitter"]))
    assert capsys.readouterr().out == BANNIERE + "\n"


def test_lancer_repl_passe_l_invite_courante_a_la_lecture() -> None:
    invites: list[str] = []
    lignes = iter(["detecte go {", "}", ":quitter"])

    def lire(invite: str) -> str:
        invites.append(invite)
        return next(lignes)

    lancer_repl(lire)
    assert invites == [INVITE, INVITE_SUITE, INVITE]


def test_lancer_repl_s_arrete_a_la_fin_de_l_entree(capsys: Capture) -> None:
    lancer_repl(lecteur(["1", EOFError()]))
    assert capsys.readouterr().out == f"{BANNIERE}\n1\n\n"


def test_lancer_repl_survit_a_ctrl_c_pendant_la_saisie(capsys: Capture) -> None:
    lancer_repl(lecteur(["detecte go {", KeyboardInterrupt(), "1", ":quitter"]))
    assert capsys.readouterr().out == f"{BANNIERE}\n\n1\n"


def test_sinon_sur_une_nouvelle_ligne_est_refuse_car_le_bloc_est_deja_execute(
    capsys: Capture,
) -> None:
    assert dialogue("detecte go {", "}", "sinon { }") == [INVITE_SUITE, INVITE, INVITE]
    assert capsys.readouterr().err == "[1:1] erreur syntaxique : instruction attendue\n"


def test_sinon_sur_la_ligne_du_bloc_ferme_continue_l_entree(capsys: Capture) -> None:
    invites = dialogue("detecte nogo {", "} sinon {", "transmets 2;", "}")
    assert invites == [INVITE_SUITE, INVITE_SUITE, INVITE_SUITE, INVITE]
    assert capsys.readouterr().out == "2\n"
