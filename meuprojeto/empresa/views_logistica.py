# =============================================================================
# VIEWS PARA MÓDULO DE LOGÍSTICA - APENAS LOGÍSTICA PURA
# =============================================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from datetime import timedelta
import logging
import json

from .decorators import require_stock_access
from .models_stock import (
    Transportadora, RastreamentoEntrega, EventoRastreamento, VeiculoInterno,
    NotificacaoLogisticaUnificada,
)
from .services.logistica_sync import (
    get_or_create_rastreamento_for_notificacao,
    sincronizar_rastreamento_com_notificacao,
    criar_evento_rastreamento,
)
from .services.pricing import calculate_quote, PricingItem
from .services.freight_service import (
    calcular_distancia_operacao,
    calcular_frete_operacao,
    distancia_result_to_dict,
    distancia_result_com_override,
    freight_result_to_dict,
    parse_distancia_km,
    estimar_carga,
    carga_estimativa_to_dict,
    resolver_carga_params,
    TIPOS_VIATURA_INTERNA,
)
from django.conf import settings
from django.core.mail import send_mail
from .services import logistica_ops

# Utilitários movidos para services/logistica_sync.py

logger = logging.getLogger(__name__)

# =============================================================================
# VIEWS PRINCIPAIS
# =============================================================================

@login_required
@require_stock_access
def logistica_main(request):
    """Página principal do módulo de Logística - SIMPLIFICADA"""
    
    # Métricas essenciais de Logística
    rastreamentos_em_transito = RastreamentoEntrega.objects.filter(
        status_atual__in=['COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO']
    ).count()
    
    # Entregas pendentes (últimos 7 dias)
    from datetime import timedelta
    from django.utils import timezone
    data_limite_entregas = timezone.now() - timedelta(days=7)
    entregas_pendentes = RastreamentoEntrega.objects.filter(
        status_atual='PREPARANDO',
        data_criacao__gte=data_limite_entregas
    ).count()

    transportadoras_ativas = Transportadora.objects.filter(status='ATIVA').count()
    entregas_concluidas = RastreamentoEntrega.objects.filter(
        status_atual='ENTREGUE'
    ).count()

    context = {
        'rastreamentos_em_transito': rastreamentos_em_transito,
        'entregas_pendentes': entregas_pendentes,
        'transportadoras_ativas': transportadoras_ativas,
        'entregas_concluidas': entregas_concluidas,
    }
    return render(request, 'stock/logistica/main.html', context)


@login_required
@require_stock_access
def logistica_dashboard(request):
    """Dashboard executivo de logística"""
    user_sucursais_ids = get_user_sucursais_ids(request.user)
    
    # Métricas de logística
    metricas = {
        'transportadoras_ativas': Transportadora.objects.filter(status='ATIVA').count(),
        'entregas_em_andamento': RastreamentoEntrega.objects.filter(
            status_atual__in=['COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO']
        ).count(),
        'entregas_concluidas': RastreamentoEntrega.objects.filter(
            status_atual='ENTREGUE'
        ).count(),
        'entregas_pendentes': RastreamentoEntrega.objects.filter(
            status_atual='PREPARANDO'
        ).count(),
    }
    
    # Alertas logísticos
    alertas = obter_alertas_logisticos(user_sucursais_ids)
    
    context = {
        'metricas': metricas,
        'alertas': alertas,
    }
    return render(request, 'stock/logistica/dashboard.html', context)


@login_required
@require_stock_access
def logistica_dashboard_data(request):
    """API para dados do dashboard"""
    user_sucursais_ids = get_user_sucursais_ids(request.user)
    
    # Métricas de logística
    metricas = {
        'transportadoras_ativas': Transportadora.objects.filter(status='ATIVA').count(),
        'entregas_em_andamento': RastreamentoEntrega.objects.filter(
            status_atual__in=['COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO']
        ).count(),
        'entregas_concluidas': RastreamentoEntrega.objects.filter(
            status_atual='ENTREGUE'
        ).count(),
        'entregas_pendentes': RastreamentoEntrega.objects.filter(
            status_atual='PREPARANDO'
        ).count(),
    }
    
    return JsonResponse(metricas)

# =============================================================================
# VIEWS DE RASTREAMENTO
# =============================================================================

@login_required
@require_stock_access
def rastreamento_list(request):
    """Lista de rastreamentos com filtros e paginação"""
    from django.core.paginator import Paginator
    
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    transportadora_id = request.GET.get('transportadora', '').strip()
    
    # Base: todos (não restringir por criado_por)
    qs = RastreamentoEntrega.objects.all().select_related(
        'transportadora', 'veiculo_interno', 'transferencia', 'ordem_compra',
        'transferencia__sucursal_origem', 'transferencia__sucursal_destino',
        'ordem_compra__fornecedor', 'ordem_compra__sucursal_destino',
    )
    
    if search:
        qs = qs.filter(
            Q(codigo_rastreamento__icontains=search) |
            Q(destinatario_nome__icontains=search) |
            Q(destinatario_telefone__icontains=search)
        )
    if status:
        qs = qs.filter(status_atual=status)
    if transportadora_id:
        qs = qs.filter(transportadora_id=transportadora_id)
    
    qs = qs.order_by('-data_criacao')

    stats = {
        'total': qs.count(),
        'em_curso': qs.filter(
            status_atual__in=('PREPARANDO', 'COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO')
        ).count(),
        'entregues': qs.filter(status_atual='ENTREGUE').count(),
        'problemas': qs.filter(status_atual__in=('DEVOLVIDO', 'PERDIDO', 'CANCELADO')).count(),
    }
    
    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Sincronizar status dos itens da página com o estado atual das operações
    try:
        from .models_stock import NotificacaoLogisticaUnificada
        for r in page_obj.object_list:
            notificacao = None
            if r.transferencia_id:
                notificacao = NotificacaoLogisticaUnificada.objects.filter(transferencia_id=r.transferencia_id).first()
            elif r.ordem_compra_id:
                notificacao = NotificacaoLogisticaUnificada.objects.filter(ordem_compra_id=r.ordem_compra_id).first()
            if notificacao:
                sincronizar_rastreamento_com_notificacao(EventoRastreamento, notificacao, r, request.user)
                # Garantir que exibimos o status atualizado na lista
                try:
                    r.refresh_from_db(fields=['status_atual', 'data_coleta', 'data_entrega_realizada'])
                except Exception:
                    pass
    except Exception:
        logger.exception('Falha ao sincronizar rastreamentos na listagem')
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'status_choices': RastreamentoEntrega.STATUS_CHOICES,
        'transportadoras': Transportadora.objects.filter(ativa=True).order_by('nome'),
        'search': search,
        'status': status,
        'transportadora_id': transportadora_id,
        'has_filters': bool(search or status or transportadora_id),
    }
    return render(request, 'stock/logistica/rastreamento/list.html', context)


@login_required
@require_stock_access
def rastreamento_detail(request, id):
    """Detalhes de um rastreamento"""
    rastreamento = get_object_or_404(RastreamentoEntrega, id=id)
    eventos = rastreamento.eventos.all().order_by('-data_evento')
    
    context = {
        'rastreamento': rastreamento,
        'eventos': eventos,
    }
    return render(request, 'stock/logistica/rastreamento/detail.html', context)


## Rotas obsoletas de rastreamento removidas (criação/adição de evento)

# =============================================================================
# VIEWS DE TRANSPORTADORAS
# =============================================================================

@login_required
@require_stock_access
def transportadoras_list(request):
    """Lista de transportadoras externas"""
    from django.core.paginator import Paginator
    
    # Filtros
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    
    # Query base - apenas transportadoras externas (excluir viaturas internas)
    transportadoras = Transportadora.objects.exclude(
        tipo__in=('VIATURA_INTERNA', 'VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO')
    )
    
    # Aplicar filtros
    if search:
        transportadoras = transportadoras.filter(
            Q(nome__icontains=search) |
            Q(codigo__icontains=search) |
            Q(cidade__icontains=search) |
            Q(nuit__icontains=search)
        )
    
    if status:
        transportadoras = transportadoras.filter(status=status)
    
    if tipo:
        transportadoras = transportadoras.filter(tipo=tipo)
    
    stats = {
        'total': transportadoras.count(),
        'ativas': transportadoras.filter(status='ATIVA', ativa=True).count(),
        'inativas': transportadoras.filter(status='INATIVA').count(),
        'suspensas': transportadoras.filter(status__in=('SUSPENSA', 'MANUTENCAO')).count(),
    }
    
    # Ordenar
    transportadoras = transportadoras.order_by('nome')
    
    # Paginação
    paginator = Paginator(transportadoras, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = Transportadora.STATUS_CHOICES
    tipo_choices = [
        choice for choice in Transportadora.TIPO_CHOICES
        if choice[0] not in ('VIATURA_INTERNA', 'VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO')
    ]
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'status': status,
        'tipo': tipo,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
        'has_filters': bool(search or status or tipo),
    }
    return render(request, 'stock/logistica/transportadoras/list.html', context)


@login_required
@require_stock_access
def transportadora_create(request):
    """Criar nova transportadora ou viatura"""
    if request.method == 'POST':
        form = TransportadoraForm(request.POST)
        if form.is_valid():
            transportadora = form.save()
            messages.success(request, f'{transportadora.get_tipo_display()} "{transportadora.nome}" criada com sucesso!')
            return redirect('stock:logistica:transportadoras_list')
        else:
            # Debug: mostrar erros do formulário
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            messages.error(request, 'Erro ao criar transportadora. Verifique os dados.')
    else:
        form = TransportadoraForm()
    
    context = {
        'form': form,
    }
    return render(request, 'stock/logistica/transportadoras/create.html', context)


@login_required
@require_stock_access
def transportadora_edit(request, id):
    """Editar transportadora ou viatura"""
    transportadora = get_object_or_404(Transportadora, id=id)
    
    if request.method == 'POST':
        form = TransportadoraForm(request.POST, instance=transportadora)
        if form.is_valid():
            transportadora = form.save()
            messages.success(request, f'{transportadora.get_tipo_display()} atualizada com sucesso!')
            return redirect('stock:logistica:transportadora_detail', id=transportadora.id)
    else:
        form = TransportadoraForm(instance=transportadora)
    
    context = {
        'form': form,
        'transportadora': transportadora,
    }
    return render(request, 'stock/logistica/transportadoras/edit.html', context)


@login_required
@require_stock_access
def transportadora_delete(request, id):
    """Excluir transportadora ou viatura"""
    transportadora = get_object_or_404(Transportadora, id=id)
    
    if request.method == 'POST':
        nome_transportadora = transportadora.nome
        transportadora.delete()
        messages.success(request, f'Transportadora "{nome_transportadora}" excluída com sucesso!')
        return redirect('stock:logistica:transportadoras_list')

    return render(request, 'stock/logistica/transportadoras/delete.html', {
        'transportadora': transportadora,
    })


@login_required
@require_stock_access
def transportadora_detail(request, id):
    """Detalhes de uma transportadora"""
    transportadora = get_object_or_404(Transportadora, id=id)
    entregas = transportadora.entregas.all().order_by('-data_criacao')[:10]
    
    # Calcular estatísticas
    total_entregas = transportadora.entregas.count()
    entregas_entregues = transportadora.entregas.filter(status_atual='ENTREGUE').count()
    entregas_em_transito = transportadora.entregas.filter(
        status_atual__in=['COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO']
    ).count()
    
    # Calcular tempo médio de entrega
    entregas_completas = transportadora.entregas.filter(
        status_atual='ENTREGUE',
        data_entrega_realizada__isnull=False
    )
    
    tempo_medio_entrega = 0
    if entregas_completas.exists():
        tempos = []
        for entrega in entregas_completas:
            if entrega.data_entrega_realizada and entrega.data_criacao:
                delta = entrega.data_entrega_realizada - entrega.data_criacao
                tempos.append(delta.total_seconds() / 3600)  # Converter para horas
        
        if tempos:
            tempo_medio_entrega = sum(tempos) / len(tempos)
    
    stats = {
        'total_entregas': total_entregas,
        'entregas_entregues': entregas_entregues,
        'entregas_em_transito': entregas_em_transito,
        'tempo_medio_entrega': tempo_medio_entrega,
    }
    
    context = {
        'transportadora': transportadora,
        'entregas': entregas,
        'stats': stats,
    }
    return render(request, 'stock/logistica/transportadoras/detail.html', context)

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def get_user_sucursais_ids(user):
    """Obtém IDs das sucursais do usuário"""
    # Implementar lógica para obter sucursais do usuário
    return []

def obter_alertas_logisticos(sucursais_ids):
    """Obtém alertas logísticos"""
    alertas = []
    
    # Verificar entregas atrasadas
    entregas_atrasadas = RastreamentoEntrega.objects.filter(
        status_atual__in=['EM_TRANSITO', 'EM_DISTRIBUICAO'],
        data_entrega_prevista__lt=timezone.now()
    ).count()
    
    if entregas_atrasadas > 0:
        alertas.append({
            'tipo': 'warning',
            'mensagem': f'{entregas_atrasadas} entregas estão atrasadas'
        })
    
    return alertas

# =============================================================================
# FORMS PARA LOGÍSTICA
# =============================================================================

from django import forms

class TransportadoraForm(forms.ModelForm):
    class Meta:
        model = Transportadora
        fields = [
            'nome', 'codigo', 'tipo',
            'nuit', 'email', 'telefone', 'website',
            'endereco', 'cidade', 'provincia',
            'prazo_entrega_padrao', 'custo_por_kg', 'custo_por_km', 'custo_fixo',
            'volume_m3_franquia', 'peso_kg_franquia', 'percentual_suplemento_carga',
            'cobertura_provincias', 'status', 'ativa', 'observacoes',
            # Campos específicos para veículos
            'categoria_veiculo', 'placa', 'marca', 'modelo', 'ano_fabricacao',
            'capacidade_kg', 'quilometragem_atual', 'proxima_revisao',
            'motorista_responsavel', 'telefone_motorista'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'nuit': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'endereco': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'provincia': forms.TextInput(attrs={'class': 'form-control'}),
            'prazo_entrega_padrao': forms.NumberInput(attrs={'class': 'form-control'}),
            'custo_por_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'custo_por_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'custo_fixo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'volume_m3_franquia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'peso_kg_franquia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'percentual_suplemento_carga': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            # Widgets para campos de veículos
            'categoria_veiculo': forms.Select(attrs={'class': 'form-control'}),
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'ano_fabricacao': forms.NumberInput(attrs={'class': 'form-control'}),
            'capacidade_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'quilometragem_atual': forms.NumberInput(attrs={'class': 'form-control'}),
            'proxima_revisao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motorista_responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone_motorista': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['volume_m3_franquia'].label = 'Volume incluído (m³)'
        self.fields['peso_kg_franquia'].label = 'Peso incluído (kg)'
        self.fields['percentual_suplemento_carga'].label = 'Suplemento % (acima das franquias)'
        
        # Tornar campos opcionais por padrão
        self.fields['codigo'].required = False
        self.fields['observacoes'].required = False
        self.fields['nuit'].required = False
        self.fields['telefone'].required = False
        self.fields['endereco'].required = False
        self.fields['cidade'].required = False
        self.fields['provincia'].required = False
        self.fields['placa'].required = False
        self.fields['motorista_responsavel'].required = False
        self.fields['telefone_motorista'].required = False
        
        # Configurar campos baseado no tipo
        if self.instance.pk:  # Se está editando
            tipo_atual = self.instance.tipo
        else:
            tipo_atual = self.data.get('tipo', '') if self.data else ''
        
        self._configurar_campos_por_tipo(tipo_atual)
    
    def _configurar_campos_por_tipo(self, tipo):
        """Configura campos baseado no tipo de transportadora"""
        if tipo == 'TRANSPORTADORA':
            # Para transportadoras externas, tornar obrigatórios os campos de contato
            self.fields['nuit'].required = True
            self.fields['telefone'].required = True
            self.fields['endereco'].required = True
            self.fields['cidade'].required = True
            self.fields['provincia'].required = True
            
            # Tornar opcionais os campos de veículo
            self.fields['placa'].required = False
            self.fields['marca'].required = False
            self.fields['modelo'].required = False
            self.fields['motorista_responsavel'].required = False
            self.fields['telefone_motorista'].required = False
            
        elif tipo == 'VIATURA_INTERNA':
            # Para veículos internos, tornar obrigatórios os campos de veículo
            self.fields['placa'].required = True
            self.fields['motorista_responsavel'].required = True
            self.fields['telefone_motorista'].required = True
            
            # Tornar opcionais os campos de contato empresarial
            self.fields['nuit'].required = False
            self.fields['telefone'].required = False
            self.fields['endereco'].required = False
            self.fields['cidade'].required = False
            self.fields['provincia'].required = False


class ViaturaForm(forms.ModelForm):
    """Formulário específico para viaturas internas"""
    
    # Choices para categoria de veículo
    CATEGORIA_VEICULO_CHOICES = [
        ('', 'Selecione uma categoria'),
        ('AUTOMOVEL', 'Automóvel'),
        ('MOTOCICLETA', 'Motocicleta'),
        ('VAN', 'Van'),
        ('CAMINHAO', 'Caminhão'),
        ('BICICLETA', 'Bicicleta'),
        ('PICKUP', 'Pickup'),
        ('CAMINHONETE', 'Caminhonete'),
        ('ONIBUS', 'Ônibus'),
        ('AMBULANCIA', 'Ambulância'),
    ]
    
    # Choices para marcas de veículos
    MARCA_CHOICES = [
        ('', 'Selecione uma marca'),
        ('TOYOTA', 'Toyota'),
        ('FORD', 'Ford'),
        ('CHEVROLET', 'Chevrolet'),
        ('VOLKSWAGEN', 'Volkswagen'),
        ('NISSAN', 'Nissan'),
        ('HONDA', 'Honda'),
        ('HYUNDAI', 'Hyundai'),
        ('KIA', 'Kia'),
        ('RENAULT', 'Renault'),
        ('PEUGEOT', 'Peugeot'),
        ('BMW', 'BMW'),
        ('MERCEDES', 'Mercedes-Benz'),
        ('AUDI', 'Audi'),
        ('VOLVO', 'Volvo'),
        ('SCANIA', 'Scania'),
        ('IVECO', 'Iveco'),
        ('MAN', 'MAN'),
        ('YAMAHA', 'Yamaha'),
        ('SUZUKI', 'Suzuki'),
        ('KAWASAKI', 'Kawasaki'),
        ('DUCATI', 'Ducati'),
        ('HARLEY_DAVIDSON', 'Harley-Davidson'),
        ('OUTRA', 'Outra'),
    ]
    
    # Choices para anos de fabricação
    ANO_CHOICES = [
        (None, 'Selecione o ano'),
    ] + [(year, str(year)) for year in range(2025, 1990, -1)]
    
    # Choices para status
    STATUS_CHOICES = [
        ('', 'Selecione o status'),
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
        ('SUSPENSA', 'Suspensa'),
        ('MANUTENCAO', 'Em Manutenção'),
    ]
    
    # Choices para tipo de viatura
    TIPO_VIATURA_CHOICES = [
        ('', 'Selecione o tipo'),
        ('VIATURA_INTERNA_ENTREGA', 'Entregas'),
        ('VIATURA_INTERNA_EXECUTIVO', 'Executivo'),
    ]
    
    # Campos customizados com choices
    categoria_veiculo = forms.ChoiceField(
        choices=CATEGORIA_VEICULO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    
    marca = forms.ChoiceField(
        choices=MARCA_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    
    ano_fabricacao = forms.ChoiceField(
        choices=ANO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    
    tipo = forms.ChoiceField(
        choices=TIPO_VIATURA_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label='Tipo de Viatura'
    )
    
    class Meta:
        model = Transportadora
        fields = [
            'nome', 'codigo', 'tipo', 'sucursal', 'categoria_veiculo',
            'placa', 'marca', 'modelo', 'ano_fabricacao',
            'capacidade_kg', 'quilometragem_atual', 'proxima_revisao',
            'motorista_responsavel', 'telefone_motorista',
            'prazo_entrega_padrao', 'custo_por_kg', 'custo_por_km', 'custo_fixo',
            'volume_m3_franquia', 'peso_kg_franquia', 'percentual_suplemento_carga',
            'status', 'ativa', 'observacoes'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'sucursal': forms.Select(attrs={'class': 'form-control'}),
            'categoria_veiculo': forms.Select(attrs={'class': 'form-control'}),
            'placa': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.Select(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'ano_fabricacao': forms.Select(attrs={'class': 'form-control'}),
            'capacidade_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'quilometragem_atual': forms.NumberInput(attrs={'class': 'form-control'}),
            'proxima_revisao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motorista_responsavel': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone_motorista': forms.TextInput(attrs={'class': 'form-control'}),
            'prazo_entrega_padrao': forms.NumberInput(attrs={'class': 'form-control'}),
            'custo_por_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'custo_por_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'custo_fixo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'volume_m3_franquia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'peso_kg_franquia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'percentual_suplemento_carga': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['volume_m3_franquia'].label = 'Volume incluído (m³)'
        self.fields['peso_kg_franquia'].label = 'Peso incluído (kg)'
        self.fields['percentual_suplemento_carga'].label = 'Suplemento % (acima das franquias)'
        
        # Configurar choices para sucursal
        from meuprojeto.empresa.models import Sucursal
        sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
        
        self.fields['sucursal'] = forms.ModelChoiceField(
            queryset=sucursais,
            widget=forms.Select(attrs={'class': 'form-control'}),
            required=True,
            label='Sucursal',
            empty_label='Selecione uma sucursal'
        )
        
        # Configurar choices para motorista responsável (funcionários)
        from meuprojeto.empresa.models_rh import Funcionario
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        motorista_choices = [('', 'Selecione um funcionário')]
        motorista_choices.extend([(func.nome_completo, f"{func.nome_completo} ({func.codigo_funcionario})") for func in funcionarios])
        
        self.fields['motorista_responsavel'] = forms.ChoiceField(
            choices=motorista_choices,
            widget=forms.Select(attrs={'class': 'form-control'}),
            required=True,
            label='Motorista Responsável'
        )
        
        # Tornar obrigatórios os campos específicos de viatura
        self.fields['placa'].required = True
        self.fields['marca'].required = True
        self.fields['modelo'].required = True
        self.fields['ano_fabricacao'].required = True
        # telefone_motorista não é obrigatório - será preenchido automaticamente

        if self.instance and self.instance.pk:
            self._ensure_choice_for_instance_value('tipo')
            self._ensure_choice_for_instance_value('categoria_veiculo')
            self._ensure_choice_for_instance_value('marca')
            self._ensure_choice_for_instance_value('status')
            self._ensure_choice_for_instance_value('motorista_responsavel')
            if self.instance.ano_fabricacao:
                ano_str = str(self.instance.ano_fabricacao)
                anos_validos = {
                    str(k) for k, _ in self.fields['ano_fabricacao'].choices if k is not None
                }
                if ano_str not in anos_validos:
                    self.fields['ano_fabricacao'].choices = list(
                        self.fields['ano_fabricacao'].choices
                    ) + [(ano_str, ano_str)]

        self._apply_stock_widget_classes()

    def _ensure_choice_for_instance_value(self, field_name):
        """Inclui valor gravado nas choices quando editar registos antigos."""
        value = getattr(self.instance, field_name, None)
        if not value:
            return
        field = self.fields.get(field_name)
        if not field or not hasattr(field, 'choices'):
            return
        valid = {str(k) for k, _ in field.choices if k not in (None, '')}
        if str(value) not in valid:
            label = value
            if field_name == 'tipo':
                label = dict(Transportadora.TIPO_CHOICES).get(value, value)
            field.choices = list(field.choices) + [(value, label)]

    def _apply_stock_widget_classes(self):
        """Classes CSS alinhadas ao padrão stock-form-page."""
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'form-check-input'
            elif isinstance(widget, forms.Select):
                widget.attrs['class'] = 'form-select'
            elif isinstance(widget, forms.Textarea):
                widget.attrs['class'] = 'form-control'
            else:
                widget.attrs['class'] = 'form-control'
    
    def get_funcionario_telefone(self, funcionario_nome):
        """Busca o telefone do funcionário pelo nome"""
        from meuprojeto.empresa.models_rh import Funcionario
        try:
            funcionario = Funcionario.objects.get(nome_completo=funcionario_nome, status='AT')
            return funcionario.telefone or funcionario.telefone_alternativo or 'N/A'
        except Funcionario.DoesNotExist:
            return 'N/A'


# =============================================================================
# VIEWS PARA VIATURAS INTERNAS (MEIOS CIRCULANTES DA EMPRESA)
# =============================================================================

def viaturas_list(request):
    """Lista de viaturas internas da empresa"""
    from django.core.paginator import Paginator
    
    # Filtros
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    tipo_viatura = request.GET.get('tipo_viatura', '').strip()
    sucursal_filter = request.GET.get('sucursal', '').strip()
    
    # Query base - apenas viaturas internas (ambas as categorias)
    viaturas = Transportadora.objects.filter(
        tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO']
    ).select_related('sucursal')
    
    # Aplicar filtros
    if search:
        viaturas = viaturas.filter(
            Q(nome__icontains=search) |
            Q(codigo__icontains=search) |
            Q(placa__icontains=search) |
            Q(motorista_responsavel__icontains=search)
        )
    
    if status:
        viaturas = viaturas.filter(status=status)
    
    if categoria:
        viaturas = viaturas.filter(categoria_veiculo=categoria)
    
    if tipo_viatura:
        viaturas = viaturas.filter(tipo=tipo_viatura)
    
    if sucursal_filter:
        viaturas = viaturas.filter(sucursal_id=sucursal_filter)
    
    stats = {
        'total': viaturas.count(),
        'ativas': viaturas.filter(status='ATIVA', ativa=True).count(),
        'entregas': viaturas.filter(tipo='VIATURA_INTERNA_ENTREGA').count(),
        'executivo': viaturas.filter(tipo='VIATURA_INTERNA_EXECUTIVO').count(),
        'manutencao': viaturas.filter(status='MANUTENCAO').count(),
    }
    
    # Ordenar por tipo primeiro, depois por nome
    viaturas = viaturas.order_by('tipo', 'nome')
    
    # Paginação
    paginator = Paginator(viaturas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = Transportadora.STATUS_CHOICES
    categoria_choices = [
        ('AUTOMOVEL', 'Automóvel'),
        ('MOTOCICLETA', 'Motocicleta'),
        ('VAN', 'Van'),
        ('CAMINHAO', 'Caminhão'),
        ('BICICLETA', 'Bicicleta'),
    ]
    
    tipo_viatura_choices = [
        ('VIATURA_INTERNA_ENTREGA', 'Entregas'),
        ('VIATURA_INTERNA_EXECUTIVO', 'Executivo'),
    ]
    
    # Obter sucursais ativas para o filtro
    from meuprojeto.empresa.models import Sucursal
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'status': status,
        'categoria': categoria,
        'tipo_viatura': tipo_viatura,
        'sucursal_filter': sucursal_filter,
        'status_choices': status_choices,
        'categoria_choices': categoria_choices,
        'tipo_viatura_choices': tipo_viatura_choices,
        'sucursais': sucursais,
        'has_filters': bool(search or status or categoria or tipo_viatura or sucursal_filter),
    }
    return render(request, 'stock/logistica/viaturas/list.html', context)


def viatura_create(request):
    """Criar nova viatura interna"""
    if request.method == 'POST':
        form = ViaturaForm(request.POST)
        if form.is_valid():
            viatura = form.save(commit=False)
            # O tipo será definido pelo formulário (VIATURA_INTERNA_ENTREGA ou VIATURA_INTERNA_EXECUTIVO)
            
            # Preencher telefone do motorista automaticamente
            if viatura.motorista_responsavel:
                telefone = form.get_funcionario_telefone(viatura.motorista_responsavel)
                viatura.telefone_motorista = telefone
            
            viatura.save()
            messages.success(request, f'Viatura {viatura.nome} criada com sucesso!')
            return redirect('stock:logistica:viaturas_list')
    else:
        form = ViaturaForm()
    
    context = {
        'form': form,
        'title': 'Nova Viatura Interna',
    }
    return render(request, 'stock/logistica/viaturas/create.html', context)


def viatura_edit(request, id):
    """Editar viatura interna"""
    viatura = get_object_or_404(
        Transportadora.objects.select_related('sucursal'),
        id=id,
        tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO'],
    )
    
    if request.method == 'POST':
        form = ViaturaForm(request.POST, instance=viatura)
        if form.is_valid():
            viatura = form.save(commit=False)
            
            # Preencher telefone do motorista automaticamente
            if viatura.motorista_responsavel:
                telefone = form.get_funcionario_telefone(viatura.motorista_responsavel)
                viatura.telefone_motorista = telefone
            
            viatura.save()
            messages.success(request, f'Viatura {viatura.nome} atualizada com sucesso!')
            return redirect('stock:logistica:viatura_detail', id=viatura.id)
    else:
        form = ViaturaForm(instance=viatura)
    
    context = {
        'form': form,
        'viatura': viatura,
        'title': f'Editar {viatura.nome}',
    }
    return render(request, 'stock/logistica/viaturas/edit.html', context)


def viatura_detail(request, id):
    """Detalhes da viatura interna"""
    viatura = get_object_or_404(
        Transportadora.objects.select_related('sucursal'),
        id=id,
        tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO'],
    )

    operacoes = viatura.operacoes_externas.all()
    entregas = viatura.entregas.all()

    operacoes_em_curso = operacoes.filter(
        status__in=['PENDENTE', 'ATRIBUIDA', 'COLETADA', 'EM_TRANSITO']
    ).count()
    operacoes_concluidas = operacoes.filter(
        status__in=['ENTREGUE', 'CONCLUIDA']
    ).count()

    entregas_completas = entregas.filter(
        status_atual='ENTREGUE',
        data_entrega_realizada__isnull=False,
    )
    tempo_medio_entrega = 0
    if entregas_completas.exists():
        tempos = []
        for entrega in entregas_completas:
            if entrega.data_entrega_realizada and entrega.data_criacao:
                delta = entrega.data_entrega_realizada - entrega.data_criacao
                tempos.append(delta.total_seconds() / 3600)
        if tempos:
            tempo_medio_entrega = sum(tempos) / len(tempos)

    stats = {
        'total_operacoes': operacoes.count(),
        'operacoes_em_curso': operacoes_em_curso,
        'operacoes_concluidas': operacoes_concluidas,
        'total_entregas': entregas.count(),
        'tempo_medio_entrega': tempo_medio_entrega,
    }

    operacoes_recentes = (
        operacoes.select_related('transferencia', 'ordem_compra')
        .order_by('-data_notificacao')[:10]
    )

    categoria_labels = {
        'AUTOMOVEL': 'Automóvel',
        'MOTOCICLETA': 'Motocicleta',
        'VAN': 'Van',
        'CAMINHAO': 'Caminhão',
        'BICICLETA': 'Bicicleta',
    }

    context = {
        'viatura': viatura,
        'stats': stats,
        'operacoes_recentes': operacoes_recentes,
        'categoria_display': (
            categoria_labels.get(viatura.categoria_veiculo)
            or viatura.categoria_veiculo
            or '—'
        ),
    }
    return render(request, 'stock/logistica/viaturas/detail.html', context)


def viatura_delete(request, id):
    """Excluir viatura interna"""
    viatura = get_object_or_404(Transportadora, id=id, tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO'])
    
    if request.method == 'POST':
        viatura.delete()
        messages.success(request, f'Viatura {viatura.nome} excluída com sucesso!')
        return redirect('stock:logistica:viaturas_list')
    
    return render(request, 'stock/logistica/viaturas/delete.html', {
        'viatura': viatura
    })


class RastreamentoForm(forms.ModelForm):
    class Meta:
        model = RastreamentoEntrega
        fields = [
            'transportadora', 'veiculo_interno',
            'destinatario_nome', 'destinatario_telefone',
            'endereco_entrega', 'cidade_entrega', 'provincia_entrega',
            'peso_total', 'valor_declarado', 'custo_envio',
            'data_entrega_prevista', 'observacoes'
        ]
        widgets = {
            'transportadora': forms.Select(attrs={'class': 'form-control'}),
            'veiculo_interno': forms.Select(attrs={'class': 'form-control'}),
            'destinatario_nome': forms.TextInput(attrs={'class': 'form-control'}),
            'destinatario_telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'endereco_entrega': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cidade_entrega': forms.TextInput(attrs={'class': 'form-control'}),
            'provincia_entrega': forms.TextInput(attrs={'class': 'form-control'}),
            'peso_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'valor_declarado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'custo_envio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'data_entrega_prevista': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Transportadoras ativas
        self.fields['transportadora'].queryset = Transportadora.objects.filter(status='ATIVA')
        
        # Veículos internos ativos
        self.fields['veiculo_interno'].queryset = VeiculoInterno.objects.filter(status='ATIVO')
        
        # Tornar campos opcionais
        self.fields['transportadora'].required = False
        self.fields['veiculo_interno'].required = False
        self.fields['peso_total'].required = False
        self.fields['valor_declarado'].required = False
        self.fields['custo_envio'].required = False
        self.fields['data_entrega_prevista'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        transportadora = cleaned_data.get('transportadora')
        veiculo_interno = cleaned_data.get('veiculo_interno')
        
        # Validar que apenas um tipo de transporte seja selecionado
        if not transportadora and not veiculo_interno:
            raise forms.ValidationError("Selecione uma transportadora ou veículo interno.")
        
        if transportadora and veiculo_interno:
            raise forms.ValidationError("Selecione apenas uma transportadora OU um veículo interno.")
        
        return cleaned_data


# =============================================================================
# VIEWS PARA RASTREAMENTO DE ENTREGAS
# =============================================================================

@login_required
@require_stock_access
def rastreamento_create(request):
    """Criar novo rastreamento de entrega."""
    if request.method == 'POST':
        form = RastreamentoForm(request.POST)
        if form.is_valid():
            try:
                rastreamento = form.save(commit=False)
                rastreamento.criado_por = request.user
                rastreamento.status_atual = 'PREPARANDO'
                
                rastreamento.save()
                
                messages.success(request, f'Rastreamento criado com sucesso! Código: {rastreamento.codigo_rastreamento}')
                return redirect('stock:logistica:rastreamento_detail', id=rastreamento.id)
                
            except Exception as e:
                logger.error(f"Erro ao criar rastreamento: {e}")
                messages.error(request, f'Erro ao criar rastreamento: {str(e)}')
    else:
        form = RastreamentoForm()
    
    context = {
        'form': form,
        'title': 'Criar Rastreamento de Entrega',
    }
    
    return render(request, 'stock/logistica/rastreamento_form.html', context)


@login_required
@require_stock_access
def rastreamento_edit(request, id):
    """Editar rastreamento de entrega."""
    rastreamento = get_object_or_404(RastreamentoEntrega, id=id)
    
    if request.method == 'POST':
        form = RastreamentoForm(request.POST, instance=rastreamento)
        if form.is_valid():
            try:
                rastreamento = form.save()
                messages.success(request, 'Rastreamento atualizado com sucesso!')
                return redirect('stock:logistica:rastreamento_detail', id=rastreamento.id)
                
            except Exception as e:
                logger.error(f"Erro ao atualizar rastreamento: {e}")
                messages.error(request, f'Erro ao atualizar rastreamento: {str(e)}')
    else:
        form = RastreamentoForm(instance=rastreamento)
    
    context = {
        'form': form,
        'rastreamento': rastreamento,
        'title': 'Editar Rastreamento de Entrega',
    }
    
    return render(request, 'stock/logistica/rastreamento_form.html', context)


# =============================================================================
# VIEWS AJAX PARA FUNCIONALIDADES DINÂMICAS
# =============================================================================

@login_required
@require_stock_access
def get_funcionario_telefone(request):
    """View AJAX para buscar telefone do funcionário"""
    from django.views.decorators.http import require_GET
    from meuprojeto.empresa.models_rh import Funcionario
    
    nome_funcionario = request.GET.get('nome', '')
    
    if not nome_funcionario:
        return JsonResponse({'telefone': ''})
    
    try:
        funcionario = Funcionario.objects.get(nome_completo=nome_funcionario, status='AT')
        telefone = funcionario.telefone or funcionario.telefone_alternativo or ''
        return JsonResponse({'telefone': telefone})
    except Funcionario.DoesNotExist:
        return JsonResponse({'telefone': ''})
        
        # Tornar campos opcionais
        self.fields['peso_total'].required = False
        self.fields['valor_declarado'].required = False
        self.fields['custo_envio'].required = False
        self.fields['data_entrega_prevista'].required = False
        self.fields['destinatario_telefone'].required = False


# =============================================================================
# VIEWS PARA NOTIFICAÇÕES LOGÍSTICAS UNIFICADAS
# =============================================================================

@login_required
@require_stock_access
def operacoes_logistica_list(request):
    """Lista unificada de operações logísticas (transferências e coletas)"""
    from .models_stock import NotificacaoLogisticaUnificada
    from django.core.paginator import Paginator
    
    # Filtros
    status = request.GET.get('status', '')
    prioridade = request.GET.get('prioridade', '')
    tipo_operacao = request.GET.get('tipo_operacao', '')
    search = request.GET.get('search', '')
    
    # Query base - mostrar todas as notificações por padrão
    notificacoes = NotificacaoLogisticaUnificada.objects.select_related(
        'transferencia', 'transferencia__sucursal_origem', 'transferencia__sucursal_destino',
        'ordem_compra', 'ordem_compra__fornecedor', 'ordem_compra__sucursal_destino',
        'veiculo_interno', 'transportadora_externa', 'usuario_notificacao'
    ).order_by('-data_notificacao')
    
    # Aplicar filtros
    if status:
        # Se status específico foi solicitado, filtrar por esse status
        notificacoes = notificacoes.filter(status=status)
    if prioridade:
        notificacoes = notificacoes.filter(prioridade=prioridade)
    if tipo_operacao:
        notificacoes = notificacoes.filter(tipo_operacao=tipo_operacao)
    if search:
        notificacoes = notificacoes.filter(
            Q(transferencia__codigo__icontains=search) |
            Q(ordem_compra__codigo__icontains=search) |
            Q(transferencia__sucursal_origem__nome__icontains=search) |
            Q(transferencia__sucursal_destino__nome__icontains=search) |
            Q(ordem_compra__fornecedor__nome__icontains=search) |
            Q(ordem_compra__sucursal_destino__nome__icontains=search) |
            Q(observacoes__icontains=search)
        )
    
    # Paginação
    paginator = Paginator(notificacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas (baseadas em todas as notificações, não apenas as filtradas)
    todas_notificacoes = NotificacaoLogisticaUnificada.objects.all()
    stats = {
        'total': todas_notificacoes.count(),
        'pendentes': todas_notificacoes.filter(status='PENDENTE').count(),
        'atribuidas': todas_notificacoes.filter(status='ATRIBUIDA').count(),
        'em_andamento': todas_notificacoes.filter(status__in=['COLETADA', 'EM_TRANSITO']).count(),
        'concluidas': todas_notificacoes.filter(status='CONCLUIDA').count(),
        'urgentes': todas_notificacoes.filter(prioridade='URGENTE').count(),
        'transferencias': todas_notificacoes.filter(tipo_operacao='TRANSFERENCIA').count(),
        'coletas': todas_notificacoes.filter(tipo_operacao='COLETA').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'status': status,
        'prioridade': prioridade,
        'tipo_operacao': tipo_operacao,
        'search': search,
        'status_choices': NotificacaoLogisticaUnificada.STATUS_CHOICES,
        'tipo_operacao_choices': NotificacaoLogisticaUnificada.TIPO_OPERACAO_CHOICES,
        'prioridade_choices': [
            ('BAIXA', 'Baixa'),
            ('NORMAL', 'Normal'),
            ('ALTA', 'Alta'),
            ('URGENTE', 'Urgente'),
        ],
    }
    
    return render(request, 'stock/logistica/operacoes/list.html', context)


@login_required
@require_stock_access
def operacao_logistica_detail(request, id):
    """Detalhes de uma operação logística unificada"""
    from .models_stock import NotificacaoLogisticaUnificada
    
    notificacao = get_object_or_404(
        NotificacaoLogisticaUnificada.objects.select_related(
            'transferencia', 'transferencia__sucursal_origem', 'transferencia__sucursal_destino',
            'ordem_compra', 'ordem_compra__fornecedor', 'ordem_compra__sucursal_destino',
            'veiculo_interno', 'transportadora_externa', 'usuario_notificacao', 'usuario_atribuicao'
        ),
        id=id
    )
    
    # Buscar itens da operação
    if notificacao.tipo_operacao == 'TRANSFERENCIA':
        itens_operacao = notificacao.transferencia.itens.select_related('item').all()
    else:
        itens_operacao = notificacao.ordem_compra.itens.all()

    # Linha do tempo (rastreamento) associada
    try:
        rastreamento = get_or_create_rastreamento_for_notificacao(RastreamentoEntrega, EventoRastreamento, notificacao, request.user)
        eventos_rastreamento = rastreamento.eventos.all().order_by('-data_evento')
    except Exception:
        rastreamento = None
        eventos_rastreamento = []
    
    context = {
        'notificacao': notificacao,
        'itens_operacao': itens_operacao,
        'rastreamento': rastreamento,
        'eventos_rastreamento': eventos_rastreamento,
    }
    
    return render(request, 'stock/logistica/operacoes/detail.html', context)


def _buscar_rastreamento_notificacao(notificacao):
    """Rastreamento ligado à operação, sem criar registo."""
    if getattr(notificacao, 'transferencia_id', None):
        return RastreamentoEntrega.objects.filter(transferencia_id=notificacao.transferencia_id).first()
    if getattr(notificacao, 'ordem_compra_id', None):
        return RastreamentoEntrega.objects.filter(ordem_compra_id=notificacao.ordem_compra_id).first()
    return None


def _valores_iniciais_atribuicao(notificacao, rastreamento=None):
    """Pré-preenche o formulário de atribuição com dados já gravados."""
    valores = {
        'tipo_transporte': notificacao.tipo_transporte or '',
        'transportadora_id': notificacao.transportadora_externa_id,
        'observacoes': notificacao.observacoes or '',
        'distancia_km': None,
        'usar_peso': False,
        'usar_dimensoes': False,
        'peso_kg': None,
        'comprimento_cm': None,
        'largura_cm': None,
        'altura_cm': None,
    }
    if rastreamento:
        if rastreamento.distancia_km:
            valores['distancia_km'] = rastreamento.distancia_km
        if rastreamento.peso_total:
            valores['usar_peso'] = True
            valores['peso_kg'] = rastreamento.peso_total
        if rastreamento.comprimento_cm and rastreamento.largura_cm and rastreamento.altura_cm:
            valores['usar_dimensoes'] = True
            valores['comprimento_cm'] = rastreamento.comprimento_cm
            valores['largura_cm'] = rastreamento.largura_cm
            valores['altura_cm'] = rastreamento.altura_cm
    return valores


@login_required
@require_stock_access
def operacao_atribuir_transporte(request, id):
    """Atribuir ou alterar transporte de uma operação logística."""
    from .models_stock import NotificacaoLogisticaUnificada, Transportadora

    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)

    if notificacao.status not in ('PENDENTE', 'ATRIBUIDA'):
        messages.error(
            request,
            'Só é possível atribuir ou alterar o transporte enquanto a operação estiver pendente ou com transporte atribuído (antes da coleta).',
        )
        return redirect('stock:logistica:operacao_detail', id=notificacao.id)

    rastreamento_existente = _buscar_rastreamento_notificacao(notificacao)
    alterar_transporte = (
        notificacao.status == 'ATRIBUIDA'
        or bool(notificacao.transportadora_externa_id or notificacao.veiculo_interno_id)
    )

    if request.method == 'POST':
        tipo_transporte = request.POST.get('tipo_transporte')
        veiculo_id = request.POST.get('veiculo_interno')
        transportadora_id = request.POST.get('transportadora_externa')
        observacoes = request.POST.get('observacoes', '')
        distancia_km = parse_distancia_km(request.POST.get('distancia_km'))
        carga_params = resolver_carga_params(
            notificacao,
            usar_peso=request.POST.get('usar_peso'),
            peso_kg_manual=request.POST.get('peso_kg'),
            usar_dimensoes=request.POST.get('usar_dimensoes'),
            volume_m3_manual=request.POST.get('volume_m3'),
            comprimento_cm_manual=request.POST.get('comprimento_cm'),
            largura_cm_manual=request.POST.get('largura_cm'),
            altura_cm_manual=request.POST.get('altura_cm'),
        )
        
        # Validação
        if distancia_km is None or distancia_km <= 0:
            messages.error(request, 'Informe a distância da entrega em km (valor maior que zero).')
        elif tipo_transporte == 'VEICULO_INTERNO' and not veiculo_id:
            messages.error(request, 'Selecione um veículo interno.')
        elif tipo_transporte == 'TRANSPORTADORA_EXTERNA' and not transportadora_id:
            messages.error(request, 'Selecione uma transportadora externa.')
        else:
            # Atualizar notificação
            notificacao.tipo_transporte = tipo_transporte
            notificacao.usuario_atribuicao = request.user
            
            if tipo_transporte == 'VEICULO_INTERNO':
                notificacao.transportadora_externa_id = veiculo_id
                notificacao.veiculo_interno = None
            else:
                # Para transportadoras externas, usar o campo transportadora_externa
                notificacao.transportadora_externa_id = transportadora_id
                notificacao.veiculo_interno = None
            
            if observacoes:
                notificacao.observacoes = observacoes
            
            notificacao.save()

            # Garantir rastreamento ligado já na atribuição e sincronizar status
            rastreamento = get_or_create_rastreamento_for_notificacao(
                RastreamentoEntrega, EventoRastreamento, notificacao, request.user,
                distancia_km_manual=distancia_km,
                carga_params=carga_params,
            )
            sincronizar_rastreamento_com_notificacao(EventoRastreamento, notificacao, rastreamento, request.user)
            rastreamento.refresh_from_db(fields=['custo_envio', 'distancia_km'])

            acao = 'alterado' if alterar_transporte else 'atribuído'
            if rastreamento.custo_envio and rastreamento.distancia_km:
                messages.success(
                    request,
                    f'Transporte {acao} com sucesso! Frete estimado: {rastreamento.custo_envio:.2f} MT '
                    f'({rastreamento.distancia_km:.1f} km).',
                )
            else:
                messages.success(request, f'Transporte {acao} com sucesso!')
            return redirect('stock:logistica:operacao_detail', id=notificacao.id)
    
    # Viaturas internas usam o cadastro de Transportadora (Logística → Viaturas)
    viaturas_internas = Transportadora.objects.filter(
        tipo__in=TIPOS_VIATURA_INTERNA,
        status='ATIVA',
    ).order_by('nome')
    
    transportadoras_externas = Transportadora.objects.filter(
        tipo__in=['TRANSPORTADORA', 'ENTREGA_RAPIDA', 'CORREIOS', 'MOTORISTA', 'TERCEIRIZADA'],
        status='ATIVA'
    ).order_by('nome')

    distancia_info = None
    carga_info = None
    try:
        distancia_info = calcular_distancia_operacao(notificacao)
    except Exception:
        logger.exception('Falha ao calcular distância da operação %s', notificacao.id)
    try:
        carga_info = estimar_carga(notificacao)
    except Exception:
        logger.exception('Falha ao estimar carga da operação %s', notificacao.id)
    
    valores_iniciais = _valores_iniciais_atribuicao(notificacao, rastreamento_existente)

    context = {
        'notificacao': notificacao,
        'viaturas_internas': viaturas_internas,
        'veiculos_internos': viaturas_internas,
        'transportadoras_externas': transportadoras_externas,
        'distancia_info': distancia_info,
        'carga_info': carga_info,
        'alterar_transporte': alterar_transporte,
        'valores_iniciais': valores_iniciais,
        'rastreamento': rastreamento_existente,
    }

    return render(request, 'stock/logistica/operacoes/atribuir.html', context)


@login_required
@require_stock_access
@require_http_methods(["POST"])
def operacao_cotacao_frete(request, id):
    """API: estimativa de frete por distância para uma operação."""
    from .models_stock import NotificacaoLogisticaUnificada

    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    try:
        tipo_transporte = payload.get('tipo_transporte')
        distancia_info = distancia_result_com_override(
            notificacao,
            payload.get('distancia_km'),
        )
        carga_params = resolver_carga_params(
            notificacao,
            usar_peso=payload.get('usar_peso'),
            peso_kg_manual=payload.get('peso_kg'),
            usar_dimensoes=payload.get('usar_dimensoes'),
            volume_m3_manual=payload.get('volume_m3'),
            comprimento_cm_manual=payload.get('comprimento_cm'),
            largura_cm_manual=payload.get('largura_cm'),
            altura_cm_manual=payload.get('altura_cm'),
        )

        veiculo = None
        transportadora = None
        if tipo_transporte == 'VEICULO_INTERNO':
            viatura_id = payload.get('veiculo_id')
            if not viatura_id:
                return JsonResponse({'error': 'veiculo_id é obrigatório'}, status=400)
            transportadora = get_object_or_404(
                Transportadora,
                id=viatura_id,
                tipo__in=TIPOS_VIATURA_INTERNA,
                status='ATIVA',
            )
        elif tipo_transporte == 'TRANSPORTADORA_EXTERNA':
            transportadora_id = payload.get('transportadora_id')
            if not transportadora_id:
                return JsonResponse({'error': 'transportadora_id é obrigatório'}, status=400)
            transportadora = get_object_or_404(Transportadora, id=transportadora_id, status='ATIVA')
        else:
            return JsonResponse({
                'distancia': distancia_result_to_dict(distancia_info),
                'carga_estimativa': carga_estimativa_to_dict(estimar_carga(notificacao)),
            })

        frete = calcular_frete_operacao(
            notificacao,
            transportadora=transportadora,
            distancia=distancia_info,
            carga=carga_params,
        )
        return JsonResponse({
            'distancia': distancia_result_to_dict(distancia_info),
            'frete': freight_result_to_dict(frete),
        })
    except Exception as exc:
        logger.exception('Falha na cotação de frete da operação %s', notificacao.id)
        return JsonResponse({'error': str(exc)}, status=500)


STATUS_COM_GUIA_TRANSPORTE = ('COLETADA', 'EM_TRANSITO', 'ENTREGUE', 'CONCLUIDA')


def _unidade_item_stock(produto):
    if not produto:
        return 'UN'
    return getattr(produto, 'unidade_medida', None) or 'UN'


def _codigo_documento_operacao(notificacao):
    if notificacao.tipo_operacao == 'TRANSFERENCIA' and getattr(notificacao, 'transferencia_id', None):
        return notificacao.transferencia.codigo
    if getattr(notificacao, 'ordem_compra_id', None):
        return notificacao.ordem_compra.codigo
    return '—'


def _linha_localidade(entidade, attr_bairro='bairro', attr_cidade='cidade', attr_provincia='provincia'):
    if not entidade:
        return ''
    partes = []
    bairro = getattr(entidade, attr_bairro, None)
    cidade = getattr(entidade, attr_cidade, None)
    if bairro:
        partes.append(str(bairro))
    if cidade:
        partes.append(str(cidade))
    if hasattr(entidade, 'get_provincia_display'):
        partes.append(entidade.get_provincia_display())
    else:
        provincia = getattr(entidade, attr_provincia, None)
        if provincia:
            partes.append(str(provincia))
    return ', '.join(partes)


def _ponto_rota_guia(notificacao, sentido):
    """Origem ou destino da operação para a guia compacta."""
    vazio = {'rotulo': '—', 'nome': '—', 'endereco': '', 'localidade': '', 'telefone': ''}
    if notificacao.tipo_operacao == 'TRANSFERENCIA' and getattr(notificacao, 'transferencia_id', None):
        suc = (
            notificacao.transferencia.sucursal_destino
            if sentido == 'destino'
            else notificacao.transferencia.sucursal_origem
        )
        if not suc:
            return vazio
        return {
            'rotulo': 'Sucursal',
            'nome': suc.nome,
            'endereco': suc.endereco or '',
            'localidade': _linha_localidade(suc, 'bairro', 'cidade', 'provincia'),
            'telefone': suc.telefone or '',
        }
    if getattr(notificacao, 'ordem_compra_id', None):
        if sentido == 'origem':
            f = notificacao.ordem_compra.fornecedor
            if not f:
                return vazio
            loc = f.cidade or ''
            if f.provincia:
                loc = f'{loc} — {f.provincia}' if loc else str(f.provincia)
            return {
                'rotulo': 'Fornecedor',
                'nome': f.nome,
                'endereco': f.endereco or '',
                'localidade': loc,
                'telefone': f.telefone or '',
            }
        suc = notificacao.ordem_compra.sucursal_destino
        if not suc:
            return vazio
        return {
            'rotulo': 'Sucursal',
            'nome': suc.nome,
            'endereco': suc.endereco or '',
            'localidade': _linha_localidade(suc, 'bairro', 'cidade', 'provincia'),
            'telefone': suc.telefone or '',
        }
    return vazio


def _resumo_linhas_guia(notificacao, total_itens):
    """Pares (rótulo, valor) agrupados de 2 em 2 para tabela compacta."""
    motorista = notificacao.motorista_operacao or ''
    if not motorista and notificacao.veiculo_interno:
        motorista = getattr(notificacao.veiculo_interno, 'motorista_responsavel', '') or ''
    veiculo = ''
    if notificacao.veiculo_interno:
        veiculo = f'{notificacao.veiculo_interno.nome} ({notificacao.veiculo_interno.placa})'
    transportadora = (
        notificacao.transportadora_externa.nome
        if notificacao.transportadora_externa_id
        else ''
    )
    coleta = (
        notificacao.data_coleta.strftime('%d/%m/%Y %H:%M')
        if notificacao.data_coleta
        else '—'
    )
    coletado = ''
    if notificacao.coletado_por:
        coletado = notificacao.coletado_por.get_full_name() or notificacao.coletado_por.username

    campos = [
        ('Tipo', notificacao.get_tipo_operacao_display()),
        ('Prioridade', notificacao.get_prioridade_display()),
        ('Doc. origem', _codigo_documento_operacao(notificacao)),
        ('Itens', str(total_itens)),
        ('Coleta', coleta),
        ('Coletado por', coletado or '—'),
    ]
    if veiculo:
        campos.append(('Veículo', veiculo))
    if motorista:
        campos.append(('Motorista', motorista))
    if transportadora:
        campos.append(('Transportadora', transportadora))
    if notificacao.telefone_motorista_operacao:
        campos.append(('Telefone', notificacao.telefone_motorista_operacao))
    if notificacao.local_coleta:
        campos.append(('Local coleta', notificacao.local_coleta))

    linhas = []
    for i in range(0, len(campos), 2):
        par = campos[i:i + 2]
        while len(par) < 2:
            par.append(('', ''))
        linhas.append(par)
    return linhas


def _itens_para_guia_transporte(notificacao):
    """Normaliza itens da operação para o template da guia de transporte."""
    itens = []
    if notificacao.tipo_operacao == 'TRANSFERENCIA' and getattr(notificacao, 'transferencia_id', None):
        for row in notificacao.transferencia.itens.select_related('item').all():
            prod = row.item
            itens.append({
                'codigo': (prod.codigo if prod else '') or '-',
                'nome': (prod.nome if prod else '') or 'Item não especificado',
                'quantidade_solicitada': row.quantidade_solicitada,
                'unidade': _unidade_item_stock(prod),
                'observacoes': row.observacoes or '-',
            })
    elif getattr(notificacao, 'ordem_compra_id', None):
        for row in notificacao.ordem_compra.itens.select_related('produto').all():
            prod = row.produto
            itens.append({
                'codigo': (prod.codigo if prod else '') or '-',
                'nome': (prod.nome if prod else '') or 'Item não especificado',
                'quantidade_solicitada': row.quantidade_solicitada,
                'unidade': _unidade_item_stock(prod),
                'observacoes': '-',
            })
    return itens


@login_required
@require_stock_access
def operacao_guia_transporte(request, id):
    """Guia de transporte imprimível (após coleta confirmada)."""
    from .models_stock import NotificacaoLogisticaUnificada

    notificacao = get_object_or_404(
        NotificacaoLogisticaUnificada.objects.select_related(
            'transferencia', 'transferencia__sucursal_origem', 'transferencia__sucursal_destino',
            'ordem_compra', 'ordem_compra__fornecedor', 'ordem_compra__sucursal_destino',
            'veiculo_interno', 'transportadora_externa', 'coletado_por',
        ),
        id=id,
    )

    if notificacao.status not in STATUS_COM_GUIA_TRANSPORTE:
        messages.error(
            request,
            'A guia de transporte só está disponível após confirmar a coleta da operação.',
        )
        return redirect('stock:logistica:operacao_detail', id=id)

    agora = timezone.now()
    itens = _itens_para_guia_transporte(notificacao)
    context = {
        'notificacao': notificacao,
        'itens': itens,
        'resumo_linhas': _resumo_linhas_guia(notificacao, len(itens)),
        'origem': _ponto_rota_guia(notificacao, 'origem'),
        'destino': _ponto_rota_guia(notificacao, 'destino'),
        'data_relatorio': agora,
        'data_geracao': agora,
        'user': request.user,
        'imprimir_auto': request.GET.get('imprimir') == '1',
    }
    return render(request, 'stock/logistica/guias/guia_carga.html', context)


@login_required
@require_stock_access
def operacao_confirmar_coleta(request, id):
    """Confirmar coleta da mercadoria"""
    from .models_stock import NotificacaoLogisticaUnificada
    
    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    
    # Verificar se pode coletar
    if notificacao.status != 'ATRIBUIDA':
        messages.error(request, f'Esta operação não pode ser coletada no status atual: {notificacao.get_status_display()}.')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    if request.method == 'POST':
        observacoes = request.POST.get('observacoes', '')
        models_ctx = {
            'RastreamentoEntrega': RastreamentoEntrega,
            'EventoRastreamento': EventoRastreamento,
            'get_or_create': get_or_create_rastreamento_for_notificacao,
            'sync': sincronizar_rastreamento_com_notificacao,
        }
        logistica_ops.confirmar_coleta(models_ctx, notificacao, request.user, observacoes)
        notificacao.refresh_from_db()

        messages.success(
            request,
            f'Coleta confirmada ({notificacao.codigo_operacao or notificacao.id}). '
            'Pode imprimir a guia de transporte.',
        )
        url = reverse('stock:logistica:operacao_guia_transporte', kwargs={'id': id})
        return redirect(f'{url}?imprimir=1')
    
    context = {
        'notificacao': notificacao,
    }
    return render(request, 'stock/logistica/operacoes/confirmar_coleta.html', context)


@login_required
@require_stock_access
def operacao_iniciar_transporte(request, id):
    """Iniciar transporte da mercadoria"""
    from .models_stock import NotificacaoLogisticaUnificada
    
    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    
    # Verificar se pode iniciar transporte
    if notificacao.status != 'COLETADA':
        messages.error(request, f'Esta operação não pode iniciar transporte no status atual: {notificacao.get_status_display()}.')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    if request.method == 'POST':
        observacoes = request.POST.get('observacoes', '')
        models_ctx = {
            'RastreamentoEntrega': RastreamentoEntrega,
            'EventoRastreamento': EventoRastreamento,
            'get_or_create': get_or_create_rastreamento_for_notificacao,
            'sync': sincronizar_rastreamento_com_notificacao,
        }
        logistica_ops.iniciar_transporte(models_ctx, notificacao, request.user, observacoes)

        messages.success(request, f'Transporte iniciado para operação {notificacao.id}!')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    context = {
        'notificacao': notificacao,
    }
    return render(request, 'stock/logistica/operacoes/iniciar_transporte.html', context)


@login_required
@require_stock_access
def operacao_confirmar_entrega(request, id):
    """Confirmar entrega da mercadoria"""
    from .models_stock import NotificacaoLogisticaUnificada
    
    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    
    # Verificar se pode entregar
    if notificacao.status != 'EM_TRANSITO':
        messages.error(request, f'Esta operação não pode ser entregue no status atual: {notificacao.get_status_display()}.')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    if request.method == 'POST':
        observacoes = request.POST.get('observacoes', '')
        models_ctx = {
            'RastreamentoEntrega': RastreamentoEntrega,
            'EventoRastreamento': EventoRastreamento,
            'get_or_create': get_or_create_rastreamento_for_notificacao,
            'sync': sincronizar_rastreamento_com_notificacao,
        }
        logistica_ops.confirmar_entrega(models_ctx, notificacao, request.user, observacoes)

        messages.success(request, f'Entrega confirmada para operação {notificacao.id}!')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    context = {
        'notificacao': notificacao,
    }
    return render(request, 'stock/logistica/operacoes/confirmar_entrega.html', context)


@login_required
@require_stock_access
def operacao_concluir(request, id):
    """Concluir uma operação logística"""
    from .models_stock import NotificacaoLogisticaUnificada
    
    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    
    # Verificar se pode concluir
    if notificacao.status != 'ENTREGUE':
        messages.error(request, f'Esta operação não pode ser concluída no status atual: {notificacao.get_status_display()}.')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    if request.method == 'POST':
        observacoes = request.POST.get('observacoes', '')
        models_ctx = {
            'RastreamentoEntrega': RastreamentoEntrega,
            'EventoRastreamento': EventoRastreamento,
            'get_or_create': get_or_create_rastreamento_for_notificacao,
            'sync': sincronizar_rastreamento_com_notificacao,
        }
        logistica_ops.concluir_operacao(models_ctx, notificacao, request.user, observacoes)
        messages.success(request, 'Operação concluída com sucesso!')
        return redirect('stock:logistica:operacoes_list')
    
    context = {
        'notificacao': notificacao,
    }
    
    return render(request, 'stock/logistica/operacoes/concluir.html', context)


@login_required
@require_stock_access
@require_http_methods(["GET", "POST"])
def operacao_editar_prioridade(request, id):
    """Editar prioridade de uma operação logística"""
    from .models_stock import NotificacaoLogisticaUnificada
    
    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    
    # Verificar se pode editar prioridade (apenas antes da coleta)
    if notificacao.status not in ['PENDENTE', 'ATRIBUIDA']:
        messages.error(request, f'Não é possível editar a prioridade após a coleta. Status atual: {notificacao.get_status_display()}.')
        return redirect('stock:logistica:operacao_detail', id=id)
    
    if request.method == 'POST':
        nova_prioridade = request.POST.get('prioridade')
        observacoes = request.POST.get('observacoes', '')
        
        if nova_prioridade:
            notificacao.prioridade = nova_prioridade
            if observacoes:
                notificacao.observacoes = f"{notificacao.observacoes}\n[Prioridade alterada para {nova_prioridade}]: {observacoes}".strip()
            notificacao.save()
            
            messages.success(request, f'Prioridade alterada para {notificacao.get_prioridade_display()}!')
            return redirect('stock:logistica:operacao_detail', id=id)
        else:
            messages.error(request, 'Selecione uma prioridade válida.')
    
    context = {
        'notificacao': notificacao,
        'prioridade_choices': [
            ('BAIXA', 'Baixa'),
            ('NORMAL', 'Normal'),
            ('ALTA', 'Alta'),
            ('URGENTE', 'Urgente'),
        ],
    }
    
    return render(request, 'stock/logistica/operacoes/editar_prioridade.html', context)


# =============================================================================
# VIEWS PARA CHECKLIST DE VIATURAS
# =============================================================================

CHECKLIST_CATEGORIA_ICONES = {
    'Sistema de Freios': 'fa-stop-circle',
    'Sistema de Direção': 'fa-steering-wheel',
    'Sistema Elétrico': 'fa-bolt',
    'Pneus e Rodas': 'fa-circle',
    'Motor e Fluidos': 'fa-cog',
    'Documentação': 'fa-file-alt',
    'Limpeza e Aparência': 'fa-broom',
    'Equipamentos de Segurança': 'fa-shield-alt',
}

CHECKLIST_ITENS_POR_CATEGORIA = {
    'Sistema de Freios': [
        ('freios_funcionando', 'Freios funcionando corretamente'),
        ('fluido_freio_ok', 'Fluido de freio em nível adequado'),
        ('pastilhas_ok', 'Pastilhas de freio em bom estado'),
    ],
    'Sistema de Direção': [
        ('direcao_funcionando', 'Direção funcionando corretamente'),
        ('fluido_direcao_ok', 'Fluido de direção em nível adequado'),
    ],
    'Sistema Elétrico': [
        ('bateria_ok', 'Bateria em bom estado'),
        ('alternador_ok', 'Alternador funcionando'),
        ('farois_funcionando', 'Faróis funcionando'),
        ('luzes_sinalizacao', 'Luzes de sinalização funcionando'),
    ],
    'Pneus e Rodas': [
        ('pneus_pressao_ok', 'Pressão dos pneus adequada'),
        ('pneus_desgaste_ok', 'Desgaste dos pneus dentro do limite'),
        ('rodas_ok', 'Rodas em bom estado'),
    ],
    'Motor e Fluidos': [
        ('motor_funcionando', 'Motor funcionando corretamente'),
        ('oleo_motor_ok', 'Óleo do motor em nível adequado'),
        ('agua_radiador_ok', 'Água do radiador em nível adequado'),
        ('combustivel_ok', 'Combustível suficiente'),
    ],
    'Documentação': [
        ('documentos_ok', 'Documentação do veículo em dia'),
        ('seguro_ok', 'Seguro do veículo em dia'),
        ('licenciamento_ok', 'Licenciamento em dia'),
    ],
    'Limpeza e Aparência': [
        ('limpeza_interior', 'Interior limpo e organizado'),
        ('limpeza_exterior', 'Exterior limpo'),
    ],
    'Equipamentos de Segurança': [
        ('extintor_ok', 'Extintor presente e em dia'),
        ('triangulo_ok', 'Triângulo de sinalização presente'),
        ('macaco_ok', 'Macaco presente e funcionando'),
        ('chave_roda_ok', 'Chave de roda presente'),
    ],
}

CHECKLIST_RESULTADO_CHOICES = [
    ('APROVADO', 'Aprovado'),
    ('REPROVADO', 'Reprovado'),
    ('CONDICIONAL', 'Com condições'),
]


def _checklist_categorias_com_estado(checklist):
    return [
        {
            'nome': categoria,
            'icone': CHECKLIST_CATEGORIA_ICONES.get(categoria, 'fa-clipboard-list'),
            'itens': [
                {
                    'cod': cod,
                    'rotulo': rotulo,
                    'ok': getattr(checklist, cod),
                }
                for cod, rotulo in itens
            ],
        }
        for categoria, itens in CHECKLIST_ITENS_POR_CATEGORIA.items()
    ]


def _checklist_item_stats(checklist):
    itens = [
        getattr(checklist, cod)
        for itens in CHECKLIST_ITENS_POR_CATEGORIA.values()
        for cod, _ in itens
    ]
    total = len(itens)
    ok = sum(1 for valor in itens if valor)
    return {
        'total': total,
        'ok': ok,
        'nok': total - ok,
        'pontuacao': checklist.get_pontuacao_total(),
    }


@login_required
@require_stock_access
def checklist_viaturas_list(request):
    """Lista todos os checklists de viaturas"""
    from django.core.paginator import Paginator
    from .models_stock import ChecklistViatura, VeiculoInterno

    search = request.GET.get('search', '').strip()
    veiculo_id = request.GET.get('veiculo', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    status = request.GET.get('status', '').strip()
    data_inicio = request.GET.get('data_inicio', '').strip()
    data_fim = request.GET.get('data_fim', '').strip()

    checklists = ChecklistViatura.objects.filter(ativo=True).select_related('veiculo', 'inspetor')

    if search:
        checklists = checklists.filter(
            Q(codigo__icontains=search)
            | Q(motorista__icontains=search)
            | Q(local_inspecao__icontains=search)
            | Q(veiculo__nome__icontains=search)
            | Q(veiculo__placa__icontains=search)
            | Q(inspetor__username__icontains=search)
            | Q(inspetor__first_name__icontains=search)
            | Q(inspetor__last_name__icontains=search)
        )
    if veiculo_id:
        checklists = checklists.filter(veiculo_id=veiculo_id)
    if tipo:
        checklists = checklists.filter(tipo=tipo)
    if status:
        checklists = checklists.filter(status_final=status)
    if data_inicio:
        checklists = checklists.filter(data_inspecao__date__gte=data_inicio)
    if data_fim:
        checklists = checklists.filter(data_inspecao__date__lte=data_fim)

    stats = {
        'total': checklists.count(),
        'aprovados': checklists.filter(status_final='APROVADO').count(),
        'reprovados': checklists.filter(status_final='REPROVADO').count(),
        'condicional': checklists.filter(status_final='CONDICIONAL').count(),
    }

    paginator = Paginator(checklists.order_by('-data_inspecao'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    veiculos = VeiculoInterno.objects.filter(ativo=True).order_by('nome')

    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'veiculo_id': veiculo_id,
        'tipo': tipo,
        'status': status,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'veiculos': veiculos,
        'tipo_choices': ChecklistViatura.TIPO_CHOICES,
        'status_choices': ChecklistViatura.STATUS_CHOICES,
        'has_filters': bool(
            search or veiculo_id or tipo or status or data_inicio or data_fim
        ),
    }

    return render(request, 'stock/logistica/checklist/list.html', context)


@login_required
@require_stock_access
def checklist_viaturas_create(request):
    """Criar novo checklist de viatura"""
    from .models_stock import ChecklistViatura, VeiculoInterno
    from django.contrib.auth.models import User
    
    if request.method == 'POST':
        try:
            # Dados básicos
            veiculo_id = request.POST.get('veiculo')
            tipo = request.POST.get('tipo')
            motorista = request.POST.get('motorista')
            local_inspecao = request.POST.get('local_inspecao')
            quilometragem = request.POST.get('quilometragem')
            
            if not all([veiculo_id, tipo, motorista, local_inspecao, quilometragem]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('stock:logistica:checklist_create')
            
            # Criar checklist
            checklist = ChecklistViatura(
                veiculo_id=veiculo_id,
                tipo=tipo,
                inspetor=request.user,
                motorista=motorista,
                local_inspecao=local_inspecao,
                quilometragem=int(quilometragem)
            )
            
            itens_checklist = [
                cod for itens in CHECKLIST_ITENS_POR_CATEGORIA.values() for cod, _ in itens
            ]

            for item in itens_checklist:
                valor = request.POST.get(item) == 'on'
                setattr(checklist, item, valor)
            
            # Observações e recomendações
            checklist.observacoes = request.POST.get('observacoes', '')
            checklist.recomendacoes = request.POST.get('recomendacoes', '')
            
            checklist.save()
            
            messages.success(request, f'Checklist {checklist.codigo} criado com sucesso!')
            return redirect('stock:logistica:checklist_detail', id=checklist.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao criar checklist: {str(e)}')
    
    veiculos = VeiculoInterno.objects.filter(ativo=True).order_by('nome')
    categorias_checklist = [
        {
            'nome': categoria,
            'icone': CHECKLIST_CATEGORIA_ICONES.get(categoria, 'fa-clipboard-list'),
            'itens': itens,
        }
        for categoria, itens in CHECKLIST_ITENS_POR_CATEGORIA.items()
    ]
    total_itens = sum(len(c['itens']) for c in categorias_checklist)

    context = {
        'veiculos': veiculos,
        'tipos': ChecklistViatura.TIPO_CHOICES,
        'itens_por_categoria': CHECKLIST_ITENS_POR_CATEGORIA,
        'categorias_checklist': categorias_checklist,
        'total_itens': total_itens,
    }

    return render(request, 'stock/logistica/checklist/create.html', context)


@login_required
@require_stock_access
def checklist_viaturas_detail(request, id):
    """Detalhes de um checklist de viatura"""
    from .models_stock import ChecklistViatura

    checklist = get_object_or_404(ChecklistViatura, id=id, ativo=True)

    context = {
        'checklist': checklist,
        'categorias_checklist': _checklist_categorias_com_estado(checklist),
        'stats': _checklist_item_stats(checklist),
        'pontuacao': checklist.get_pontuacao_total(),
    }

    return render(request, 'stock/logistica/checklist/detail.html', context)


@login_required
@require_stock_access
def checklist_viaturas_print(request, id):
    """Imprimir checklist de viatura"""
    from .models_stock import ChecklistViatura

    checklist = get_object_or_404(ChecklistViatura, id=id, ativo=True)

    context = {
        'checklist': checklist,
        'categorias_checklist': _checklist_categorias_com_estado(checklist),
        'tipo_choices': ChecklistViatura.TIPO_CHOICES,
        'resultado_choices': CHECKLIST_RESULTADO_CHOICES,
        'pontuacao': checklist.get_pontuacao_total(),
    }

    return render(request, 'stock/logistica/checklist/print.html', context)


@login_required
@require_stock_access
def checklist_viaturas_print_blank(request):
    """Imprimir checklist em branco para verificação física em campo"""
    from .models_stock import ChecklistViatura

    context = {
        'itens_por_categoria': CHECKLIST_ITENS_POR_CATEGORIA,
        'tipo_choices': ChecklistViatura.TIPO_CHOICES,
        'data_relatorio': timezone.now(),
    }

    return render(request, 'stock/logistica/checklist/print_blank.html', context)


# =============================================================================
# API INTERNA: COTAÇÃO LOGÍSTICA
# =============================================================================

@login_required
@require_stock_access
@require_http_methods(["POST"])
def cotacao_interna(request):
    """Calcula cotação interna usando regras básicas (sem integrações externas)."""
    import json
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    transportadora_id = payload.get('transportadora_id')
    items_payload = payload.get('items') or []
    origem_provincia = payload.get('origem_provincia')
    destino_provincia = payload.get('destino_provincia')
    fuel_surcharge_pct = float(payload.get('fuel_surcharge_pct') or 0)
    tolls_flat = float(payload.get('tolls_flat') or 0)
    insurance_pct = float(payload.get('insurance_pct') or 0)
    distancia_km = payload.get('distancia_km')

    if not transportadora_id or not items_payload:
        return JsonResponse({'error': 'Campos obrigatórios: transportadora_id e items'}, status=400)

    transportadora = get_object_or_404(Transportadora, id=transportadora_id, status='ATIVA')

    try:
        items = []
        for it in items_payload:
            items.append(PricingItem(
                weight_kg=float(it.get('weight_kg') or 0),
                length_cm=float(it.get('length_cm') or 0),
                width_cm=float(it.get('width_cm') or 0),
                height_cm=float(it.get('height_cm') or 0),
                declared_value=float(it.get('declared_value') or 0),
            ))
    except Exception:
        return JsonResponse({'error': 'Items inválidos'}, status=400)

    result = calculate_quote(
        transportadora=transportadora,
        items=items,
        origem_provincia=origem_provincia,
        destino_provincia=destino_provincia,
        distancia_km=float(distancia_km) if distancia_km is not None else None,
        fuel_surcharge_pct=max(0.0, fuel_surcharge_pct),
        tolls_flat=max(0.0, tolls_flat),
        insurance_pct=max(0.0, insurance_pct),
    )

    return JsonResponse({
        'total_cost': result.total_cost,
        'currency': result.currency,
        'estimated_days': result.estimated_days,
        'breakdown': result.breakdown,
    })


@login_required
@require_stock_access
def cotacao_form(request):
    """Formulário simples para testar cotação interna pelo navegador."""
    transportadoras = Transportadora.objects.filter(status='ATIVA').order_by('nome')
    context = {
        'transportadoras': transportadoras,
    }
    return render(request, 'stock/logistica/cotacao/form.html', context)


# =============================================================================
# WEBHOOKS DE TRANSPORTADORAS (SKELETON)
# =============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def carrier_webhook(request, carrier):
    """Webhook para receber atualizações de transportadoras."""
    from .services.webhook_service import CarrierWebhookView
    
    # Usar a view de webhook do serviço
    webhook_view = CarrierWebhookView()
    return webhook_view.post(request, carrier)


# =============================================================================
# NOTIFICAÇÕES INTERNAS (E-MAIL BÁSICO)
# =============================================================================

def send_internal_email_notification(request):
    """Endpoint para envio de notificações por email interno."""
    from .services.email_service import email_service
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            notification_type = data.get('type')
            recipient_email = data.get('recipient_email')
            
            if not notification_type or not recipient_email:
                return JsonResponse({
                    'success': False,
                    'error': 'type e recipient_email são obrigatórios'
                }, status=400)
            
            # Processar baseado no tipo
            if notification_type == 'tracking_update':
                result = email_service.send_tracking_update(
                    recipient_email=recipient_email,
                    tracking_code=data.get('tracking_code', ''),
                    status=data.get('status', ''),
                    location=data.get('location'),
                    estimated_delivery=data.get('estimated_delivery')
                )
            elif notification_type == 'delivery_confirmation':
                result = email_service.send_delivery_confirmation(
                    recipient_email=recipient_email,
                    tracking_code=data.get('tracking_code', ''),
                    delivery_date=data.get('delivery_date', ''),
                    signature_name=data.get('signature_name')
                )
            elif notification_type == 'delay_notification':
                result = email_service.send_delay_notification(
                    recipient_email=recipient_email,
                    tracking_code=data.get('tracking_code', ''),
                    original_date=data.get('original_date', ''),
                    new_date=data.get('new_date', ''),
                    reason=data.get('reason')
                )
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Tipo de notificação não suportado: {notification_type}'
                }, status=400)
            
            return JsonResponse({
                'success': result,
                'message': 'Email enviado com sucesso' if result else 'Falha ao enviar email'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'JSON inválido'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'error': 'Método não permitido'
    }, status=405)
