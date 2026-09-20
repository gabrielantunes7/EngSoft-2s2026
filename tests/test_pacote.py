"""Testes de fumaça do pacote.

Garantem que a distribuição instalada é importável e expõe seus metadados.
Os testes de comportamento de cada contexto de votação (CA, assembleia e
congresso) são desenvolvidos junto das funcionalidades correspondentes.
"""

import votacao


def test_pacote_expoe_versao_semantica():
    partes = votacao.__version__.split(".")

    assert len(partes) == 3, "a versão deve seguir o formato maior.menor.correcao"
    assert all(parte.isdigit() for parte in partes)


def test_pacote_expoe_simbolos_principais():
    simbolos_esperados = [
        "AptidaoVoto",
        "BancoDadosMock",
        "BancoDadosSQL",
        "CasaLegislativa",
        "ElegibilidadeCandidato",
        "EstadoSessao",
        "HASH_GENESE",
        "LogDeAuditoria",
        "MotorApuracao",
        "RegistroAuditoria",
        "RegistroTramitacao",
        "RegraAssembleia",
        "RegraCA",
        "RegraCongresso",
        "RegraDeVotacao",
        "ResultadoApuracao",
        "ResultadoVerificacao",
        "ServicoElegibilidade",
        "SessaoVotacao",
        "StatusResultado",
        "StatusTramitacao",
        "TipoDecisaoAssembleia",
        "TipoEvento",
        "TipoMateriaCongresso",
        "TramitacaoInvalidaError",
        "TramitacaoLegislativa",
        "TransicaoInvalidaError",
        "Usuario",
        "ValidadorElegibilidadeAssembleia",
        "ValidadorElegibilidadeCA",
        "ValidadorElegibilidadeCongresso",
        "Voto",
        "VotoRecusadoError",
        "__version__",
    ]
    for simbolo in simbolos_esperados:
        assert hasattr(votacao, simbolo), f"Símbolo '{simbolo}' não encontrado em votacao."
    assert set(votacao.__all__) == set(simbolos_esperados)
