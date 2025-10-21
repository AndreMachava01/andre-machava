"""
Modelos para roteirização e planejamento logístico.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal


class ZonaEntrega(models.Model):
    """Zona geográfica para agrupamento de entregas."""
    
    nome = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=20, unique=True)
    provincia = models.CharField(max_length=50)
    cidade = models.CharField(max_length=100)
    bairros = models.TextField(help_text="Lista de bairros separados por vírgula")
    
    # Coordenadas aproximadas do centro da zona
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Configurações de entrega
    prazo_entrega_padrao = models.PositiveIntegerField(
        default=1, 
        help_text="Prazo padrão em dias úteis"
    )
    custo_adicional = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Custo adicional por entrega nesta zona"
    )
    
    # Status e configurações
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    class Meta:
        verbose_name = "Zona de Entrega"
        verbose_name_plural = "Zonas de Entrega"
        ordering = ['provincia', 'cidade', 'nome']
    
    def __str__(self):
        return f"{self.nome} - {self.cidade}/{self.provincia}"


class Rota(models.Model):
    """Rota de entrega com sequência de paradas."""
    
    STATUS_CHOICES = [
        ('PLANEJADA', 'Planejada'),
        ('EM_EXECUCAO', 'Em Execução'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configurações da rota
    zona_origem = models.ForeignKey(
        ZonaEntrega, 
        on_delete=models.CASCADE,
        related_name='rotas_origem'
    )
    zonas_destino = models.ManyToManyField(
        ZonaEntrega,
        related_name='rotas_destino',
        help_text="Zonas que esta rota atende"
    )
    
    # Veículo e motorista
    veiculo_interno = models.ForeignKey(
        'VeiculoInterno',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Veículo interno designado para esta rota"
    )
    motorista = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'groups__name': 'Motoristas'},
        help_text="Motorista designado para esta rota"
    )
    
    # Datas e horários
    data_planejada = models.DateField()
    hora_inicio_prevista = models.TimeField()
    hora_fim_prevista = models.TimeField()
    
    # Status e execução
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANEJADA')
    data_inicio_real = models.DateTimeField(null=True, blank=True)
    data_fim_real = models.DateTimeField(null=True, blank=True)
    
    # Métricas
    distancia_total_km = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Distância total estimada em km"
    )
    tempo_estimado_minutos = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Tempo total estimado em minutos"
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rotas_criadas'
    )
    
    class Meta:
        verbose_name = "Rota"
        verbose_name_plural = "Rotas"
        ordering = ['-data_planejada', 'hora_inicio_prevista']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.data_planejada})"


class ParadaRota(models.Model):
    """Parada individual dentro de uma rota."""
    
    TIPO_CHOICES = [
        ('COLETA', 'Coleta'),
        ('ENTREGA', 'Entrega'),
        ('COMBUSTIVEL', 'Abastecimento'),
        ('REFEICAO', 'Refeição'),
        ('DESCANSO', 'Descanso'),
    ]
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
        ('PROBLEMA', 'Problema'),
    ]
    
    rota = models.ForeignKey(Rota, on_delete=models.CASCADE, related_name='paradas')
    sequencia = models.PositiveIntegerField(help_text="Ordem da parada na rota")
    
    # Tipo e destino
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    endereco = models.TextField()
    cidade = models.CharField(max_length=100)
    provincia = models.CharField(max_length=50)
    
    # Coordenadas
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Janela de tempo
    hora_chegada_prevista = models.TimeField()
    hora_saida_prevista = models.TimeField()
    tempo_estimado_minutos = models.PositiveIntegerField(
        default=30,
        help_text="Tempo estimado para completar a parada"
    )
    
    # Execução real
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    hora_chegada_real = models.DateTimeField(null=True, blank=True)
    hora_saida_real = models.DateTimeField(null=True, blank=True)
    
    # Detalhes específicos
    observacoes = models.TextField(blank=True)
    contato_nome = models.CharField(max_length=100, blank=True)
    contato_telefone = models.CharField(max_length=20, blank=True)
    
    # Relacionamento com entregas (para paradas de entrega)
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Entrega associada a esta parada"
    )
    
    class Meta:
        verbose_name = "Parada da Rota"
        verbose_name_plural = "Paradas da Rota"
        ordering = ['rota', 'sequencia']
        unique_together = ['rota', 'sequencia']
    
    def __str__(self):
        return f"{self.rota.codigo} - Parada {self.sequencia} ({self.tipo})"


class PlanejamentoEntrega(models.Model):
    """Planejamento de entregas por zona e rota."""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('AGENDADA', 'Agendada'),
        ('EM_ROTA', 'Em Rota'),
        ('ENTREGUE', 'Entregue'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('NORMAL', 'Normal'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    
    # Destino
    zona_entrega = models.ForeignKey(ZonaEntrega, on_delete=models.CASCADE)
    endereco_completo = models.TextField()
    cidade = models.CharField(max_length=100)
    provincia = models.CharField(max_length=50)
    
    # Coordenadas
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Janela de entrega
    data_entrega_preferida = models.DateField()
    janela_inicio = models.TimeField(help_text="Horário de início da janela de entrega")
    janela_fim = models.TimeField(help_text="Horário de fim da janela de entrega")
    
    # Prioridade e configurações
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    observacoes_entrega = models.TextField(blank=True)
    instrucoes_especiais = models.TextField(blank=True)
    
    # Contato
    contato_nome = models.CharField(max_length=100)
    contato_telefone = models.CharField(max_length=20)
    contato_email = models.EmailField(blank=True)
    
    # Execução
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    rota_atribuida = models.ForeignKey(
        Rota, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='planejamentos'
    )
    parada_rota = models.ForeignKey(
        ParadaRota,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planejamentos'
    )
    
    # Relacionamento com rastreamento
    rastreamento_entrega = models.OneToOneField(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='planejamento'
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Planejamento de Entrega"
        verbose_name_plural = "Planejamentos de Entrega"
        ordering = ['-data_entrega_preferida', 'prioridade', 'janela_inicio']
    
    def __str__(self):
        return f"{self.codigo} - {self.cidade} ({self.data_entrega_preferida})"


class ConfiguracaoRoteirizacao(models.Model):
    """Configurações para algoritmos de roteirização."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Parâmetros do algoritmo
    capacidade_maxima_veiculo = models.PositiveIntegerField(
        default=50,
        help_text="Capacidade máxima do veículo (kg)"
    )
    tempo_maximo_rota_horas = models.PositiveIntegerField(
        default=8,
        help_text="Tempo máximo de uma rota em horas"
    )
    distancia_maxima_rota_km = models.PositiveIntegerField(
        default=200,
        help_text="Distância máxima de uma rota em km"
    )
    
    # Fatores de otimização (pesos)
    peso_tempo = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Peso do tempo na otimização (0-10)"
    )
    peso_distancia = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Peso da distância na otimização (0-10)"
    )
    peso_prioridade = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(10.0)],
        help_text="Peso da prioridade na otimização (0-10)"
    )
    
    # Configurações avançadas
    considerar_trafego = models.BooleanField(default=True)
    considerar_janelas_tempo = models.BooleanField(default=True)
    agrupar_por_zona = models.BooleanField(default=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração de Roteirização"
        verbose_name_plural = "Configurações de Roteirização"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoRoteirizacao.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)
