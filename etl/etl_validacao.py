#Saída: validacao_pos_carga.csv (na raiz do projeto) e código de saída 1 se houver algum ERRO.
 
import os
import sys
from dataclasses import dataclass, asdict
 
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv
 
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
 
DB = os.getenv('DB_NAME')
if not DB:
    sys.exit("DB_NAME não definido no .env")
 
engine = create_engine(URL.create(
    "mysql+pymysql",
    username=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST', '127.0.0.1'),
    port=int(os.getenv('DB_PORT', '3306')),
    database=DB,
    query={"charset": "utf8mb4"},
))
 
SAIDA_CSV = os.path.join(os.path.dirname(__file__), '..', 'validacao_pos_carga.csv')
 
FONTES_ESPERADAS = ["SSP-SP", "Imprensa", "SINESP", "IBGE-SIDRA"]
 
TABELAS_ESPERADAS = [
    "dim_fonte", "dim_local", "dim_tempo_mes", "dim_regiao_sp", "dim_tipo_ocorrencia",
    "fato_ocorrencias_ssp", "dim_tempo_dia", "dim_vinculo", "dim_arma", "dim_local_crime",
    "dim_atributos_caso", "dim_faixa_etaria", "fato_casos_feminicidio", "fato_populacao",
]
 
# Código IBGE (chave geográfica)
UF_POR_CODIGO = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL", 28: "SE", 29: "BA",
    31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS",
    50: "MS", 51: "MT", 52: "GO", 53: "DF",
}
 
 
def uf_do_prefixo(codigo):
    """UF correspondente aos 2 primeiros dígitos do código IBGE; None se inválido."""
    s = str(codigo)[:2]
    return UF_POR_CODIGO.get(int(s)) if s.isdigit() else None
 
 
def municipios_esperados(ano):
    """Total de municípios do Brasil: 5565 até 2012, 5570 a partir de 2013."""
    return 5565 if int(ano) < 2013 else 5570
 
 
def dv_ibge(codigo6):
    """Dígito verificador do código IBGE de município (pesos 1,2,1,2,1,2)."""
    soma = 0
    for d, w in zip(str(codigo6).zfill(6)[:6], (1, 2, 1, 2, 1, 2)):
        p = int(d) * w
        soma += p - 9 if p > 9 else p
    return (10 - soma % 10) % 10
 
 
def codigo_ibge_valido(codigo):
    s = str(codigo)
    return len(s) == 7 and s.isdigit() and int(s[6]) == dv_ibge(s[:6])
 
 
# Infraestrutura dos checks
@dataclass
class Resultado:
    check: str
    tabela: str
    status: str   # OK | INFO | AVISO | ERRO
    qtd: int
    detalhe: str = ""
 
 
RESULTADOS: list = []
 
 
def q(conn, sql, **params):
    return pd.read_sql(text(sql), conn, params=params)
 
 
def scalar(conn, sql, **params):
    valor = q(conn, sql, **params).iloc[0, 0]
    return 0 if pd.isna(valor) else int(valor)
 
 
def add(check, tabela, qtd, detalhe="", ruim="ERRO"):
    """qtd == 0 -> OK; qtd > 0 -> status `ruim` (ERRO, AVISO ou INFO)."""
    RESULTADOS.append(Resultado(check, tabela, "OK" if qtd == 0 else ruim, int(qtd), detalhe))
 
 
# 1. Volumetria
def check_volumetria(conn):
    for t in TABELAS_ESPERADAS:
        try:
            n = scalar(conn, f"SELECT COUNT(*) FROM `{t}`")
        except Exception as e:  # tabela inexistente não derruba as demais
            RESULTADOS.append(Resultado("tabela_existe", t, "ERRO", 0,
                                        f"não consultável: {str(e)[:80]}"))
            continue
        RESULTADOS.append(Resultado("tabela_populada", t, "OK" if n > 0 else "ERRO", n,
                                    f"{n} linhas" if n else "tabela vazia"))
 
 
# 2. Integridade referencial (FKs lidas do information_schema; suporta FKs compostas)
def check_integridade(conn):
    fks = q(conn, """
        SELECT CONSTRAINT_NAME AS n, ORDINAL_POSITION AS pos,
               TABLE_NAME AS t, COLUMN_NAME AS c,
               REFERENCED_TABLE_NAME AS rt, REFERENCED_COLUMN_NAME AS rc
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = :db AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION""", db=DB)
 
    # Uma entrada por constraint: (tabela filha, tabela pai, [(col_filha, col_pai), ...])
    constraints = []
    for (t, _n), grp in fks.groupby(["t", "n"], sort=False):
        pares = list(zip(grp["c"], grp["rc"]))
        constraints.append((t, grp.iloc[0]["rt"], pares))
 
    # Órfãos: linha filha apontando para pai inexistente
    for t, rt, pares in constraints:
        join = " AND ".join(f"p.`{rc}` = f.`{c}`" for c, rc in pares)
        nao_nulos = " AND ".join(f"f.`{c}` IS NOT NULL" for c, _ in pares)
        n = scalar(conn, f"""
            SELECT COUNT(*) FROM `{t}` f
            LEFT JOIN `{rt}` p ON {join}
            WHERE {nao_nulos} AND p.`{pares[0][1]}` IS NULL""")
        cols_filha = ",".join(c for c, _ in pares)
        cols_pai = ",".join(rc for _, rc in pares)
        add(f"fk_orfa:{cols_filha}->{rt}.{cols_pai}", t, n, f"{n} registro(s) sem pai")
 
    # Dimensões com linhas que nenhuma tabela filha usa
    por_pai = {}
    for t, rt, pares in constraints:
        por_pai.setdefault(rt, []).append((t, pares))
 
    for rt, filhos in por_pai.items():
        condicoes = []
        for t, pares in filhos:
            igual = " AND ".join(f"x.`{c}` = d.`{rc}`" for c, rc in pares)
            condicoes.append(f"NOT EXISTS (SELECT 1 FROM `{t}` x WHERE {igual})")
        n = scalar(conn, f"SELECT COUNT(*) FROM `{rt}` d WHERE {' AND '.join(condicoes)}")
        add("dimensao_sem_uso", rt, n, f"{n} linha(s) nunca referenciada(s)", ruim="INFO")
 
 
# 3. Duplicatas
DUP_CHECKS = {
    "dim_fonte": ["nome_fonte"],
    "dim_local": ["municipio", "estado"],
    "dim_tipo_ocorrencia": ["descricao"],
    "dim_vinculo": ["descricao_vinculo"],
    "dim_arma": ["descricao_arma"],
    "dim_local_crime": ["descricao_cenario"],
    "dim_atributos_caso": ["consumado_tentado", "filhos_dependentes", "periodo_dia"],
    "dim_faixa_etaria": ["faixa_etaria"],
    "dim_regiao_sp": ["nome_regiao"],
    "fato_casos_feminicidio": ["identificador_caso"],
    "dim_tempo_dia": ["ano", "mes", "dia"],
}
 
 
def check_duplicatas(conn):
    for tabela, colunas in DUP_CHECKS.items():
        expressao = ", ".join(f"LOWER(TRIM(CAST(`{c}` AS CHAR)))" for c in colunas)
        n = scalar(conn, f"""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM `{tabela}` GROUP BY {expressao} HAVING COUNT(*) > 1
            ) AS duplicados""")
        add(f"duplicata({', '.join(colunas)})", tabela, n, f"{n} grupo(s) duplicado(s)")
 
    n = scalar(conn, """
        SELECT COUNT(*) FROM (
            SELECT codigo_ibge FROM dim_local
            WHERE codigo_ibge IS NOT NULL
            GROUP BY codigo_ibge HAVING COUNT(*) > 1
        ) AS duplicados""")
    add("codigo_ibge_duplicado", "dim_local", n, f"{n} código(s) IBGE duplicado(s)")
 
    n = scalar(conn, """
        SELECT COUNT(*) FROM (
            SELECT estado, LOWER(TRIM(municipio)) FROM dim_local
            WHERE municipio IS NOT NULL AND estado IS NOT NULL AND codigo_ibge IS NOT NULL
            GROUP BY estado, LOWER(TRIM(municipio))
            HAVING COUNT(DISTINCT codigo_ibge) > 1
        ) AS municipios""")
    exemplos = ""
    if n:
        ex = q(conn, """
            SELECT l.codigo_ibge, l.municipio, l.estado FROM dim_local l
            JOIN (SELECT estado, LOWER(TRIM(municipio)) AS m FROM dim_local
                  GROUP BY estado, LOWER(TRIM(municipio))
                  HAVING COUNT(DISTINCT codigo_ibge) > 1) d
              ON d.estado = l.estado AND d.m = LOWER(TRIM(l.municipio))
            ORDER BY l.estado, l.municipio, l.codigo_ibge""")
        exemplos = ": " + "; ".join(
            f"{r.codigo_ibge} {r.municipio}/{r.estado}" for r in ex.head(15).itertuples())
    add("municipio_com_varios_codigos_ibge", "dim_local", n,
        f"{n} município(s) com códigos diferentes{exemplos}")
 
 
# 4. Nulos e placeholders
PLACEHOLDERS = "('', 'nan', 'none', 'null', 'nat', '<na>', 'n/a')"
 
 
def check_nulos(conn):
    cols_null = q(conn, """
        SELECT TABLE_NAME AS t, COLUMN_NAME AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = :db AND IS_NULLABLE = 'YES'""", db=DB)
    for r in cols_null.itertuples():
        n = scalar(conn, f"SELECT COUNT(*) FROM `{r.t}` WHERE `{r.c}` IS NULL")
        add(f"nulos:{r.c}", r.t, n, f"{n} nulo(s) em coluna anulável", ruim="INFO")
 
    cols_txt = q(conn, """
        SELECT TABLE_NAME AS t, COLUMN_NAME AS c FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = :db AND DATA_TYPE IN ('varchar', 'char')""", db=DB)
    for r in cols_txt.itertuples():
        n = scalar(conn, f"SELECT COUNT(*) FROM `{r.t}` WHERE LOWER(TRIM(`{r.c}`)) IN {PLACEHOLDERS}")
        add(f"placeholder_nulo:{r.c}", r.t, n, f"{n} valor(es) vazio/'nan'/'null'")
        n = scalar(conn, f"SELECT COUNT(*) FROM `{r.t}` "
                         f"WHERE CHAR_LENGTH(`{r.c}`) <> CHAR_LENGTH(TRIM(`{r.c}`))")
        add(f"espacos_nas_pontas:{r.c}", r.t, n, f"{n} valor(es) com espaço sobrando", ruim="AVISO")
 
 
# 5. Chave geográfica (codigo_ibge) e população
def check_codigo_ibge(conn):
    # CAST AS CHAR evita que NULLs transformem a coluna em float64 ("3550308.0")
    loc = q(conn, """SELECT id_local, CAST(codigo_ibge AS CHAR) AS codigo_ibge,
                            municipio, estado FROM dim_local""")
    # nulos já são reportados em check_nulos
    loc = loc[loc["codigo_ibge"].notna()]
    if loc.empty:
        return
    cod = loc["codigo_ibge"].astype(str).str.strip()
 
    sem_7 = int((~cod.str.fullmatch(r"\d{7}", na=False)).sum())
    add("codigo_ibge_7_digitos", "dim_local", sem_7,
        f"{sem_7} código(s) sem 7 dígitos (provável código de 6 dígitos sem DV)")
 
    sete_digitos = cod.str.fullmatch(r"\d{7}", na=False)
    invalidos = loc[sete_digitos & ~cod.map(codigo_ibge_valido)]
    n = len(invalidos)
    add("codigo_ibge_dv_valido", "dim_local", n,
        f"{n} código(s) com dígito verificador inválido; "
        f"exemplos: {invalidos['codigo_ibge'].head(5).tolist()}")
 
    uf_do_codigo = cod.map(uf_do_prefixo)
    uf_registrada = loc["estado"].astype(str).str.upper().str.strip()
    incoerentes = loc[uf_do_codigo != uf_registrada]
    n = len(incoerentes)
    exemplos = ""
    if n:
        exemplos = " (código município/UF registrada, UF do código): " + "; ".join(
            f"{r.codigo_ibge} {r.municipio}/{r.estado}, código={uf_do_prefixo(r.codigo_ibge) or '?'}"
            for r in incoerentes.head(15).itertuples())
    add("uf_coerente_com_codigo_ibge", "dim_local", n,
        f"{n} município(s) cuja UF não bate com o prefixo do código IBGE{exemplos}")
 
 
def check_populacao(conn):
    # todo município com caso precisa ter população
    n = scalar(conn, """
        SELECT COUNT(DISTINCT f.id_local) FROM fato_casos_feminicidio f
        LEFT JOIN fato_populacao p ON p.id_local = f.id_local
        WHERE p.id_local IS NULL""")
    add("municipio_com_caso_sem_populacao", "fato_casos_feminicidio", n,
        f"{n} município(s) com caso e nenhuma população (taxa impossível)")
 
    # cobertura por ano do caso
    cob = q(conn, """
        SELECT t.ano AS ano, COUNT(*) AS total, SUM(p.id_local IS NULL) AS sem_pop
        FROM fato_casos_feminicidio f
        JOIN dim_tempo_dia t ON t.id_tempo = f.id_tempo_dia
        LEFT JOIN fato_populacao p ON p.id_local = f.id_local AND p.ano = t.ano
        GROUP BY t.ano ORDER BY t.ano""")
    cob["sem_pop"] = pd.to_numeric(cob["sem_pop"])
    ruins = cob[cob["sem_pop"] > 0]
    add("caso_sem_populacao_no_mesmo_ano", "fato_casos_feminicidio", int(ruins["sem_pop"].sum()),
        "; ".join(f"{r.ano}: {int(r.sem_pop)}/{int(r.total)}" for r in ruins.itertuples()),
        ruim="AVISO")
 
    # população cobre todos os municípios? (5565 até 2012; 5570 a partir de 2013)
    por_ano = q(conn, "SELECT ano, COUNT(DISTINCT id_local) AS n FROM fato_populacao GROUP BY ano")
    faltando = por_ano[por_ano.apply(lambda r: int(r["n"]) != municipios_esperados(r["ano"]), axis=1)]
    add("populacao_cobre_todos_municipios", "fato_populacao", len(faltando),
        "; ".join(f"{r.ano}: {r.n} (esperado {municipios_esperados(r.ano)})"
                  for r in faltando.itertuples()), ruim="AVISO")
 
    n = scalar(conn, "SELECT COUNT(*) FROM fato_populacao WHERE populacao <= 0")
    add("populacao_positiva", "fato_populacao", n, f"{n} linha(s) com população <= 0")
 
 
# 6. Regras de domínio
def check_dominio(conn):
    # datas
    d = q(conn, "SELECT ano, mes, dia FROM dim_tempo_dia WHERE dia IS NOT NULL")
    if not d.empty:
        dt = pd.to_datetime(dict(year=d.ano, month=d.mes, day=d.dia), errors="coerce")
        add("data_impossivel", "dim_tempo_dia", int(dt.isna().sum()), "ex.: 31/02")
        add("data_futura", "dim_tempo_dia", int((dt > pd.Timestamp.today()).sum()), "", ruim="AVISO")
 
    n = scalar(conn, """
        SELECT COUNT(*) FROM fato_casos_feminicidio f
        JOIN dim_tempo_dia t ON t.id_tempo = f.id_tempo_dia
        JOIN dim_fonte s ON s.id_fonte = f.id_fonte
        WHERE t.dia IS NULL AND s.nome_fonte <> 'SINESP'""")
    add("dia_nulo_fora_do_sinesp", "fato_casos_feminicidio", n,
        "dia nulo só é esperado quando a fonte é SINESP")
 
    n = scalar(conn, "SELECT COUNT(*) FROM dim_tempo_mes WHERE ano < 2000 OR ano > YEAR(CURDATE())")
    add("ano_fora_do_intervalo", "dim_tempo_mes", n, "ano < 2000 ou no futuro", ruim="AVISO")
 
    n = scalar(conn, "SELECT COUNT(*) FROM fato_ocorrencias_ssp WHERE quantidade_ocorrencias < 0")
    add("quantidade_negativa", "fato_ocorrencias_ssp", n, "")
 
    # valores permitidos
    def dominio(tabela, coluna, permitidos):
        df = q(conn, f"SELECT DISTINCT `{coluna}` AS v FROM `{tabela}`")
        fora = sorted(set(df["v"].dropna()) - set(permitidos))
        add(f"dominio:{coluna}", tabela, len(fora), f"fora do esperado: {fora}", ruim="AVISO")
 
    dominio("dim_regiao_sp", "nome_regiao", ["Capital", "Demacro", "Interior"])
    dominio("dim_atributos_caso", "consumado_tentado", ["Consumado", "Tentado"])
    dominio("dim_atributos_caso", "filhos_dependentes", ["Sim", "Não", "Incerto"])
    dominio("dim_atributos_caso", "periodo_dia", ["Manhã", "Tarde", "Noite", "Incerto"])
 
    fx = q(conn, "SELECT faixa_etaria AS v FROM dim_faixa_etaria")["v"].astype(str)
    fora = fx[~fx.str.match(r"^\d+\s*-\s*\d+$|^\d+\+$")].tolist()
    add("formato_faixa_etaria", "dim_faixa_etaria", len(fora),
        f"fora do padrão 'NN-NN': {fora[:10]}", ruim="AVISO")
 
    permitidas = {
        "fato_ocorrencias_ssp": {"SSP-SP"},
        "fato_casos_feminicidio": {"SINESP", "Imprensa"},
        "fato_populacao": {"IBGE-SIDRA"},
    }
    for t, ok in permitidas.items():
        usadas = q(conn, f"""SELECT DISTINCT s.nome_fonte AS v FROM `{t}` f
                             JOIN dim_fonte s ON s.id_fonte = f.id_fonte""")["v"].tolist()
        fora = sorted(set(usadas) - ok)
        add("fonte_coerente_com_a_tabela", t, len(fora), f"fontes inesperadas: {fora}")
 
    nomes = set(q(conn, "SELECT nome_fonte AS v FROM dim_fonte")["v"])
    falta = sorted(set(FONTES_ESPERADAS) - nomes)
    add("dim_fonte_completa", "dim_fonte", len(falta), f"faltando: {falta}")
 
    # municipio é VARCHAR(30) no DDL; INSERT IGNORE trunca em silêncio
    mx = scalar(conn, "SELECT COALESCE(MAX(CHAR_LENGTH(municipio)), 0) FROM dim_local")
    add("municipio_no_limite_do_varchar", "dim_local", int(mx >= 30),
        f"maior nome tem {mx} caracteres (limite 30): risco de truncar", ruim="AVISO")
 
 
def validar(engine, saida_csv=SAIDA_CSV):
    RESULTADOS.clear()
    with engine.connect() as conn:
        # check_codigo_ibge e check_populacao são independentes: a falha ou o
        # vazio de um não impede o outro de rodar.
        for fn in (check_volumetria, check_integridade, check_duplicatas,
                   check_nulos, check_codigo_ibge, check_populacao, check_dominio):
            try:
                fn(conn)
            except Exception as e:
                RESULTADOS.append(Resultado(fn.__name__, "-", "ERRO", 0,
                                            f"falha ao executar: {e}"))
 
    df = pd.DataFrame(asdict(r) for r in RESULTADOS)
    df.to_csv(saida_csv, index=False, encoding="utf-8-sig")
 
    pd.set_option("display.width", 220, "display.max_colwidth", 90, "display.max_rows", 500)
    problemas = df[df["status"] != "OK"]
    print(problemas.to_string(index=False) if len(problemas) else "Nenhum problema encontrado.")
    print(f"\nResumo: {df['status'].value_counts().to_dict()}  |  relatório completo em {os.path.abspath(saida_csv)}")
    return 1 if (df["status"] == "ERRO").any() else 0
 
 
if __name__ == "__main__":
    try:
        sys.exit(validar(engine))
    finally:
        engine.dispose()
 
