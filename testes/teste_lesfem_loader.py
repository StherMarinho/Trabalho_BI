import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'etl'))

import pandas as pd
import pytest
from lesfem_loader import carregar_lesfem, SIGLAS_ESTADO

CAMINHO_EXCEL = os.path.join(os.path.dirname(__file__), '..', 'dados', 'Base-de-dados-2025_v1.xlsx')

@pytest.fixture
def df():
    return carregar_lesfem(CAMINHO_EXCEL)

# --- Shape e estrutura ---

def test_tem_registros(df):
    assert len(df) > 0, "DataFrame veio vazio"

def test_colunas_presentes(df):
    colunas_esperadas = [
        'Identificador', 'Fonte', 'Dia', 'Mês', 'Ano',
        'Estado', 'Município', 'Código do município',
        'Local do crime', 'Idade da vítima',
        'Vínculo entre vítima e suspeito', 'Arma ou meio utilizado',
        'Filhos dependentes (informação disponível?)',
        'Consumado ou Tentado', 'Idade do agressor', 'Período do dia'
    ]
    for col in colunas_esperadas:
        assert col in df.columns, f"Coluna ausente: {col}"

# --- Código IBGE ---

def test_codigo_ibge_e_string(df):
    # Checa se os valores são strings, não o dtype (compatível com pandas moderno)
    amostra = df['Código do município'].dropna().iloc[0]
    assert isinstance(amostra, str), "Código IBGE não é string"

def test_codigo_ibge_tem_7_digitos(df):
    invalidos = df[df['Código do município'].str.len() != 7]
    assert len(invalidos) == 0, (
        f"{len(invalidos)} registros com código IBGE fora de 7 dígitos:\n"
        f"{invalidos[['Identificador', 'Código do município']].head()}"
    )

def test_codigo_ibge_sem_nan(df):
    nulos = df['Código do município'].isna().sum()
    assert nulos == 0, f"{nulos} registros com código IBGE nulo"

# --- Estado ---

def test_estado_virou_sigla(df):
    # Filtra apenas estados não nulos e verifica se todos têm 2 caracteres
    estados = df['Estado'].dropna()
    nao_sigla = estados[estados.str.len() > 2]
    assert len(nao_sigla) == 0, (
        f"Estados não convertidos para sigla: {nao_sigla.unique()}"
    )

def test_estado_sem_nome_desconhecido(df):
    siglas_validas = set(SIGLAS_ESTADO.values())
    estados_na_base = set(df['Estado'].dropna().unique())
    desconhecidos = estados_na_base - siglas_validas
    assert len(desconhecidos) == 0, f"Siglas não mapeadas: {desconhecidos}"

# --- NaN virou None ---

def test_nan_virou_none(df):
    for col in df.columns:
        for val in df[col]:
            assert not (isinstance(val, float) and pd.isna(val)), (
                f"NaN encontrado na coluna '{col}' — deveria ser None"
            )