"""
ETL da Pessoa 4 — dimensões e fato do Lesfem.

Popula:  dim_vinculo, dim_arma, dim_atributos_caso, dim_faixa_etaria,
         fato_casos_feminicidio
Lê (só leitura, populadas pela Pessoa 3 / Pessoa 5):
         dim_local, dim_tempo_dia, dim_local_crime, dim_fonte

Rodar da raiz do repositório:  python etl/pessoa4_lesfem.py
"""
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(__file__))  # lesfem_loader.py está na mesma pasta (etl/)
from lesfem_loader import carregar_lesfem  # noqa: E402

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
C = {  # nomes reais das colunas na aba Dados2025
    'caso':      'Identificador',
    'fonte':     'Fonte',
    'ibge':      'Código do município',
    'dia':       'Dia',
    'mes':       'Mês',
    'ano':       'Ano',
    'cenario':   'Local do crime',
    'vinculo':   'Vínculo entre vítima e suspeito',
    'arma':      'Arma ou meio utilizado',
    'consumado': 'Consumado ou Tentado',
    'filhos':    'Filhos dependentes (informação disponível?)',
    'periodo':   'Período do dia',
    'idade_vit': 'Idade da vítima',
    'idade_agr': 'Idade do agressor',
}

SEM_INFO = 'Não informado'                 
BINS = [0, 10, 20, 30, 40, 50, 60, 200]    # combinar com o grupo
ROTULOS = ['0-9', '10-19', '20-29', '30-39', '40-49', '50-59', '60+']


def get_engine():
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    return create_engine(
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


# ----------------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------------
def limpar(serie, padrao):
    """strip + vazio vira padrão. Não altera maiúsculas/minúsculas."""
    return (serie.astype('string').str.strip()
                 .replace('', pd.NA).fillna(padrao))


def curto(serie):
    """Para colunas VARCHAR(10): 'Incerto/Desconhecido' (20 chars) vira 'Incerto'."""
    return limpar(serie, 'Incerto').replace({'Incerto/Desconhecido': 'Incerto'})


def faixa(idade):
    idade = pd.to_numeric(idade, errors='coerce')
    return (pd.cut(idade, bins=BINS, labels=ROTULOS, right=False)
              .astype('string').fillna(SEM_INFO))


def inteiro(serie):
    return pd.to_numeric(serie, errors='coerce').astype('Int64')


def carregar_dimensao(df, tabela, colunas, engine):
    """Insere só as combinações que ainda não existem (não depende de UNIQUE)
    e devolve a dimensão completa, já com as chaves substitutas."""
    df = df[colunas].drop_duplicates()
    existentes = pd.read_sql(f"SELECT {', '.join(colunas)} FROM {tabela}", engine)
    novos = df.merge(existentes, on=colunas, how='left', indicator=True)
    novos = novos[novos['_merge'] == 'left_only'].drop(columns='_merge')
    if not novos.empty:
        novos.to_sql(tabela, engine, if_exists='append', index=False)
    return pd.read_sql(f"SELECT * FROM {tabela}", engine)


def exigir_unicidade(dim, chaves, nome):
    """Dimensão duplicada multiplica linhas do fato no merge."""
    dup = dim[dim.duplicated(chaves, keep=False)]
    if not dup.empty:
        raise ValueError(
            f"{nome} tem duplicatas em {chaves}; avise a dona da tabela:\n{dup.head(10)}")


# ----------------------------------------------------------------------------
# Transformação
# ----------------------------------------------------------------------------
def transformar(df):
    t = pd.DataFrame({
        'identificador_caso': df[C['caso']].astype(str).str.strip(),
        'fonte':              limpar(df[C['fonte']], ''),
        # minhas dimensões
        'descricao_vinculo':  limpar(df[C['vinculo']], 'Incerto/Desconhecido'),
        'descricao_arma':     limpar(df[C['arma']], 'Incerto/Desconhecido'),
        'consumado_tentado':  curto(df[C['consumado']]),
        'filhos_dependentes': curto(df[C['filhos']]),
        'periodo_dia':        curto(df[C['periodo']]),
        'faixa_vitima':       faixa(df[C['idade_vit']]),
        'faixa_agressor':     faixa(df[C['idade_agr']]),
        # chaves das dimensões da Pessoa 3: valores CRUS, como ela inseriu
        'codigo_ibge':        inteiro(df[C['ibge']]),
        'dia':                inteiro(df[C['dia']]),
        'mes':                inteiro(df[C['mes']]),
        'ano':                inteiro(df[C['ano']]),
        'descricao_cenario':  df[C['cenario']].fillna(''),
    }).drop_duplicates(subset='identificador_caso')

    # falhar aqui é melhor do que o MySQL truncar em silêncio
    for col in ['consumado_tentado', 'filhos_dependentes', 'periodo_dia']:
        assert t[col].str.len().max() <= 10, f"{col} passa de 10 caracteres"
    assert (t['fonte'] != '').all(), "há linhas sem Fonte"
    return t


# ----------------------------------------------------------------------------
# Dimensões da Pessoa 4
# ----------------------------------------------------------------------------
def carregar_dims(t, engine):
    return {
        'vinculo': carregar_dimensao(t, 'dim_vinculo', ['descricao_vinculo'], engine),
        'arma': carregar_dimensao(t, 'dim_arma', ['descricao_arma'], engine),
        'attr': carregar_dimensao(
            t, 'dim_atributos_caso',
            ['consumado_tentado', 'filhos_dependentes', 'periodo_dia'], engine),
        # faixas fixas + 'Não informado' (as FKs de vítima/agressor são NOT NULL)
        'faixa': carregar_dimensao(
            pd.DataFrame({'faixa_etaria': ROTULOS + [SEM_INFO]}),
            'dim_faixa_etaria', ['faixa_etaria'], engine),
    }


# ----------------------------------------------------------------------------
# Fato de feminicídio
# ----------------------------------------------------------------------------
def carregar_fato(t, dims, engine):
    # dimensões de outras pessoas (só leitura)
    d_local = pd.read_sql("SELECT id_local, codigo_ibge FROM dim_local", engine)
    d_local['codigo_ibge'] = d_local['codigo_ibge'].astype('Int64')
    d_tempo = pd.read_sql(
        "SELECT id_tempo AS id_tempo_dia, ano, mes, dia FROM dim_tempo_dia", engine)
    d_tempo[['ano', 'mes', 'dia']] = d_tempo[['ano', 'mes', 'dia']].astype('Int64')
    d_cen = pd.read_sql(
        "SELECT id_local_crime, descricao_cenario FROM dim_local_crime", engine)
    d_fonte = pd.read_sql("SELECT id_fonte, nome_fonte FROM dim_fonte", engine)

    for dim, chaves, nome in [
        (dims['vinculo'], ['descricao_vinculo'], 'dim_vinculo'),
        (dims['arma'], ['descricao_arma'], 'dim_arma'),
        (dims['attr'], ['consumado_tentado', 'filhos_dependentes', 'periodo_dia'],
         'dim_atributos_caso'),
        (dims['faixa'], ['faixa_etaria'], 'dim_faixa_etaria'),
        (d_local, ['codigo_ibge'], 'dim_local'),
        (d_tempo, ['ano', 'mes', 'dia'], 'dim_tempo_dia'),
        (d_cen, ['descricao_cenario'], 'dim_local_crime'),
        (d_fonte, ['nome_fonte'], 'dim_fonte'),
    ]:
        exigir_unicidade(dim, chaves, nome)

    f = t.copy()
    f = f.merge(dims['vinculo'], on='descricao_vinculo', how='left')
    f = f.merge(dims['arma'], on='descricao_arma', how='left')
    f = f.merge(dims['attr'],
                on=['consumado_tentado', 'filhos_dependentes', 'periodo_dia'], how='left')

    # mesma dimensão, dois papéis (vítima e agressor)
    fx = dims['faixa'][['id_faixa', 'faixa_etaria']]
    f = f.merge(fx.rename(columns={'id_faixa': 'id_faixa_vitima',
                                   'faixa_etaria': 'faixa_vitima'}),
                on='faixa_vitima', how='left')
    f = f.merge(fx.rename(columns={'id_faixa': 'id_faixa_agressor',
                                   'faixa_etaria': 'faixa_agressor'}),
                on='faixa_agressor', how='left')

    f = f.merge(d_local, on='codigo_ibge', how='left')
    f = f.merge(d_tempo, on=['ano', 'mes', 'dia'], how='left')   # NA casa com NA
    f = f.merge(d_cen, on='descricao_cenario', how='left')
    f = f.merge(d_fonte, left_on='fonte', right_on='nome_fonte', how='left')  # por linha

    assert len(f) == len(t), "o merge multiplicou linhas: há duplicata em alguma dimensão"

    fks = ['id_tempo_dia', 'id_local', 'id_vinculo', 'id_arma', 'id_local_crime',
           'id_atributos_caso', 'id_fonte', 'id_faixa_vitima', 'id_faixa_agressor']
    ruins = f[f[fks].isna().any(axis=1)]
    if not ruins.empty:
        print(f[fks].isna().sum()[lambda s: s > 0])      # qual FK está falhando
        print(ruins[['identificador_caso', 'fonte', 'codigo_ibge', 'ano', 'mes', 'dia']]
              .head(20))
        raise ValueError(f"{len(ruins)} linhas sem FK; veja acima qual dimensão falhou")

    # idempotência: só insere casos que ainda não estão no fato
    ja = pd.read_sql("SELECT identificador_caso FROM fato_casos_feminicidio", engine)
    f = f[~f['identificador_caso'].isin(ja['identificador_caso'])]

    with engine.begin() as conn:            # tudo ou nada
        f[['identificador_caso'] + fks].to_sql(
            'fato_casos_feminicidio', conn, if_exists='append',
            index=False, chunksize=1000, method='multi')
    print(f"fato_casos_feminicidio: {len(f)} casos inseridos")


# ----------------------------------------------------------------------------
# Orquestração
# ----------------------------------------------------------------------------
def main(engine=None):
    engine = engine or get_engine()
    t = transformar(carregar_lesfem())
    dims = carregar_dims(t, engine)
    print('dimensões da Pessoa 4 carregadas')
    carregar_fato(t, dims, engine)


if __name__ == '__main__':
    main()