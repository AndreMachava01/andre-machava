"""Serviço de empreitadas e contratos com prestadores externos."""
import json
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Sum
from django.utils import timezone

from meuprojeto.empresa.models_producao_servicos import (
    AtividadeExecucao,
    ConfiguracaoContratoEmpreitada,
    ContratoEmpreitada,
    OrdemServico,
    ParcelaPagamentoEmpreitada,
    PrestadorServico,
    ServicoOrcamentoServico,
    TrabalhoEmpreitada,
)


def get_or_create_contrato_empreitada(trabalho):
    """Obtém ou cria o contrato consolidado (prestador + ordem de serviço)."""
    ordem_id = None
    if trabalho.servico_orcamento_id:
        ordem_id = trabalho.servico_orcamento.ordem_servico_id
    elif trabalho.atividade_execucao_id:
        ordem_id = trabalho.atividade_execucao.ordem_servico_id

    contrato, _ = ContratoEmpreitada.objects.get_or_create(
        prestador_id=trabalho.prestador_id,
        ordem_servico_id=ordem_id,
    )
    return contrato


def vincular_trabalho_ao_contrato(trabalho):
    contrato = get_or_create_contrato_empreitada(trabalho)
    if trabalho.contrato_empreitada_id != contrato.id:
        trabalho.contrato_empreitada = contrato
        trabalho.save(update_fields=['contrato_empreitada'])
    return contrato


def queryset_empreitadas_lista(status_filter=''):
    trabalhos_qs = TrabalhoEmpreitada.objects.select_related(
        'prestador',
        'servico_orcamento__ordem_servico',
        'servico_orcamento__servico',
        'atividade_execucao__ordem_servico',
        'contrato_empreitada__prestador',
        'contrato_empreitada__ordem_servico',
    )
    if status_filter:
        trabalhos_qs = trabalhos_qs.filter(status=status_filter)

    contrato_ids = (
        trabalhos_qs.exclude(contrato_empreitada__isnull=True)
        .values_list('contrato_empreitada_id', flat=True)
        .distinct()
    )
    contratos = (
        ContratoEmpreitada.objects.filter(id__in=contrato_ids)
        .select_related('prestador', 'ordem_servico')
        .prefetch_related(
            Prefetch(
                'trabalhos',
                queryset=trabalhos_qs.filter(contrato_empreitada_id__isnull=False),
            )
        )
        .order_by('-data_atualizacao')
    )
    trabalhos_sem_contrato = list(
        trabalhos_qs.filter(contrato_empreitada__isnull=True).order_by('-data_criacao')
    )
    return contratos, trabalhos_sem_contrato


def _valor_atividade(atividade):
    total = Decimal('0')
    for servico in atividade.servicos_entregues.all():
        total += (servico.valor_unitario or Decimal('0')) * (servico.quantidade or Decimal('1'))
    return total


def build_formulario_empreitada_json():
    ordens = (
        OrdemServico.objects.filter(
            codigo__startswith='OS',
            status__in=['AGENDADA', 'EM_ANDAMENTO'],
        )
        .select_related('sucursal')
        .prefetch_related(
            'servicos_orcamento__servico',
            'atividades_execucao__servicos_entregues__servico',
        )
        .order_by('-data_agendada')
    )
    ordens_servicos = {}
    ordens_atividades = {}
    for ordem in ordens:
        oid = str(ordem.id)
        ordens_servicos[oid] = [
            {
                'id': s.id,
                'desc': s.servico.nome if s.servico_id else str(s),
                'valor': str(s.valor_unitario or 0),
                'sucursal': ordem.sucursal_id or '',
            }
            for s in ordem.servicos_orcamento.all()
        ]
        atividades = []
        for atv in ordem.atividades_execucao.filter(parent__isnull=True):
            valor = _valor_atividade(atv)
            atividades.append({
                'id': atv.id,
                'desc': atv.nome,
                'valor': str(valor),
                'sucursal': ordem.sucursal_id or '',
            })
        ordens_atividades[oid] = atividades
    return list(ordens), json.dumps(ordens_servicos), json.dumps(ordens_atividades)


def _parse_date(value):
    if not value:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


@transaction.atomic
def criar_trabalhos_empreitada(post_data):
    prestadores = post_data.getlist('prestador')
    descricoes = post_data.getlist('descricao')
    valores = post_data.getlist('valor_fixo')
    servicos = post_data.getlist('servico_orcamento')
    atividades = post_data.getlist('atividade_execucao')
    status = post_data.get('status', 'PENDENTE')
    data_inicio = _parse_date(post_data.get('data_inicio'))
    data_conclusao = _parse_date(post_data.get('data_conclusao'))
    observacoes = post_data.get('observacoes', '')
    sucursal_id = post_data.get('sucursal') or None

    criados = 0
    for i, prestador_id in enumerate(prestadores):
        if not prestador_id:
            continue
        descricao = (descricoes[i] if i < len(descricoes) else '').strip()
        if not descricao:
            continue
        valor_raw = valores[i] if i < len(valores) else '0'
        try:
            valor = Decimal(str(valor_raw or '0'))
        except Exception:
            valor = Decimal('0')

        servico_id = servicos[i] if i < len(servicos) and servicos[i] else None
        atividade_id = atividades[i] if i < len(atividades) and atividades[i] else None

        trabalho = TrabalhoEmpreitada(
            prestador_id=int(prestador_id),
            descricao=descricao,
            valor_fixo=valor,
            status=status,
            data_inicio=data_inicio,
            data_conclusao=data_conclusao,
            observacoes=observacoes,
            sucursal_id=int(sucursal_id) if sucursal_id else None,
        )
        if atividade_id:
            trabalho.atividade_execucao_id = int(atividade_id)
        elif servico_id:
            trabalho.servico_orcamento_id = int(servico_id)
        trabalho.save()
        vincular_trabalho_ao_contrato(trabalho)
        criados += 1
    return criados


@transaction.atomic
def atualizar_trabalho_empreitada(trabalho, post_data):
    trabalho.prestador_id = int(post_data.get('prestador'))
    trabalho.descricao = post_data.get('descricao', '').strip()
    trabalho.valor_fixo = Decimal(post_data.get('valor_fixo') or '0')
    trabalho.status = post_data.get('status', trabalho.status)
    trabalho.data_inicio = _parse_date(post_data.get('data_inicio'))
    trabalho.data_conclusao = _parse_date(post_data.get('data_conclusao'))
    trabalho.observacoes = post_data.get('observacoes', '')
    sucursal = post_data.get('sucursal')
    trabalho.sucursal_id = int(sucursal) if sucursal else None

    servico_id = post_data.get('servico_orcamento')
    atividade_id = post_data.get('atividade_execucao')
    trabalho.servico_orcamento_id = int(servico_id) if servico_id else None
    trabalho.atividade_execucao_id = int(atividade_id) if atividade_id else None
    trabalho.save()
    vincular_trabalho_ao_contrato(trabalho)
    return trabalho


def salvar_parcelas_contrato(contrato, post_data):
    parcela_count = int(post_data.get('parcela_count') or 0)
    contrato.parcelas_pagamento.all().delete()
    if parcela_count <= 0:
        return
    for i in range(parcela_count):
        pct = post_data.get(f'parcela_{i}_percentagem')
        tipo = post_data.get(f'parcela_{i}_tipo') or ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TOTAL
        if pct is None:
            continue
        parcela = ParcelaPagamentoEmpreitada.objects.create(
            contrato_empreitada=contrato,
            numero_ordem=i + 1,
            percentagem=int(pct),
            tipo=tipo[:24],
        )
        if tipo == ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TRABALHOS:
            ids = post_data.getlist(f'parcela_{i}_trabalhos')
            if ids:
                parcela.trabalhos.set(
                    TrabalhoEmpreitada.objects.filter(
                        id__in=ids, contrato_empreitada=contrato,
                    )
                )


def aplicar_clausulas_contrato(contrato, post_data):
    campos_texto = [
        'clausula2_pagamento', 'clausula6_alteracoes', 'clausula7_rescisao',
        'clausula8_confidencialidade', 'clausula9_foro', 'clausula_suspensao_clima',
    ]
    campos_char = [
        'obrigacao_contratada_1', 'obrigacao_contratada_2', 'obrigacao_contratada_3',
        'obrigacao_contratante_1', 'obrigacao_contratante_2', 'obrigacao_contratante_3',
    ]
    for campo in campos_texto:
        if campo in post_data:
            setattr(contrato, campo, post_data.get(campo) or '')
    for campo in campos_char:
        if campo in post_data:
            setattr(contrato, campo, (post_data.get(campo) or '')[:500])

    prazo_num = post_data.get('prazo_execucao_numero')
    contrato.prazo_execucao_numero = int(prazo_num) if prazo_num else None
    contrato.prazo_execucao_unidade = post_data.get('prazo_execucao_unidade') or 'DIAS'
    garantia_val = post_data.get('validade_garantia_valor')
    contrato.validade_garantia_dias = int(garantia_val) if garantia_val else None
    contrato.validade_garantia_unidade = post_data.get('validade_garantia_unidade') or 'DIAS'
    contrato.incluir_clausula_suspensao_clima = post_data.get('incluir_clausula_suspensao_clima') == '1'
    contrato.save()


def contexto_editar_contrato(contrato, trabalho=None):
    trabalhos = list(contrato.trabalhos.all())
    parcelas = list(contrato.parcelas_pagamento.prefetch_related('trabalhos').order_by('numero_ordem'))
    parcelas_assinatura = [
        p for p in parcelas
        if p.tipo == ParcelaPagamentoEmpreitada.TIPO_ASSINATURA and not p.data_pago
    ]
    return {
        'contrato': contrato,
        'trabalho': trabalho,
        'trabalhos': trabalhos,
        'valor_total': contrato.valor_total,
        'parcelas': parcelas,
        'parcelas_assinatura_por_pagar': parcelas_assinatura and not contrato.data_assinatura,
        'recibos_adiantamento': [],
        'clausula2_pagamento': contrato.clausula2_pagamento or '',
        'obrigacao_contratada_1': contrato.obrigacao_contratada_1 or '',
        'obrigacao_contratada_2': contrato.obrigacao_contratada_2 or '',
        'obrigacao_contratada_3': contrato.obrigacao_contratada_3 or '',
        'obrigacao_contratante_1': contrato.obrigacao_contratante_1 or '',
        'obrigacao_contratante_2': contrato.obrigacao_contratante_2 or '',
        'obrigacao_contratante_3': contrato.obrigacao_contratante_3 or '',
        'garantia_valor': contrato.validade_garantia_dias or 90,
    }


def _valor_extenso_meticais(valor):
    try:
        from num2words import num2words
        return (
            num2words(float(valor), lang='pt', to='currency', currency='EUR')
            .replace('euros', 'meticais')
            .replace('euro', 'metical')
        )
    except Exception:
        return str(valor)


def contexto_preview_contrato(contrato, request):
    from meuprojeto.empresa.models_base import DadosEmpresa

    trabalhos = list(contrato.trabalhos.all())
    empresa = DadosEmpresa.objects.filter(is_sede=True).first()
    prestador = contrato.prestador
    valor_total = contrato.valor_total
    parcelas = list(contrato.parcelas_pagamento.order_by('numero_ordem'))
    pagamento_parcelas = []
    for p in parcelas:
        val = p.valor_parcela()
        pagamento_parcelas.append({
            'texto': f'{p.percentagem}% — {p.get_tipo_display()}',
            'valor': f'{val:.2f}',
        })

    unidade_map = {'DIAS': 'dias', 'MESES': 'meses', 'ANOS': 'anos'}
    prazo_num = contrato.prazo_execucao_numero or 30
    prazo_un = unidade_map.get(contrato.prazo_execucao_unidade or 'DIAS', 'dias')
    prazo_texto = f'O prazo de execução dos trabalhos é de {prazo_num} {prazo_un}, contados a partir da assinatura do contrato.'

    garantia_num = contrato.validade_garantia_dias or 90
    garantia_un = unidade_map.get(contrato.validade_garantia_unidade or 'DIAS', 'dias')
    garantia_texto = (
        f'A CONTRATADA garante a qualidade dos trabalhos pelo prazo de {garantia_num} {garantia_un}, '
        'nos termos da legislação aplicável.'
    )

    config = ConfiguracaoContratoEmpreitada.objects.filter(padrao=True, ativo=True).first()
    codigo_os = contrato.ordem_servico.codigo if contrato.ordem_servico_id else 'AVULSO'

    return {
        'contrato': contrato,
        'dados_empresa': empresa,
        'ano': timezone.now().year,
        'sequencia': f'{contrato.id:04d}',
        'data_contrato': timezone.now().strftime('%d/%m/%Y'),
        'numero_ref': codigo_os,
        'nome_contratante': empresa.nome if empresa else 'Conception Lda',
        'nuit_contratante': empresa.nuit if empresa else '',
        'morada_contratante': empresa.endereco if empresa else '',
        'representante_contratante': 'Representante legal',
        'nome_contratada': prestador.nome,
        'nuit_contratada': prestador.nuit,
        'morada_contratada': prestador.endereco,
        'contacto_contratada': prestador.contacto,
        'representante_contratada': prestador.representante_legal or prestador.nome,
        'descricoes_trabalhos': [t.descricao for t in trabalhos],
        'descricao_trabalho': trabalhos[0].descricao if len(trabalhos) == 1 else '',
        'valor_total': f'{valor_total:.2f}',
        'valor_extenso': _valor_extenso_meticais(valor_total),
        'pagamento_parcelas_com_valores': pagamento_parcelas,
        'clausula2_pagamento': contrato.clausula2_pagamento,
        'prazo_texto': prazo_texto,
        'clausula_suspensao_clima_texto': contrato.clausula_suspensao_clima or (
            'Os prazos suspendem-se em caso de condições climáticas adversas que impeçam a execução segura dos trabalhos.'
        ),
        'obrigacao_contratada_1': contrato.obrigacao_contratada_1,
        'obrigacao_contratada_2': contrato.obrigacao_contratada_2,
        'obrigacao_contratada_3': contrato.obrigacao_contratada_3,
        'obrigacao_contratante_1': contrato.obrigacao_contratante_1,
        'obrigacao_contratante_2': contrato.obrigacao_contratante_2,
        'obrigacao_contratante_3': contrato.obrigacao_contratante_3,
        'clausula5_garantia': contrato.clausula5_garantia,
        'clausula6_alteracoes': contrato.clausula6_alteracoes,
        'clausula7_rescisao': contrato.clausula7_rescisao,
        'clausula8_confidencialidade': contrato.clausula8_confidencialidade,
        'clausula9_foro': contrato.clausula9_foro,
        'config_contrato': config,
        'garantia_texto': garantia_texto,
        'url_voltar': f'/rh/empreitadas/contrato/{contrato.id}/editar/',
        'url_gerar': '#',
    }


def confirmar_assinatura_contrato(contrato):
    if contrato.data_assinatura:
        return False
    contrato.data_assinatura = timezone.now()
    contrato.save(update_fields=['data_assinatura'])

    from meuprojeto.empresa.models_financas import PendenteContaPagar

    for parcela in contrato.parcelas_pagamento.filter(
        tipo=ParcelaPagamentoEmpreitada.TIPO_ASSINATURA,
        data_pago__isnull=True,
    ):
        valor = parcela.valor_parcela()
        if valor <= 0:
            continue
        if PendenteContaPagar.objects.filter(
            origem_tipo='RH_EMP_PARCELA', origem_id=parcela.id,
        ).exists():
            continue
        PendenteContaPagar.objects.create(
            origem_tipo='RH_EMP_PARCELA',
            origem_id=parcela.id,
            beneficiario=contrato.prestador.nome[:300],
            descricao='Empreitada — parcela à assinatura do contrato',
            valor=valor,
            data_vencimento=timezone.now().date(),
            estado='PENDENTE',
        )
    return True


def _criar_pendente_parcela_empreitada(parcela, contrato, descricao):
    from meuprojeto.empresa.models_financas import PendenteContaPagar

    valor = parcela.valor_parcela()
    if valor <= 0:
        return False
    if PendenteContaPagar.objects.filter(
        origem_tipo='RH_EMP_PARCELA', origem_id=parcela.id,
    ).exists():
        return False
    PendenteContaPagar.objects.create(
        origem_tipo='RH_EMP_PARCELA',
        origem_id=parcela.id,
        beneficiario=contrato.prestador.nome[:300],
        descricao=descricao,
        valor=valor,
        data_vencimento=timezone.now().date(),
        estado='PENDENTE',
    )
    return True


def processar_empreitada_concluida(trabalho, user=None):
    """
    Ao concluir um trabalho de empreitada, gera pendente(s) de pagamento em Finanças
    conforme parcelas do contrato (conclusão parcial ou total).
    """
    contrato = trabalho.contrato_empreitada
    if not contrato:
        contrato = vincular_trabalho_ao_contrato(trabalho)

    for parcela in contrato.parcelas_pagamento.filter(
        tipo=ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TRABALHOS,
        data_pago__isnull=True,
    ):
        if not parcela.trabalhos.filter(id=trabalho.id).exists():
            continue
        trabalhos_parcela = parcela.trabalhos.all()
        if not trabalhos_parcela.exclude(status='CONCLUIDO').exists():
            _criar_pendente_parcela_empreitada(
                parcela, contrato,
                f'Empreitada — conclusão dos trabalhos (parcela {parcela.numero_ordem})',
            )

    todos_concluidos = not contrato.trabalhos.exclude(status='CONCLUIDO').exists()
    if todos_concluidos:
        for parcela in contrato.parcelas_pagamento.filter(
            tipo=ParcelaPagamentoEmpreitada.TIPO_CONCLUSAO_TOTAL,
            data_pago__isnull=True,
        ):
            _criar_pendente_parcela_empreitada(
                parcela, contrato,
                f'Empreitada — conclusão total (parcela {parcela.numero_ordem})',
            )

    if trabalho.valor_fixo and trabalho.valor_fixo > 0:
        from meuprojeto.empresa.models_financas import PendenteContaPagar
        if not PendenteContaPagar.objects.filter(
            origem_tipo='RH_EMPREITADA', origem_id=trabalho.id,
        ).exists():
            PendenteContaPagar.objects.create(
                origem_tipo='RH_EMPREITADA',
                origem_id=trabalho.id,
                beneficiario=trabalho.prestador.nome[:300],
                descricao=f'Empreitada — {trabalho.descricao[:200]}',
                valor=trabalho.valor_fixo,
                data_vencimento=timezone.now().date(),
                estado='PENDENTE',
            )
