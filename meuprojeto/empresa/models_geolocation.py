"""
Modelos para geolocalização e cálculo de distâncias.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import json


class EnderecoNormalizado(models.Model):
    """Endereços normalizados com coordenadas geográficas."""
    
    # Endereço original
    endereco_original = models.TextField()
    endereco_normalizado = models.TextField()
    
    # Componentes do endereço
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=50, blank=True)
    pais = models.CharField(max_length=50, default='Moçambique')
    cep = models.CharField(max_length=20, blank=True)
    
    # Coordenadas geográficas
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(Decimal('-90.0')), MaxValueValidator(Decimal('90.0'))]
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        validators=[MinValueValidator(Decimal('-180.0')), MaxValueValidator(Decimal('180.0'))]
    )
    
    # Precisão e qualidade
    precisao = models.CharField(
        max_length=20,
        choices=[
            ('ROOFTOP', 'Precisão de Telhado'),
            ('RANGE_INTERPOLATED', 'Interpolado por Faixa'),
            ('GEOMETRIC_CENTER', 'Centro Geométrico'),
            ('APPROXIMATE', 'Aproximado'),
        ],
        default='APPROXIMATE'
    )
    nivel_confianca = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    
    # Metadados
    fonte_geocoding = models.CharField(max_length=50, default='MANUAL')
    data_geocoding = models.DateTimeField(auto_now_add=True)
    hash_endereco = models.CharField(max_length=64, unique=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    validado = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Endereço Normalizado"
        verbose_name_plural = "Endereços Normalizados"
        ordering = ['-data_geocoding']
        indexes = [
            models.Index(fields=['cidade', 'estado']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['hash_endereco']),
        ]
    
    def __str__(self):
        return f"{self.endereco_normalizado} ({self.latitude}, {self.longitude})"
    
    def save(self, *args, **kwargs):
        if not self.hash_endereco:
            self.hash_endereco = self._gerar_hash_endereco()
        super().save(*args, **kwargs)
    
    def _gerar_hash_endereco(self):
        """Gera hash único para o endereço."""
        import hashlib
        endereco_str = f"{self.endereco_original}{self.cidade}{self.estado}".lower()
        return hashlib.sha256(endereco_str.encode()).hexdigest()


class CalculoDistancia(models.Model):
    """Cálculos de distância entre pontos geográficos."""
    
    TIPO_CALCULO_CHOICES = [
        ('HAVERSINE', 'Fórmula de Haversine'),
        ('MANHATTAN', 'Distância de Manhattan'),
        ('EUCLIDIANA', 'Distância Euclidiana'),
        ('API_EXTERNA', 'API Externa'),
    ]
    
    # Pontos de origem e destino
    origem_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    origem_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    destino_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    destino_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Endereços relacionados
    endereco_origem = models.ForeignKey(
        EnderecoNormalizado,
        on_delete=models.CASCADE,
        related_name='calculos_origem',
        null=True,
        blank=True
    )
    endereco_destino = models.ForeignKey(
        EnderecoNormalizado,
        on_delete=models.CASCADE,
        related_name='calculos_destino',
        null=True,
        blank=True
    )
    
    # Resultados
    distancia_km = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    tempo_estimado_minutos = models.PositiveIntegerField()
    
    # Configurações do cálculo
    tipo_calculo = models.CharField(max_length=20, choices=TIPO_CALCULO_CHOICES)
    velocidade_media_kmh = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('50.00')
    )
    
    # Metadados
    precisao_calculo = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('95.00')
    )
    fonte_dados = models.CharField(max_length=50, default='CALCULADO')
    
    # Timestamp
    data_calculo = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Cálculo de Distância"
        verbose_name_plural = "Cálculos de Distância"
        ordering = ['-data_calculo']
        indexes = [
            models.Index(fields=['origem_latitude', 'origem_longitude']),
            models.Index(fields=['destino_latitude', 'destino_longitude']),
            models.Index(fields=['distancia_km']),
        ]
    
    def __str__(self):
        return f"{self.distancia_km}km - {self.tempo_estimado_minutos}min"


class ETACalculo(models.Model):
    """Cálculos de ETA (Estimated Time of Arrival)."""
    
    TIPO_ETA_CHOICES = [
        ('DISTANCIA', 'Baseado em Distância'),
        ('TRAFEGO', 'Com Tráfego'),
        ('HISTORICO', 'Histórico'),
        ('TEMPO_REAL', 'Tempo Real'),
    ]
    
    # Relacionamentos
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='etas_calculados',
        null=True,
        blank=True
    )
    calculo_distancia = models.ForeignKey(
        CalculoDistancia,
        on_delete=models.CASCADE,
        related_name='etas'
    )
    
    # Configurações do ETA
    tipo_eta = models.CharField(max_length=20, choices=TIPO_ETA_CHOICES)
    data_partida = models.DateTimeField()
    data_chegada_estimada = models.DateTimeField()
    
    # Fatores de ajuste
    fator_trafego = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text="Fator multiplicador para tráfego"
    )
    fator_clima = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text="Fator multiplicador para clima"
    )
    fator_horario = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text="Fator multiplicador para horário"
    )
    
    # Resultado final
    tempo_total_minutos = models.PositiveIntegerField()
    confiabilidade_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('80.00')
    )
    
    # Status
    eta_atualizado = models.BooleanField(default=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Cálculo de ETA"
        verbose_name_plural = "Cálculos de ETA"
        ordering = ['-data_atualizacao']
        indexes = [
            models.Index(fields=['rastreamento_entrega', 'data_partida']),
            models.Index(fields=['data_chegada_estimada']),
        ]
    
    def __str__(self):
        return f"ETA: {self.data_chegada_estimada} ({self.tempo_total_minutos}min)"


class ZonaGeografica(models.Model):
    """Zonas geográficas para agrupamento e análise."""
    
    TIPO_ZONA_CHOICES = [
        ('CIDADE', 'Cidade'),
        ('BAIRRO', 'Bairro'),
        ('REGIAO', 'Região'),
        ('POLIGONO', 'Polígono'),
        ('CIRCULO', 'Círculo'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Tipo e configuração
    tipo_zona = models.CharField(max_length=20, choices=TIPO_ZONA_CHOICES)
    
    # Coordenadas do centro
    centro_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    centro_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Geometria da zona
    geometria = models.JSONField(
        default=dict,
        help_text="Coordenadas que definem a zona (polígono, círculo, etc.)"
    )
    
    # Configurações
    raio_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Raio em km para zonas circulares"
    )
    
    # Metadados
    populacao_estimada = models.PositiveIntegerField(null=True, blank=True)
    area_km2 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Zona Geográfica"
        verbose_name_plural = "Zonas Geográficas"
        ordering = ['tipo_zona', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ConfiguracaoGeolocalizacao(models.Model):
    """Configurações para geolocalização e geocoding."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de geocoding
    geocoding_automatico = models.BooleanField(default=True)
    api_geocoding = models.CharField(
        max_length=50,
        choices=[
            ('GOOGLE', 'Google Maps'),
            ('OPENSTREET', 'OpenStreetMap'),
            ('MANUAL', 'Manual'),
        ],
        default='MANUAL'
    )
    api_key = models.CharField(max_length=200, blank=True)
    
    # Configurações de distância
    calculo_distancia_padrao = models.CharField(
        max_length=20,
        choices=[
            ('HAVERSINE', 'Fórmula de Haversine'),
            ('MANHATTAN', 'Distância de Manhattan'),
            ('EUCLIDIANA', 'Distância Euclidiana'),
        ],
        default='HAVERSINE'
    )
    velocidade_padrao_kmh = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('50.00')
    )
    
    # Configurações de ETA
    eta_automatico = models.BooleanField(default=True)
    considerar_trafego = models.BooleanField(default=False)
    considerar_clima = models.BooleanField(default=False)
    considerar_horario = models.BooleanField(default=True)
    
    # Configurações de cache
    cache_habilitado = models.BooleanField(default=True)
    tempo_cache_horas = models.PositiveIntegerField(default=24)
    
    # Configurações de precisão
    precisao_minima_metros = models.PositiveIntegerField(default=100)
    nivel_confianca_minimo = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('80.00')
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração Geolocalização"
        verbose_name_plural = "Configurações Geolocalização"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoGeolocalizacao.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)


class LogGeolocalizacao(models.Model):
    """Log de operações de geolocalização."""
    
    TIPO_OPERACAO_CHOICES = [
        ('GEOCODING', 'Geocoding'),
        ('REVERSE_GEOCODING', 'Reverse Geocoding'),
        ('CALCULO_DISTANCIA', 'Cálculo de Distância'),
        ('CALCULO_ETA', 'Cálculo de ETA'),
        ('NORMALIZACAO', 'Normalização de Endereço'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Operação
    tipo_operacao = models.CharField(max_length=20, choices=TIPO_OPERACAO_CHOICES)
    entrada_dados = models.JSONField(default=dict)
    resultado_dados = models.JSONField(default=dict)
    
    # Performance
    tempo_execucao_ms = models.PositiveIntegerField()
    sucesso = models.BooleanField(default=True)
    erro_mensagem = models.TextField(blank=True)
    
    # Fonte
    fonte_api = models.CharField(max_length=50, blank=True)
    custo_api = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )
    
    # Usuário e contexto
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Timestamp
    data_operacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log Geolocalização"
        verbose_name_plural = "Logs Geolocalização"
        ordering = ['-data_operacao']
        indexes = [
            models.Index(fields=['tipo_operacao', 'data_operacao']),
            models.Index(fields=['sucesso', 'data_operacao']),
            models.Index(fields=['fonte_api', 'data_operacao']),
        ]
    
    def __str__(self):
        return f"{self.tipo_operacao} - {self.data_operacao} - {self.tempo_execucao_ms}ms"
