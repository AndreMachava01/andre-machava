"""
Modelos para dados mestres (masterdata) do sistema logístico.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class Regiao(models.Model):
    """Regiões geográficas para organização logística."""
    
    codigo = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Hierarquia geográfica
    pais = models.CharField(max_length=50, default='Moçambique')
    provincia = models.CharField(max_length=50)
    distrito = models.CharField(max_length=50, blank=True)
    
    # Coordenadas geográficas
    latitude_centro = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True
    )
    longitude_centro = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True
    )
    
    # Configurações
    ativo = models.BooleanField(default=True)
    prioridade = models.PositiveIntegerField(default=1)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Região"
        verbose_name_plural = "Regiões"
        ordering = ['prioridade', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


# ZonaEntrega movida para models_routing.py para evitar conflito de modelos


class HubLogistico(models.Model):
    """Hubs logísticos para consolidação e distribuição."""
    
    TIPO_CHOICES = [
        ('ORIGEM', 'Hub de Origem'),
        ('DESTINO', 'Hub de Destino'),
        ('CONSOLIDACAO', 'Hub de Consolidação'),
        ('DISTRIBUICAO', 'Hub de Distribuição'),
    ]
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Localização
    endereco = models.TextField()
    cidade = models.CharField(max_length=50)
    regiao = models.ForeignKey(Regiao, on_delete=models.CASCADE, related_name='hubs')
    
    # Coordenadas
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Configurações
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    capacidade_maxima_m3 = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    capacidade_maxima_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Horários de funcionamento
    horario_inicio = models.TimeField(default='06:00')
    horario_fim = models.TimeField(default='22:00')
    funcionamento_24h = models.BooleanField(default=False)
    
    # Contato
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    responsavel = models.CharField(max_length=100, blank=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Hub Logístico"
        verbose_name_plural = "Hubs Logísticos"
        ordering = ['tipo', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class CatalogoDimensoes(models.Model):
    """Catálogo de dimensões padrão para produtos."""
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Dimensões em centímetros
    comprimento_cm = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    largura_cm = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    altura_cm = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Peso em quilogramas
    peso_kg = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Volume calculado
    volume_m3 = models.DecimalField(
        max_digits=8, 
        decimal_places=4,
        editable=False
    )
    
    # Categoria
    categoria = models.CharField(
        max_length=50,
        choices=[
            ('DOCUMENTO', 'Documento'),
            ('PACOTE_PEQUENO', 'Pacote Pequeno'),
            ('PACOTE_MEDIO', 'Pacote Médio'),
            ('PACOTE_GRANDE', 'Pacote Grande'),
            ('VOLUME_ESPECIAL', 'Volume Especial'),
        ],
        default='PACOTE_MEDIO'
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Catálogo de Dimensões"
        verbose_name_plural = "Catálogo de Dimensões"
        ordering = ['categoria', 'volume_m3']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"
    
    def save(self, *args, **kwargs):
        # Calcular volume automaticamente
        self.volume_m3 = (
            self.comprimento_cm * self.largura_cm * self.altura_cm
        ) / 1000000  # Converter cm³ para m³
        super().save(*args, **kwargs)


class RestricaoLogistica(models.Model):
    """Restrições logísticas para produtos e serviços."""
    
    TIPO_CHOICES = [
        ('PESO', 'Restrição de Peso'),
        ('VOLUME', 'Restrição de Volume'),
        ('DIMENSAO', 'Restrição de Dimensão'),
        ('TEMPERATURA', 'Restrição de Temperatura'),
        ('FRAGILIDADE', 'Restrição de Fragilidade'),
        ('PERIGOSO', 'Produto Perigoso'),
        ('VALOR', 'Restrição de Valor'),
        ('HORARIO', 'Restrição de Horário'),
        ('ZONA', 'Restrição de Zona'),
        ('TRANSPORTADORA', 'Restrição de Transportadora'),
    ]
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Tipo de restrição
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    
    # Valores da restrição
    valor_minimo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    valor_maximo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    unidade_medida = models.CharField(max_length=20, blank=True)
    
    # Aplicação
    aplicavel_veiculo_interno = models.BooleanField(default=True)
    aplicavel_transportadora = models.BooleanField(default=True)
    
    # Ações quando restrição é violada
    acao_violacao = models.CharField(
        max_length=20,
        choices=[
            ('BLOQUEAR', 'Bloquear Operação'),
            ('AVISAR', 'Apenas Avisar'),
            ('CUSTO_ADICIONAL', 'Aplicar Custo Adicional'),
            ('APROVACAO_MANUAL', 'Requer Aprovação Manual'),
        ],
        default='AVISAR'
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Restrição Logística"
        verbose_name_plural = "Restrições Logísticas"
        ordering = ['tipo', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class PermissaoLogistica(models.Model):
    """Permissões específicas para operações logísticas."""
    
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Escopo da permissão
    modulo = models.CharField(
        max_length=20,
        choices=[
            ('RASTREAMENTO', 'Rastreamento'),
            ('CUSTOS', 'Custos'),
            ('FATURAMENTO', 'Faturamento'),
            ('POD', 'POD'),
            ('ROTEAMENTO', 'Roteamento'),
            ('EXCECOES', 'Exceções'),
            ('ALOCACAO', 'Alocação'),
            ('MASTERDATA', 'Dados Mestres'),
        ]
    )
    
    # Ação permitida
    acao = models.CharField(
        max_length=20,
        choices=[
            ('CRIAR', 'Criar'),
            ('EDITAR', 'Editar'),
            ('EXCLUIR', 'Excluir'),
            ('APROVAR', 'Aprovar'),
            ('REJEITAR', 'Rejeitar'),
            ('VISUALIZAR', 'Visualizar'),
            ('EXPORTAR', 'Exportar'),
            ('IMPORTAR', 'Importar'),
        ]
    )
    
    # Condições
    condicoes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Condições específicas para aplicação da permissão"
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Permissão Logística"
        verbose_name_plural = "Permissões Logísticas"
        ordering = ['modulo', 'acao', 'nome']
        unique_together = ['codigo', 'modulo', 'acao']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ConfiguracaoMasterdata(models.Model):
    """Configurações gerais para dados mestres."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de zonas
    zona_padrao_prazo_dias = models.PositiveIntegerField(default=1)
    zona_padrao_custo_adicional = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    
    # Configurações de hubs
    hub_padrao_capacidade_m3 = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('1000.00')
    )
    hub_padrao_capacidade_kg = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('10000.00')
    )
    
    # Configurações de dimensões
    dimensao_padrao_comprimento = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('30.00')
    )
    dimensao_padrao_largura = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('20.00')
    )
    dimensao_padrao_altura = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('10.00')
    )
    dimensao_padrao_peso = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('1.00')
    )
    
    # Configurações de restrições
    aplicar_restricoes_automaticamente = models.BooleanField(default=True)
    bloquear_violacoes_criticas = models.BooleanField(default=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração Masterdata"
        verbose_name_plural = "Configurações Masterdata"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoMasterdata.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)


class LogMasterdata(models.Model):
    """Log de alterações em dados mestres."""
    
    TIPO_OPERACAO_CHOICES = [
        ('CRIAR', 'Criar'),
        ('EDITAR', 'Editar'),
        ('EXCLUIR', 'Excluir'),
        ('ATIVAR', 'Ativar'),
        ('DESATIVAR', 'Desativar'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Operação
    tipo_operacao = models.CharField(max_length=20, choices=TIPO_OPERACAO_CHOICES)
    modelo_afetado = models.CharField(max_length=50)
    objeto_id = models.PositiveIntegerField()
    
    # Dados
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    
    # Usuário e contexto
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamp
    data_operacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log Masterdata"
        verbose_name_plural = "Logs Masterdata"
        ordering = ['-data_operacao']
        indexes = [
            models.Index(fields=['modelo_afetado', 'objeto_id']),
            models.Index(fields=['usuario', 'data_operacao']),
        ]
    
    def __str__(self):
        return f"{self.tipo_operacao} - {self.modelo_afetado} - {self.data_operacao}"
