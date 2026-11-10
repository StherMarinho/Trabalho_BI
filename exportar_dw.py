import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configura a conexão com o MySQL
engine = create_engine(
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST', '127.0.0.1')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME')}"
)

# Lista de todas as tabelas do DW
tabelas = [
    "dim_fonte",
    "dim_local",
    "dim_tempo_mes",
    "dim_regiao_sp",
    "dim_tipo_ocorrencia",
    "fato_ocorrencias_ssp",
    "dim_tempo_dia",
    "dim_vinculo",
    "dim_arma",
    "dim_local_crime",
    "dim_atributos_caso",
    "dim_faixa_etaria",
    "fato_casos_feminicidio",
    "fato_populacao"
]

# Cria uma pasta para salvar os arquivos exportados
os.makedirs("export_dw", exist_ok=True)

for t in tabelas:
    try:
        df = pd.read_sql(f"SELECT * FROM `{t}`", engine)
        caminho = f"export_dw/{t}.csv"
        df.to_csv(caminho, index=False, encoding="utf-8-sig")
        print(f"Tabela '{t}' exportada com sucesso ({len(df)} registros).")
    except Exception as e:
        print(f"Erro ao exportar a tabela {t}: {e}")

print("\nExportação concluída! Os arquivos estão na pasta 'export_dw/'.")