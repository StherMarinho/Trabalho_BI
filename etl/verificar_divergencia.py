import sys, os
sys.path.insert(0, 'etl')
from lesfem_loader import carregar_lesfem

df = carregar_lesfem()
municipios = df[['Código do município', 'Município', 'Estado']].drop_duplicates()

# Municípios com mesmo codigo_ibge mas nome/estado diferente
duplicados = municipios[municipios.duplicated(subset=['Código do município'], keep=False)]
print(duplicados.sort_values('Código do município').to_string())