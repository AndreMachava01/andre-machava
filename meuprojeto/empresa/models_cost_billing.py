"""
Modelos para gestão de custos e faturamento logístico.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class CentroCusto(models.Model):
    """Centros de custo para rateio de despesas logísticas."""
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Hierarquia
    centro_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='centros_filhos'
    )
    
    # Configurações
    tipo = models.CharField(
        max_length=20,
        choices=[
            ('DEPARTAMENTO', 'Departamento'),
            ('PROJETO', 'Projeto'),
            ('CLIENTE', 'Cliente'),
            ('PRODUTO', 'Produto'),
            ('REGIONAL', 'Regional'),
        ],
        default='DEPARTAMENTO'
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        ordering = ['codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class TipoCusto(models.Model):
    """Tipos de custos logísticos."""
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configurações
    categoria = models.CharField(
        max_length=20,
        choices=[
            ('FRETE', 'Frete'),
            ('COMBUSTIVEL', 'Combustível'),
            ('MANUTENCAO', 'Manutenção'),
            ('PEDAGIO', 'Pedágio'),
            ('SEGURO', 'Seguro'),
            ('MULTA', 'Multa'),
            ('OUTROS', 'Outros'),
        ],
        default='FRETE'
    )
    
    # Rateio automático
    rateio_automatico = models.BooleanField(default=False)
    percentual_rateio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))]
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tipo de Custo"
        verbose_name_plural = "Tipos de Custo"
        ordering = ['categoria', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class CustoLogistico(models.Model):
    """Custos logísticos individuais."""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
        ('RATEADO', 'Rateado'),
        ('FATURADO', 'Faturado'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Relacionamentos
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='custos_logisticos',
        null=True,
        blank=True
    )
    tipo_custo = models.ForeignKey(TipoCusto, on_delete=models.PROTECT)
    centro_custo = models.ForeignKey(CentroCusto, on_delete=models.PROTECT)
    
    # Detalhes do custo
    descricao = models.TextField()
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    moeda = models.CharField(max_length=3, default='MZN')
    
    # Data e período
    data_custo = models.DateField(default=timezone.now)
    periodo_referencia = models.CharField(
        max_length=7,
        help_text="Formato: YYYY-MM"
    )
    
    # Documentação
    numero_documento = models.CharField(max_length=50, blank=True)
    arquivo_comprovante = models.FileField(
        upload_to='custos/comprovantes/%Y/%m/%d/',
        blank=True,
        null=True
    )
    
    # Rateio
    valor_rateado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    percentual_rateio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00')
    )
    
    # Status e aprovação
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    aprovado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custos_aprovados'
    )
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    observacoes_aprovacao = models.TextField(blank=True)
    
    # Auditoria
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custos_criados'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Custo Logístico"
        verbose_name_plural = "Custos Logísticos"
        ordering = ['-data_custo', '-data_criacao']
    
    def __str__(self):
        return f"{self.codigo} - {self.tipo_custo.nome} - R$ {self.valor}"
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_custo()
        if not self.periodo_referencia:
            self.periodo_referencia = timezone.now().strftime('%Y-%m')
        super().save(*args, **kwargs)
    
    def _gerar_codigo_custo(self):
        """Gera código único para custo."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        count = CustoLogistico.objects.filter(
            codigo__startswith=f"CL-{timestamp}"
        ).count()
        return f"CL-{timestamp}-{count + 1:03d}"


class RateioCusto(models.Model):
    """Rateio de custos entre centros de custo."""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
        ('APLICADO', 'Aplicado'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    
    # Relacionamentos
    custo_logistico = models.ForeignKey(
        CustoLogistico,
        on_delete=models.CASCADE,
        related_name='rateios'
    )
    centro_custo_destino = models.ForeignKey(
        CentroCusto,
        on_delete=models.CASCADE,
        related_name='rateios_recebidos'
    )
    
    # Detalhes do rateio
    valor_rateado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    percentual_rateio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100.00'))]
    )
    
    # Critério de rateio
    criterio_rateio = models.CharField(
        max_length=20,
        choices=[
            ('VOLUME', 'Volume'),
            ('PESO', 'Peso'),
            ('QUANTIDADE', 'Quantidade'),
            ('VALOR', 'Valor'),
            ('DISTANCIA', 'Distância'),
            ('MANUAL', 'Manual'),
        ],
        default='VOLUME'
    )
    
    # Status e aprovação
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    aprovado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rateios_aprovados'
    )
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Rateio de Custo"
        verbose_name_plural = "Rateios de Custo"
        ordering = ['-data_criacao']
        unique_together = ['custo_logistico', 'centro_custo_destino']
    
    def __str__(self):
        return f"{self.codigo} - {self.centro_custo_destino.nome} - R$ {self.valor_rateado}"
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_rateio()
        super().save(*args, **kwargs)
    
    def _gerar_codigo_rateio(self):
        """Gera código único para rateio."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        count = RateioCusto.objects.filter(
            codigo__startswith=f"RT-{timestamp}"
        ).count()
        return f"RT-{timestamp}-{count + 1:03d}"


class FaturamentoFrete(models.Model):
    """Faturamento de fretes para clientes."""
    
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('ENVIADO', 'Enviado'),
        ('PAGO', 'Pago'),
        ('VENCIDO', 'Vencido'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    # Identificação
    numero_fatura = models.CharField(max_length=20, unique=True)
    serie_fatura = models.CharField(max_length=10, default='LOG')
    
    # Cliente
    cliente_nome = models.CharField(max_length=100)
    cliente_documento = models.CharField(max_length=20)
    cliente_endereco = models.TextField()
    cliente_email = models.EmailField(blank=True)
    
    # Período e datas
    periodo_inicio = models.DateField()
    periodo_fim = models.DateField()
    data_emissao = models.DateField(default=timezone.now)
    data_vencimento = models.DateField()
    
    # Valores
    valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    valor_desconto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    valor_liquido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    moeda = models.CharField(max_length=3, default='MZN')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RASCUNHO')
    data_pagamento = models.DateField(null=True, blank=True)
    
    # Observações
    observacoes = models.TextField(blank=True)
    instrucoes_pagamento = models.TextField(blank=True)
    
    # Auditoria
    emitido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='faturas_emitidas'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Faturamento de Frete"
        verbose_name_plural = "Faturamentos de Frete"
        ordering = ['-data_emissao', '-numero_fatura']
    
    def __str__(self):
        return f"{self.numero_fatura} - {self.cliente_nome} - R$ {self.valor_liquido}"
    
    def save(self, *args, **kwargs):
        if not self.numero_fatura:
            self.numero_fatura = self._gerar_numero_fatura()
        if not self.data_vencimento:
            self.data_vencimento = self.data_emissao + timezone.timedelta(days=30)
        super().save(*args, **kwargs)
    
    def _gerar_numero_fatura(self):
        """Gera número único para fatura."""
        ano = timezone.now().year
        count = FaturamentoFrete.objects.filter(
            numero_fatura__startswith=f"{self.serie_fatura}{ano}"
        ).count()
        return f"{self.serie_fatura}{ano}{count + 1:06d}"


class ItemFaturamento(models.Model):
    """Itens de faturamento de frete."""
    
    # Relacionamentos
    faturamento = models.ForeignKey(
        FaturamentoFrete,
        on_delete=models.CASCADE,
        related_name='itens'
    )
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='itens_faturamento'
    )
    
    # Detalhes do item
    descricao = models.CharField(max_length=200)
    quantidade = models.PositiveIntegerField(default=1)
    valor_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    valor_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Data do serviço
    data_servico = models.DateField()
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Item de Faturamento"
        verbose_name_plural = "Itens de Faturamento"
        ordering = ['data_servico']
        unique_together = ['faturamento', 'rastreamento_entrega']
    
    def __str__(self):
        return f"{self.faturamento.numero_fatura} - {self.descricao} - R$ {self.valor_total}"
    
    def save(self, *args, **kwargs):
        # Calcular valor total automaticamente
        self.valor_total = self.quantidade * self.valor_unitario
        super().save(*args, **kwargs)


class ConfiguracaoFaturamento(models.Model):
    """Configurações para faturamento de fretes."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de faturamento
    serie_padrao = models.CharField(max_length=10, default='LOG')
    prazo_pagamento_dias = models.PositiveIntegerField(default=30)
    incluir_observacoes_padrao = models.TextField(blank=True)
    incluir_instrucoes_pagamento = models.TextField(blank=True)
    
    # Configurações de desconto
    permitir_desconto = models.BooleanField(default=True)
    desconto_maximo_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00')
    )
    
    # Configurações de agrupamento
    agrupar_por_cliente = models.BooleanField(default=True)
    agrupar_por_periodo = models.BooleanField(default=True)
    periodo_agrupamento_dias = models.PositiveIntegerField(default=30)
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração de Faturamento"
        verbose_name_plural = "Configurações de Faturamento"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoFaturamento.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)
