import pandas as pd

CAMINHO_PADRAO = 'dados/BASE_VD.csv'

# A tela pública da SSP (ssp.sp.gov.br/estatistica/violencia-contra-a-mulher)
# só mostra 3 regiões: Capital, Demacro (demais municípios da Região
# Metropolitana de SP) e Interior. GRANDE_AREA_CIRC na base bruta traz
# "CAPITAL", "GRANDE SÃO PAULO" e "INTERIOR" -- padronizamos para o nome
# usado na tela.
MAPA_REGIAO = {
    'CAPITAL': 'Capital',
    'GRANDE SÃO PAULO': 'Demacro',
    'DEMACRO': 'Demacro',
    'INTERIOR': 'Interior',
}

# Só lemos as colunas realmente necessárias para reproduzir a tela pública
# (a base bruta tem 69 colunas / ~900 mil linhas).
# ESPECIE entrou para compor dim_tipo_ocorrencia.categoria_agregada --
# ver carregar_ssp() abaixo.
COLUNAS_NECESSARIAS = [
    'ANO_BO',
    'NUM_BO',
    'GRANDE_AREA_CIRC',
    'NATUREZA_APURADA',
    'ESPECIE',
    'MES_ESTATISTICA',
    'ANO_ESTATISTICA',
    'FLAG_VIOLENCIA_DOMESTICA',
    'DESCR_TIPO_PESSOA',
    'SEXO_PESSOA',
]


def carregar_ssp(caminho=CAMINHO_PADRAO):
    df = pd.read_csv(
        caminho,
        sep=';',
        usecols=COLUNAS_NECESSARIAS,
        dtype=str,
        encoding='utf-8',
    )

    # cada B.O. tem 1 linha por pessoa envolvida; a tela pública conta
    # ocorrências de violência doméstica contra a mulher na condição de vítima
    df = df[df['DESCR_TIPO_PESSOA'].str.strip().eq('Vítima')]
    df = df[df['SEXO_PESSOA'].str.strip().eq('F')]
    df = df[df['FLAG_VIOLENCIA_DOMESTICA'].str.strip().eq('VIOLÊNCIA DOMÉSTICA')]

    df['regiao'] = df['GRANDE_AREA_CIRC'].str.strip().str.upper().map(MAPA_REGIAO)
    df = df.dropna(subset=['regiao'])

    # descricao = tipo atômico (ex.: "LESÃO CORPORAL DOLOSA") -- é o que a
    # tela pública mostra linha a linha
    df['tipo_ocorrencia'] = df['NATUREZA_APURADA'].str.strip().str.upper()

    # categoria_agregada = título da lei (ESPECIE, ex.: "Dos crimes contra a
    # pessoa") -- permite recompor os subtotais que a SSP às vezes publica
    # agrupando vários tipos atômicos. Nem toda linha vem com ESPECIE
    # preenchido, então usamos o valor mais frequente para cada tipo.
    df['especie'] = df['ESPECIE'].str.strip()
    moda_especie = (
        df[df['especie'].notna() & df['especie'].ne('')]
        .groupby('tipo_ocorrencia')['especie']
        .agg(lambda s: s.mode().iat[0])
    )
    df['categoria_agregada'] = df['tipo_ocorrencia'].map(moda_especie).fillna('Outros')

    df['ano'] = pd.to_numeric(df['ANO_ESTATISTICA'], errors='coerce')
    df['mes'] = pd.to_numeric(df['MES_ESTATISTICA'], errors='coerce')
    df = df.dropna(subset=['ano', 'mes'])
    df['ano'] = df['ano'].astype(int)
    df['mes'] = df['mes'].astype(int)

    # um mesmo B.O. pode repetir a mesma vítima quando há mais de uma
    # tipificação (NATUREZA_APURADA); mantemos 1 linha por
    # (B.O. + tipo de ocorrência), que é o que a tela pública conta
    df = df.drop_duplicates(subset=['ANO_BO', 'NUM_BO', 'tipo_ocorrencia'])

    df = df.astype(object).where(df.notna(), None)

    return df[['regiao', 'tipo_ocorrencia', 'categoria_agregada', 'ano', 'mes']]
