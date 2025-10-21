"""
Modelos para POD (Prova de Entrega) e documentos logísticos.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class TipoDocumento(models.Model):
    """Tipos de documentos logísticos."""
    
    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configurações do documento
    obrigatorio = models.BooleanField(default=True)
    permite_multiplos = models.BooleanField(default=False)
    formato_arquivo = models.CharField(
        max_length=10,
        choices=[
            ('PDF', 'PDF'),
            ('JPG', 'JPG'),
            ('PNG', 'PNG'),
            ('DOC', 'DOC'),
            ('DOCX', 'DOCX'),
        ],
        default='PDF'
    )
    
    # Validações
    tamanho_maximo_mb = models.PositiveIntegerField(default=10)
    dimensoes_minimas = models.CharField(max_length=20, blank=True, help_text="Ex: 800x600")
    
    # Status
    ativo = models.BooleanField(default=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ProvaEntrega(models.Model):
    """Prova de entrega com assinatura, foto e GPS."""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('CONCLUIDA', 'Concluída'),
        ('REJEITADA', 'Rejeitada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    TIPO_ENTREGA_CHOICES = [
        ('COMPLETA', 'Entrega Completa'),
        ('PARCIAL', 'Entrega Parcial'),
        ('RECUSADA', 'Entrega Recusada'),
        ('DEVOLVIDA', 'Devolvida'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Relacionamentos
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='provas_entrega'
    )
    
    # Detalhes da entrega
    tipo_entrega = models.CharField(max_length=20, choices=TIPO_ENTREGA_CHOICES, default='COMPLETA')
    data_entrega = models.DateTimeField(default=timezone.now)
    endereco_entrega = models.CharField(max_length=255)
    
    # Localização GPS
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    precisao_gps = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Precisão em metros")
    
    # Informações do destinatário
    nome_destinatario = models.CharField(max_length=100)
    documento_destinatario = models.CharField(max_length=20, blank=True)
    telefone_destinatario = models.CharField(max_length=20, blank=True)
    parentesco_destinatario = models.CharField(max_length=50, blank=True, help_text="Ex: Filho, Pai, Vizinho")
    
    # Observações
    observacoes = models.TextField(blank=True)
    motivo_recusa = models.TextField(blank=True, help_text="Se entrega foi recusada")
    
    # Status e validação
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    validada = models.BooleanField(default=False)
    validada_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='provas_validadas'
    )
    data_validacao = models.DateTimeField(null=True, blank=True)
    
    # Responsável pela entrega
    entregue_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas_realizadas'
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Prova de Entrega"
        verbose_name_plural = "Provas de Entrega"
        ordering = ['-data_entrega']
    
    def __str__(self):
        return f"{self.codigo} - {self.rastreamento_entrega.codigo_rastreamento}"
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_pod()
        super().save(*args, **kwargs)
    
    def _gerar_codigo_pod(self):
        """Gera código único para POD."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        count = ProvaEntrega.objects.filter(
            codigo__startswith=f"POD-{timestamp}"
        ).count()
        return f"POD-{timestamp}-{count + 1:03d}"


class DocumentoPOD(models.Model):
    """Documentos anexados à prova de entrega."""
    
    TIPO_DOCUMENTO_CHOICES = [
        ('ASSINATURA', 'Assinatura'),
        ('FOTO_ENTREGA', 'Foto da Entrega'),
        ('FOTO_PRODUTO', 'Foto do Produto'),
        ('FOTO_DESTINATARIO', 'Foto do Destinatário'),
        ('COMPROVANTE', 'Comprovante'),
        ('NOTA_FISCAL', 'Nota Fiscal'),
        ('OUTROS', 'Outros'),
    ]
    
    # Relacionamentos
    prova_entrega = models.ForeignKey(ProvaEntrega, on_delete=models.CASCADE, related_name='documentos')
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.CASCADE, null=True, blank=True)
    
    # Detalhes do documento
    tipo = models.CharField(max_length=20, choices=TIPO_DOCUMENTO_CHOICES)
    nome_arquivo = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to='pod/documentos/%Y/%m/%d/')
    tamanho_arquivo = models.PositiveIntegerField(help_text="Tamanho em bytes")
    
    # Metadados
    descricao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    
    # Validação
    validado = models.BooleanField(default=False)
    validado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    data_validacao = models.DateTimeField(null=True, blank=True)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Documento POD"
        verbose_name_plural = "Documentos POD"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.prova_entrega.codigo} - {self.get_tipo_display()}"


class AssinaturaDigital(models.Model):
    """Assinatura digital do destinatário."""
    
    # Relacionamentos
    prova_entrega = models.OneToOneField(ProvaEntrega, on_delete=models.CASCADE, related_name='assinatura')
    
    # Dados da assinatura
    dados_assinatura = models.JSONField(help_text="Dados da assinatura em formato JSON")
    imagem_assinatura = models.ImageField(
        upload_to='pod/assinaturas/%Y/%m/%d/',
        null=True,
        blank=True
    )
    
    # Informações do dispositivo
    dispositivo = models.CharField(max_length=100, blank=True)
    navegador = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Validação
    hash_validacao = models.CharField(max_length=64, blank=True, help_text="Hash para validação de integridade")
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Assinatura Digital"
        verbose_name_plural = "Assinaturas Digitais"
    
    def __str__(self):
        return f"Assinatura - {self.prova_entrega.codigo}"


class GuiaRemessa(models.Model):
    """Guia de remessa para envio."""
    
    STATUS_CHOICES = [
        ('GERADA', 'Gerada'),
        ('IMPRESSA', 'Impressa'),
        ('ENVIADA', 'Enviada'),
        ('ENTREGUE', 'Entregue'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    numero_sequencial = models.PositiveIntegerField(unique=True)
    
    # Relacionamentos
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='guias_remessa'
    )
    
    # Detalhes da guia
    data_emissao = models.DateTimeField(default=timezone.now)
    data_prevista_entrega = models.DateField()
    
    # Remetente
    nome_remetente = models.CharField(max_length=100)
    endereco_remetente = models.TextField()
    telefone_remetente = models.CharField(max_length=20, blank=True)
    
    # Destinatário
    nome_destinatario = models.CharField(max_length=100)
    endereco_destinatario = models.TextField()
    telefone_destinatario = models.CharField(max_length=20, blank=True)
    
    # Produto/Serviço
    descricao_produto = models.TextField()
    peso = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    valor_declarado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Instruções
    instrucoes_especiais = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    
    # Status e impressão
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GERADA')
    impressa = models.BooleanField(default=False)
    data_impressao = models.DateTimeField(null=True, blank=True)
    impressa_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guias_impressas'
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Guia de Remessa"
        verbose_name_plural = "Guias de Remessa"
        ordering = ['-data_emissao']
    
    def __str__(self):
        return f"{self.codigo} - {self.rastreamento_entrega.codigo_rastreamento}"
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_guia()
        if not self.numero_sequencial:
            self.numero_sequencial = self._gerar_numero_sequencial()
        super().save(*args, **kwargs)
    
    def _gerar_codigo_guia(self):
        """Gera código único para guia."""
        timestamp = timezone.now().strftime("%Y%m%d")
        count = GuiaRemessa.objects.filter(
            codigo__startswith=f"GR-{timestamp}"
        ).count()
        return f"GR-{timestamp}-{count + 1:04d}"
    
    def _gerar_numero_sequencial(self):
        """Gera número sequencial único."""
        ultimo_numero = GuiaRemessa.objects.aggregate(
            max_numero=models.Max('numero_sequencial')
        )['max_numero']
        return (ultimo_numero or 0) + 1


class Etiqueta(models.Model):
    """Etiquetas para produtos/envios."""
    
    TIPO_CHOICES = [
        ('PRODUTO', 'Etiqueta de Produto'),
        ('ENVIO', 'Etiqueta de Envio'),
        ('RASTREAMENTO', 'Etiqueta de Rastreamento'),
        ('ESPECIAL', 'Etiqueta Especial'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=20, unique=True)
    codigo_barras = models.CharField(max_length=50, unique=True, blank=True)
    codigo_qr = models.CharField(max_length=100, unique=True, blank=True)
    
    # Relacionamentos
    rastreamento_entrega = models.ForeignKey(
        'RastreamentoEntrega',
        on_delete=models.CASCADE,
        related_name='etiquetas',
        null=True,
        blank=True
    )
    guia_remessa = models.ForeignKey(
        GuiaRemessa,
        on_delete=models.CASCADE,
        related_name='etiquetas',
        null=True,
        blank=True
    )
    
    # Detalhes da etiqueta
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    conteudo = models.JSONField(help_text="Conteúdo da etiqueta em formato JSON")
    
    # Dimensões
    largura_mm = models.PositiveIntegerField(default=100)
    altura_mm = models.PositiveIntegerField(default=60)
    
    # Status
    impressa = models.BooleanField(default=False)
    data_impressao = models.DateTimeField(null=True, blank=True)
    impressa_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etiquetas_impressas'
    )
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.codigo} - {self.get_tipo_display()}"
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_etiqueta()
        if not self.codigo_barras:
            self.codigo_barras = self._gerar_codigo_barras()
        if not self.codigo_qr:
            self.codigo_qr = self._gerar_codigo_qr()
        super().save(*args, **kwargs)
    
    def _gerar_codigo_etiqueta(self):
        """Gera código único para etiqueta."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        count = Etiqueta.objects.filter(
            codigo__startswith=f"ETQ-{timestamp}"
        ).count()
        return f"ETQ-{timestamp}-{count + 1:03d}"
    
    def _gerar_codigo_barras(self):
        """Gera código de barras único."""
        import random
        return f"ETQ{random.randint(100000000, 999999999)}"
    
    def _gerar_codigo_qr(self):
        """Gera código QR único."""
        return f"QR-{self.codigo}"


class ConfiguracaoPOD(models.Model):
    """Configurações para POD e documentos."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de POD
    obrigatorio_gps = models.BooleanField(default=True)
    precisao_gps_minima = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text="Precisão mínima do GPS em metros"
    )
    obrigatorio_foto = models.BooleanField(default=True)
    obrigatorio_assinatura = models.BooleanField(default=True)
    
    # Configurações de documentos
    tamanho_maximo_mb = models.PositiveIntegerField(default=10)
    formatos_permitidos = models.JSONField(
        default=list,
        help_text="Lista de formatos permitidos: ['PDF', 'JPG', 'PNG']"
    )
    
    # Configurações de guias
    template_guia = models.CharField(max_length=100, default='guia_padrao.html')
    incluir_codigo_barras = models.BooleanField(default=True)
    incluir_qr_code = models.BooleanField(default=True)
    
    # Configurações de etiquetas
    template_etiqueta = models.CharField(max_length=100, default='etiqueta_padrao.html')
    dimensoes_etiqueta = models.JSONField(
        default=dict,
        help_text="Ex: {'largura': 100, 'altura': 60}"
    )
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração POD"
        verbose_name_plural = "Configurações POD"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoPOD.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)
