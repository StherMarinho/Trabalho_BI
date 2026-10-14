CREATE DATABASE dw_violencia_mulher;
USE dw_violencia_mulher;

-- DIMENSÕES COMPARTILHADAS

CREATE TABLE dim_fonte (
    id_fonte     INT AUTO_INCREMENT PRIMARY KEY,
    nome_fonte   VARCHAR(30)  NOT NULL,   -- 'SSP-SP', 'Imprensa', 'SINESP'
    tipo_base    VARCHAR(30)  NOT NULL    -- 'Oficial', 'Jornalística'
);

CREATE TABLE dim_local (
    id_local     INT AUTO_INCREMENT PRIMARY KEY,
    codigo_ibge  INT NOT NULL,
    municipio    VARCHAR(30) NOT NULL,
    estado       VARCHAR(2)   NOT NULL,
    UNIQUE KEY uq_dim_local_ibge (codigo_ibge)
);

-- DIMENSÕES E FATO: FATO_OCORRENCIAS_SSP

CREATE TABLE dim_tempo_mes (
    id_tempo  INT AUTO_INCREMENT PRIMARY KEY,
    ano       INT NOT NULL,
    mes       INT NOT NULL,
    UNIQUE KEY uq_dim_tempo_mes (ano, mes),
    CONSTRAINT chk_dim_tempo_mes_mes CHECK (mes BETWEEN 1 AND 12)
);

CREATE TABLE dim_regiao_sp (
    id_regiao    INT AUTO_INCREMENT PRIMARY KEY,
    nome_regiao  VARCHAR(20) NOT NULL,   -- 'Capital', 'Demacro', 'Interior'
    UNIQUE KEY uq_dim_regiao_sp (nome_regiao)
);

CREATE TABLE dim_tipo_ocorrencia (
    id_tipo_ocorrencia  INT AUTO_INCREMENT PRIMARY KEY,
    descricao           VARCHAR(100) NOT NULL,  -- atômica, sem subtotais
    categoria_agregada  VARCHAR(50)  NOT NULL  -- recompor subtotais originais
);

CREATE TABLE fato_ocorrencias_ssp (
    id_fato               INT AUTO_INCREMENT PRIMARY KEY,
    id_tempo_mes          INT NOT NULL,
    id_regiao             INT NOT NULL,
    id_tipo_ocorrencia    INT NOT NULL,
    id_fonte              INT NOT NULL,
    quantidade_ocorrencias INT NOT NULL,
    CONSTRAINT fk_fossp_tempo    FOREIGN KEY (id_tempo_mes)       REFERENCES dim_tempo_mes (id_tempo),
    CONSTRAINT fk_fossp_regiao   FOREIGN KEY (id_regiao)          REFERENCES dim_regiao_sp (id_regiao),
    CONSTRAINT fk_fossp_tipo     FOREIGN KEY (id_tipo_ocorrencia) REFERENCES dim_tipo_ocorrencia (id_tipo_ocorrencia),
    CONSTRAINT fk_fossp_fonte    FOREIGN KEY (id_fonte)           REFERENCES dim_fonte (id_fonte),
    UNIQUE KEY uq_fossp_grao (id_tempo_mes, id_regiao, id_tipo_ocorrencia, id_fonte)
);

-- DIMENSÕES E FATO: FATO_CASOS_FEMINICIDIO


CREATE TABLE dim_tempo_dia (
    id_tempo  INT AUTO_INCREMENT PRIMARY KEY,
    ano       INT NOT NULL,
    mes       INT NOT NULL,
    dia       INT NULL,     -- pode ficar nulo quando a fonte é o SINESP
    UNIQUE KEY uq_dim_tempo_dia (ano, mes, dia),
    CONSTRAINT chk_dim_tempo_dia_mes CHECK (mes BETWEEN 1 AND 12),
    CONSTRAINT chk_dim_tempo_dia_dia CHECK (dia IS NULL OR dia BETWEEN 1 AND 31)
);

CREATE TABLE dim_vinculo (
    id_vinculo         INT AUTO_INCREMENT PRIMARY KEY,
    descricao_vinculo  VARCHAR(100) NOT NULL
);

CREATE TABLE dim_arma (
    id_arma         INT AUTO_INCREMENT PRIMARY KEY,
    descricao_arma  VARCHAR(100) NOT NULL
);

CREATE TABLE dim_local_crime (
    id_local_crime     INT AUTO_INCREMENT PRIMARY KEY,
    descricao_cenario  VARCHAR(100) NOT NULL
);

CREATE TABLE dim_atributos_caso (
    id_atributos_caso    INT AUTO_INCREMENT PRIMARY KEY,
    consumado_tentado    VARCHAR(10) NOT NULL,  -- 'Consumado', 'Tentado'
    filhos_dependentes   VARCHAR(10) NOT NULL,  -- 'Sim', 'Não', 'Incerto'
    periodo_dia          VARCHAR(10) NOT NULL  -- 'Manhã', 'Tarde', 'Noite', 'Incerto'
);

CREATE TABLE dim_faixa_etaria (
    id_faixa      INT AUTO_INCREMENT PRIMARY KEY,
    faixa_etaria  VARCHAR(20) NOT NULL -- '10-20', '20-30', '30-40' ...
);

CREATE TABLE fato_casos_feminicidio (
    id_fato             INT AUTO_INCREMENT PRIMARY KEY,
    identificador_caso  VARCHAR(60) NOT NULL,   -- chave natural da fonte (LESFEM)
    id_tempo_dia        INT NOT NULL,
    id_local            INT NOT NULL,
    id_vinculo          INT NOT NULL,
    id_arma             INT NOT NULL,
    id_local_crime      INT NOT NULL,
    id_atributos_caso   INT NOT NULL,
    id_fonte            INT NOT NULL,
    id_faixa_vitima     INT NOT NULL,
    id_faixa_agressor   INT NOT NULL,
    CONSTRAINT fk_fcf_tempo      FOREIGN KEY (id_tempo_dia)      REFERENCES dim_tempo_dia (id_tempo),
    CONSTRAINT fk_fcf_local      FOREIGN KEY (id_local)          REFERENCES dim_local (id_local),
    CONSTRAINT fk_fcf_vinculo    FOREIGN KEY (id_vinculo)        REFERENCES dim_vinculo (id_vinculo),
    CONSTRAINT fk_fcf_arma       FOREIGN KEY (id_arma)           REFERENCES dim_arma (id_arma),
    CONSTRAINT fk_fcf_cenario    FOREIGN KEY (id_local_crime)    REFERENCES dim_local_crime (id_local_crime),
    CONSTRAINT fk_fcf_atributos  FOREIGN KEY (id_atributos_caso) REFERENCES dim_atributos_caso (id_atributos_caso),
    CONSTRAINT fk_fcf_fonte      FOREIGN KEY (id_fonte)          REFERENCES dim_fonte (id_fonte),
    CONSTRAINT fk_fcf_faixa_vit  FOREIGN KEY (id_faixa_vitima)   REFERENCES dim_faixa_etaria (id_faixa),
    CONSTRAINT fk_fcf_faixa_agr  FOREIGN KEY (id_faixa_agressor) REFERENCES dim_faixa_etaria (id_faixa)
);

-- AUXILIAR: FATO_POPULACAO

CREATE TABLE fato_populacao (
    id_fato_populacao  INT AUTO_INCREMENT PRIMARY KEY,
    id_local           INT NOT NULL,
    ano                INT NOT NULL,
    populacao          INT NOT NULL,
    id_fonte           INT NOT NULL,
    CONSTRAINT fk_fpop_local  FOREIGN KEY (id_local) REFERENCES dim_local (id_local),
    CONSTRAINT fk_fpop_fonte  FOREIGN KEY (id_fonte) REFERENCES dim_fonte (id_fonte),
    UNIQUE KEY uq_fpop_grao (id_local, ano, id_fonte)
);