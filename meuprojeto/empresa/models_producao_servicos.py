"""
Modelos de produção, serviços e empreitadas.
Necessários para o ORM Django (módulos Vendas/Produção e RH/empreitadas).
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class ClienteServico(models.Model):
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=50, blank=True, null=True)
    nuit = models.CharField(max_length=20, blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Cliente de Serviço'
        verbose_name_plural = 'Clientes de Serviço'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class OrdemServico(models.Model):
    STATUS_CHOICES = [
        ('AGENDADA', 'Agendada'),
        ('EM_ANDAMENTO', 'Em andamento'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]

    codigo = models.CharField(max_length=30, unique=True)
    data_agendada = models.DateTimeField()
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    endereco_servico = models.TextField()
    cidade_servico = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AGENDADA')
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1'))
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    validade_garantia_dias = models.PositiveIntegerField(null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    cliente = models.ForeignKey(
        ClienteServico, on_delete=models.CASCADE, related_name='ordens_servico',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico_criadas',
    )
    orcamento_origem = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_geradas',
    )
    sucursal = models.ForeignKey(
        'Sucursal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico',
    )

    class Meta:
        verbose_name = 'Ordem de Serviço'
        verbose_name_plural = 'Ordens de Serviço'
        ordering = ['-data_agendada', '-data_criacao']

    def __str__(self):
        return self.codigo


class ServicoOrcamentoServico(models.Model):
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1'))
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    desconto_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='servicos_orcamento',
    )
    servico = models.ForeignKey('Item', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Serviço de Orçamento'
        verbose_name_plural = 'Serviços de Orçamento'
        ordering = ['-data_criacao']
        unique_together = [('ordem_servico', 'servico')]


class AtividadeExecucao(models.Model):
    nome = models.CharField(max_length=300)
    numero_ordem = models.PositiveIntegerField(default=1)
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='atividades_execucao',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='subatividades',
    )

    class Meta:
        verbose_name = 'Actividade de execução'
        verbose_name_plural = 'Actividades de execução'
        ordering = ['ordem_servico_id', 'parent_id', 'numero_ordem']

    def __str__(self):
        return self.nome


class ServicoEntregueExecucao(models.Model):
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1'))
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    atividade = models.ForeignKey(
        AtividadeExecucao, on_delete=models.CASCADE, related_name='servicos_entregues',
    )
    servico = models.ForeignKey('Item', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Serviço entregue na actividade'
        verbose_name_plural = 'Serviços entregues na actividade'


class PrestadorServico(models.Model):
    TIPO_CHOICES = [
        ('SINGULAR', 'Pessoa singular'),
        ('EMPRESA', 'Empresa'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='SINGULAR')
    nome = models.CharField(max_length=200)
    representante_legal = models.CharField(max_length=200, blank=True)
    contacto = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    nuit = models.CharField(max_length=20, blank=True)
    endereco = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Prestador de Serviços'
        verbose_name_plural = 'Prestadores de Serviços'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ContratoEmpreitada(models.Model):
    clausula2_pagamento = models.TextField(blank=True, null=True)
    clausula3_prazo = models.TextField(blank=True, null=True)
    obrigacao_contratada_1 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratada_2 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratada_3 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_1 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_2 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_3 = models.CharField(max_length=500, blank=True, null=True)
    clausula5_garantia = models.TextField(blank=True, null=True)
    clausula6_alteracoes = models.TextField(blank=True, null=True)
    clausula7_rescisao = models.TextField(blank=True, null=True)
    clausula8_confidencialidade = models.TextField(blank=True, null=True)
    clausula9_foro = models.TextField(blank=True, null=True)
    prazo_execucao_numero = models.IntegerField(null=True, blank=True)
    prazo_execucao_unidade = models.CharField(max_length=10, blank=True, null=True)
    validade_garantia_dias = models.IntegerField(null=True, blank=True)
    validade_garantia_unidade = models.CharField(max_length=10, blank=True, null=True)
    incluir_clausula_suspensao_clima = models.BooleanField(default=False)
    clausula_suspensao_clima = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    data_assinatura = models.DateTimeField(null=True, blank=True)
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE,
        null=True, blank=True, related_name='contratos_empreitada',
    )
    prestador = models.ForeignKey(
        PrestadorServico, on_delete=models.CASCADE, related_name='contratos',
    )

    @property
    def valor_total(self):
        from django.db.models import Sum
        return self.trabalhos.aggregate(s=Sum('valor_fixo'))['s'] or Decimal('0')

    @property
    def pode_editar_clausulas(self):
        return not self.trabalhos.exclude(status__in=['PENDENTE', 'CANCELADO']).exists()

    class Meta:
        verbose_name = 'Contrato de Empreitada'
        verbose_name_plural = 'Contratos de Empreitada'
        unique_together = [('prestador', 'ordem_servico')]


class TrabalhoEmpreitada(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EM_ANDAMENTO', 'Em andamento'),
        ('CONCLUIDO', 'Concluído'),
        ('CANCELADO', 'Cancelado'),
    ]

    descricao = models.CharField(max_length=300)
    valor_fixo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_inicio = models.DateField(null=True, blank=True)
    data_conclusao = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    sucursal = models.ForeignKey(
        'Sucursal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='trabalhos_empreitada',
    )
    prestador = models.ForeignKey(
        PrestadorServico, on_delete=models.CASCADE, related_name='trabalhos_empreitada',
    )
    servico_orcamento = models.ForeignKey(
        ServicoOrcamentoServico, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='trabalhos_empreitada',
    )
    contrato_empreitada = models.ForeignKey(
        ContratoEmpreitada, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='trabalhos',
    )
    atividade_execucao = models.ForeignKey(
        AtividadeExecucao, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='trabalhos_vinculados',
    )
    clausula2_pagamento = models.TextField(blank=True, null=True)
    clausula3_prazo = models.TextField(blank=True, null=True)
    obrigacao_contratada_1 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratada_2 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratada_3 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_1 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_2 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_3 = models.CharField(max_length=500, blank=True, null=True)
    clausula5_garantia = models.TextField(blank=True, null=True)
    clausula6_alteracoes = models.TextField(blank=True, null=True)
    clausula7_rescisao = models.TextField(blank=True, null=True)
    clausula8_confidencialidade = models.TextField(blank=True, null=True)
    clausula9_foro = models.TextField(blank=True, null=True)
    prazo_execucao_numero = models.IntegerField(null=True, blank=True)
    prazo_execucao_unidade = models.CharField(max_length=10, blank=True, null=True)
    validade_garantia_dias = models.IntegerField(null=True, blank=True)
    validade_garantia_unidade = models.CharField(max_length=10, blank=True, null=True)
    incluir_clausula_suspensao_clima = models.BooleanField(default=False)
    clausula_suspensao_clima = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Trabalho por empreitada'
        verbose_name_plural = 'Trabalhos por empreitada'
        ordering = ['-data_criacao']

    def __str__(self):
        return self.descricao


class ParcelaPagamentoEmpreitada(models.Model):
    TIPO_ASSINATURA = 'ASSINATURA'
    TIPO_CONCLUSAO_TRABALHOS = 'CONCLUSAO_TRABALHOS'
    TIPO_CONCLUSAO_TOTAL = 'CONCLUSAO_TOTAL'
    TIPO_CHOICES = [
        (TIPO_ASSINATURA, 'À assinatura'),
        (TIPO_CONCLUSAO_TRABALHOS, 'À conclusão de trabalhos seleccionados'),
        (TIPO_CONCLUSAO_TOTAL, 'À conclusão total'),
    ]

    contrato_empreitada = models.ForeignKey(
        ContratoEmpreitada, on_delete=models.CASCADE, related_name='parcelas_pagamento',
    )
    numero_ordem = models.PositiveIntegerField(default=1)
    percentagem = models.PositiveIntegerField(default=0)
    tipo = models.CharField(max_length=24, choices=TIPO_CHOICES, default=TIPO_CONCLUSAO_TOTAL)
    data_pago = models.DateTimeField(null=True, blank=True)
    trabalhos = models.ManyToManyField(
        TrabalhoEmpreitada, blank=True, related_name='parcelas_pagamento',
    )

    class Meta:
        verbose_name = 'Parcela de pagamento (empreitada)'
        verbose_name_plural = 'Parcelas de pagamento (empreitada)'
        ordering = ['contrato_empreitada', 'numero_ordem']

    def valor_parcela(self):
        total = self.contrato_empreitada.valor_total
        return (total * Decimal(self.percentagem) / Decimal('100')).quantize(Decimal('0.01'))


class ConfiguracaoContratoEmpreitada(models.Model):
    nome = models.CharField(max_length=200)
    padrao = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    texto_cabecalho = models.TextField(blank=True, null=True)
    texto_rodape = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de contrato de empreitada'
        verbose_name_plural = 'Configurações de contrato de empreitada'
        ordering = ['-padrao', 'nome']

    def __str__(self):
        return self.nome
