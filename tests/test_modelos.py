"""Testes unitários para os modelos de dados e validações."""

import pytest

from votacao.modelos import (
    AptidaoVoto,
    ElegibilidadeCandidato,
    ResultadoApuracao,
    StatusResultado,
    Usuario,
    Voto,
)


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


def test_usuario_criacao_valida():
    user = Usuario(id="247314", nome="Lucas Bussinger", email="lucas@unicamp.br")
    assert user.id == "247314"
    assert user.nome == "Lucas Bussinger"
    assert user.email == "lucas@unicamp.br"
    assert user.ativo is True


def test_usuario_invalido():
    with pytest.raises(ValueError, match="identificador do usuário não pode ser vazio"):
        Usuario(id="   ", nome="Lucas")

    with pytest.raises(ValueError, match="nome do usuário não pode ser vazio"):
        Usuario(id="247314", nome="  ")


def test_aptidao_voto_criacao():
    aptidao = AptidaoVoto(apto=True, peso_voto=5, dados_eleitor={"tipo": "acionista"})
    assert aptidao.apto is True
    assert aptidao.peso_voto == 5
    assert aptidao.motivo_inaptidao is None
    assert aptidao.dados_eleitor["tipo"] == "acionista"


def test_aptidao_voto_peso_negativo():
    with pytest.raises(ValueError, match="peso do voto não pode ser negativo"):
        AptidaoVoto(apto=False, peso_voto=-1)


def test_elegibilidade_candidato_criacao():
    eleg = ElegibilidadeCandidato(
        elegivel=False,
        motivo_inelegibilidade="Membro formando no próximo semestre.",
        detalhes={"membro": "RA 123456"},
    )
    assert eleg.elegivel is False
    assert eleg.motivo_inelegibilidade == "Membro formando no próximo semestre."
    assert eleg.detalhes["membro"] == "RA 123456"
