import pandas as pd

CAMINHO_PADRAO = 'dados/BASE_VD.csv'

# só as ocorrências deste ano vão para o DW
ANO_ALVO = '2025'

# A tabela do site da SSP (ssp.sp.gov.br/estatistica/violencia-contra-a-mulher)
# tem 3 regiões: Capital, Demacro (demais municípios da Região Metropolitana)
# e Interior. GRANDE_AREA_CIRC na base bruta traz "CAPITAL",
# "GRANDE SÃO PAULO" e "INTERIOR" -- padronizamos para o nome usado no site.
MAPA_REGIAO = {
    'CAPITAL': 'Capital',
    'GRANDE SÃO PAULO': 'Demacro',
    'DEMACRO': 'Demacro',
    'INTERIOR': 'Interior',
}
REGIOES = ['Capital', 'Demacro', 'Interior']

# A base baixada é de ocorrências individuais (1 linha por pessoa envolvida em
# cada B.O.), e não a tabela agregada do site. Lemos só o necessário para
# reconstruir essa tabela.
# Um B.O. é identificado por ID_DELEGACIA + ANO_BO + NUM_BO (o número do B.O.
# sozinho se repete entre delegacias).
COLUNAS_NECESSARIAS = [
    'ID_DELEGACIA',
    'ANO_BO',
    'NUM_BO',
    'GRANDE_AREA_CIRC',
    'NATUREZA_APURADA',
    'MES_ESTATISTICA',
    'ANO_ESTATISTICA',
]


def carregar_ocorrencias(caminho=CAMINHO_PADRAO, ano=ANO_ALVO):
    """Passo 1: lê a base e devolve 1 linha por ocorrência
    (B.O. + tipo de crime), já padronizada."""
    df = pd.read_csv(
        caminho,
        sep=';',
        usecols=COLUNAS_NECESSARIAS,
        dtype=str,
        encoding='utf-8',
    )

    # a base já é de violência contra a mulher (todos os tipos de crime),
    # então não filtramos por sexo, tipo de pessoa ou violência doméstica.
    # Só filtramos o ano da estatística (o mesmo critério do site).
    df = df[df['ANO_ESTATISTICA'].str.strip().eq(ano)].copy()

    # região (Capital / Demacro / Interior)
    df['regiao'] = df['GRANDE_AREA_CIRC'].str.strip().str.upper().map(MAPA_REGIAO)
    sem_regiao = df['regiao'].isna()
    if sem_regiao.any():
        print(f"AVISO: {sem_regiao.sum()} linhas descartadas por região fora do mapeamento:")
        print(df.loc[sem_regiao, 'GRANDE_AREA_CIRC'].value_counts(dropna=False))
    df = df[~sem_regiao]

    # tipo de ocorrência (ex.: "LESÃO CORPORAL DOLOSA")
    df['tipo_ocorrencia'] = df['NATUREZA_APURADA'].str.strip().str.upper()
    df = df.dropna(subset=['tipo_ocorrencia'])

    # período
    df['ano'] = pd.to_numeric(df['ANO_ESTATISTICA'], errors='coerce')
    df['mes'] = pd.to_numeric(df['MES_ESTATISTICA'], errors='coerce')
    df = df.dropna(subset=['ano', 'mes'])
    df['ano'] = df['ano'].astype(int)
    df['mes'] = df['mes'].astype(int)

    # 1 linha por B.O. e tipo de crime: um B.O. tem várias linhas (uma por
    # pessoa envolvida) e contaria o mesmo crime mais de uma vez
    df = df.drop_duplicates(
        subset=['ID_DELEGACIA', 'ANO_BO', 'NUM_BO', 'tipo_ocorrencia']
    )

    return df[['regiao', 'tipo_ocorrencia', 'ano', 'mes']]


def montar_tabela_site(ocorrencias):
    """Passo 2: emula a tabela do site da SSP, por mês:
    Tipo de Ocorrência | Capital | Demacro | Interior | Total"""
    tabela = (
        ocorrencias
        .groupby(['ano', 'mes', 'tipo_ocorrencia', 'regiao'])
        .size()
        .unstack('regiao', fill_value=0)
        .reindex(columns=REGIOES, fill_value=0)
        .reset_index()
    )
    tabela.columns.name = None
    tabela['Total'] = tabela[REGIOES].sum(axis=1)
    return tabela


def carregar_ssp(caminho=CAMINHO_PADRAO, ano=ANO_ALVO):
    """Devolve a tabela no formato do site (já agregada)."""
    return montar_tabela_site(carregar_ocorrencias(caminho, ano))


def tabela_site_para_fato(tabela):
    """Passo 3: transforma as colunas Capital/Demacro/Interior em linhas,
    que é o formato da fato_ocorrencias_ssp (1 linha por região).
    A coluna Total NÃO vai para o DW: ela é a soma das regiões, e carregá-la
    duplicaria a contagem."""
    longo = tabela.melt(
        id_vars=['ano', 'mes', 'tipo_ocorrencia'],
        value_vars=REGIOES,
        var_name='regiao',
        value_name='quantidade_ocorrencias',
    )
    return longo[longo['quantidade_ocorrencias'] > 0]
