"""Mecanismo de banco de dados relacional SQL (SQLite) para dados mockados."""

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from votacao.dados.assembleia import (
    Acionista,
    CandidatoConselho,
    Procuracao,
    RepositorioAssembleia,
)
from votacao.dados.ca import ChapaCA, Discente, RepositorioCA
from votacao.dados.congresso import (
    MateriaLegislativa,
    Parlamentar,
    RepositorioCongresso,
)
from votacao.modelos import CasaLegislativa, TipoMateriaCongresso

DIRETORIO_DADOS = Path(__file__).resolve().parent
CAMINHO_SCHEMA = DIRETORIO_DADOS / "schema.sql"
CAMINHO_SEEDS = DIRETORIO_DADOS / "seeds.sql"


class BancoDadosSQL:
    """Gerenciador de banco relacional SQLite para persistência e consulta SQL mockada.

    Permite executar DDL/DML a partir dos arquivos schema.sql e seeds.sql,
    além de realizar queries SQL diretamente sobre as tabelas dos três domínios.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self.database = database
        self.conexao = sqlite3.connect(database)
        self.conexao.row_factory = sqlite3.Row
        self.conexao.execute("PRAGMA foreign_keys = ON;")

    def inicializar_schema(self, script_path: Path | str | None = None) -> None:
        """Executa o script DDL de criação das tabelas SQL."""
        caminho = Path(script_path) if script_path else CAMINHO_SCHEMA
        sql = caminho.read_text(encoding="utf-8")
        self.conexao.executescript(sql)

    def carregar_seeds(self, script_path: Path | str | None = None) -> None:
        """Executa o script DML com os dados simulados padrão."""
        caminho = Path(script_path) if script_path else CAMINHO_SEEDS
        sql = caminho.read_text(encoding="utf-8")
        self.conexao.executescript(sql)

    def executar(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Executa um comando SQL arbitrário."""
        return self.conexao.execute(sql, params)

    def consultar(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Executa uma query SELECT e retorna os registros como lista de Rows."""
        cursor = self.conexao.execute(sql, params)
        return cursor.fetchall()

    def fechar(self) -> None:
        """Encerra a conexão com o banco de dados."""
        self.conexao.close()

    # --- Consultas tipadas via SQL ---

    def obter_discente(self, ra: str) -> Discente | None:
        """Consulta um discente via comando SQL SELECT na tabela discentes."""
        rows = self.consultar(
            "SELECT ra, nome, curso, matricula_ativa, formando_proximo_semestre, suspenso "
            "FROM discentes WHERE ra = ?",
            (ra.strip(),),
        )
        if not rows:
            return None
        r = rows[0]
        return Discente(
            ra=r["ra"],
            nome=r["nome"],
            curso=r["curso"],
            matricula_ativa=bool(r["matricula_ativa"]),
            formando_proximo_semestre=bool(r["formando_proximo_semestre"]),
            suspenso=bool(r["suspenso"]),
        )

    def obter_chapa(self, nome: str) -> ChapaCA | None:
        """Consulta uma chapa e seus integrantes via JOIN SQL."""
        rows = self.consultar(
            "SELECT nome, plano_gestao, ativa FROM chapas WHERE UPPER(nome) = ?",
            (nome.strip().upper(),),
        )
        if not rows:
            return None
        chapa_row = rows[0]

        integrantes_rows = self.consultar(
            "SELECT discente_ra FROM chapa_integrantes WHERE UPPER(chapa_nome) = ?",
            (nome.strip().upper(),),
        )
        integrantes = tuple(row["discente_ra"] for row in integrantes_rows)

        return ChapaCA(
            nome=chapa_row["nome"],
            integrantes_ra=integrantes,
            plano_gestao=chapa_row["plano_gestao"],
            ativa=bool(chapa_row["ativa"]),
        )

    def obter_acionista(self, id_acionista: str) -> Acionista | None:
        """Consulta um acionista via comando SQL SELECT."""
        rows = self.consultar(
            "SELECT id, nome, acoes_ordinarias, acoes_preferenciais, bloqueado, ativo "
            "FROM acionistas WHERE id = ?",
            (id_acionista.strip(),),
        )
        if not rows:
            return None
        r = rows[0]
        return Acionista(
            id=r["id"],
            nome=r["nome"],
            acoes_ordinarias=r["acoes_ordinarias"],
            acoes_preferenciais=r["acoes_preferenciais"],
            bloqueado=bool(r["bloqueado"]),
            ativo=bool(r["ativo"]),
        )

    def obter_procuracao(self, outorgante_id: str, procurador_id: str) -> Procuracao | None:
        """Consulta um instrumento de procuração via SQL."""
        rows = self.consultar(
            "SELECT outorgante_id, procurador_id, data_expiracao, ativa "
            "FROM procuracoes WHERE outorgante_id = ? AND procurador_id = ?",
            (outorgante_id.strip(), procurador_id.strip()),
        )
        if not rows:
            return None
        r = rows[0]
        expira_str = r["data_expiracao"]
        data_exp = None
        if expira_str:
            data_exp = datetime.fromisoformat(expira_str.replace("Z", "+00:00")).astimezone(UTC)
        return Procuracao(
            outorgante_id=r["outorgante_id"],
            procurador_id=r["procurador_id"],
            data_expiracao=data_exp,
            ativa=bool(r["ativa"]),
        )

    def obter_parlamentar(self, id_parlamentar: str) -> Parlamentar | None:
        """Consulta um parlamentar via comando SQL SELECT."""
        rows = self.consultar(
            "SELECT id, nome, casa, partido, uf, em_exercicio, licenciado, suspenso "
            "FROM parlamentares WHERE id = ?",
            (id_parlamentar.strip(),),
        )
        if not rows:
            return None
        r = rows[0]
        return Parlamentar(
            id=r["id"],
            nome=r["nome"],
            casa=CasaLegislativa(r["casa"]),
            partido=r["partido"],
            uf=r["uf"],
            em_exercicio=bool(r["em_exercicio"]),
            licenciado=bool(r["licenciado"]),
            suspenso=bool(r["suspenso"]),
        )

    def obter_materia(self, id_materia: str) -> MateriaLegislativa | None:
        """Consulta uma matéria legislativa via comando SQL SELECT."""
        rows = self.consultar(
            "SELECT id, tipo, casa_atual, titulo, ativa "
            "FROM materias_legislativas WHERE UPPER(id) = ?",
            (id_materia.strip().upper(),),
        )
        if not rows:
            return None
        r = rows[0]
        return MateriaLegislativa(
            id=r["id"],
            tipo=TipoMateriaCongresso(r["tipo"]),
            casa_atual=CasaLegislativa(r["casa_atual"]),
            titulo=r["titulo"],
            ativa=bool(r["ativa"]),
        )

    # --- Povoamento de repositórios a partir das tabelas SQL ---

    def carregar_repositorios_a_partir_do_sql(
        self,
        repo_ca: RepositorioCA,
        repo_assembleia: RepositorioAssembleia,
        repo_congresso: RepositorioCongresso,
    ) -> None:
        """Lê todas as tabelas SQL e popula os repositórios em memória correspondentes."""
        # 1. CA
        repo_ca.limpar()
        for r in self.consultar("SELECT * FROM discentes"):
            repo_ca.adicionar_discente(
                Discente(
                    ra=r["ra"],
                    nome=r["nome"],
                    curso=r["curso"],
                    matricula_ativa=bool(r["matricula_ativa"]),
                    formando_proximo_semestre=bool(r["formando_proximo_semestre"]),
                    suspenso=bool(r["suspenso"]),
                )
            )

        for r in self.consultar("SELECT * FROM chapas"):
            integrantes_rows = self.consultar(
                "SELECT discente_ra FROM chapa_integrantes WHERE chapa_nome = ?",
                (r["nome"],),
            )
            integrantes = tuple(row["discente_ra"] for row in integrantes_rows)
            repo_ca.adicionar_chapa(
                ChapaCA(
                    nome=r["nome"],
                    integrantes_ra=integrantes,
                    plano_gestao=r["plano_gestao"],
                    ativa=bool(r["ativa"]),
                )
            )

        # 2. Assembleia
        repo_assembleia.limpar()
        for r in self.consultar("SELECT * FROM acionistas"):
            repo_assembleia.adicionar_acionista(
                Acionista(
                    id=r["id"],
                    nome=r["nome"],
                    acoes_ordinarias=r["acoes_ordinarias"],
                    acoes_preferenciais=r["acoes_preferenciais"],
                    bloqueado=bool(r["bloqueado"]),
                    ativo=bool(r["ativo"]),
                )
            )

        for r in self.consultar("SELECT * FROM procuracoes"):
            expira_str = r["data_expiracao"]
            data_exp = (
                datetime.fromisoformat(expira_str.replace("Z", "+00:00")).astimezone(UTC)
                if expira_str
                else None
            )
            repo_assembleia.adicionar_procuracao(
                Procuracao(
                    outorgante_id=r["outorgante_id"],
                    procurador_id=r["procurador_id"],
                    data_expiracao=data_exp,
                    ativa=bool(r["ativa"]),
                )
            )

        for r in self.consultar("SELECT * FROM candidatos_conselho"):
            repo_assembleia.adicionar_candidato_conselho(
                CandidatoConselho(
                    id=r["id"],
                    nome=r["nome"],
                    titular_acoes=bool(r["titular_acoes"]),
                    conflito_interesse=bool(r["conflito_interesse"]),
                    ativo=bool(r["ativo"]),
                )
            )

        # 3. Congresso
        repo_congresso.limpar()
        for r in self.consultar("SELECT * FROM parlamentares"):
            repo_congresso.adicionar_parlamentar(
                Parlamentar(
                    id=r["id"],
                    nome=r["nome"],
                    casa=CasaLegislativa(r["casa"]),
                    partido=r["partido"],
                    uf=r["uf"],
                    em_exercicio=bool(r["em_exercicio"]),
                    licenciado=bool(r["licenciado"]),
                    suspenso=bool(r["suspenso"]),
                )
            )

        for r in self.consultar("SELECT * FROM materias_legislativas"):
            repo_congresso.adicionar_materia(
                MateriaLegislativa(
                    id=r["id"],
                    tipo=TipoMateriaCongresso(r["tipo"]),
                    casa_atual=CasaLegislativa(r["casa_atual"]),
                    titulo=r["titulo"],
                    ativa=bool(r["ativa"]),
                )
            )
