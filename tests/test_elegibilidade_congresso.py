"""Testes unitários de elegibilidade para o Congresso Nacional."""

from votacao.dados.congresso import (
    MateriaLegislativa,
    Parlamentar,
    RepositorioCongresso,
)
from votacao.elegibilidade.validador_congresso import (
    ValidadorElegibilidadeCongresso,
)
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso


def test_elegibilidade_parlamentar_apto():
    repo = RepositorioCongresso()
    repo.adicionar_parlamentar(
        Parlamentar(
            id="DEP-1",
            nome="Deputada Maria",
            casa=CasaLegislativa.CAMARA,
            partido="PUNI",
            uf="SP",
            em_exercicio=True,
        )
    )

    aptidao = ValidadorElegibilidadeCongresso.validar_eleitor(
        parlamentar_id="DEP-1",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert aptidao.apto is True
    assert aptidao.peso_voto == 1
    assert aptidao.dados_eleitor["casa"] == "CAMARA"


def test_elegibilidade_parlamentar_inexistente():
    repo = RepositorioCongresso()
    aptidao = ValidadorElegibilidadeCongresso.validar_eleitor(
        parlamentar_id="DEP-FANTASMA",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert aptidao.apto is False
    assert "não encontrado" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_parlamentar_casa_divergente():
    repo = RepositorioCongresso()
    repo.adicionar_parlamentar(
        Parlamentar(
            id="DEP-1",
            nome="Deputada Maria",
            casa=CasaLegislativa.CAMARA,
            partido="PUNI",
            uf="SP",
        )
    )

    # Deputado tentando votar em sessão do Senado
    aptidao = ValidadorElegibilidadeCongresso.validar_eleitor(
        parlamentar_id="DEP-1",
        casa_votacao=CasaLegislativa.SENADO,
        repo=repo,
    )
    assert aptidao.apto is False
    assert "não possui competência para votar em deliberações do(a) SENADO" in (
        aptidao.motivo_inaptidao or ""
    )


def test_elegibilidade_parlamentar_licenciado():
    repo = RepositorioCongresso()
    repo.adicionar_parlamentar(
        Parlamentar(
            id="DEP-2",
            nome="Deputado Licenciado",
            casa=CasaLegislativa.CAMARA,
            partido="PUNI",
            uf="RJ",
            em_exercicio=False,
            licenciado=True,
        )
    )

    aptidao = ValidadorElegibilidadeCongresso.validar_eleitor(
        parlamentar_id="DEP-2",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert aptidao.apto is False
    assert "licenciado do mandato" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_parlamentar_suspenso():
    repo = RepositorioCongresso()
    repo.adicionar_parlamentar(
        Parlamentar(
            id="DEP-3",
            nome="Deputado Suspenso",
            casa=CasaLegislativa.CAMARA,
            partido="PENG",
            uf="MG",
            em_exercicio=False,
            suspenso=True,
        )
    )

    aptidao = ValidadorElegibilidadeCongresso.validar_eleitor(
        parlamentar_id="DEP-3",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert aptidao.apto is False
    assert "suspenso do exercício parlamentar" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_parlamentar_fora_de_exercicio():
    repo = RepositorioCongresso()
    repo.adicionar_parlamentar(
        Parlamentar(
            id="DEP-4",
            nome="Deputado Afastado",
            casa=CasaLegislativa.CAMARA,
            partido="PENG",
            uf="RS",
            em_exercicio=False,
            licenciado=False,
            suspenso=False,
        )
    )

    aptidao = ValidadorElegibilidadeCongresso.validar_eleitor(
        parlamentar_id="DEP-4",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert aptidao.apto is False
    assert "não está no exercício efetivo do mandato" in (aptidao.motivo_inaptidao or "")


def test_elegibilidade_materia_apta():
    repo = RepositorioCongresso()
    repo.adicionar_materia(
        MateriaLegislativa(
            id="PL-101/2026",
            tipo=TipoMateriaCongresso.LEI_ORDINARIA,
            casa_atual=CasaLegislativa.CAMARA,
            titulo="Incentivo à tecnologia.",
            ativa=True,
        )
    )

    eleg = ValidadorElegibilidadeCongresso.validar_materia(
        materia_id="PL-101/2026",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert eleg.elegivel is True
    assert eleg.detalhes["tipo"] == "LEI_ORDINARIA"


def test_elegibilidade_materia_inexistente():
    repo = RepositorioCongresso()
    eleg = ValidadorElegibilidadeCongresso.validar_materia(
        materia_id="PL-999",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert eleg.elegivel is False
    assert "não encontrada" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_materia_inativa():
    repo = RepositorioCongresso()
    repo.adicionar_materia(
        MateriaLegislativa(
            id="PL-ARQ",
            tipo=TipoMateriaCongresso.LEI_ORDINARIA,
            casa_atual=CasaLegislativa.CAMARA,
            ativa=False,
        )
    )

    eleg = ValidadorElegibilidadeCongresso.validar_materia(
        materia_id="PL-ARQ",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert eleg.elegivel is False
    assert "não se encontra pautada ou está arquivada" in (eleg.motivo_inelegibilidade or "")


def test_elegibilidade_materia_casa_divergente():
    repo = RepositorioCongresso()
    repo.adicionar_materia(
        MateriaLegislativa(
            id="PEC-1",
            tipo=TipoMateriaCongresso.PEC,
            casa_atual=CasaLegislativa.SENADO,
            ativa=True,
        )
    )

    eleg = ValidadorElegibilidadeCongresso.validar_materia(
        materia_id="PEC-1",
        casa_votacao=CasaLegislativa.CAMARA,
        repo=repo,
    )
    assert eleg.elegivel is False
    assert "tramitação na SENADO, não na CAMARA" in (eleg.motivo_inelegibilidade or "")
