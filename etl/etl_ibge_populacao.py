"""
ETL da Pessoa 4 — população por município (IBGE/SIDRA) -> fato_populacao.

Lê (só leitura): dim_local (Pessoa 3) e dim_fonte (etl_fontes.py)
Rodar DEPOIS de etl_lesfem_geografico.py. Não depende de etl_lesfem_atributos.py.
Rodar da raiz do repositório:  python etl/etl_ibge_populacao.py
"""
import os

import pandas as pd
import requests
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy import create_engine

FONTE_IBGE = 'IBGE-SIDRA'        # igual ao inserido por etl_fontes.py
SIDRA_TABELA = '6579'            # CONFERIR no site do SIDRA
SIDRA_VARIAVEL = '9324'          # CONFERIR
ANOS_POPULACAO = [2025]          # a base do Lesfem só tem 2025


def get_engine():
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    return create_engine(URL.create(
        "mysql+pymysql",
        username=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', '127.0.0.1'),
        port=int(os.getenv('DB_PORT', '3306')),
        database=os.getenv('DB_NAME'),
    ))


def extrair_sidra(tabela, variavel, ano):
    """População por município para um ano (um ano por chamada, por causa do limite da API)."""
    url = (f"https://apisidra.ibge.gov.br/values/t/{tabela}"
           f"/n6/all/v/{variavel}/p/{ano}")
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    dados = resp.json()
    cab, linhas = dados[0], dados[1:]
    df = pd.DataFrame(linhas)

    # acha as colunas pelo texto do cabeçalho (D1C/D2C mudam entre tabelas)
    col_mun = next(k for k, v in cab.items() if v == 'Município (Código)')
    col_ano = next(k for k, v in cab.items() if v == 'Ano (Código)')

    out = pd.DataFrame({
        'codigo_ibge': pd.to_numeric(df[col_mun], errors='coerce'),
        'ano': pd.to_numeric(df[col_ano], errors='coerce'),
        'populacao': pd.to_numeric(df['V'], errors='coerce'),  # '...' e '-' viram NaN
    })
    return out.dropna().astype(int)


def carregar_populacao(engine):
    pop = pd.concat(
        [extrair_sidra(SIDRA_TABELA, SIDRA_VARIAVEL, a) for a in ANOS_POPULACAO],
        ignore_index=True)

    d_local = pd.read_sql("SELECT id_local, codigo_ibge FROM dim_local", engine)
    pop = pop.merge(d_local, on='codigo_ibge', how='inner')  # só municípios do DW

    r = pd.read_sql(text("SELECT id_fonte FROM dim_fonte WHERE nome_fonte = :n"),
                    engine, params={'n': FONTE_IBGE})
    if r.empty:
        raise ValueError(f"'{FONTE_IBGE}' não existe em dim_fonte; peça à Pessoa 5.")
    pop['id_fonte'] = int(r.iloc[0, 0])

    sql = text("""
        INSERT INTO fato_populacao (id_local, ano, populacao, id_fonte)
        VALUES (:id_local, :ano, :populacao, :id_fonte)
        ON DUPLICATE KEY UPDATE populacao = VALUES(populacao)
    """)  # usa o UNIQUE (id_local, ano, id_fonte): rodar de novo atualiza, não duplica
    with engine.begin() as conn:
        conn.execute(sql, pop[['id_local', 'ano', 'populacao', 'id_fonte']]
                     .to_dict('records'))
    print(f"fato_populacao: {len(pop)} linhas carregadas")


if __name__ == '__main__':
    engine = get_engine()
    try:
        carregar_populacao(engine)
    finally:
        engine.dispose()