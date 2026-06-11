from django import template
from decimal import Decimal

register = template.Library()

@register.filter(name='formatar_codigo_ordem')
def formatar_codigo_ordem(codigo):
    """
    Formata o código da ordem para exibição
    Exemplo: 'OS-2023-0001' -> 'OS/2023/0001'
    """
    if not codigo:
        return ""
    return codigo.replace('-', '/')

@register.filter(name='valor_total_servico')
def valor_total_servico(servico):
    """
    Calcula o valor total do serviço incluindo itens
    """
    total = servico.valor_total
    if hasattr(servico, 'itens'):
        for item in servico.itens.all():
            if hasattr(item, 'valor_total'):
                total += item.valor_total
    return total

@register.filter
def formatar_codigo_ordem_antigo(codigo):
    """Formata código de ordem de serviço ou cotação do formato antigo para o novo"""
    if not codigo:
        return codigo
    
    # Se já está no formato novo (tem hífen), retornar como está
    if '-' in codigo:
        return codigo
    
    # Se é muito curto, retornar como está
    if len(codigo) <= 10:
        return codigo
    
    # Formatar código antigo OS2025110001 para OS-2025-000001
    if codigo.startswith('OS') or codigo.startswith('COT'):
        prefixo = codigo[:2] if codigo.startswith('OS') else codigo[:3]
        resto = codigo[len(prefixo):]
        
        if len(resto) >= 8:
            # Formato antigo: OS2025110001 (OS + ano4 + mes2 + numero4)
            ano = resto[:4]
            mes = resto[4:6]
            numero_antigo = resto[6:]  # 4 dígitos do formato antigo
            # Converter para formato novo: OS-2025-000001 (ignorar mês, usar número como está)
            return f"{prefixo}-{ano}-{numero_antigo.zfill(6)}"
        elif len(resto) >= 4:
            # Formato alternativo: apenas ano + número
            ano = resto[:4]
            numero = resto[4:]
            return f"{prefixo}-{ano}-{numero.zfill(6)}"
    
    # Se não corresponde a nenhum padrão conhecido, retornar como está
    return codigo


# Mapeamento de códigos de unidade para forma empírica (símbolos/abreviações)
UNIDADE_EMPIRICA = {
    'UN': 'un',
    'HR': 'h',
    'DIA': 'dia',
    'SEM': 'sem',
    'MES': 'mês',
    'PROJ': 'proj',
    'PISO': 'piso',
    'KG': 'kg',
    'G': 'g',
    'L': 'L',
    'ML': 'ml',
    'M': 'm',
    'CM': 'cm',
    'M2': 'm²',
    'M3': 'm³',
    'CX': 'cx',
    'PC': 'pc',
    'DZ': 'dz',
    'GR': 'gr',
    'ROL': 'rol',
    'FOL': 'fol',
    'BAR': 'bar',
    'TUB': 'tub',
}


@register.filter(name='unidade_empirica')
def unidade_empirica(unidade_medida):
    """Converte código de unidade de medida para forma empírica (ex: M2 -> m², UN -> un)"""
    if not unidade_medida:
        return 'un'
    return UNIDADE_EMPIRICA.get(str(unidade_medida).upper(), str(unidade_medida).lower())


