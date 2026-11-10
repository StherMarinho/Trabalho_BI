import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from ssp_loader import carregar_ssp, tabela_site_para_fato

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Tabela no formato do site da SSP: tipo de ocorrência x Capital/Demacro/
# Interior/Total, por mês
tabela_site = carregar_ssp()

# Salva a tabela emulada para conferir com os números publicados no site
tabela_site.to_csv('ssp_tabela_site.csv', index=False, encoding='utf-8-sig')
print(f"tabela do site emulada: {len(tabela_site)} linhas (salva em ssp_tabela_site.csv)")

# Formato da fato: 1 linha por região (sem a coluna Total)
df = tabela_site_para_fato(tabela_site)


def inserir_ignorando_duplicatas(df, tabela, engine):
    """Insere registros pulando duplicatas (INSERT IGNORE)."""
    colunas = ', '.join(df.columns)
    placeholders = ', '.join([f':{c}' for c in df.columns])
    sql = text(f"INSERT IGNORE INTO {tabela} ({colunas}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(sql, df.to_dict(orient='records'))


# DIM_FONTE -- Garante de forma segura que a fonte 'SSP-SP' exista sem duplicar
sql_fonte = text("""
    INSERT INTO dim_fonte (nome_fonte, tipo_base)
    VALUES (:nome_fonte, :tipo_base)
    ON DUPLICATE KEY UPDATE tipo_base = VALUES(tipo_base)
""")
with engine.begin() as conn:
    conn.execute(sql_fonte, {'nome_fonte': 'SSP-SP', 'tipo_base': 'Oficial'})

# DIM_REGIAO_SP -- domínio fixo, só existem 3 regiões na tabela do site
dim_regiao = pd.DataFrame({'nome_regiao': ['Capital', 'Demacro', 'Interior']})
inserir_ignorando_duplicatas(dim_regiao, 'dim_regiao_sp', engine)
print(f"dim_regiao_sp: {len(dim_regiao)} registros processados")

# DIM_TIPO_OCORRENCIA
dim_tipo = (
    df[['tipo_ocorrencia']]
    .drop_duplicates()
    .rename(columns={'tipo_ocorrencia': 'descricao'})
)
dim_tipo['categoria_agregada'] = dim_tipo['descricao'].str.slice(0, 50)
inserir_ignorando_duplicatas(dim_tipo, 'dim_tipo_ocorrencia', engine)
print(f"dim_tipo_ocorrencia: {len(dim_tipo)} registros processados")

# DIM_TEMPO_MES
dim_tempo = df[['ano', 'mes']].drop_duplicates()
inserir_ignorando_duplicatas(dim_tempo, 'dim_tempo_mes', engine)
print(f"dim_tempo_mes: {len(dim_tempo)} registros processados")

# FATO_OCORRENCIAS_SSP -- precisa das PKs já geradas no banco (AUTO_INCREMENT)
fonte_id = pd.read_sql(
    "SELECT id_fonte FROM dim_fonte WHERE nome_fonte = 'SSP-SP'", engine
).iloc[0]['id_fonte']
regiao_ids = pd.read_sql("SELECT id_regiao, nome_regiao FROM dim_regiao_sp", engine)
tipo_ids = (
    pd.read_sql("SELECT id_tipo_ocorrencia, descricao FROM dim_tipo_ocorrencia", engine)
    .drop_duplicates(subset='descricao')
)
tempo_ids = pd.read_sql("SELECT id_tempo, ano, mes FROM dim_tempo_mes", engine)

fato = df.merge(regiao_ids, left_on='regiao', right_on='nome_regiao')
fato = fato.merge(tipo_ids, left_on='tipo_ocorrencia', right_on='descricao')
fato = fato.merge(tempo_ids, on=['ano', 'mes'])
fato = fato.rename(columns={'id_tempo': 'id_tempo_mes'})
fato['id_fonte'] = fonte_id

fato = fato[
    ['id_tempo_mes', 'id_regiao', 'id_tipo_ocorrencia', 'id_fonte', 'quantidade_ocorrencias']
]

inserir_ignorando_duplicatas(fato, 'fato_ocorrencias_ssp', engine)
print(f"fato_ocorrencias_ssp: {len(fato)} registros processados")