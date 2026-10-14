import pandas as pd
import numpy as np

CAMINHO_PADRAO = 'dados/Base-de-dados-2025_v1.xlsx'

SIGLAS_ESTADO = {
    'Minas Gerais': 'MG', 'São Paulo': 'SP', 'Goiás': 'GO',
    'Mato Grosso': 'MT', 'Rondônia': 'RO', 'Santa Catarina': 'SC',
    'Paraná': 'PR', 'Paraíba': 'PB', 'Piauí': 'PI', 'Pará': 'PA',
    'Amazonas': 'AM', 'Maranhão': 'MA', 'Acre': 'AC', 'Bahia': 'BA',
    'Rio de Janeiro': 'RJ', 'Roraima': 'RR', 'Mato Grosso do Sul': 'MS',
    'Espírito Santo': 'ES', 'Tocantins': 'TO', 'Sergipe': 'SE',
    'Pernambuco': 'PE', 'Rio Grande do Sul': 'RS', 'Ceará': 'CE',
    'Rio Grande do Norte': 'RN', 'Alagoas': 'AL', 'Amapá': 'AP',
    'Distrito Federal': 'DF'
}

def carregar_lesfem(caminho=CAMINHO_PADRAO):
    df = pd.read_excel(caminho, sheet_name='Dados2025')

    df['Código do município'] = (
        df['Código do município']
        .astype(str).str.strip().str.zfill(7)
    )
    df['Município'] = df['Município'].str.strip()
    df['Estado'] = df['Estado'].map(SIGLAS_ESTADO)

    # Converter NaN para None em TODAS as colunas, incluindo numéricas
    df = df.astype(object).where(df.notna(), None)

    return df