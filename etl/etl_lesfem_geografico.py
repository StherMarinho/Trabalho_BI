import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from lesfem_loader import carregar_lesfem

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

df = carregar_lesfem()

def inserir_ignorando_duplicatas(df, tabela, engine):
    """Insere registros pulando duplicatas (INSERT IGNORE)."""
    colunas = ', '.join(df.columns)
    placeholders = ', '.join([f':{c}' for c in df.columns])
    sql = text(f"INSERT IGNORE INTO {tabela} ({colunas}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(sql, df.to_dict(orient='records'))

# DIM_LOCAL
dim_local = (
    df[['Código do município', 'Município', 'Estado']]
    .drop_duplicates()
    .rename(columns={
        'Código do município': 'codigo_ibge',
        'Município': 'municipio',
        'Estado': 'estado'
    })
)
inserir_ignorando_duplicatas(dim_local, 'dim_local', engine)
print(f"dim_local: {len(dim_local)} registros processados")

# DIM_LOCAL_CRIME
dim_local_crime = (
    df[['Local do crime']]
    .drop_duplicates()
    .rename(columns={'Local do crime': 'descricao_cenario'})
)
inserir_ignorando_duplicatas(dim_local_crime, 'dim_local_crime', engine)
print(f"dim_local_crime: {len(dim_local_crime)} registros processados")

# DIM_TEMPO_DIA
dim_tempo = (
    df[['Dia', 'Mês', 'Ano']]
    .drop_duplicates()
    .rename(columns={'Dia': 'dia', 'Mês': 'mes', 'Ano': 'ano'})
)
inserir_ignorando_duplicatas(dim_tempo, 'dim_tempo_dia', engine)
print(f"dim_tempo_dia: {len(dim_tempo)} registros processados")