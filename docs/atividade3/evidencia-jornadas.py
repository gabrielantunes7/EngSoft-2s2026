"""Confronto das jornadas J1 e J2 com o comportamento atual do pacote.

Script de evidência da elicitação por cenários descrita em
`jornadas-sessao-tramitacao.md`, seção 6. Executar da raiz do repositório:

    PYTHONPATH=src python docs/atividade3/evidencia-jornadas.py

Cada bloco Exx corresponde a um desvio levantado no passo 3 de uma das jornadas.
"""

from datetime import UTC, datetime

from votacao.modelos import CasaLegislativa, TipoMateriaCongresso, Voto
from votacao.regras.congresso import RegraCongresso
from votacao.sessao import EstadoSessao, SessaoVotacao, TransicaoInvalidaError
from votacao.tramitacao import TramitacaoLegislativa

INSTANTE_FIXO = datetime(2026, 10, 4, 14, 0, tzinfo=UTC)


def relogio_fixo() -> datetime:
    """Relógio determinístico, para que os dois turnos caiam no mesmo instante."""
    return INSTANTE_FIXO


def vencer_etapa(tramitacao: TramitacaoLegislativa, votos_sim: int):
    """Convoca a sessão da etapa corrente, aprova por `votos_sim` votos e registra."""
    sessao = tramitacao.nova_sessao()
    etapa = (tramitacao.casa_atual.value, tramitacao.turno_atual)
    sessao.abrir()
    sessao.liberar_votacao()
    for numero in range(votos_sim):
        sessao.registrar_voto(Voto(eleitor_id=f"{etapa[0]}-{etapa[1]}-p{numero}", opcao="SIM"))
    sessao.encerrar_votacao()
    sessao.apurar()
    return etapa, tramitacao.registrar_resultado(sessao)


def e1_pec_aprovada_nas_duas_casas() -> None:
    """A PEC vence os dois turnos de cada Casa e o rito termina sem emenda nem promulgação."""
    print("E1 | J1 passo 3: PEC aprovada nas duas Casas")
    pec = TramitacaoLegislativa("PEC-50/2026", TipoMateriaCongresso.PEC, CasaLegislativa.CAMARA)
    for _ in range(4):
        etapa, status = vencer_etapa(pec, 410)
        print(f"     {etapa[0]:7} T{etapa[1]} -> {status.value}")
    print(f"     status final: {pec.status.value}")
    print("     nao ha etapa de emenda da revisora nem de promulgacao: o rito termina aqui.")
    print("     registrar_resultado so recebe a sessao:")
    print("     nao ha como informar 'aprovada com emenda'.")


def e2_irrepetibilidade() -> None:
    """Matéria rejeitada é reinstanciada no instante seguinte, sem recusa."""
    print("E2 | J1 passo 3: irrepetibilidade na mesma sessao legislativa")
    projeto = TramitacaoLegislativa("PL-1234/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    sessao = projeto.nova_sessao()
    sessao.abrir()
    sessao.liberar_votacao()
    for numero in range(300):
        sessao.registrar_voto(Voto(eleitor_id=f"rej{numero}", opcao="NAO"))
    sessao.encerrar_votacao()
    sessao.apurar()
    print(f"     1a tramitacao -> {projeto.registrar_resultado(sessao).value}")
    repetida = TramitacaoLegislativa("PL-1234/2026", TipoMateriaCongresso.LEI_ORDINARIA)
    print(f"     mesma materia reinstanciada -> {repetida.status.value}  (nenhuma recusa)")


def e3_intersticio_entre_turnos() -> None:
    """Os dois turnos da PEC são convocados no mesmo instante, sem interstício."""
    print("E3 | J1 passo 3: intersticio entre os dois turnos de PEC")
    pec = TramitacaoLegislativa("PEC-51/2026", TipoMateriaCongresso.PEC)
    primeiro = pec.nova_sessao(relogio=relogio_fixo)
    primeiro.abrir()
    primeiro.liberar_votacao()
    for numero in range(410):
        primeiro.registrar_voto(Voto(eleitor_id=f"t1-{numero}", opcao="SIM"))
    primeiro.encerrar_votacao()
    primeiro.apurar()
    pec.registrar_resultado(primeiro)
    segundo = pec.nova_sessao(relogio=relogio_fixo)
    print(f"     turno 1 e turno 2 convocados no mesmo instante ({INSTANTE_FIXO.isoformat()})")
    print(f"     turno atual: {pec.turno_atual} | sessao: {segundo.id_sessao}  (nenhuma recusa)")


def e4_quorum_aferido_tarde() -> None:
    """A sessão abre e recebe votos sem aferir presença; o quórum só pesa na apuração."""
    print("E4 | J2 passo 3: quorum so e aferido na apuracao")
    regra = RegraCongresso(materia=TipoMateriaCongresso.LEI_ORDINARIA, casa=CasaLegislativa.CAMARA)
    print(f"     quorum_instalacao da Camara: {regra.quorum_instalacao} de {regra.total_membros}")
    sessao = SessaoVotacao("PL-9999/2026-CAMARA-T1", regra, total_aptos=regra.total_membros)
    sessao.abrir()
    sessao.liberar_votacao()
    print(f"     sessao aberta sem nenhuma afericao de presenca -> estado {sessao.estado.value}")
    for numero in range(10):
        sessao.registrar_voto(Voto(eleitor_id=f"dep{numero}", opcao="SIM"))
    print("     10 votos aceitos sem recusa")
    sessao.encerrar_votacao()
    resultado = sessao.apurar()
    print(
        f"     apuracao -> {resultado.status.value} | quorum_atingido={resultado.quorum_atingido}"
    )
    print(f"     estado da sessao: {sessao.estado.value}  (os votos foram colhidos em vao)")


def e5_sessao_nao_suspende() -> None:
    """Não há estado de suspensão: a máquina de estados é estritamente progressiva."""
    print("E5 | J2 passo 3: suspensao da sessao")
    print(f"     estados disponiveis: {[estado.value for estado in EstadoSessao]}")
    print("     nao ha estado de suspensao nem metodo para suspender/retomar")
    regra = RegraCongresso(materia=TipoMateriaCongresso.LEI_ORDINARIA, casa=CasaLegislativa.CAMARA)
    sessao = SessaoVotacao("PL-8888/2026-CAMARA-T1", regra, total_aptos=regra.total_membros)
    sessao.abrir()
    sessao.liberar_votacao()
    try:
        sessao.abrir()
    except TransicaoInvalidaError as erro:
        print(f"     a maquina de estados e estritamente progressiva: {type(erro).__name__}")


def main() -> None:
    """Executa os cinco blocos de evidência, na ordem em que o documento os cita."""
    for bloco in (
        e1_pec_aprovada_nas_duas_casas,
        e2_irrepetibilidade,
        e3_intersticio_entre_turnos,
        e4_quorum_aferido_tarde,
        e5_sessao_nao_suspende,
    ):
        bloco()
        print()


if __name__ == "__main__":
    main()
