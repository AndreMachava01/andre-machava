"""
Modelos do módulo Finanças — Plano de Contas e movimentos (base para conformidade legal MZ).

Referência contabilística: PGC-NIRF (Plano Geral de Contabilidade - Normas Internacionais
de Relato Financeiro), Decreto n.º 70/2009 de 22 de dezembro, Moçambique. O plano aplica-se
a empresas grandes e médias e baseia-se nas NIRF/IFRS. Códigos de contas utilizados no sistema
(61.xx, 62.xx, 63.xx = Gastos; 71.xx, 72.xx = Receitas) estão alinhados com a estrutura
de classes do PGC-NIRF (classe 6 = Gastos por natureza, classe 7 = Receitas).
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save
from decimal import Decimal


class Conta(models.Model):
    """
    Plano de Contas — contas contabilísticas (PGC-NIRF MZ, Decreto 70/2009).
    Hierarquia via conta_pai; tipo define natureza para balanço e DRE.
    Mapeamento tipo → classes PGC-NIRF: ATIVO (1–2), PASSIVO (2–3), PATRIMONIO (4),
    RECEITA (7), DESPESA (6 = Gastos por natureza).
    """
    TIPO_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('PASSIVO', 'Passivo'),
        ('PATRIMONIO', 'Património líquido'),
        ('RECEITA', 'Receita'),
        ('DESPESA', 'Despesa'),
    ]
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código da conta PGC-NIRF MZ (ex: 11.01 Activo, 61.01/62.01/63.01 Gastos, 71.01/72.01 Receitas)'
    )
    nome = models.CharField(max_length=200, help_text='Nome da conta')
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        help_text='Natureza da conta para balanço e DRE'
    )
    conta_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcontas',
        help_text='Conta pai na hierarquia do plano'
    )
    ordem = models.PositiveIntegerField(
        default=0,
        help_text='Ordem de exibição'
    )
    ativo = models.BooleanField(default=True)
    descricao = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conta (Plano de Contas)'
        verbose_name_plural = 'Contas (Plano de Contas)'
        ordering = ['codigo']
        permissions = [
            ('acesso_financas', 'Pode aceder ao módulo Finanças'),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class LancamentoFinanceiro(models.Model):
    """
    Movimento/lançamento financeiro para livro diário e rasto de auditoria.
    Pode ser manual ou referenciar origem (Vendas, Compras, RH, Logística).
    Valor: positivo = entrada/crédito na conta de receita ou redução de despesa;
          negativo = saída/débito ou aumento de despesa (conforme tipo da conta).
    """
    ORIGEM_CHOICES = [
        ('MANUAL', 'Lançamento manual'),
        ('VENDAS', 'Vendas (fatura/OS)'),
        ('COMPRAS', 'Compras'),
        ('RH', 'RH (folha de pagamento)'),
        ('RH_TREINAMENTO', 'RH (treinamentos)'),
        ('RH_EMPREITADA', 'RH (empreitada/trabalho por tarefa)'),
        ('RH_EMP_PARCELA', 'RH (empreitada parcela)'),
        ('LOGISTICA', 'Logística (custos/faturamento)'),
        ('TRANSFERENCIA', 'Transferência entre sucursais'),
    ]
    data = models.DateField(help_text='Data do movimento')
    conta = models.ForeignKey(
        Conta,
        on_delete=models.PROTECT,
        related_name='lancamentos',
        help_text='Conta do plano de contas'
    )
    valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('-999999999999.99'))],
        help_text='Valor (positivo = entrada/crédito, negativo = saída/débito conforme conta)'
    )
    descricao = models.CharField(
        max_length=500,
        help_text='Descrição do movimento'
    )
    documento_ref = models.CharField(
        max_length=100,
        blank=True,
        help_text='Referência do documento (factura, recibo, etc.)'
    )
    origem_tipo = models.CharField(
        max_length=20,
        choices=ORIGEM_CHOICES,
        default='MANUAL'
    )
    origem_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='ID do registo de origem (ex: OrdemServico.id, OrdemCompra.id)'
    )
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lancamentos_financeiros_criados'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento financeiro'
        verbose_name_plural = 'Lançamentos financeiros'
        ordering = ['-data', '-data_criacao']

    def __str__(self):
        return f"{self.data} - {self.conta.codigo} - {self.valor} MT"


class PendenteContaPagar(models.Model):
    """
    Item pendente em Contas a pagar — aguarda confirmação do departamento de Finanças.
    Os lançamentos só são criados quando Finanças confirma.
    """
    ESTADO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CONFIRMADO', 'Confirmado'),
        ('REJEITADO', 'Rejeitado'),
    ]
    ORIGEM_CHOICES = [
        ('RH_EMP_PARCELA', 'RH (empreitada parcela)'),
        ('RH_EMPREITADA', 'RH (empreitada)'),
        ('RH_TREINAMENTO', 'RH (treinamento)'),
        ('RH_FOLHA_SALARIAL', 'RH (folha salarial)'),
        ('COMPRAS', 'Compras'),
        ('LOGISTICA', 'Logística'),
        ('OUTRO', 'Outro'),
    ]
    origem_tipo = models.CharField(max_length=30, choices=ORIGEM_CHOICES, default='OUTRO')
    origem_id = models.PositiveIntegerField(null=True, blank=True, help_text='ID do registo de origem')
    beneficiario = models.CharField(max_length=300, help_text='Nome do prestador/fornecedor a pagar')
    valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Valor a pagar (MT)',
    )
    descricao = models.CharField(max_length=500, help_text='Descrição do pagamento')
    data_vencimento = models.DateField(null=True, blank=True, help_text='Data prevista de pagamento')
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='PENDENTE',
        db_index=True,
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_confirmacao = models.DateTimeField(null=True, blank=True)
    confirmado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contas_pagar_confirmadas',
    )
    lancamento = models.ForeignKey(
        LancamentoFinanceiro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pendente_conta_pagar',
        help_text='Lançamento criado após confirmação',
    )
    observacoes = models.TextField(blank=True)
    url_origem = models.CharField(max_length=500, blank=True, help_text='URL para ver o documento de origem')

    class Meta:
        verbose_name = 'Pendente Conta a Pagar'
        verbose_name_plural = 'Pendentes Contas a Pagar'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.beneficiario} — {self.valor} MT ({self.get_estado_display()})"


class PendenteContaReceber(models.Model):
    """
    Item pendente em Contas a receber — aguarda confirmação do departamento de Finanças.
    Os lançamentos só são criados quando Finanças confirma.
    """
    ESTADO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CONFIRMADO', 'Confirmado'),
        ('REJEITADO', 'Rejeitado'),
    ]
    ORIGEM_CHOICES = [
        ('VENDAS_PARCELA', 'Vendas (parcela contrato)'),
        ('VENDAS_FATURA', 'Vendas (fatura)'),
        ('LOGISTICA', 'Logística (faturamento)'),
        ('PROPOSTA_TECNICA', 'Proposta técnica (adiantamento levantamento)'),
        ('OUTRO', 'Outro'),
    ]
    origem_tipo = models.CharField(max_length=30, choices=ORIGEM_CHOICES, default='OUTRO')
    origem_id = models.PositiveIntegerField(null=True, blank=True, help_text='ID do registo de origem')
    credor = models.CharField(max_length=300, help_text='Nome do cliente a cobrar')
    valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Valor a receber (MT)',
    )
    descricao = models.CharField(max_length=500, help_text='Descrição do recebimento')
    data_vencimento = models.DateField(null=True, blank=True, help_text='Data prevista de recebimento')
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='PENDENTE',
        db_index=True,
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_confirmacao = models.DateTimeField(null=True, blank=True)
    confirmado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contas_receber_confirmadas',
    )
    lancamento = models.ForeignKey(
        LancamentoFinanceiro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pendente_conta_receber',
        help_text='Lançamento criado após confirmação',
    )
    observacoes = models.TextField(blank=True)
    url_origem = models.CharField(max_length=500, blank=True, help_text='URL para ver o documento de origem')

    class Meta:
        verbose_name = 'Pendente Conta a Receber'
        verbose_name_plural = 'Pendentes Contas a Receber'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.credor} — {self.valor} MT ({self.get_estado_display()})"


class ContadorSerieDocumento(models.Model):
    """
    Controlo de numeração sequencial por série e ano (facturas, recibos, etc.).
    Uso: obter próximo número com get_proximo_numero(serie, ano).
    """
    serie = models.CharField(max_length=20, help_text='Ex: FT, RC, NC')
    ano = models.PositiveIntegerField(help_text='Ano (ex: 2025)')
    proximo_numero = models.PositiveIntegerField(
        default=1,
        help_text='Próximo número a atribuir (incrementa após uso)'
    )
    descricao = models.CharField(max_length=100, blank=True, help_text='Ex: Factura de venda')

    class Meta:
        verbose_name = 'Contador de série (numeração legal)'
        verbose_name_plural = 'Contadores de série'
        unique_together = [['serie', 'ano']]
        ordering = ['serie', '-ano']

    def __str__(self):
        return f"{self.serie} {self.ano} → próximo: {self.proximo_numero}"

    @classmethod
    def get_proximo_numero(cls, serie, ano):
        """Atribui e devolve o próximo número da série/ano (thread-safe via select_for_update)."""
        from django.db import transaction
        with transaction.atomic():
            cont, created = cls.objects.select_for_update().get_or_create(
                serie=serie, ano=ano,
                defaults={'proximo_numero': 1},
            )
            num = cont.proximo_numero
            cont.proximo_numero += 1
            cont.save(update_fields=['proximo_numero'])
        return num


class LogAuditoria(models.Model):
    """
    Histórico de alterações para auditoria (ex.: lançamentos financeiros).
    modelo: nome do modelo (ex: LancamentoFinanceiro), objeto_id: PK, acao: CREATED/UPDATED/DELETED.
    """
    ACAO_CHOICES = [
        ('CREATED', 'Criado'),
        ('UPDATED', 'Alterado'),
        ('DELETED', 'Eliminado'),
    ]
    modelo = models.CharField(max_length=100, db_index=True)
    objeto_id = models.PositiveIntegerField(db_index=True)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    utilizador = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_auditoria',
    )
    data = models.DateTimeField(auto_now_add=True, db_index=True)
    dados_resumo = models.CharField(
        max_length=500,
        blank=True,
        help_text='Resumo dos dados alterados (ex: valor, conta)',
    )

    class Meta:
        verbose_name = 'Registo de auditoria'
        verbose_name_plural = 'Registos de auditoria'
        ordering = ['-data']

    def __str__(self):
        return f"{self.modelo} #{self.objeto_id} - {self.get_acao_display()} em {self.data}"


@receiver(post_save, sender=LancamentoFinanceiro)
def _log_auditoria_lancamento(sender, instance, created, **kwargs):
    """Regista criação/alteração de LancamentoFinanceiro para auditoria."""
    try:
        acao = 'CREATED' if created else 'UPDATED'
        resumo = f"data={instance.data} conta={instance.conta_id} valor={instance.valor}"
        LogAuditoria.objects.create(
            modelo='LancamentoFinanceiro',
            objeto_id=instance.pk,
            acao=acao,
            utilizador=instance.criado_por,
            dados_resumo=resumo[:500],
        )
    except Exception:
        pass  # não falhar o save por causa do log


@receiver(post_save, sender=Conta)
def _log_auditoria_conta(sender, instance, created, **kwargs):
    """Regista criação/alteração de Conta (Plano de Contas) para auditoria."""
    try:
        acao = 'CREATED' if created else 'UPDATED'
        resumo = f"codigo={instance.codigo} nome={instance.nome} tipo={instance.tipo}"
        LogAuditoria.objects.create(
            modelo='Conta',
            objeto_id=instance.pk,
            acao=acao,
            utilizador=None,  # Conta não tem campo utilizador
            dados_resumo=resumo[:500],
        )
    except Exception:
        pass


def _log_auditoria_configuracao_fiscal(sender, instance, created, **kwargs):
    """Regista criação/alteração de ConfiguracaoFiscal para auditoria."""
    try:
        acao = 'CREATED' if created else 'UPDATED'
        resumo = f"nome={instance.nome} taxa_iva={instance.taxa_iva}"
        LogAuditoria.objects.create(
            modelo='ConfiguracaoFiscal',
            objeto_id=instance.pk,
            acao=acao,
            utilizador=None,
            dados_resumo=resumo[:500],
        )
    except Exception:
        pass


# Registo de auditoria para ConfiguracaoFiscal (import tardio para evitar dependência circular)
from .models_base import ConfiguracaoFiscal
post_save.connect(_log_auditoria_configuracao_fiscal, sender=ConfiguracaoFiscal)
