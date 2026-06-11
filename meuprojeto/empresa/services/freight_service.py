"""
Cálculo de distância e frete para operações logísticas.
Integra geolocalização com tarifas de transportadoras externas e veículos internos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from .pricing import PricingItem, calculate_quote, calculate_freight_veiculo_interno


# Coordenadas aproximadas de cidades moçambicanas (fallback)
COORDS_CIDADES_MOZ: Dict[str, Tuple[Decimal, Decimal]] = {
    'maputo': (Decimal('-25.969248'), Decimal('32.573924')),
    'matola': (Decimal('-25.962222'), Decimal('32.458889')),
    'machava': (Decimal('-25.976000'), Decimal('32.446000')),
    'beira': (Decimal('-19.833333'), Decimal('34.850000')),
    'nampula': (Decimal('-15.116667'), Decimal('39.266667')),
    'pemba': (Decimal('-12.973953'), Decimal('40.517801')),
    'quelimane': (Decimal('-17.850000'), Decimal('36.883333')),
    'tete': (Decimal('-16.156389'), Decimal('33.586667')),
    'chimoio': (Decimal('-19.116667'), Decimal('33.483333')),
    'xai-xai': (Decimal('-25.050000'), Decimal('33.633333')),
    'inhambane': (Decimal('-23.865000'), Decimal('35.383333')),
    'lichinga': (Decimal('-13.312778'), Decimal('35.240556')),
    'maxixe': (Decimal('-23.859722'), Decimal('35.347222')),
}

COORDS_PROVINCIAS_MOZ: Dict[str, Tuple[Decimal, Decimal]] = {
    'maputo': (Decimal('-25.969248'), Decimal('32.573924')),
    'maputo cidade': (Decimal('-25.969248'), Decimal('32.573924')),
    'gaza': (Decimal('-25.050000'), Decimal('33.633333')),
    'inhambane': (Decimal('-23.865000'), Decimal('35.383333')),
    'sofala': (Decimal('-19.833333'), Decimal('34.850000')),
    'manica': (Decimal('-19.116667'), Decimal('33.483333')),
    'tete': (Decimal('-16.156389'), Decimal('33.586667')),
    'zambezia': (Decimal('-17.850000'), Decimal('36.883333')),
    'nampula': (Decimal('-15.116667'), Decimal('39.266667')),
    'niassa': (Decimal('-13.312778'), Decimal('35.240556')),
    'cabo delgado': (Decimal('-12.973953'), Decimal('40.517801')),
}

# Códigos de província (Provincia.choices) → chave do catálogo
PROVINCIA_CODIGO_CATALOGO: Dict[str, str] = {
    'mp': 'maputo',
    'ma': 'matola',
    'ga': 'xai-xai',
    'in': 'inhambane',
    'mn': 'chimoio',
    'so': 'beira',
    'za': 'quelimane',
    'te': 'tete',
    'na': 'nampula',
    'ni': 'lichinga',
    'cd': 'pemba',
}

CENTRO_MOZAMBIQUE = (Decimal('-18.665695'), Decimal('35.529562'))
PESO_PADRAO_KG = Decimal('1.000')
CUSTO_FIXO_ENTREGA_INTERNA = Decimal('20.00')
TIPOS_VIATURA_INTERNA = frozenset({'VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO'})
TIPOS_TRANSPORTADORA_EXTERNA = frozenset({
    'TRANSPORTADORA', 'ENTREGA_RAPIDA', 'CORREIOS', 'MOTORISTA', 'TERCEIRIZADA',
})
TIPO_VIATURA_INTERNA_LEGADO = 'VIATURA_INTERNA'


def is_viatura_interna(obj) -> bool:
    tipo = getattr(obj, 'tipo', None)
    codigo = getattr(obj, 'codigo', '') or ''
    return tipo in TIPOS_VIATURA_INTERNA or tipo == TIPO_VIATURA_INTERNA_LEGADO or codigo.upper().startswith('VIAT')


def queryset_transportadoras_externas():
    from ..models_stock import Transportadora

    return Transportadora.objects.filter(
        tipo__in=TIPOS_TRANSPORTADORA_EXTERNA,
        status='ATIVA',
        ativa=True,
    ).exclude(codigo__istartswith='VIAT').order_by('nome')


def queryset_viaturas_internas_catalogo():
    from django.db.models import Q
    from ..models_stock import Transportadora

    return Transportadora.objects.filter(
        Q(tipo__in=TIPOS_VIATURA_INTERNA)
        | Q(tipo=TIPO_VIATURA_INTERNA_LEGADO)
        | Q(codigo__istartswith='VIAT'),
        status='ATIVA',
        ativa=True,
    ).order_by('nome')


def opcoes_filtro_viatura_interna():
    """Frota (VeiculoInterno) + viaturas no catálogo Transportadora, sem duplicar código."""
    from ..models_stock import VeiculoInterno

    opcoes = []
    codigos_vistos = set()
    for v in VeiculoInterno.objects.filter(ativo=True, status='ATIVO').order_by('nome'):
        codigos_vistos.add((v.codigo or '').upper())
        opcoes.append({'value': f'vi:{v.pk}', 'label': f'{v.codigo} — {v.nome}'})
    for t in queryset_viaturas_internas_catalogo():
        if (t.codigo or '').upper() in codigos_vistos:
            continue
        opcoes.append({'value': f'vt:{t.pk}', 'label': f'{t.codigo} — {t.nome}'})
    return opcoes


def resolver_filtro_viatura_interna(valor: str) -> Dict[str, str]:
    from ..models_stock import Transportadora, VeiculoInterno

    if not valor:
        return {}
    if valor.startswith('vi:'):
        veiculo = VeiculoInterno.objects.filter(pk=valor[3:]).first()
        return {'veiculo_interno': veiculo.nome} if veiculo else {}
    if valor.startswith('vt:'):
        viatura = Transportadora.objects.filter(pk=valor[3:]).first()
        return {'transportadora': viatura.nome} if viatura else {}
    return {}


def _buscar_viatura_interna_por_veiculo(veiculo_interno):
    """Compatibilidade: localiza tarifas de viatura interna (Transportadora) pelo nome/placa."""
    if not veiculo_interno:
        return None
    try:
        from ..models_stock import Transportadora
    except Exception:
        return None

    nome = (getattr(veiculo_interno, 'nome', '') or '').strip()
    placa = (getattr(veiculo_interno, 'placa', '') or '').strip()
    qs = Transportadora.objects.filter(tipo__in=TIPOS_VIATURA_INTERNA, status='ATIVA')
    if placa and placa != 'N/A':
        viatura = qs.filter(placa__iexact=placa).first()
        if viatura:
            return viatura
    if nome:
        viatura = qs.filter(nome__iexact=nome).first()
        if viatura:
            return viatura
        viatura = qs.filter(nome__icontains=nome).first()
        if viatura:
            return viatura
    return None


@dataclass
class PontoLogistico:
    label: str
    cidade: str
    provincia: str
    endereco: str
    latitude: Decimal
    longitude: Decimal
    fonte: str


@dataclass
class DistanciaResult:
    distancia_km: Decimal
    origem: PontoLogistico
    destino: PontoLogistico
    tempo_estimado_minutos: int = 0


@dataclass
class CargaEstimativa:
    peso_kg: Decimal
    comprimento_cm: Decimal
    largura_cm: Decimal
    altura_cm: Decimal


@dataclass
class CargaParams:
    usar_peso: bool = False
    usar_dimensoes: bool = False
    peso_kg: Decimal = Decimal('0')
    comprimento_cm: Decimal = Decimal('0')
    largura_cm: Decimal = Decimal('0')
    altura_cm: Decimal = Decimal('0')
    volume_m3: Optional[Decimal] = None


@dataclass
class FreightResult:
    total_cost: Decimal
    distancia_km: Decimal
    peso_kg: Decimal
    currency: str = 'MZN'
    breakdown: Dict[str, float] = field(default_factory=dict)
    origem_label: str = ''
    destino_label: str = ''
    carga: Optional[CargaParams] = None


def _normalizar_chave(texto: str) -> str:
    if not texto:
        return ''
    return ' '.join(texto.strip().lower().split())


def _buscar_endereco_normalizado(cidade: str, provincia: str):
    try:
        from ..models_geolocation import EnderecoNormalizado
    except Exception:
        return None

    try:
        qs = EnderecoNormalizado.objects.filter(ativo=True)
        if cidade:
            qs = qs.filter(cidade__iexact=cidade.strip())
        if provincia:
            qs = qs.filter(estado__iexact=provincia.strip())
        return qs.order_by('-validado', '-nivel_confianca').first()
    except Exception:
        return None


def _buscar_regiao(provincia: str, cidade: str):
    try:
        from ..models_masterdata import Regiao
    except Exception:
        return None

    try:
        qs = Regiao.objects.filter(ativo=True)
        if provincia:
            qs = qs.filter(provincia__icontains=provincia.strip())
        if cidade:
            regiao = qs.filter(distrito__icontains=cidade.strip()).first()
            if regiao:
                return regiao
        return qs.filter(latitude_centro__isnull=False).first()
    except Exception:
        return None


def resolver_coordenadas(
    label: str,
    cidade: str,
    provincia: str,
    endereco: str = '',
) -> PontoLogistico:
    """Resolve coordenadas a partir de endereço normalizado, região ou catálogo local."""
    endereco_norm = _buscar_endereco_normalizado(cidade, provincia)
    if endereco_norm:
        return PontoLogistico(
            label=label,
            cidade=cidade or endereco_norm.cidade,
            provincia=provincia or endereco_norm.estado,
            endereco=endereco or endereco_norm.endereco_normalizado,
            latitude=endereco_norm.latitude,
            longitude=endereco_norm.longitude,
            fonte='endereco_normalizado',
        )

    regiao = _buscar_regiao(provincia, cidade)
    if regiao and regiao.latitude_centro is not None and regiao.longitude_centro is not None:
        return PontoLogistico(
            label=label,
            cidade=cidade or regiao.distrito or regiao.nome,
            provincia=provincia or regiao.provincia,
            endereco=endereco or regiao.nome,
            latitude=regiao.latitude_centro,
            longitude=regiao.longitude_centro,
            fonte='regiao_masterdata',
        )

    chave_cidade = _normalizar_chave(cidade)
    if chave_cidade in COORDS_CIDADES_MOZ:
        lat, lon = COORDS_CIDADES_MOZ[chave_cidade]
        return PontoLogistico(
            label=label,
            cidade=cidade,
            provincia=provincia,
            endereco=endereco,
            latitude=lat,
            longitude=lon,
            fonte='catalogo_cidade',
        )

    texto = _normalizar_chave(f'{label} {endereco} {cidade} {provincia}')
    for nome, coords in COORDS_CIDADES_MOZ.items():
        if nome in texto:
            lat, lon = coords
            return PontoLogistico(
                label=label,
                cidade=cidade or nome.title(),
                provincia=provincia,
                endereco=endereco,
                latitude=lat,
                longitude=lon,
                fonte='catalogo_texto',
            )

    chave_prov = _normalizar_chave(provincia)
    if chave_prov in PROVINCIA_CODIGO_CATALOGO:
        nome_cat = PROVINCIA_CODIGO_CATALOGO[chave_prov]
        if nome_cat in COORDS_CIDADES_MOZ:
            lat, lon = COORDS_CIDADES_MOZ[nome_cat]
            return PontoLogistico(
                label=label,
                cidade=cidade or nome_cat.title(),
                provincia=provincia,
                endereco=endereco,
                latitude=lat,
                longitude=lon,
                fonte='catalogo_provincia_codigo',
            )

    if chave_prov in COORDS_PROVINCIAS_MOZ:
        lat, lon = COORDS_PROVINCIAS_MOZ[chave_prov]
        return PontoLogistico(
            label=label,
            cidade=cidade or provincia,
            provincia=provincia,
            endereco=endereco,
            latitude=lat,
            longitude=lon,
            fonte='catalogo_provincia',
        )

    lat, lon = CENTRO_MOZAMBIQUE
    return PontoLogistico(
        label=label,
        cidade=cidade or '—',
        provincia=provincia or '—',
        endereco=endereco,
        latitude=lat,
        longitude=lon,
        fonte='fallback_nacional',
    )


def calcular_distancia_km(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> Decimal:
    import math

    lat1_f = math.radians(float(lat1))
    lon1_f = math.radians(float(lon1))
    lat2_f = math.radians(float(lat2))
    lon2_f = math.radians(float(lon2))
    dlat = lat2_f - lat1_f
    dlon = lon2_f - lon1_f
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_f) * math.cos(lat2_f) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distancia = 6371.0 * c
    return Decimal(str(round(distancia, 3)))


def pontos_operacao(notificacao) -> Tuple[PontoLogistico, PontoLogistico]:
    if notificacao.tipo_operacao == 'TRANSFERENCIA':
        origem = notificacao.transferencia.sucursal_origem
        destino = notificacao.transferencia.sucursal_destino
        ponto_origem = resolver_coordenadas(
            label=origem.nome,
            cidade=origem.cidade,
            provincia=str(origem.provincia),
            endereco=origem.endereco,
        )
        ponto_destino = resolver_coordenadas(
            label=destino.nome,
            cidade=destino.cidade,
            provincia=str(destino.provincia),
            endereco=destino.endereco,
        )
    else:
        fornecedor = notificacao.ordem_compra.fornecedor
        destino = notificacao.ordem_compra.sucursal_destino
        ponto_origem = resolver_coordenadas(
            label=fornecedor.nome,
            cidade=fornecedor.cidade or '',
            provincia=fornecedor.provincia or '',
            endereco=fornecedor.endereco or '',
        )
        ponto_destino = resolver_coordenadas(
            label=destino.nome,
            cidade=destino.cidade,
            provincia=str(destino.provincia),
            endereco=destino.endereco,
        )
    return ponto_origem, ponto_destino


def _quantidade_item_carga(item) -> Decimal:
    """Quantidade efectiva do item para estimativa de peso/volume."""
    recebida = getattr(item, 'quantidade_recebida', None)
    solicitada = getattr(item, 'quantidade_solicitada', None)
    if solicitada is not None:
        if recebida is not None and recebida > 0:
            return Decimal(str(recebida))
        return Decimal(str(solicitada))
    qtd = getattr(item, 'quantidade', None)
    if qtd is not None:
        return Decimal(str(qtd))
    return Decimal('0')


def estimar_peso_kg(notificacao) -> Decimal:
    if notificacao.tipo_operacao == 'TRANSFERENCIA':
        itens = getattr(notificacao.transferencia, 'itens', None)
        if itens is not None:
            total = sum((_quantidade_item_carga(item) for item in itens.all()), Decimal('0'))
            if total > 0:
                return max(PESO_PADRAO_KG, total)
    else:
        itens = getattr(notificacao.ordem_compra, 'itens', None)
        if itens is not None:
            total = sum((_quantidade_item_carga(item) for item in itens.all()), Decimal('0'))
            if total > 0:
                return max(PESO_PADRAO_KG, total)
    return PESO_PADRAO_KG


def estimar_dimensoes_cm(notificacao) -> Tuple[Decimal, Decimal, Decimal]:
    """Dimensões padrão do volume (cm); escala levemente com quantidade de itens."""
    comprimento = Decimal('30.00')
    largura = Decimal('20.00')
    altura = Decimal('10.00')
    try:
        from ..models_masterdata import ConfiguracaoMasterdata
        cfg = ConfiguracaoMasterdata.objects.filter(padrao=True, ativo=True).first()
        if cfg:
            comprimento = Decimal(str(cfg.dimensao_padrao_comprimento))
            largura = Decimal(str(cfg.dimensao_padrao_largura))
            altura = Decimal(str(cfg.dimensao_padrao_altura))
    except Exception:
        pass

    qtd_itens = Decimal('1')
    if notificacao.tipo_operacao == 'TRANSFERENCIA':
        itens = getattr(notificacao.transferencia, 'itens', None)
        if itens is not None:
            qtd_itens = max(Decimal('1'), sum((_quantidade_item_carga(item) for item in itens.all()), Decimal('0')))
    else:
        itens = getattr(notificacao.ordem_compra, 'itens', None)
        if itens is not None:
            qtd_itens = max(
                Decimal('1'),
                sum((_quantidade_item_carga(item) for item in itens.all()), Decimal('0')),
            )

    if qtd_itens > 1:
        fator = min(Decimal('3'), Decimal('1') + (qtd_itens - 1) * Decimal('0.15'))
        comprimento = (comprimento * fator).quantize(Decimal('0.01'))
        largura = (largura * fator).quantize(Decimal('0.01'))
        altura = (altura * fator).quantize(Decimal('0.01'))

    return comprimento, largura, altura


def estimar_carga(notificacao) -> CargaEstimativa:
    comp, larg, alt = estimar_dimensoes_cm(notificacao)
    return CargaEstimativa(
        peso_kg=estimar_peso_kg(notificacao),
        comprimento_cm=comp,
        largura_cm=larg,
        altura_cm=alt,
    )


def _parse_bool(value) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    texto = str(value).strip().lower()
    return texto in ('1', 'true', 'on', 'yes', 'sim')


def parse_peso_kg(value) -> Optional[Decimal]:
    if value is None:
        return None
    texto = str(value).strip().replace(',', '.')
    if not texto:
        return None
    try:
        peso = Decimal(texto)
    except Exception:
        return None
    return peso if peso >= 0 else None


def parse_dimensao_cm(value) -> Optional[Decimal]:
    return parse_peso_kg(value)


def parse_volume_m3(value) -> Optional[Decimal]:
    """Volume em metros cúbicos (m³)."""
    return parse_peso_kg(value)


def dimensoes_cubo_from_volume_m3(volume_m3: Decimal) -> Tuple[Decimal, Decimal, Decimal]:
    """Converte m³ num cubo equivalente (lado em cm) para peso volumétrico."""
    if volume_m3 <= 0:
        return Decimal('0'), Decimal('0'), Decimal('0')
    cm3 = float(volume_m3) * 1_000_000.0
    lado = round(cm3 ** (1.0 / 3.0), 1)
    aresta = Decimal(str(lado))
    return aresta, aresta, aresta


def resolver_carga_params(
    notificacao,
    *,
    usar_peso=None,
    peso_kg_manual=None,
    usar_dimensoes=None,
    volume_m3_manual=None,
    comprimento_cm_manual=None,
    largura_cm_manual=None,
    altura_cm_manual=None,
) -> CargaParams:
    estimativa = estimar_carga(notificacao)
    incluir_peso = _parse_bool(usar_peso)
    incluir_dimensoes = _parse_bool(usar_dimensoes)

    volume_m3 = parse_volume_m3(volume_m3_manual)
    comp_manual = parse_dimensao_cm(comprimento_cm_manual)
    larg_manual = parse_dimensao_cm(largura_cm_manual)
    alt_manual = parse_dimensao_cm(altura_cm_manual)

    if volume_m3 is not None and volume_m3 > 0:
        incluir_dimensoes = True
        comp, larg, alt = dimensoes_cubo_from_volume_m3(volume_m3)
    elif comp_manual or larg_manual or alt_manual:
        incluir_dimensoes = True
        comp = comp_manual if comp_manual and comp_manual > 0 else estimativa.comprimento_cm
        larg = larg_manual if larg_manual and larg_manual > 0 else estimativa.largura_cm
        alt = alt_manual if alt_manual and alt_manual > 0 else estimativa.altura_cm
    elif incluir_dimensoes:
        comp = comp_manual if comp_manual and comp_manual > 0 else estimativa.comprimento_cm
        larg = larg_manual if larg_manual and larg_manual > 0 else estimativa.largura_cm
        alt = alt_manual if alt_manual and alt_manual > 0 else estimativa.altura_cm
        volume_m3 = None
    else:
        comp = larg = alt = Decimal('0')
        volume_m3 = None

    peso = parse_peso_kg(peso_kg_manual) if incluir_peso else None
    if incluir_peso:
        peso = peso if peso is not None and peso > 0 else estimativa.peso_kg

    return CargaParams(
        usar_peso=incluir_peso,
        usar_dimensoes=incluir_dimensoes,
        peso_kg=peso if incluir_peso else Decimal('0'),
        comprimento_cm=comp if incluir_dimensoes else Decimal('0'),
        largura_cm=larg if incluir_dimensoes else Decimal('0'),
        altura_cm=alt if incluir_dimensoes else Decimal('0'),
        volume_m3=volume_m3 if incluir_dimensoes and volume_m3 else None,
    )


def calcular_distancia_operacao(notificacao) -> DistanciaResult:
    origem, destino = pontos_operacao(notificacao)
    distancia_km = calcular_distancia_km(
        origem.latitude, origem.longitude,
        destino.latitude, destino.longitude,
    )
    if distancia_km <= 0 and origem.label != destino.label:
        distancia_km = Decimal('5.000')

    try:
        from .geolocation_service import GeolocationService
        velocidade = GeolocationService().config_padrao.velocidade_padrao_kmh
    except Exception:
        velocidade = Decimal('50.00')

    tempo_minutos = int((distancia_km / velocidade) * 60) if velocidade else 0
    return DistanciaResult(
        distancia_km=distancia_km,
        origem=origem,
        destino=destino,
        tempo_estimado_minutos=max(1, tempo_minutos),
    )


def parse_distancia_km(value) -> Optional[Decimal]:
    """Converte valor do formulário/API em km; None se vazio ou inválido."""
    if value is None:
        return None
    texto = str(value).strip().replace(',', '.')
    if not texto:
        return None
    try:
        km = Decimal(texto)
    except Exception:
        return None
    return km if km >= 0 else None


def volume_m3_from_carga(carga: CargaParams) -> float:
    """Volume total em m³ a partir do campo m³ ou das dimensões em cm."""
    if carga.volume_m3 and float(carga.volume_m3) > 0:
        return float(carga.volume_m3)
    if carga.usar_dimensoes:
        comp = float(carga.comprimento_cm or 0)
        larg = float(carga.largura_cm or 0)
        alt = float(carga.altura_cm or 0)
        if comp > 0 and larg > 0 and alt > 0:
            return (comp * larg * alt) / 1_000_000.0
    return 0.0


def peso_kg_para_suplemento(carga_params: CargaParams, breakdown: Dict[str, Any], peso_registo) -> float:
    """Peso (kg) usado para verificar franquia de 25 kg."""
    peso = float(breakdown.get('weight_kg') or breakdown.get('peso_real_kg') or 0)
    if peso <= 0 and carga_params.usar_peso and float(carga_params.peso_kg or 0) > 0:
        peso = float(carga_params.peso_kg)
    if peso <= 0:
        peso = float(peso_registo or 0)
    return max(0.0, peso)


def calcular_suplemento_percentual_carga(
    transportadora,
    volume_m3: float,
    peso_kg: float,
    base_cost: float,
) -> Dict[str, float]:
    """
    Taxa percentual sobre o frete base quando volume > franquia m³ ou peso > franquia kg.
    Ex.: 1 m³ e 25 kg incluídos; 10% de suplemento se exceder qualquer um.
    """
    pct = float(getattr(transportadora, 'percentual_suplemento_carga', 0) or 0)
    franquia_m3 = float(getattr(transportadora, 'volume_m3_franquia', 1) or 1)
    franquia_kg = float(getattr(transportadora, 'peso_kg_franquia', 25) or 25)
    vol = max(0.0, float(volume_m3 or 0))
    peso = max(0.0, float(peso_kg or 0))
    excede_volume = vol > franquia_m3
    excede_peso = peso > franquia_kg
    aplica = (excede_volume or excede_peso) and pct > 0 and base_cost > 0
    custo_sup = round(base_cost * (pct / 100.0), 2) if aplica else 0.0
    return {
        'volume_m3_total': round(vol, 3),
        'volume_m3_franquia': franquia_m3,
        'excede_franquia_volume': excede_volume,
        'peso_kg_total': round(peso, 3),
        'peso_kg_franquia': franquia_kg,
        'excede_franquia_peso': excede_peso,
        'percentual_suplemento': pct,
        'base_antes_suplemento': round(max(0.0, base_cost), 2),
        'custo_suplemento_percentual': custo_sup,
    }


def _aplicar_suplemento_percentual_tarifa(
    tarifa,
    carga_params: CargaParams,
    total_cost: float,
    breakdown: Dict[str, Any],
    peso_registo,
) -> Tuple[float, Dict[str, Any]]:
    vol_m3 = volume_m3_from_carga(carga_params)
    peso_kg = peso_kg_para_suplemento(carga_params, breakdown, peso_registo)
    sup = calcular_suplemento_percentual_carga(tarifa, vol_m3, peso_kg, total_cost)
    breakdown = {**breakdown, **sup}
    if vol_m3 > 0:
        breakdown['volume_m3'] = vol_m3
    total_cost = round(total_cost + sup['custo_suplemento_percentual'], 2)
    if not sup['custo_suplemento_percentual'] and float(sup['percentual_suplemento']) <= 0:
        if sup['excede_franquia_volume'] or sup['excede_franquia_peso']:
            breakdown['aviso_suplemento'] = (
                'Volume ou peso acima da franquia, mas o percentual de suplemento está a 0% no cadastro.'
            )
    elif not sup['excede_franquia_volume'] and not sup['excede_franquia_peso']:
        breakdown['aviso_suplemento'] = (
            f'Dentro das franquias ({sup["volume_m3_franquia"]:.2f} m³ e {sup["peso_kg_franquia"]:.1f} kg) — sem suplemento.'
        )
    return total_cost, breakdown


def distancia_result_com_override(notificacao, distancia_km_manual=None) -> DistanciaResult:
    """Usa distância informada manualmente ou a estimativa automática."""
    base = calcular_distancia_operacao(notificacao)
    manual = parse_distancia_km(distancia_km_manual)
    if manual is None:
        return base
    if manual <= 0:
        manual = Decimal('0.001')

    try:
        from .geolocation_service import GeolocationService
        velocidade = GeolocationService().config_padrao.velocidade_padrao_kmh
    except Exception:
        velocidade = Decimal('50.00')

    tempo_minutos = int((manual / velocidade) * 60) if velocidade else 0
    return DistanciaResult(
        distancia_km=manual,
        origem=base.origem,
        destino=base.destino,
        tempo_estimado_minutos=max(1, tempo_minutos),
    )


def calcular_frete_operacao(
    notificacao,
    *,
    veiculo_interno=None,
    transportadora=None,
    distancia: Optional[DistanciaResult] = None,
    carga: Optional[CargaParams] = None,
) -> FreightResult:
    dist = distancia or calcular_distancia_operacao(notificacao)
    carga_params = carga or resolver_carga_params(notificacao)
    peso_registo = carga_params.peso_kg if carga_params.usar_peso else estimar_peso_kg(notificacao)
    distancia_km = float(dist.distancia_km)
    valor_declarado = float(getattr(notificacao, 'valor_operacao', 0) or 0)

    peso_calculo = float(carga_params.peso_kg) if carga_params.usar_peso else 0.0
    comp_calculo = float(carga_params.comprimento_cm) if carga_params.usar_dimensoes else 0.0
    larg_calculo = float(carga_params.largura_cm) if carga_params.usar_dimensoes else 0.0
    alt_calculo = float(carga_params.altura_cm) if carga_params.usar_dimensoes else 0.0

    tarifa = transportadora
    if not tarifa and veiculo_interno:
        tarifa = _buscar_viatura_interna_por_veiculo(veiculo_interno)

    if tarifa:
        origem_prov = dist.origem.provincia
        destino_prov = dist.destino.provincia
        resultado = calculate_quote(
            transportadora=tarifa,
            items=[PricingItem(
                weight_kg=peso_calculo,
                length_cm=comp_calculo,
                width_cm=larg_calculo,
                height_cm=alt_calculo,
                declared_value=valor_declarado,
            )],
            origem_provincia=origem_prov,
            destino_provincia=destino_prov,
            distancia_km=distancia_km,
        )
        breakdown = dict(resultado.breakdown)
        breakdown['usar_peso'] = carga_params.usar_peso
        breakdown['usar_dimensoes'] = carga_params.usar_dimensoes
        breakdown['fonte_tarifa'] = 'viatura_interna' if is_viatura_interna(tarifa) else 'transportadora_externa'
        breakdown['tarifa_custo_fixo'] = float(getattr(tarifa, 'custo_fixo', 0) or 0)
        breakdown['tarifa_custo_por_kg'] = float(getattr(tarifa, 'custo_por_kg', 0) or 0)
        breakdown['tarifa_custo_por_km'] = float(getattr(tarifa, 'custo_por_km', 0) or 0)
        breakdown['tarifa_volume_m3_franquia'] = float(getattr(tarifa, 'volume_m3_franquia', 1) or 1)
        breakdown['tarifa_peso_kg_franquia'] = float(getattr(tarifa, 'peso_kg_franquia', 25) or 25)
        breakdown['tarifa_percentual_suplemento'] = float(
            getattr(tarifa, 'percentual_suplemento_carga', 0) or 0
        )
        total_com_sup, breakdown = _aplicar_suplemento_percentual_tarifa(
            tarifa, carga_params, float(resultado.total_cost), breakdown, peso_registo,
        )
        return FreightResult(
            total_cost=Decimal(str(total_com_sup)),
            distancia_km=dist.distancia_km,
            peso_kg=peso_registo,
            currency=resultado.currency,
            breakdown=breakdown,
            origem_label=dist.origem.label,
            destino_label=dist.destino.label,
            carga=carga_params,
        )

    if veiculo_interno:
        resultado = calculate_freight_veiculo_interno(
            veiculo=veiculo_interno,
            distancia_km=distancia_km,
            peso_kg=peso_calculo if carga_params.usar_peso else float(peso_registo),
            custo_fixo_entrega=float(CUSTO_FIXO_ENTREGA_INTERNA),
        )
        breakdown = dict(resultado.breakdown)
        breakdown['usar_peso'] = carga_params.usar_peso
        breakdown['usar_dimensoes'] = carga_params.usar_dimensoes
        breakdown['fonte_tarifa'] = 'veiculo_interno_legado'
        return FreightResult(
            total_cost=Decimal(str(resultado.total_cost)),
            distancia_km=dist.distancia_km,
            peso_kg=peso_registo,
            currency=resultado.currency,
            breakdown=breakdown,
            origem_label=dist.origem.label,
            destino_label=dist.destino.label,
            carga=carga_params,
        )

    return FreightResult(
        total_cost=Decimal('0.00'),
        distancia_km=dist.distancia_km,
        peso_kg=peso_registo,
        breakdown={'distancia_km': distancia_km},
        origem_label=dist.origem.label,
        destino_label=dist.destino.label,
        carga=carga_params,
    )


def aplicar_frete_rastreamento(
    rastreamento,
    notificacao,
    distancia_km_manual=None,
    carga_params: Optional[CargaParams] = None,
) -> Optional[FreightResult]:
    """Calcula e persiste distância + custo_envio no rastreamento."""
    if not rastreamento.veiculo_interno and not rastreamento.transportadora:
        return None

    carga = carga_params or resolver_carga_params(notificacao)
    distancia = distancia_result_com_override(notificacao, distancia_km_manual)
    veiculo = rastreamento.veiculo_interno
    transportadora = rastreamento.transportadora
    if transportadora and is_viatura_interna(transportadora):
        veiculo = None
    frete = calcular_frete_operacao(
        notificacao,
        veiculo_interno=veiculo,
        transportadora=transportadora,
        distancia=distancia,
        carga=carga,
    )
    rastreamento.distancia_km = frete.distancia_km
    rastreamento.custo_envio = frete.total_cost
    if carga.usar_peso:
        rastreamento.peso_total = carga.peso_kg
    elif not rastreamento.peso_total:
        rastreamento.peso_total = frete.peso_kg
    if carga.usar_dimensoes:
        rastreamento.comprimento_cm = carga.comprimento_cm
        rastreamento.largura_cm = carga.largura_cm
        rastreamento.altura_cm = carga.altura_cm
    if not rastreamento.valor_declarado and hasattr(notificacao, 'valor_operacao'):
        try:
            rastreamento.valor_declarado = notificacao.valor_operacao
        except Exception:
            pass
    return frete


def distancia_result_to_dict(result: DistanciaResult) -> Dict[str, Any]:
    return {
        'distancia_km': float(result.distancia_km),
        'tempo_estimado_minutos': result.tempo_estimado_minutos,
        'origem': {
            'label': result.origem.label,
            'cidade': result.origem.cidade,
            'provincia': result.origem.provincia,
            'fonte': result.origem.fonte,
        },
        'destino': {
            'label': result.destino.label,
            'cidade': result.destino.cidade,
            'provincia': result.destino.provincia,
            'fonte': result.destino.fonte,
        },
    }


def carga_estimativa_to_dict(estimativa: CargaEstimativa) -> Dict[str, Any]:
    return {
        'peso_kg': float(estimativa.peso_kg),
        'comprimento_cm': float(estimativa.comprimento_cm),
        'largura_cm': float(estimativa.largura_cm),
        'altura_cm': float(estimativa.altura_cm),
    }


def carga_params_to_dict(carga: CargaParams) -> Dict[str, Any]:
    payload = {
        'usar_peso': carga.usar_peso,
        'usar_dimensoes': carga.usar_dimensoes,
        'peso_kg': float(carga.peso_kg),
        'comprimento_cm': float(carga.comprimento_cm),
        'largura_cm': float(carga.largura_cm),
        'altura_cm': float(carga.altura_cm),
    }
    if carga.volume_m3:
        payload['volume_m3'] = float(carga.volume_m3)
    return payload


def freight_result_to_dict(result: FreightResult) -> Dict[str, Any]:
    payload = {
        'total_cost': float(result.total_cost),
        'distancia_km': float(result.distancia_km),
        'peso_kg': float(result.peso_kg),
        'currency': result.currency,
        'breakdown': result.breakdown,
        'origem_label': result.origem_label,
        'destino_label': result.destino_label,
    }
    if result.carga:
        payload['carga'] = carga_params_to_dict(result.carga)
    return payload
