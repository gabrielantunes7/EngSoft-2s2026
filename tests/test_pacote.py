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
