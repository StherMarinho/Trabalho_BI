import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from ssp_loader import carregar_ssp

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

df = carregar_ssp()


def inserir_ignorando_duplicatas(df, tabela, engine):
    """Insere registros pulando duplicatas (INSERT IGNORE)."""
    colunas = ', '.join(df.columns)
    placeholders = ', '.join([f':{c}' for c in df.columns])
    sql = text(f"INSERT IGNORE INTO {tabela} ({colunas}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(sql, df.to_dict(orient='records'))


# DIM_FONTE -- dimensão compartilhada com o fato do Lesfem; aqui só
# garantimos que a linha 'SSP-SP' exista (INSERT IGNORE não duplica)
dim_fonte = pd.DataFrame({'nome_fonte': ['SSP-SP'], 'tipo_base': ['Oficial']})
inserir_ignorando_duplicatas(dim_fonte, 'dim_fonte', engine)

# DIM_REGIAO_SP -- domínio fixo, só existem 3 regiões na tela da SSP
dim_regiao = pd.DataFrame({'nome_regiao': ['Capital', 'Demacro', 'Interior']})
inserir_ignorando_duplicatas(dim_regiao, 'dim_regiao_sp', engine)
print(f"dim_regiao_sp: {len(dim_regiao)} registros processados")

# DIM_TIPO_OCORRENCIA
dim_tipo = (
    df[['tipo_ocorrencia', 'categoria_agregada']]
    .drop_duplicates()
    .rename(columns={'tipo_ocorrencia': 'descricao'})
)
inserir_ignorando_duplicatas(dim_tipo, 'dim_tipo_ocorrencia', engine)
print(f"dim_tipo_ocorrencia: {len(dim_tipo)} registros processados")

# DIM_TEMPO_MES
dim_tempo = df[['ano', 'mes']].drop_duplicates()
inserir_ignorando_duplicatas(dim_tempo, 'dim_tempo_mes', engine)
print(f"dim_tempo_mes: {len(dim_tempo)} registros processados")

# FATO_OCORRENCIAS_SSP -- diferente das dims acima, aqui precisamos das PKs
# já geradas no banco (AUTO_INCREMENT), porque o fato referencia as
# dimensões por id, não pelo valor natural
fonte_id = pd.read_sql(
    "SELECT id_fonte FROM dim_fonte WHERE nome_fonte = 'SSP-SP'", engine
).iloc[0]['id_fonte']
regiao_ids = pd.read_sql("SELECT id_regiao, nome_regiao FROM dim_regiao_sp", engine)
tipo_ids = pd.read_sql("SELECT id_tipo_ocorrencia, descricao FROM dim_tipo_ocorrencia", engine)
tempo_ids = pd.read_sql("SELECT id_tempo, ano, mes FROM dim_tempo_mes", engine)

fato = (
    df.groupby(['regiao', 'tipo_ocorrencia', 'ano', 'mes'])
    .size()
    .reset_index(name='quantidade_ocorrencias')
)
fato = fato.merge(regiao_ids, left_on='regiao', right_on='nome_regiao')
fato = fato.merge(tipo_ids, left_on='tipo_ocorrencia', right_on='descricao')
fato = fato.merge(tempo_ids, on=['ano', 'mes'])
fato = fato.rename(columns={'id_tempo': 'id_tempo_mes'})
fato['id_fonte'] = fonte_id

fato = fato[
    ['id_tempo_mes', 'id_regiao', 'id_tipo_ocorrencia', 'id_fonte', 'quantidade_ocorrencias']
]

inserir_ignorando_duplicatas(fato, 'fato_ocorrencias_ssp', engine)
print(f"fato_ocorrencias_ssp: {len(fato)} registros processados")
