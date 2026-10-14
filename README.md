# DW Violência contra a Mulher

Trabalho prático da disciplina de Business Intelligence.

## Integrantes

- Ana Giulia Ferreira de Abreu
- Fernanda Soares Santos Paiva
- Gabriela de Souza Konig
- Miguel Oliveira Faria
- Sther Marinho Brito

## Como rodar

### 1. Criar o banco
Execute o script SQL no MySQL:
```sql
SOURCE sql/criacao_DW_etapa_3.sql;
```

### 2. Configurar o ambiente
```bash
pip install pandas openpyxl sqlalchemy pymysql python-dotenv pytest
cp .env.example .env
# edite o .env com sua senha do MySQL
```

### 3. Rodar os testes
```bash
python -m pytest testes/ -v
```

### 4. Rodar o ETL
```bash
python etl/etl_lesfem_geografico.py
```

## Fontes de dados

- **Lesfem** — casos de feminicídio (Base-de-dados-2025_v1.xlsx)
- **SSP-SP** — ocorrências registradas no estado de São Paulo
- **IBGE/SIDRA** — dados populacionais por município
