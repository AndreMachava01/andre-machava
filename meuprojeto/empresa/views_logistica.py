# =============================================================================
# VIEWS PARA MÓDULO DE LOGÍSTICA - APENAS LOGÍSTICA PURA
# =============================================================================

from django.shortcuts import render, get_object_or_404, redirect
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
    Transportadora, RastreamentoEntrega, EventoRastreamento, VeiculoInterno
)
from .services.logistica_sync import (
    get_or_create_rastreamento_for_notificacao,
    sincronizar_rastreamento_com_notificacao,
    criar_evento_rastreamento,
)
from .services.pricing import calculate_quote, PricingItem
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

    context = {
        'rastreamentos_em_transito': rastreamentos_em_transito,
        'entregas_pendentes': entregas_pendentes,
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
    qs = RastreamentoEntrega.objects.all().select_related('transportadora', 'transferencia', 'ordem_compra')
    
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
        'status_choices': RastreamentoEntrega.STATUS_CHOICES,
        'transportadoras': Transportadora.objects.exclude(tipo='VIATURA_INTERNA').order_by('nome'),
        'search': search,
        'status': status,
        'transportadora_id': transportadora_id,
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
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    tipo = request.GET.get('tipo', '')
    
    # Query base - apenas transportadoras externas (excluir viaturas internas)
    transportadoras = Transportadora.objects.exclude(tipo='VIATURA_INTERNA')
    
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
    
    # Ordenar
    transportadoras = transportadoras.order_by('nome')
    
    # Paginação
    paginator = Paginator(transportadoras, 20)  # 20 itens por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opções para filtros
    status_choices = Transportadora.STATUS_CHOICES
    tipo_choices = [
        ('TRANSPORTADORA', 'Transportadora Externa'),
        ('ENTREGA_RAPIDA', 'Entrega Rápida'),
        ('CORREIOS', 'Correios'),
        ('MOTORISTA', 'Motorista Próprio'),
        ('TERCEIRIZADA', 'Terceirizada'),
    ]
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'tipo': tipo,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
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
            return redirect('logistica:transportadoras_list')
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
            return redirect('logistica:transportadora_detail', id=transportadora.id)
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
        return redirect('logistica:transportadoras_list')
    
    # Se não for POST, redirecionar para a lista
    return redirect('logistica:transportadoras_list')


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
            'prazo_entrega_padrao', 'custo_por_kg', 'custo_fixo',
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
            'custo_fixo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
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
            'prazo_entrega_padrao', 'custo_por_kg', 'custo_fixo',
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
            'custo_fixo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
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
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    categoria = request.GET.get('categoria', '')
    tipo_viatura = request.GET.get('tipo_viatura', '')
    sucursal_filter = request.GET.get('sucursal', '')
    
    # Query base - apenas viaturas internas (ambas as categorias)
    viaturas = Transportadora.objects.filter(
        tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO']
    )
    
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
        'search': search,
        'status': status,
        'categoria': categoria,
        'tipo_viatura': tipo_viatura,
        'sucursal_filter': sucursal_filter,
        'status_choices': status_choices,
        'categoria_choices': categoria_choices,
        'tipo_viatura_choices': tipo_viatura_choices,
        'sucursais': sucursais,
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
    viatura = get_object_or_404(Transportadora, id=id, tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO'])
    
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
    viatura = get_object_or_404(Transportadora, id=id, tipo__in=['VIATURA_INTERNA_ENTREGA', 'VIATURA_INTERNA_EXECUTIVO'])
    
    context = {
        'viatura': viatura,
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
                
                # Gerar código de rastreamento único
                rastreamento.codigo_rastreamento = _gerar_codigo_rastreamento()
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


def _gerar_codigo_rastreamento():
    """Gera código único para rastreamento."""
    import random
    import string
    
    # Formato: RAST + ano + mês + 4 dígitos aleatórios
    from django.utils import timezone
    now = timezone.now()
    
    prefix = f"RAST{now.year}{now.month:02d}"
    
    # Gerar 4 dígitos aleatórios
    random_suffix = ''.join(random.choices(string.digits, k=4))
    
    codigo = f"{prefix}{random_suffix}"
    
    # Verificar se já existe
    while RastreamentoEntrega.objects.filter(codigo_rastreamento=codigo).exists():
        random_suffix = ''.join(random.choices(string.digits, k=4))
        codigo = f"{prefix}{random_suffix}"
    
    return codigo


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


@login_required
@require_stock_access
def operacao_atribuir_transporte(request, id):
    """Atribuir transporte a uma operação logística"""
    from .models_stock import NotificacaoLogisticaUnificada, Transportadora
    
    notificacao = get_object_or_404(NotificacaoLogisticaUnificada, id=id)
    
    if request.method == 'POST':
        tipo_transporte = request.POST.get('tipo_transporte')
        veiculo_id = request.POST.get('veiculo_interno')
        transportadora_id = request.POST.get('transportadora_externa')
        observacoes = request.POST.get('observacoes', '')
        
        # Validação
        if tipo_transporte == 'VEICULO_INTERNO' and not veiculo_id:
            messages.error(request, 'Selecione um veículo interno.')
        elif tipo_transporte == 'TRANSPORTADORA_EXTERNA' and not transportadora_id:
            messages.error(request, 'Selecione uma transportadora externa.')
        else:
            # Atualizar notificação
            notificacao.tipo_transporte = tipo_transporte
            notificacao.usuario_atribuicao = request.user
            
            if tipo_transporte == 'VEICULO_INTERNO':
                # Para veículos internos, usar o campo veiculo_interno
                notificacao.veiculo_interno_id = veiculo_id
                notificacao.transportadora_externa = None
            else:
                # Para transportadoras externas, usar o campo transportadora_externa
                notificacao.transportadora_externa_id = transportadora_id
                notificacao.veiculo_interno = None
            
            if observacoes:
                notificacao.observacoes = observacoes
            
            notificacao.save()

            # Garantir rastreamento ligado já na atribuição e sincronizar status
            rastreamento = get_or_create_rastreamento_for_notificacao(RastreamentoEntrega, EventoRastreamento, notificacao, request.user)
            sincronizar_rastreamento_com_notificacao(EventoRastreamento, notificacao, rastreamento, request.user)
            
            messages.success(request, 'Transporte atribuído com sucesso!')
            return redirect('stock:logistica:operacao_detail', id=notificacao.id)
    
    # Buscar opções de transporte
    from .models_stock import VeiculoInterno
    veiculos_internos = VeiculoInterno.objects.filter(
        ativo=True
    ).order_by('nome')
    
    transportadoras_externas = Transportadora.objects.filter(
        tipo__in=['TRANSPORTADORA', 'ENTREGA_RAPIDA', 'CORREIOS', 'MOTORISTA', 'TERCEIRIZADA'],
        status='ATIVA'
    ).order_by('nome')
    
    context = {
        'notificacao': notificacao,
        'veiculos_internos': veiculos_internos,
        'transportadoras_externas': transportadoras_externas,
    }
    
    return render(request, 'stock/logistica/operacoes/atribuir.html', context)


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

        messages.success(request, f'Coleta confirmada para operação {notificacao.id}!')
        return redirect('stock:logistica:operacao_detail', id=id)
    
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

@login_required
@require_stock_access
def checklist_viaturas_list(request):
    """Lista todos os checklists de viaturas"""
    from .models_stock import ChecklistViatura, VeiculoInterno
    
    # Filtros
    veiculo_id = request.GET.get('veiculo')
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    
    checklists = ChecklistViatura.objects.filter(ativo=True).select_related('veiculo', 'inspetor')
    
    # Aplicar filtros
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
    
    # Paginação
    from django.core.paginator import Paginator
    paginator = Paginator(checklists.order_by('-data_inspecao'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    veiculos = VeiculoInterno.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'page_obj': page_obj,
        'veiculos': veiculos,
        'tipos': ChecklistViatura.TIPO_CHOICES,
        'status_choices': ChecklistViatura.STATUS_CHOICES,
        'filtros': {
            'veiculo_id': veiculo_id,
            'tipo': tipo,
            'status': status,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        }
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
            
            # Itens do checklist
            itens_checklist = [
                'freios_funcionando', 'fluido_freio_ok', 'pastilhas_ok',
                'direcao_funcionando', 'fluido_direcao_ok', 'bateria_ok',
                'alternador_ok', 'farois_funcionando', 'luzes_sinalizacao',
                'pneus_pressao_ok', 'pneus_desgaste_ok', 'rodas_ok',
                'motor_funcionando', 'oleo_motor_ok', 'agua_radiador_ok',
                'combustivel_ok', 'documentos_ok', 'seguro_ok',
                'licenciamento_ok', 'limpeza_interior', 'limpeza_exterior',
                'extintor_ok', 'triangulo_ok', 'macaco_ok', 'chave_roda_ok'
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
    
    # Dados para o formulário
    veiculos = VeiculoInterno.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'veiculos': veiculos,
        'tipos': ChecklistViatura.TIPO_CHOICES,
    }
    
    return render(request, 'stock/logistica/checklist/create.html', context)


@login_required
@require_stock_access
def checklist_viaturas_detail(request, id):
    """Detalhes de um checklist de viatura"""
    from .models_stock import ChecklistViatura
    
    checklist = get_object_or_404(ChecklistViatura, id=id, ativo=True)
    
    # Agrupar itens por categoria
    itens_por_categoria = {
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
    
    context = {
        'checklist': checklist,
        'itens_por_categoria': itens_por_categoria,
        'pontuacao': checklist.get_pontuacao_total(),
    }
    
    return render(request, 'stock/logistica/checklist/detail.html', context)


@login_required
@require_stock_access
def checklist_viaturas_print(request, id):
    """Imprimir checklist de viatura"""
    from .models_stock import ChecklistViatura
    
    checklist = get_object_or_404(ChecklistViatura, id=id, ativo=True)
    
    # Mesma estrutura do detail
    itens_por_categoria = {
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
    
    context = {
        'checklist': checklist,
        'itens_por_categoria': itens_por_categoria,
        'pontuacao': checklist.get_pontuacao_total(),
    }
    
    return render(request, 'stock/logistica/checklist/print.html', context)


@login_required
@require_stock_access
def checklist_viaturas_print_blank(request):
    """Imprimir checklist em branco para verificação física em campo"""
    # Estrutura de itens por categoria (igual ao detail/print) para renderização
    itens_por_categoria = {
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

    context = {
        'itens_por_categoria': itens_por_categoria,
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
