"""
Modelos para fluxo de exceções logísticas.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal


class TipoExcecao(models.Model):
    """Tipos de exceções logísticas."""
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configurações da exceção
    requer_acao = models.BooleanField(default=True, help_text="Se requer ação manual")
    permite_reativacao = models.BooleanField(default=True, help_text="Se permite reativação automática")
    tempo_maximo_resolucao_horas = models.PositiveIntegerField(
        default=24,
        help_text="Tempo máximo para resolução em horas"
    )
    
    # Impacto na operação
    bloqueia_entrega = models.BooleanField(default=False)
    bloqueia_coleta = models.BooleanField(default=False)
    requer_notificacao = models.BooleanField(default=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tipo de Exceção"
        verbose_name_plural = "Tipos de Exceção"
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ExcecaoLogistica(models.Model):
    """Exceções logísticas ocorridas durante operações."""
    
    STATUS_CHOICES = [
        ('ABERTA', 'Aberta'),
        ('EM_ANALISE', 'Em Análise'),
        ('RESOLVIDA', 'Resolvida'),
        ('CANCELADA', 'Cancelada'),
        ('ESCALADA', 'Escalada'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('NORMAL', 'Normal'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    tipo_excecao = models.ForeignKey(TipoExcecao, on_delete=models.CASCADE)
    
    # Relacionamentos
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='excecoes'
    )
    # planejamento_entrega = models.ForeignKey(
    #     'PlanejamentoEntrega',
    #     on_delete=models.CASCADE,
    #     null=True,
    #     blank=True,
    #     related_name='excecoes'
    # )
    # rota = models.ForeignKey(
    #     'Rota',
    #     on_delete=models.CASCADE,
    #     null=True,
    #     blank=True,
    #     related_name='excecoes'
    # )
    
    # Detalhes da exceção
    descricao = models.TextField()
    observacoes = models.TextField(blank=True)
    evidencia_fotos = models.JSONField(default=list, blank=True, help_text="URLs das fotos de evidência")
    
    # Localização e contexto
    local_ocorrencia = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Status e prioridade
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTA')
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    
    # Responsáveis
    reportado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='excecoes_reportadas'
    )
    responsavel_resolucao = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='excecoes_responsavel'
    )
    
    # Datas e prazos
    data_ocorrencia = models.DateTimeField(default=timezone.now)
    data_limite_resolucao = models.DateTimeField(null=True, blank=True)
    data_resolucao = models.DateTimeField(null=True, blank=True)
    
    # Impacto financeiro
    custo_estimado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custo estimado da exceção"
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Exceção Logística"
        verbose_name_plural = "Exceções Logísticas"
        ordering = ['-data_ocorrencia', 'prioridade']
    
    def __str__(self):
        return f"{self.codigo} - {self.tipo_excecao.nome}"
    
    def save(self, *args, **kwargs):
        # Calcular data limite de resolução se não definida
        if not self.data_limite_resolucao and self.tipo_excecao.tempo_maximo_resolucao_horas:
            self.data_limite_resolucao = self.data_ocorrencia + timezone.timedelta(
                hours=self.tipo_excecao.tempo_maximo_resolucao_horas
            )
        super().save(*args, **kwargs)


class AcaoExcecao(models.Model):
    """Ações tomadas para resolver exceções."""
    
    TIPO_CHOICES = [
        ('INVESTIGACAO', 'Investigação'),
        ('CONTATO_CLIENTE', 'Contato com Cliente'),
        ('REAGENDAMENTO', 'Reagendamento'),
        ('DEVOLUCAO', 'Devolução'),
        ('REPARO', 'Reparo'),
        ('SUBSTITUICAO', 'Substituição'),
        ('CANCELAMENTO', 'Cancelamento'),
        ('ESCALACAO', 'Escalação'),
        ('OUTROS', 'Outros'),
    ]
    
    excecao = models.ForeignKey(ExcecaoLogistica, on_delete=models.CASCADE, related_name='acoes')
    tipo_acao = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()
    
    # Responsável pela ação
    executado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Datas
    data_execucao = models.DateTimeField(default=timezone.now)
    data_prevista_conclusao = models.DateTimeField(null=True, blank=True)
    
    # Status da ação
    concluida = models.BooleanField(default=False)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    
    # Resultado
    resultado = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Ação de Exceção"
        verbose_name_plural = "Ações de Exceção"
        ordering = ['-data_execucao']
    
    def __str__(self):
        return f"{self.excecao.codigo} - {self.get_tipo_acao_display()}"


class DevolucaoLogistica(models.Model):
    """Devoluções logísticas (logística reversa)."""
    
    STATUS_CHOICES = [
        ('SOLICITADA', 'Solicitada'),
        ('APROVADA', 'Aprovada'),
        ('EM_COLETA', 'Em Coleta'),
        ('COLETADA', 'Coletada'),
        ('EM_TRANSITO', 'Em Trânsito'),
        ('RECEBIDA', 'Recebida'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    MOTIVO_CHOICES = [
        ('PRODUTO_DEFEITUOSO', 'Produto Defeituoso'),
        ('PRODUTO_ERRADO', 'Produto Errado'),
        ('ARREPENDIMENTO', 'Arrependimento'),
        ('DANOS_TRANSPORTE', 'Danos no Transporte'),
        ('NAO_RECEBIDO', 'Não Recebido'),
        ('OUTROS', 'Outros'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    
    # Relacionamentos
    rastreamento_original = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='devolucoes'
    )
    excecao_relacionada = models.ForeignKey(
        ExcecaoLogistica,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devolucoes'
    )
    
    # Detalhes da devolução
    motivo = models.CharField(max_length=30, choices=MOTIVO_CHOICES)
    descricao_motivo = models.TextField()
    solicitado_por = models.CharField(max_length=100, help_text="Nome de quem solicitou a devolução")
    contato_solicitante = models.CharField(max_length=20, blank=True)
    
    # Status e datas
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SOLICITADA')
    data_solicitacao = models.DateTimeField(default=timezone.now)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_coleta = models.DateTimeField(null=True, blank=True)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    
    # Responsáveis
    aprovado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devolucoes_aprovadas'
    )
    
    # Custos
    custo_devolucao = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custo da devolução"
    )
    
    # Observações
    observacoes = models.TextField(blank=True)
    instrucoes_coleta = models.TextField(blank=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Devolução Logística"
        verbose_name_plural = "Devoluções Logísticas"
        ordering = ['-data_solicitacao']
    
    def __str__(self):
        return f"{self.codigo} - {self.get_motivo_display()}"


class Reentrega(models.Model):
    """Reentregas após tentativas falhadas."""
    
    STATUS_CHOICES = [
        ('AGENDADA', 'Agendada'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('CONCLUIDA', 'Concluída'),
        ('FALHADA', 'Falhada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    
    # Relacionamentos
    rastreamento_original = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='reentregas'
    )
    excecao_relacionada = models.ForeignKey(
        ExcecaoLogistica,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reentregas'
    )
    
    # Detalhes da reentrega
    motivo_tentativa_anterior = models.TextField()
    nova_data_entrega = models.DateField()
    nova_janela_inicio = models.TimeField()
    nova_janela_fim = models.TimeField()
    
    # Status e datas
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AGENDADA')
    data_agendamento = models.DateTimeField(default=timezone.now)
    data_tentativa = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    
    # Responsáveis
    agendado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reentregas_agendadas'
    )
    
    # Observações
    observacoes = models.TextField(blank=True)
    instrucoes_especiais = models.TextField(blank=True)
    
    # Custos
    custo_reentrega = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Custo adicional da reentrega"
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Reentrega"
        verbose_name_plural = "Reentregas"
        ordering = ['-data_agendamento']
    
    def __str__(self):
        return f"{self.codigo} - {self.nova_data_entrega}"


class ConfiguracaoExcecoes(models.Model):
    """Configurações para tratamento de exceções."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de notificação
    notificar_imediato = models.BooleanField(default=True)
    notificar_escalacao = models.BooleanField(default=True)
    notificar_resolucao = models.BooleanField(default=True)
    
    # Configurações de tempo
    tempo_escalacao_horas = models.PositiveIntegerField(
        default=4,
        help_text="Tempo para escalação automática em horas"
    )
    tentativas_maximas = models.PositiveIntegerField(
        default=3,
        help_text="Número máximo de tentativas antes de escalação"
    )
    
    # Configurações de custo
    limite_custo_aprovacao = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Limite de custo para aprovação automática"
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração de Exceções"
        verbose_name_plural = "Configurações de Exceções"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoExcecoes.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)
