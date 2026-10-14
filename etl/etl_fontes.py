import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

engine = create_engine(URL.create(
    "mysql+pymysql",
    username=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST', '127.0.0.1'),
    port=int(os.getenv('DB_PORT', '3306')),
    database=os.getenv('DB_NAME'),
))

# DIM_FONTE
dim_fonte = [
    {'nome_fonte': 'SSP-SP',     'tipo_base': 'Oficial'},        # fato_ocorrencias_ssp
    {'nome_fonte': 'Imprensa',   'tipo_base': 'Jornalística'},   # fato_casos_feminicidio
    {'nome_fonte': 'SINESP',     'tipo_base': 'Oficial'},        # fato_casos_feminicidio
    {'nome_fonte': 'IBGE-SIDRA', 'tipo_base': 'Oficial'},        # fato_populacao (SIDRA 6579)
]

sql = text("""
    INSERT INTO dim_fonte (nome_fonte, tipo_base)
    SELECT :nome_fonte, :tipo_base
    FROM DUAL
    WHERE NOT EXISTS (
        SELECT 1
        FROM dim_fonte
        WHERE nome_fonte = :nome_fonte
    )
""")

inseridas = 0

with engine.begin() as conn:
    for fonte in dim_fonte:
        resultado = conn.execute(sql, fonte)
        inseridas += resultado.rowcount

print(
    f"dim_fonte: {len(dim_fonte)} registros processados, "
    f"{inseridas} inseridos"
)