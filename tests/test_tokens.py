"""Étape 2 : types de token et classe Token."""

import dataclasses

import pytest
from cosmo.tokens import MOTS_CLES, SYMBOLES, Position, Token, TypeToken


def test_un_mot_cle_retrouve_son_type_depuis_son_texte() -> None:
    assert TypeToken("orbite") is TypeToken.ORBITE
    assert MOTS_CLES["transmets"] is TypeToken.TRANSMETS


def test_un_symbole_retrouve_son_type_depuis_son_texte() -> None:
    assert TypeToken("<=") is TypeToken.INFERIEUR_EGAL
    assert SYMBOLES[".."] is TypeToken.POINT_POINT


def test_tous_les_mots_reserves_de_la_spec_sont_des_mots_cles() -> None:
    spec = "module mission atterris detecte sinon orbite survole dans transmets go nogo et ou non"
    assert set(MOTS_CLES) == set(spec.split())


def test_tous_les_symboles_de_la_spec_sont_connus() -> None:
    spec = "+ - * / % == != < <= > >= = ( ) { } , ; .."
    assert set(SYMBOLES) == set(spec.split())


def test_mots_cles_et_symboles_ne_se_chevauchent_pas() -> None:
    assert not set(MOTS_CLES.values()) & set(SYMBOLES.values())


def test_un_token_est_immuable() -> None:
    token = Token(TypeToken.ENTIER, "42", Position(1, 1), 42)
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.texte = "43"  # type: ignore[misc]


def test_deux_tokens_identiques_sont_egaux_et_hachables() -> None:
    a = Token(TypeToken.IDENT, "x", Position(2, 5))
    b = Token(TypeToken.IDENT, "x", Position(2, 5))
    assert a == b
    assert len({a, b}) == 1


def test_le_repr_d_un_token_est_compact() -> None:
    token = Token(TypeToken.ENTIER, "42", Position(3, 7), 42)
    assert repr(token) == "Token(ENTIER, '42', 3:7)"


def test_une_position_s_affiche_ligne_deux_points_colonne() -> None:
    assert str(Position(12, 4)) == "12:4"
