"""Testes unitários para os modelos de dados e validações."""

import pytest

from votacao.modelos import ResultadoApuracao, StatusResultado, Voto


def test_voto_criacao_valida():
    voto = Voto(eleitor_id="aluno123", opcao="Chapa A", peso=1)
    assert voto.eleitor_id == "aluno123"
    assert voto.opcao == "Chapa A"
    assert voto.peso == 1


def test_voto_peso_invalido():
    with pytest.raises(ValueError, match="peso do voto deve ser um número inteiro positivo"):
        Voto(eleitor_id="aluno123", opcao="Chapa A", peso=0)

    with pytest.raises(ValueError, match="peso do voto deve ser um número inteiro positivo"):
        Voto(eleitor_id="aluno123", opcao="Chapa A", peso=-5)


def test_voto_eleitor_ou_opcao_vazia():
    with pytest.raises(ValueError, match="identificador do eleitor não pode ser vazio"):
        Voto(eleitor_id="   ", opcao="Chapa A")

    with pytest.raises(ValueError, match="opção de voto não pode ser vazia"):
        Voto(eleitor_id="aluno123", opcao="   ")


def test_resultado_apuracao_imutavel():
    res = ResultadoApuracao(
        status=StatusResultado.ELEITO,
        vencedor_ou_decisao="Chapa 1",
        quorum_atingido=True,
        total_votantes=10,
        total_peso_apurado=10,
    )
    assert res.status == StatusResultado.ELEITO
    assert res.vencedor_ou_decisao == "Chapa 1"
    assert res.quorum_atingido is True
