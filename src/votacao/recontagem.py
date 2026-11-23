"""Recontagem independente do resultado a partir do log de auditoria (história #29).

O resultado chegava ao log pronto, no RESULTADO_PROCLAMADO, e nada conferia se ele
correspondia aos votos registrados (D-AUD-05). Como no Belenios ("qualquer um pode
recontar") e no boletim de urna do TSE, o fiscal reapura a votação usando só o que o log
publica: as cédulas do encerramento (#28) e o total de aptos da abertura. Fica num
módulo próprio, e não em `auditoria.py`, para que a Auditoria continue sem depender das
regras de apuração (decisão 1.4.3 da Atividade 4).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from votacao.auditoria import LogDeAuditoria, RegistroAuditoria, ResumoEncerramento, TipoEvento
from votacao.modelos import ResultadoApuracao, Voto
from votacao.motor import MotorApuracao
from votacao.regras.base import RegraDeVotacao


class RecontagemRecusadaError(Exception):
    """A recontagem não pode ser feita sobre este log."""


@dataclass(frozen=True)
class Recontagem:
    """Resultado da recontagem e da comparação com o resultado proclamado.

    Attributes:
        resultado: Resultado calculado somente a partir do log.
        confere: True se coincide com o RESULTADO_PROCLAMADO, False se diverge, ou None
            se o log não tem resultado proclamado para comparar.
        opcoes_divergentes: Opções cuja contagem difere entre recontagem e proclamação,
            mapeadas para o par (recontado, proclamado).
        campos_divergentes: Demais campos do resultado que divergem (status, decisão,
            quórum, totais), mapeados para o par (recontado, proclamado).
    """

    resultado: ResultadoApuracao
    confere: bool | None
    opcoes_divergentes: dict[str, tuple[int, int]] = field(default_factory=dict)
    campos_divergentes: dict[str, tuple[Any, Any]] = field(default_factory=dict)


def recontar(
    log: LogDeAuditoria,
    regra: RegraDeVotacao,
    ancora: ResumoEncerramento | None = None,
) -> Recontagem:
    """Reapura a votação somente a partir do log e compara com o resultado proclamado.

    Args:
        log: Log de auditoria da votação, já encerrada.
        regra: Regra de votação do contexto (a mesma usada na sessão).
        ancora: Âncora guardada no encerramento (#27). Sem ela, a recontagem confia apenas
            na coerência interna da cadeia.

    Returns:
        O resultado recontado e o veredito da comparação com o RESULTADO_PROCLAMADO.

    Raises:
        RecontagemRecusadaError: Se a cadeia for reprovada na verificação de integridade
            (com ou sem âncora), ou se o log não tiver abertura ou encerramento com
            cédulas.
    """
    verificacao = log.verificar_integridade(ancora=ancora)
    if not verificacao.integro:
        msg = (
            "Recontagem recusada: a cadeia do log foi reprovada na verificação de "
            f"integridade ({verificacao.motivo}). Um log adulterado não serve de base."
        )
        raise RecontagemRecusadaError(msg)

    abertura = _primeiro(log, TipoEvento.VOTACAO_ABERTA)
    encerramento = _primeiro(log, TipoEvento.VOTACAO_ENCERRADA)
    if abertura is None or encerramento is None or "cedulas" not in encerramento.dados:
        msg = (
            "Recontagem recusada: o log precisa da abertura (total de aptos) e do "
            "encerramento com as cédulas."
        )
        raise RecontagemRecusadaError(msg)

    total_aptos = int(abertura.dados.get("total_aptos", 0) or 0)
    votos = [
        Voto(eleitor_id=f"cedula-{posicao}", opcao=str(opcao), peso=int(peso))
        for posicao, (opcao, peso) in enumerate(encerramento.dados["cedulas"], start=1)
    ]
    resultado = MotorApuracao.apurar(votos=votos, regra=regra, total_aptos_ou_capital=total_aptos)

    proclamado = _primeiro(log, TipoEvento.RESULTADO_PROCLAMADO)
    if proclamado is None:
        return Recontagem(resultado=resultado, confere=None)

    opcoes = _divergencias_de_contagem(
        resultado.contagem_por_opcao, proclamado.dados.get("contagem_por_opcao", {})
    )
    campos = _divergencias_de_campos(resultado, proclamado.dados)
    return Recontagem(
        resultado=resultado,
        confere=not opcoes and not campos,
        opcoes_divergentes=opcoes,
        campos_divergentes=campos,
    )


def _primeiro(log: LogDeAuditoria, evento: TipoEvento) -> RegistroAuditoria | None:
    return next((r for r in log.registros if r.evento == evento), None)


def _divergencias_de_contagem(
    recontada: Mapping[str, int], proclamada: Mapping[str, Any]
) -> dict[str, tuple[int, int]]:
    divergentes: dict[str, tuple[int, int]] = {}
    for opcao in sorted(set(recontada) | set(proclamada)):
        valor_recontado = int(recontada.get(opcao, 0))
        valor_proclamado = int(proclamada.get(opcao, 0))
        if valor_recontado != valor_proclamado:
            divergentes[opcao] = (valor_recontado, valor_proclamado)
    return divergentes


# Campos do RESULTADO_PROCLAMADO (gravados por SessaoVotacao.apurar) conferidos um a um.
_CAMPOS_COMPARADOS = (
    "status",
    "vencedor_ou_decisao",
    "quorum_atingido",
    "total_votantes",
    "total_peso_apurado",
)


def _divergencias_de_campos(
    resultado: ResultadoApuracao, proclamado: Mapping[str, Any]
) -> dict[str, tuple[Any, Any]]:
    recontado: dict[str, Any] = {
        "status": resultado.status.value,
        "vencedor_ou_decisao": resultado.vencedor_ou_decisao,
        "quorum_atingido": resultado.quorum_atingido,
        "total_votantes": resultado.total_votantes,
        "total_peso_apurado": resultado.total_peso_apurado,
    }
    return {
        campo: (recontado[campo], proclamado.get(campo))
        for campo in _CAMPOS_COMPARADOS
        if recontado[campo] != proclamado.get(campo)
    }
