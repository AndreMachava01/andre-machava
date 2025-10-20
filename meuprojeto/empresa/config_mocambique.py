"""
Configurações específicas para Moçambique
"""

# Tipos societários comuns em Moçambique
TIPOS_SOCIETARIOS_MOZ = [
    ('SA', 'Sociedade Anónima'),
    ('LDA', 'Sociedade por Quotas'),
    ('SU', 'Sociedade Unipessoal'),
    ('ENI', 'Empresário em Nome Individual'),
    ('SC', 'Sociedade em Comandita'),
    ('SNC', 'Sociedade em Nome Colectivo'),
    ('COOP', 'Cooperativa'),
    ('ONG', 'Organização Não Governamental'),
    ('FUNDACAO', 'Fundação'),
    ('ASSOCIACAO', 'Associação'),
]

# Actividades económicas principais em Moçambique
ACTIVIDADES_ECONOMICAS = [
    ('AGRICULTURA', 'Agricultura, Pecuária e Pesca'),
    ('MINERACAO', 'Extracção de Minerais'),
    ('INDUSTRIA', 'Indústria Transformadora'),
    ('CONSTRUCAO', 'Construção Civil'),
    ('COMERCIO', 'Comércio por Grosso e Retalho'),
    ('HOTELARIA', 'Alojamento e Restauração'),
    ('TRANSPORTES', 'Transportes e Armazenagem'),
    ('INFORMACAO', 'Tecnologias de Informação e Comunicação'),
    ('FINANCEIRO', 'Actividades Financeiras e Seguros'),
    ('IMOBILIARIO', 'Actividades Imobiliárias'),
    ('PROFISSIONAL', 'Actividades Profissionais e Técnicas'),
    ('ADMINISTRATIVO', 'Actividades Administrativas'),
    ('EDUCACAO', 'Educação'),
    ('SAUDE', 'Actividades de Saúde'),
    ('CULTURAL', 'Actividades Artísticas e Culturais'),
    ('DESPORTO', 'Actividades Desportivas e Recreativas'),
    ('OUTRAS', 'Outras Actividades de Serviços'),
]

# Códigos de área telefónica moçambicana
CODIGOS_AREA_TELEFONE = {
    'MP': '+258 21',  # Maputo Cidade
    'MA': '+258 21',  # Maputo Província
    'GA': '+258 28',  # Gaza
    'IN': '+258 29',  # Inhambane
    'MN': '+258 25',  # Manica
    'SO': '+258 23',  # Sofala
    'ZA': '+258 24',  # Zambézia
    'TE': '+258 25',  # Tete
    'NA': '+258 26',  # Nampula
    'NI': '+258 27',  # Niassa
    'CD': '+258 27',  # Cabo Delgado
}

# Moeda e formatação
MOEDA = 'MZN'
SIMBOLO_MOEDA = 'MT'
FORMATO_MOEDA = '{:,.2f} MT'

# Feriados nacionais de Moçambique (2024)
FERIADOS_NACIONAIS = [
    '2024-01-01',  # Dia de Ano Novo
    '2024-02-03',  # Dia dos Heróis Moçambicanos
    '2024-04-07',  # Dia da Mulher Moçambicana
    '2024-04-19',  # Sexta-feira Santa
    '2024-04-22',  # Segunda-feira de Páscoa
    '2024-05-01',  # Dia do Trabalhador
    '2024-06-25',  # Dia da Independência
    '2024-09-07',  # Dia da Vitória
    '2024-09-25',  # Dia das Forças Armadas
    '2024-10-04',  # Dia da Paz e Reconciliação
    '2024-12-25',  # Natal
]

# Configurações de localização
LOCALE = 'pt_MZ'
TIMEZONE = 'Africa/Maputo'
DATE_FORMAT = '%d/%m/%Y'
DATETIME_FORMAT = '%d/%m/%Y %H:%M'

# Validações específicas
VALIDACOES = {
    'nuit_length': 9,
    'telefone_length': 9,
    'telefone_prefixes': ['8', '2'],
    'alvara_format': r'^[A-Z]{2,3}\d{6,8}$',
    'registro_comercial_format': r'^\d{6,10}$',
}

# Mensagens em português de Moçambique
MENSAGENS = {
    'empresa_criada': 'Empresa registada com sucesso!',
    'sucursal_criada': 'Sucursal criada automaticamente.',
    'nuit_invalido': 'NUIT inválido. Deve conter 9 dígitos.',
    'telefone_invalido': 'Número de telefone inválido. Use o formato: +258XXXXXXXXX',
    'provincia_obrigatoria': 'Província é obrigatória.',
    'cidade_obrigatoria': 'Cidade é obrigatória.',
}


