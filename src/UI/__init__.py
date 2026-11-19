"""Pacote da interface gráfica web (UI) responsiva do sistema de votação."""

from UI.app import EstadoAplicacaoUI
from UI.servidor import (
    ManipuladorRequisicoesUI,
    ServidorVotacaoHTTP,
    criar_servidor,
    iniciar_servidor,
    main,
)

__all__ = [
    "EstadoAplicacaoUI",
    "ManipuladorRequisicoesUI",
    "ServidorVotacaoHTTP",
    "criar_servidor",
    "iniciar_servidor",
    "main",
]
