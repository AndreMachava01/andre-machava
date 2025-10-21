"""
Modelos para UX Mobile e painel motorista.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import json


class SessaoMotorista(models.Model):
    """Sessões de motoristas no sistema mobile."""
    
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('PAUSADA', 'Pausada'),
        ('FINALIZADA', 'Finalizada'),
        ('EXPIRADA', 'Expirada'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    token_sessao = models.CharField(max_length=100, unique=True)
    
    # Motorista
    motorista = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='sessoes_motorista'
    )
    veiculo_interno = models.ForeignKey(
        'VeiculoInterno',
        on_delete=models.CASCADE,
        related_name='sessoes_motorista',
        null=True,
        blank=True
    )
    
    # Localização
    latitude_inicial = models.DecimalField(max_digits=9, decimal_places=6)
    longitude_inicial = models.DecimalField(max_digits=9, decimal_places=6)
    latitude_atual = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude_atual = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Status e controle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVA')
    dispositivo_info = models.JSONField(default=dict)
    versao_app = models.CharField(max_length=20, blank=True)
    
    # Timestamps
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    ultima_atividade = models.DateTimeField(auto_now=True)
    
    # Metadados
    total_km_percorridos = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_entregas_realizadas = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Sessão Motorista"
        verbose_name_plural = "Sessões Motorista"
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['motorista', 'status']),
            models.Index(fields=['token_sessao']),
            models.Index(fields=['data_inicio']),
        ]
    
    def __str__(self):
        return f"{self.motorista.username} - {self.data_inicio}"


class EventoMotorista(models.Model):
    """Eventos registrados pelo motorista."""
    
    TIPO_EVENTO_CHOICES = [
        ('INICIO_JORNADA', 'Início de Jornada'),
        ('FIM_JORNADA', 'Fim de Jornada'),
        ('INICIO_ENTREGA', 'Início de Entrega'),
        ('FIM_ENTREGA', 'Fim de Entrega'),
        ('PAUSA', 'Pausa'),
        ('RETOMADA', 'Retomada'),
        ('COMBUSTIVEL', 'Abastecimento'),
        ('MANUTENCAO', 'Manutenção'),
        ('PROBLEMA_VEICULO', 'Problema no Veículo'),
        ('PROBLEMA_ROTA', 'Problema na Rota'),
        ('ACIDENTE', 'Acidente'),
        ('MULTAS', 'Multas'),
        ('OUTROS', 'Outros'),
    ]
    
    # Relacionamentos
    sessao_motorista = models.ForeignKey(
        SessaoMotorista,
        on_delete=models.CASCADE,
        related_name='eventos'
    )
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='eventos_motorista',
        null=True,
        blank=True
    )
    
    # Evento
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO_CHOICES)
    descricao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    
    # Localização
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    precisao_gps = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # Dados adicionais
    dados_evento = models.JSONField(default=dict)
    fotos = models.JSONField(default=list, help_text="Lista de URLs de fotos")
    
    # Status
    sincronizado = models.BooleanField(default=False)
    offline = models.BooleanField(default=False)
    
    # Timestamp
    data_evento = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Evento Motorista"
        verbose_name_plural = "Eventos Motorista"
        ordering = ['-data_evento']
        indexes = [
            models.Index(fields=['sessao_motorista', 'data_evento']),
            models.Index(fields=['tipo_evento', 'data_evento']),
            models.Index(fields=['offline', 'sincronizado']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_evento_display()} - {self.data_evento}"


class PODOffline(models.Model):
    """PODs registrados offline pelo motorista."""
    
    STATUS_CHOICES = [
        ('PENDENTE_SINCRONIZACAO', 'Pendente Sincronização'),
        ('SINCRONIZADO', 'Sincronizado'),
        ('ERRO_SINCRONIZACAO', 'Erro na Sincronização'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    codigo_offline = models.CharField(max_length=50, unique=True)
    
    # Relacionamentos
    sessao_motorista = models.ForeignKey(
        SessaoMotorista,
        on_delete=models.CASCADE,
        related_name='pods_offline'
    )
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='pods_offline',
        null=True,
        blank=True
    )
    
    # Dados da POD
    tipo_entrega = models.CharField(max_length=20, default='COMPLETA')
    nome_destinatario = models.CharField(max_length=100)
    documento_destinatario = models.CharField(max_length=20, blank=True)
    telefone_destinatario = models.CharField(max_length=20, blank=True)
    
    # Localização
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    precisao_gps = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    endereco_entrega = models.CharField(max_length=255)
    
    # Documentos
    assinatura_digital = models.JSONField(default=dict)
    fotos_entrega = models.JSONField(default=list)
    fotos_produto = models.JSONField(default=list)
    fotos_destinatario = models.JSONField(default=list)
    
    # Observações
    observacoes = models.TextField(blank=True)
    motivo_recusa = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDENTE_SINCRONIZACAO')
    erro_sincronizacao = models.TextField(blank=True)
    
    # Timestamps
    data_entrega = models.DateTimeField()
    data_criacao_offline = models.DateTimeField(auto_now_add=True)
    data_sincronizacao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "POD Offline"
        verbose_name_plural = "PODs Offline"
        ordering = ['-data_criacao_offline']
        indexes = [
            models.Index(fields=['sessao_motorista', 'status']),
            models.Index(fields=['status', 'data_criacao_offline']),
            models.Index(fields=['codigo_offline']),
        ]
    
    def __str__(self):
        return f"{self.codigo_offline} - {self.nome_destinatario}"
    
    def save(self, *args, **kwargs):
        if not self.codigo_offline:
            self.codigo_offline = self._gerar_codigo_offline()
        super().save(*args, **kwargs)
    
    def _gerar_codigo_offline(self):
        """Gera código único para POD offline."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        count = PODOffline.objects.filter(
            codigo_offline__startswith=f"POD-OFF-{timestamp}"
        ).count()
        return f"POD-OFF-{timestamp}-{count + 1:03d}"


class RotaMotorista(models.Model):
    """Rotas planejadas para motoristas."""
    
    STATUS_CHOICES = [
        ('PLANEJADA', 'Planejada'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    
    # Relacionamentos
    motorista = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='rotas_motorista'
    )
    veiculo_interno = models.ForeignKey(
        'VeiculoInterno',
        on_delete=models.CASCADE,
        related_name='rotas_motorista'
    )
    sessao_motorista = models.ForeignKey(
        SessaoMotorista,
        on_delete=models.CASCADE,
        related_name='rotas',
        null=True,
        blank=True
    )
    
    # Configuração da rota
    nome_rota = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Datas
    data_planejada = models.DateField()
    hora_inicio_prevista = models.TimeField()
    hora_fim_prevista = models.TimeField()
    
    # Estatísticas
    total_entregas = models.PositiveIntegerField(default=0)
    entregas_realizadas = models.PositiveIntegerField(default=0)
    distancia_total_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tempo_estimado_minutos = models.PositiveIntegerField(default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANEJADA')
    
    # Timestamps
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_inicio_real = models.DateTimeField(null=True, blank=True)
    data_fim_real = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Rota Motorista"
        verbose_name_plural = "Rotas Motorista"
        ordering = ['-data_planejada', 'hora_inicio_prevista']
        indexes = [
            models.Index(fields=['motorista', 'data_planejada']),
            models.Index(fields=['status', 'data_planejada']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nome_rota}"


class ParadaRota(models.Model):
    """Paradas individuais em uma rota."""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
        ('PROBLEMA', 'Problema'),
    ]
    
    # Relacionamentos
    rota_motorista = models.ForeignKey(
        RotaMotorista,
        on_delete=models.CASCADE,
        related_name='paradas'
    )
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='paradas_rota'
    )
    
    # Ordem e configuração
    ordem_parada = models.PositiveIntegerField()
    tempo_estimado_minutos = models.PositiveIntegerField(default=15)
    
    # Localização
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    endereco_parada = models.CharField(max_length=255)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    
    # Timestamps
    hora_prevista_chegada = models.TimeField()
    hora_prevista_saida = models.TimeField()
    hora_real_chegada = models.DateTimeField(null=True, blank=True)
    hora_real_saida = models.DateTimeField(null=True, blank=True)
    
    # Observações
    observacoes = models.TextField(blank=True)
    problema_relatado = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Parada Rota"
        verbose_name_plural = "Paradas Rota"
        ordering = ['rota_motorista', 'ordem_parada']
        unique_together = ['rota_motorista', 'ordem_parada']
        indexes = [
            models.Index(fields=['rota_motorista', 'status']),
            models.Index(fields=['status', 'hora_prevista_chegada']),
        ]
    
    def __str__(self):
        return f"{self.rota_motorista.codigo} - Parada {self.ordem_parada}"


class ConfiguracaoMobile(models.Model):
    """Configurações para aplicativo mobile."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de sessão
    duracao_sessao_horas = models.PositiveIntegerField(default=8)
    timeout_inatividade_minutos = models.PositiveIntegerField(default=30)
    sincronizacao_automatica = models.BooleanField(default=True)
    intervalo_sincronizacao_minutos = models.PositiveIntegerField(default=5)
    
    # Configurações de GPS
    precisao_gps_minima = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('50.00')
    )
    intervalo_atualizacao_gps_segundos = models.PositiveIntegerField(default=30)
    rastreamento_background = models.BooleanField(default=True)
    
    # Configurações de POD
    pod_offline_habilitado = models.BooleanField(default=True)
    fotos_obrigatorias = models.BooleanField(default=True)
    assinatura_obrigatoria = models.BooleanField(default=True)
    gps_obrigatorio = models.BooleanField(default=True)
    
    # Configurações de notificações
    notificacoes_push = models.BooleanField(default=True)
    notificacoes_rota = models.BooleanField(default=True)
    notificacoes_entrega = models.BooleanField(default=True)
    notificacoes_problemas = models.BooleanField(default=True)
    
    # Configurações de cache
    cache_habilitado = models.BooleanField(default=True)
    tamanho_cache_mb = models.PositiveIntegerField(default=100)
    tempo_cache_horas = models.PositiveIntegerField(default=24)
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração Mobile"
        verbose_name_plural = "Configurações Mobile"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoMobile.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)


class LogMobile(models.Model):
    """Logs de operações mobile."""
    
    TIPO_OPERACAO_CHOICES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('SINCRONIZACAO', 'Sincronização'),
        ('EVENTO', 'Evento'),
        ('POD', 'POD'),
        ('GPS', 'GPS'),
        ('ERRO', 'Erro'),
    ]
    
    # Relacionamentos
    sessao_motorista = models.ForeignKey(
        SessaoMotorista,
        on_delete=models.CASCADE,
        related_name='logs',
        null=True,
        blank=True
    )
    
    # Operação
    tipo_operacao = models.CharField(max_length=20, choices=TIPO_OPERACAO_CHOICES)
    descricao = models.TextField(blank=True)
    dados_operacao = models.JSONField(default=dict)
    
    # Dispositivo
    dispositivo_info = models.JSONField(default=dict)
    versao_app = models.CharField(max_length=20, blank=True)
    plataforma = models.CharField(max_length=20, blank=True)
    
    # Status
    sucesso = models.BooleanField(default=True)
    erro_mensagem = models.TextField(blank=True)
    
    # Performance
    tempo_execucao_ms = models.PositiveIntegerField(null=True, blank=True)
    tamanho_dados_kb = models.PositiveIntegerField(null=True, blank=True)
    
    # Timestamp
    data_operacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log Mobile"
        verbose_name_plural = "Logs Mobile"
        ordering = ['-data_operacao']
        indexes = [
            models.Index(fields=['sessao_motorista', 'data_operacao']),
            models.Index(fields=['tipo_operacao', 'data_operacao']),
            models.Index(fields=['sucesso', 'data_operacao']),
        ]
    
    def __str__(self):
        return f"{self.tipo_operacao} - {self.data_operacao}"
