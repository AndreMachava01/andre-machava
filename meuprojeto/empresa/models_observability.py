"""
Modelos para observabilidade e métricas logísticas.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import json


class AuditoriaTransicao(models.Model):
    """Auditoria de transições de status em operações logísticas."""
    
    TIPO_OPERACAO_CHOICES = [
        ('STATUS_CHANGE', 'Mudança de Status'),
        ('ALLOCATION', 'Alocação'),
        ('ROUTING', 'Roteamento'),
        ('EXCEPTION', 'Exceção'),
        ('POD', 'POD'),
        ('COST', 'Custo'),
        ('BILLING', 'Faturamento'),
        ('MASTERDATA', 'Dados Mestres'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Operação
    tipo_operacao = models.CharField(max_length=20, choices=TIPO_OPERACAO_CHOICES)
    modelo_afetado = models.CharField(max_length=50)
    objeto_id = models.PositiveIntegerField()
    
    # Transição
    status_anterior = models.CharField(max_length=50, blank=True)
    status_novo = models.CharField(max_length=50, blank=True)
    
    # Dados
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    contexto_operacao = models.JSONField(default=dict, blank=True)
    
    # Usuário e contexto
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    
    # Timestamp
    data_operacao = models.DateTimeField(auto_now_add=True)
    
    # Metadados
    duracao_ms = models.PositiveIntegerField(null=True, blank=True, help_text="Duração da operação em milissegundos")
    sucesso = models.BooleanField(default=True)
    erro_mensagem = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Auditoria de Transição"
        verbose_name_plural = "Auditorias de Transição"
        ordering = ['-data_operacao']
        indexes = [
            models.Index(fields=['modelo_afetado', 'objeto_id']),
            models.Index(fields=['tipo_operacao', 'data_operacao']),
            models.Index(fields=['usuario', 'data_operacao']),
            models.Index(fields=['status_anterior', 'status_novo']),
        ]
    
    def __str__(self):
        return f"{self.tipo_operacao} - {self.modelo_afetado} - {self.data_operacao}"


class MetricaLogistica(models.Model):
    """Métricas logísticas para análise de performance."""
    
    TIPO_METRICA_CHOICES = [
        ('OTD', 'On-Time Delivery'),
        ('LEAD_TIME', 'Lead Time'),
        ('COST_PER_DELIVERY', 'Custo por Entrega'),
        ('VOLUME_DELIVERED', 'Volume Entregue'),
        ('EXCEPTION_RATE', 'Taxa de Exceções'),
        ('CUSTOMER_SATISFACTION', 'Satisfação do Cliente'),
        ('FLEET_UTILIZATION', 'Utilização da Frota'),
        ('ROUTE_EFFICIENCY', 'Eficiência de Rota'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Tipo e configuração
    tipo_metrica = models.CharField(max_length=30, choices=TIPO_METRICA_CHOICES)
    unidade_medida = models.CharField(max_length=20)
    formato_exibicao = models.CharField(max_length=20, default='DECIMAL')
    
    # Agregação
    periodo_agregacao = models.CharField(
        max_length=10,
        choices=[
            ('HOUR', 'Hora'),
            ('DAY', 'Dia'),
            ('WEEK', 'Semana'),
            ('MONTH', 'Mês'),
            ('QUARTER', 'Trimestre'),
            ('YEAR', 'Ano'),
        ],
        default='DAY'
    )
    
    # Filtros
    filtros_disponiveis = models.JSONField(
        default=list,
        help_text="Lista de filtros disponíveis: ['regiao', 'transportadora', 'tipo_produto']"
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Métrica Logística"
        verbose_name_plural = "Métricas Logísticas"
        ordering = ['tipo_metrica', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ValorMetrica(models.Model):
    """Valores das métricas logísticas por período."""
    
    # Relacionamentos
    metrica = models.ForeignKey(MetricaLogistica, on_delete=models.CASCADE, related_name='valores')
    
    # Período
    data_referencia = models.DateField()
    periodo_inicio = models.DateTimeField()
    periodo_fim = models.DateTimeField()
    
    # Valor
    valor = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Filtros aplicados
    filtros = models.JSONField(
        default=dict,
        help_text="Filtros aplicados: {'regiao': 'Maputo', 'transportadora': 'Correios'}"
    )
    
    # Metadados
    quantidade_registros = models.PositiveIntegerField(default=1)
    confiabilidade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    
    # Auditoria
    data_calculo = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Valor de Métrica"
        verbose_name_plural = "Valores de Métricas"
        ordering = ['-data_referencia', '-periodo_inicio']
        unique_together = ['metrica', 'data_referencia', 'filtros']
        indexes = [
            models.Index(fields=['metrica', 'data_referencia']),
            models.Index(fields=['periodo_inicio', 'periodo_fim']),
        ]
    
    def __str__(self):
        return f"{self.metrica.nome} - {self.data_referencia} - {self.valor}"


class RelatorioLogistico(models.Model):
    """Relatórios logísticos pré-configurados."""
    
    TIPO_RELATORIO_CHOICES = [
        ('PERFORMANCE', 'Performance'),
        ('FINANCEIRO', 'Financeiro'),
        ('OPERACIONAL', 'Operacional'),
        ('EXCECOES', 'Exceções'),
        ('CUSTOMIZADO', 'Customizado'),
    ]
    
    FORMATO_EXPORTACAO_CHOICES = [
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('CSV', 'CSV'),
        ('JSON', 'JSON'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configuração
    tipo_relatorio = models.CharField(max_length=20, choices=TIPO_RELATORIO_CHOICES)
    formato_padrao = models.CharField(max_length=10, choices=FORMATO_EXPORTACAO_CHOICES, default='PDF')
    
    # Métricas incluídas
    metricas_incluidas = models.ManyToManyField(
        MetricaLogistica,
        related_name='relatorios',
        blank=True
    )
    
    # Filtros padrão
    filtros_padrao = models.JSONField(
        default=dict,
        help_text="Filtros padrão do relatório"
    )
    
    # Configurações de agrupamento
    agrupamentos = models.JSONField(
        default=list,
        help_text="Lista de campos para agrupamento"
    )
    
    # Configurações de ordenação
    ordenacao_padrao = models.JSONField(
        default=list,
        help_text="Lista de campos para ordenação"
    )
    
    # Configurações de visualização
    configuracoes_visualizacao = models.JSONField(
        default=dict,
        help_text="Configurações de gráficos e tabelas"
    )
    
    # Permissões
    usuarios_permitidos = models.ManyToManyField(
        'auth.User',
        related_name='relatorios_permitidos',
        blank=True
    )
    grupos_permitidos = models.ManyToManyField(
        'auth.Group',
        related_name='relatorios_permitidos',
        blank=True
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    publico = models.BooleanField(default=False)
    
    # Auditoria
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='relatorios_criados'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Relatório Logístico"
        verbose_name_plural = "Relatórios Logísticos"
        ordering = ['tipo_relatorio', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ExecucaoRelatorio(models.Model):
    """Execuções de relatórios logísticos."""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PROCESSANDO', 'Processando'),
        ('CONCLUIDO', 'Concluído'),
        ('ERRO', 'Erro'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    # Relacionamentos
    relatorio = models.ForeignKey(RelatorioLogistico, on_delete=models.CASCADE, related_name='execucoes')
    usuario = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='execucoes_relatorios')
    
    # Parâmetros da execução
    filtros_aplicados = models.JSONField(default=dict)
    formato_solicitado = models.CharField(max_length=10)
    parametros_extras = models.JSONField(default=dict)
    
    # Status e resultado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    progresso_percentual = models.PositiveIntegerField(default=0)
    
    # Arquivo gerado
    arquivo_gerado = models.FileField(
        upload_to='relatorios/%Y/%m/%d/',
        null=True,
        blank=True
    )
    tamanho_arquivo = models.PositiveIntegerField(null=True, blank=True)
    
    # Metadados
    tempo_processamento_segundos = models.PositiveIntegerField(null=True, blank=True)
    registros_processados = models.PositiveIntegerField(null=True, blank=True)
    erro_mensagem = models.TextField(blank=True)
    
    # Timestamps
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    data_expiracao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Execução de Relatório"
        verbose_name_plural = "Execuções de Relatórios"
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['relatorio', 'status']),
            models.Index(fields=['usuario', 'data_inicio']),
        ]
    
    def __str__(self):
        return f"{self.relatorio.nome} - {self.usuario.username} - {self.data_inicio}"


class APILog(models.Model):
    """Log de chamadas de API para auditoria."""
    
    METODO_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Requisição
    metodo = models.CharField(max_length=10, choices=METODO_CHOICES)
    endpoint = models.CharField(max_length=200)
    query_params = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    body_request = models.TextField(blank=True)
    
    # Resposta
    status_code = models.PositiveIntegerField()
    body_response = models.TextField(blank=True)
    headers_response = models.JSONField(default=dict)
    
    # Usuário e contexto
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Performance
    tempo_resposta_ms = models.PositiveIntegerField()
    tamanho_request_bytes = models.PositiveIntegerField()
    tamanho_response_bytes = models.PositiveIntegerField()
    
    # Timestamps
    data_requisicao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log de API"
        verbose_name_plural = "Logs de API"
        ordering = ['-data_requisicao']
        indexes = [
            models.Index(fields=['endpoint', 'data_requisicao']),
            models.Index(fields=['usuario', 'data_requisicao']),
            models.Index(fields=['status_code', 'data_requisicao']),
        ]
    
    def __str__(self):
        return f"{self.metodo} {self.endpoint} - {self.status_code} - {self.data_requisicao}"


class ConfiguracaoObservabilidade(models.Model):
    """Configurações para observabilidade e métricas."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de auditoria
    auditoria_habilitada = models.BooleanField(default=True)
    retencao_auditoria_dias = models.PositiveIntegerField(default=365)
    incluir_dados_sensiveis = models.BooleanField(default=False)
    
    # Configurações de métricas
    calculo_metricas_automatico = models.BooleanField(default=True)
    intervalo_calculo_minutos = models.PositiveIntegerField(default=60)
    retencao_metricas_dias = models.PositiveIntegerField(default=730)
    
    # Configurações de relatórios
    relatorios_automaticos = models.BooleanField(default=True)
    execucao_relatorios_horario = models.TimeField(default='06:00')
    retencao_relatorios_dias = models.PositiveIntegerField(default=90)
    
    # Configurações de API
    log_api_habilitado = models.BooleanField(default=True)
    retencao_logs_api_dias = models.PositiveIntegerField(default=30)
    incluir_body_requests = models.BooleanField(default=False)
    
    # Configurações de alertas
    alertas_habilitados = models.BooleanField(default=True)
    email_alertas = models.EmailField(blank=True)
    threshold_otd_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00')
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração Observabilidade"
        verbose_name_plural = "Configurações Observabilidade"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoObservabilidade.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)
