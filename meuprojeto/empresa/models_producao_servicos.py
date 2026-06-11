"""
Modelos de produção e serviços (Vendas / Produção).
Alinhados ao schema PostgreSQL (inspectdb) e às migrações 0155+.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def _valor_linha(quantidade, valor_unitario, desconto=None, desconto_percentual=None):
    """Total de linha (serviço/item) com desconto fixo e/ou percentual."""
    q = Decimal(str(quantidade or 0))
    vu = Decimal(str(valor_unitario or 0))
    bruto = q * vu
    pct = Decimal(str(desconto_percentual or 0))
    if pct:
        bruto -= bruto * (pct / Decimal('100'))
    bruto -= Decimal(str(desconto or 0))
    return max(bruto, Decimal('0'))


class OrdemProducao(models.Model):
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('PLANEJADA', 'Planejada'),
        ('EM_PRODUCAO', 'Em Produção'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
        ('PAUSADA', 'Pausada'),
    ]
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('NORMAL', 'Normal'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]
    FASE_CHOICES = [
        ('FASE1_CRIACAO', 'Fase 1: Criação e Aprovação'),
        ('FASE2_EXECUCAO', 'Fase 2: Preparação e Execução'),
        ('FASE3_FINALIZACAO', 'Fase 3: Acabamentos e Finalizações'),
        ('FINALIZADA', 'Finalizada'),
        ('CANCELADA', 'Cancelada'),
    ]
    STATUS_APROVACAO_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADA', 'Aprovada'),
        ('REJEITADA', 'Rejeitada'),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    data_criacao = models.DateTimeField(auto_now_add=True)
    quantidade_produzida = models.PositiveIntegerField(default=0)
    data_cancelamento = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.TextField(blank=True)
    fase_atual = models.CharField(max_length=20, choices=FASE_CHOICES, default='FASE1_CRIACAO')
    status_aprovacao = models.CharField(
        max_length=20, choices=STATUS_APROVACAO_CHOICES, default='PENDENTE',
    )
    acabamentos_concluidos = models.BooleanField(default=False)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_producao_aprovadas',
    )
    aprovado_qualidade_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_aprovadas_qualidade',
    )
    controle_qualidade_aprovado = models.BooleanField(default=False)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_aprovacao_qualidade = models.DateTimeField(null=True, blank=True)
    data_finalizacao = models.DateTimeField(null=True, blank=True)
    data_inicio_fase2 = models.DateTimeField(null=True, blank=True)
    data_inicio_fase3 = models.DateTimeField(null=True, blank=True)
    montagem_concluida = models.BooleanField(default=False)
    motivo_rejeicao = models.TextField(blank=True)
    observacoes_criacao = models.TextField(blank=True)
    observacoes_execucao = models.TextField(blank=True)
    observacoes_finalizacao = models.TextField(blank=True)
    observacoes_qualidade = models.TextField(blank=True)
    preparacao_pecas_concluida = models.BooleanField(default=False)
    produto_disponibilizado = models.BooleanField(default=False)
    requisicao_material_criada = models.BooleanField(default=False)
    responsavel_fase2 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_responsavel_fase2',
    )
    responsavel_fase3 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_responsavel_fase3',
    )
    retoques_concluidos = models.BooleanField(default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_producao_criadas',
    )
    receita = models.ForeignKey(
        'Receita', on_delete=models.CASCADE, related_name='ordens_producao',
    )
    sucursal = models.ForeignKey('Sucursal', on_delete=models.CASCADE)
    requisicao_material = models.ForeignKey(
        'RequisicaoProducao', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordem_producao_rel',
    )

    class Meta:
        verbose_name = 'Ordem de Produção'
        verbose_name_plural = 'Ordens de Produção'
        ordering = ['-data_criacao']

    @property
    def status(self):
        """Compatibilidade com views/formulários antigos baseados em fase."""
        if getattr(self, '_pausada', False) and self.fase_atual in (
            'FASE2_EXECUCAO', 'FASE3_FINALIZACAO',
        ):
            return 'PAUSADA'
        if self.fase_atual == 'CANCELADA':
            return 'CANCELADA'
        if self.fase_atual == 'FINALIZADA':
            return 'CONCLUIDA'
        if self.fase_atual == 'FASE2_EXECUCAO':
            return 'EM_PRODUCAO'
        if self.fase_atual == 'FASE3_FINALIZACAO':
            return 'EM_PRODUCAO'
        if self.status_aprovacao == 'APROVADA':
            return 'PLANEJADA'
        return 'RASCUNHO'

    @status.setter
    def status(self, value):
        if value == 'PAUSADA':
            if self.fase_atual in ('FASE2_EXECUCAO', 'FASE3_FINALIZACAO'):
                self._pausada = True
            return
        self._pausada = False
        if value == 'CANCELADA':
            self.fase_atual = 'CANCELADA'
        elif value == 'CONCLUIDA':
            self.fase_atual = 'FINALIZADA'
            if not self.data_finalizacao:
                self.data_finalizacao = timezone.now()
        elif value == 'EM_PRODUCAO':
            if self.fase_atual == 'FASE1_CRIACAO':
                self.fase_atual = 'FASE2_EXECUCAO'
            if not self.data_inicio_fase2:
                self.data_inicio_fase2 = timezone.now()
        elif value == 'PLANEJADA' and self.fase_atual == 'FASE1_CRIACAO':
            self.status_aprovacao = 'APROVADA'
        elif value == 'RASCUNHO' and self.fase_atual not in ('FINALIZADA', 'CANCELADA'):
            self.fase_atual = 'FASE1_CRIACAO'
            self.status_aprovacao = 'PENDENTE'

    def pode_avancar_fase(self):
        if self.fase_atual == 'FASE2_EXECUCAO':
            return self.preparacao_pecas_concluida and self.montagem_concluida
        if self.fase_atual == 'FASE3_FINALIZACAO':
            return (
                self.acabamentos_concluidos
                and self.retoques_concluidos
                and self.controle_qualidade_aprovado
            )
        return False

    @property
    def processo(self):
        """Processo via receita (coluna removida na migração 0164)."""
        override = getattr(self, '_processo_override', None)
        if override is not None:
            return override
        if self.receita_id:
            return self.receita.processos.filter(
                status__in=['ATIVO', 'APROVADO'],
            ).first()
        return None

    @processo.setter
    def processo(self, value):
        self._processo_override = value

    @property
    def observacoes(self):
        return self.observacoes_criacao

    @observacoes.setter
    def observacoes(self, value):
        self.observacoes_criacao = value or ''

    @property
    def responsavel(self):
        return self.responsavel_fase2

    @responsavel.setter
    def responsavel(self, value):
        self.responsavel_fase2 = value

    @property
    def data_planejada_inicio(self):
        return getattr(self, '_data_planejada_inicio', None)

    @data_planejada_inicio.setter
    def data_planejada_inicio(self, value):
        self._data_planejada_inicio = value

    @property
    def data_planejada_conclusao(self):
        return getattr(self, '_data_planejada_conclusao', None)

    @data_planejada_conclusao.setter
    def data_planejada_conclusao(self, value):
        self._data_planejada_conclusao = value

    @property
    def data_inicio(self):
        return self.data_inicio_fase2

    @data_inicio.setter
    def data_inicio(self, value):
        self.data_inicio_fase2 = value

    @property
    def data_conclusao(self):
        return self.data_finalizacao

    @data_conclusao.setter
    def data_conclusao(self, value):
        self.data_finalizacao = value


class ProcessoProducao(models.Model):
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
        ('RASCUNHO', 'Rascunho'),
        ('APROVADO', 'Aprovado'),
    ]

    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True, blank=True)
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RASCUNHO')
    tempo_total_estimado = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
    )
    observacoes = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='processos_criados',
    )
    receitas = models.ManyToManyField(
        'Receita', blank=True, related_name='processos',
    )

    class Meta:
        verbose_name = 'Processo de Produção'
        verbose_name_plural = 'Processos de Produção'
        ordering = ['-data_criacao']


class EtapaProcesso(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=1)
    tempo_estimado = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
    )
    observacoes = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='etapas_responsaveis',
    )
    processo = models.ForeignKey(
        ProcessoProducao, on_delete=models.CASCADE, related_name='etapas',
    )

    class Meta:
        verbose_name = 'Etapa do Processo'
        verbose_name_plural = 'Etapas do Processo'
        ordering = ['processo', 'ordem', 'nome']


class EtapaOrdemConcluida(models.Model):
    data_conclusao = models.DateTimeField(auto_now_add=True)
    observacoes = models.TextField(blank=True)
    concluida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='etapas_concluidas',
    )
    etapa = models.ForeignKey(
        EtapaProcesso, on_delete=models.CASCADE, related_name='ordens_concluidas',
    )
    ordem = models.ForeignKey(
        OrdemProducao, on_delete=models.CASCADE, related_name='etapas_concluidas',
    )

    class Meta:
        verbose_name = 'Etapa Concluída'
        verbose_name_plural = 'Etapas Concluídas'
        ordering = ['ordem', 'etapa__ordem', 'data_conclusao']
        unique_together = [('ordem', 'etapa')]


class Maquina(models.Model):
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),
        ('EM_USO', 'Em Uso'),
        ('MANUTENCAO', 'Em Manutenção'),
        ('INATIVO', 'Inativo'),
        ('RESERVADO', 'Reservado'),
    ]
    TIPO_CHOICES = [
        ('MAQUINA', 'Máquina'),
        ('EQUIPAMENTO', 'Equipamento'),
        ('FERRAMENTA', 'Ferramenta'),
        ('LINHA_PRODUCAO', 'Linha de Produção'),
        ('CELULA_PRODUCAO', 'Célula de Produção'),
        ('OUTRO', 'Outro'),
    ]

    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='MAQUINA')
    descricao = models.TextField(blank=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    numero_serie = models.CharField(max_length=100, blank=True)
    capacidade = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidade_capacidade = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')
    localizacao = models.CharField(max_length=200, blank=True)
    data_aquisicao = models.DateField(null=True, blank=True)
    data_proxima_manutencao = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='maquinas_criadas',
    )
    sucursal = models.ForeignKey('Sucursal', on_delete=models.CASCADE, related_name='maquinas')

    class Meta:
        verbose_name = 'Máquina'
        verbose_name_plural = 'Máquinas'
        ordering = ['-data_criacao']


class LinhaProducao(models.Model):
    TIPO_CHOICES = [
        ('LINHA', 'Linha de Produção'),
        ('CELULA', 'Célula de Produção'),
        ('ESTACAO', 'Estação de Trabalho'),
        ('AREA', 'Área de Produção'),
    ]
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
        ('MANUTENCAO', 'Em Manutenção'),
        ('RESERVADA', 'Reservada'),
    ]

    nome = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='LINHA')
    descricao = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVA')
    localizacao = models.CharField(max_length=200, blank=True)
    capacidade_horaria = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observacoes = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='linhas_producao_criadas',
    )
    maquinas = models.ManyToManyField(Maquina, blank=True, related_name='linhas_producao')
    processos = models.ManyToManyField(ProcessoProducao, blank=True, related_name='linhas_producao')
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='linhas_producao_responsavel',
    )
    sucursal = models.ForeignKey('Sucursal', on_delete=models.CASCADE, related_name='linhas_producao')

    class Meta:
        verbose_name = 'Linha de Produção'
        verbose_name_plural = 'Linhas de Produção'
        ordering = ['-data_criacao']


class ClienteServico(models.Model):
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    nuit = models.CharField(max_length=20, blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)
    isento_iva = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Cliente de Serviço'
        verbose_name_plural = 'Clientes de Serviço'
        ordering = ['nome']


class OrdemServico(models.Model):
    STATUS_CHOICES = [
        ('AGENDADA', 'Agendada'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('PAUSADA', 'Pausada'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('NORMAL', 'Normal'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]
    FORMA_PAGAMENTO_CHOICES = [
        ('PRONTO_PAGAMENTO', 'CASH'),
        ('CREDITO', 'CREDITO'),
        ('POR_CONTA', 'Por Conta'),  # legado
    ]

    codigo = models.CharField(max_length=20, unique=True, blank=True)
    data_agendada = models.DateTimeField()
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    endereco_servico = models.TextField()
    cidade_servico = models.CharField(max_length=100, blank=True, null=True)
    equipe = models.CharField(max_length=200, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AGENDADA')
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True)
    problema_relatado = models.TextField(blank=True, null=True)
    solucao_aplicada = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    forma_pagamento = models.CharField(
        max_length=20, choices=FORMA_PAGAMENTO_CHOICES, default='PRONTO_PAGAMENTO',
    )
    nome_cliente_pagamento = models.CharField(max_length=200, blank=True, null=True)
    nuit_cliente_pagamento = models.CharField(max_length=20, blank=True, null=True)
    telefone_cliente_pagamento = models.CharField(max_length=20, blank=True, null=True)
    nome_documento = models.CharField(max_length=200, blank=True, null=True)
    orcamento_origem = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico_geradas',
    )
    numero_impressao_fatura = models.IntegerField(default=0)
    numero_impressao_garantia = models.IntegerField(default=0)
    validade_garantia_dias = models.IntegerField(default=90)
    numero_fatura_fiscal = models.CharField(max_length=30, blank=True, default='')
    data_cobranca = models.DateField(null=True, blank=True)
    departamento_origem = models.CharField(max_length=20, blank=True, null=True)
    prazo_excluir_feriados = models.BooleanField(default=False)
    prazo_excluir_fins_semana = models.BooleanField(default=False)
    prazo_execucao_numero = models.IntegerField(null=True, blank=True)
    prazo_execucao_unidade = models.CharField(max_length=10, blank=True, default='')
    validade_garantia_unidade = models.CharField(max_length=10, blank=True, default='')
    pagamento_percentagem_assinatura = models.SmallIntegerField(null=True, blank=True)
    pagamento_percentagem_conclusao = models.SmallIntegerField(null=True, blank=True)
    prazo_fins_semana_modo = models.CharField(max_length=20, blank=True, null=True)
    incluir_clausula_suspensao_clima = models.BooleanField(default=False)
    clausula2_pagamento = models.TextField(blank=True, null=True)
    clausula3_prazo = models.TextField(blank=True, null=True)
    clausula4_obrigacoes = models.TextField(blank=True, null=True)
    clausula5_garantia = models.TextField(blank=True, null=True)
    clausula6_alteracoes = models.TextField(blank=True, null=True)
    clausula7_rescisao = models.TextField(blank=True, null=True)
    clausula8_confidencialidade = models.TextField(blank=True, null=True)
    clausula9_foro = models.TextField(blank=True, null=True)
    clausula_suspensao_clima = models.TextField(blank=True, null=True)
    obrigacao_contratada_1 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratada_2 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratada_3 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_1 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_2 = models.CharField(max_length=500, blank=True, null=True)
    obrigacao_contratante_3 = models.CharField(max_length=500, blank=True, null=True)
    cliente = models.ForeignKey(
        ClienteServico, on_delete=models.CASCADE,
        null=True, blank=True, related_name='ordens_servico',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico_criadas',
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico_responsavel',
    )
    servico = models.ForeignKey(
        'Item', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico_legado',
    )
    forma_pagamento_configurada = models.ForeignKey(
        'FormaPagamento', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico',
    )
    sucursal = models.ForeignKey(
        'Sucursal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ordens_servico',
    )

    class Meta:
        verbose_name = 'Ordem de Serviço'
        verbose_name_plural = 'Ordens de Serviço'
        ordering = ['-data_agendada', '-data_criacao']

    def gerar_codigo(self, is_orcamento=True):
        ano = timezone.now().year
        prefix = 'COT' if is_orcamento else 'OS'
        base = f'{prefix}-{ano}-'
        ultimo = (
            OrdemServico.objects.filter(codigo__startswith=base)
            .order_by('-codigo')
            .values_list('codigo', flat=True)
            .first()
        )
        seq = 1
        if ultimo:
            try:
                seq = int(str(ultimo).split('-')[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        return f'{base}{seq:06d}'

    def save(self, *args, **kwargs):
        is_orcamento = kwargs.pop('is_orcamento', None)
        if not self.codigo:
            if is_orcamento is None:
                is_orcamento = True
            self.codigo = self.gerar_codigo(is_orcamento=is_orcamento)
        super().save(*args, **kwargs)

    def recalcular_valor_total(self):
        """Soma serviços, itens por serviço e transportes, menos desconto global."""
        valor_servicos = sum(
            s.valor_total for s in self.servicos_orcamento.all()
        )
        valor_itens = sum(
            item.valor_total
            for s in self.servicos_orcamento.all()
            for item in s.itens.all()
        )
        valor_transporte = sum(
            t.valor_frete or Decimal('0')
            for t in self.transportes_orcamento.all()
        )
        subtotal = valor_servicos + valor_itens + valor_transporte
        desconto = self.desconto or Decimal('0')
        self.valor_total = max(subtotal - desconto, Decimal('0'))
        return self.valor_total


class ItemOrcamentoServico(models.Model):
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    desconto_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    item = models.ForeignKey('Item', on_delete=models.CASCADE)
    servico_orcamento = models.ForeignKey(
        'ServicoOrcamentoServico', on_delete=models.CASCADE,
        null=True, blank=True, related_name='itens',
    )
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE,
        null=True, blank=True, related_name='itens_orcamento_legado',
    )

    class Meta:
        verbose_name = 'Item de Orçamento'
        verbose_name_plural = 'Itens de Orçamento'
        ordering = ['-data_criacao']
        unique_together = [('servico_orcamento', 'item')]

    @property
    def valor_total(self):
        return _valor_linha(
            self.quantidade, self.valor_unitario, self.desconto, self.desconto_percentual,
        )

    @property
    def valor_total_bruto(self):
        return getattr(self, '_valor_total_bruto', self.valor_total)

    @valor_total_bruto.setter
    def valor_total_bruto(self, value):
        self._valor_total_bruto = value


class TransporteOrcamentoServico(models.Model):
    TIPO_TRANSPORTE_CHOICES = [
        ('INTERNO', 'Veículo Interno'),
        ('EXTERNO', 'Transportadora Externa'),
    ]
    tipo_transporte = models.CharField(
        max_length=30, choices=TIPO_TRANSPORTE_CHOICES, default='EXTERNO',
    )
    valor_frete = models.DecimalField(max_digits=10, decimal_places=2)
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='transportes_orcamento',
    )
    transportadora = models.ForeignKey('Transportadora', on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Transporte de Orçamento'
        verbose_name_plural = 'Transportes de Orçamento'
        ordering = ['-data_criacao']


class ServicoOrcamentoServico(models.Model):
    quantidade = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    desconto_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField(blank=True, null=True)
    nome_documento = models.CharField(max_length=200, blank=True, null=True)
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

    @property
    def valor_total(self):
        return _valor_linha(
            self.quantidade, self.valor_unitario, self.desconto, self.desconto_percentual,
        )

    @property
    def valor_total_bruto(self):
        return getattr(self, '_valor_total_bruto', self.valor_total)

    @valor_total_bruto.setter
    def valor_total_bruto(self, value):
        self._valor_total_bruto = value

    @property
    def valor_total_calculado(self):
        return getattr(self, '_valor_total_calculado', self.valor_total)

    @valor_total_calculado.setter
    def valor_total_calculado(self, value):
        self._valor_total_calculado = value


class RequisicaoProducao(models.Model):
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('PENDENTE', 'Pendente'),
        ('APROVADA', 'Aprovada'),
        ('REJEITADA', 'Rejeitada'),
        ('ATENDIDA', 'Atendida'),
        ('CANCELADA', 'Cancelada'),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RASCUNHO')
    observacoes = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_atendimento = models.DateTimeField(null=True, blank=True)
    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='requisicoes_producao_aprovadas',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='requisicoes_producao_criadas',
    )
    ordem_producao = models.ForeignKey(
        OrdemProducao, on_delete=models.CASCADE, related_name='requisicoes_material',
    )
    sucursal_origem = models.ForeignKey(
        'Sucursal', on_delete=models.PROTECT, related_name='requisicoes_producao_enviadas',
    )

    class Meta:
        verbose_name = 'Requisição de Produção'
        verbose_name_plural = 'Requisições de Produção'
        ordering = ['-data_criacao']


class ItemRequisicaoProducao(models.Model):
    quantidade_solicitada = models.PositiveIntegerField()
    quantidade_atendida = models.PositiveIntegerField(default=0)
    observacoes = models.TextField(blank=True)
    item = models.ForeignKey('Item', on_delete=models.CASCADE)
    requisicao = models.ForeignKey(
        RequisicaoProducao, on_delete=models.CASCADE, related_name='itens',
    )

    class Meta:
        verbose_name = 'Item de Requisição de Produção'
        verbose_name_plural = 'Itens de Requisição de Produção'
        unique_together = [('requisicao', 'item')]


class PropostaTecnica(models.Model):
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),
        ('EM_ANDAMENTO', 'Em andamento'),
        ('ATRASADA', 'Atrasada'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    ESTAGIO_CHOICES = [
        ('LEVANTAMENTO', '1. Levantamento'),
        ('ANALISE_TECNICA', '2. Análise técnica'),
        ('ELABORACAO_PROPOSTA', '3. Elaboração da proposta'),
        ('APRESENTACAO', '4. Apresentação'),
        ('AJUSTES_FINAIS', '5. Ajustes finais'),
        ('APROVACAO', '6. Aprovação'),
    ]

    codigo = models.CharField(max_length=20, unique=True)
    titulo = models.CharField(max_length=200)
    escopo = models.TextField(blank=True, null=True)
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_inicio_prevista = models.DateField(null=True, blank=True)
    data_fim_prevista = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')
    estagio_atual = models.CharField(max_length=30, choices=ESTAGIO_CHOICES, default='LEVANTAMENTO')
    duracao_prevista_horas = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
    )
    valor_levantamento_previsto = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    data_conclusao = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True)
    nome_cliente_personalizado = models.CharField(max_length=200, blank=True, null=True)
    nuit_cliente_personalizado = models.CharField(max_length=20, blank=True, null=True)
    telefone_cliente_personalizado = models.CharField(max_length=20, blank=True, null=True)
    cliente = models.ForeignKey(
        ClienteServico, on_delete=models.PROTECT,
        null=True, blank=True, related_name='propostas_tecnicas',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='propostas_tecnicas_criadas',
    )
    orcamento_servico = models.ForeignKey(
        OrdemServico, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='propostas_origem',
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='propostas_tecnicas_responsavel',
    )
    sucursal = models.ForeignKey(
        'Sucursal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='propostas_tecnicas',
    )

    class Meta:
        verbose_name = 'Proposta técnica'
        verbose_name_plural = 'Propostas técnicas'
        ordering = ['-data_solicitacao', 'codigo']


class ParcelaPagamentoOrcamento(models.Model):
    TIPO_ASSINATURA = 'ASSINATURA'
    TIPO_CONCLUSAO_SERVICOS = 'CONCLUSAO_SERVICOS'
    TIPO_CONCLUSAO_TOTAL = 'CONCLUSAO_TOTAL'
    TIPO_CHOICES = [
        (TIPO_ASSINATURA, 'À assinatura do contrato'),
        (TIPO_CONCLUSAO_SERVICOS, 'Na conclusão dos serviços seleccionados'),
        (TIPO_CONCLUSAO_TOTAL, 'Na conclusão total dos serviços'),
    ]

    numero_ordem = models.PositiveSmallIntegerField()
    percentagem = models.PositiveSmallIntegerField()
    tipo = models.CharField(max_length=24, choices=TIPO_CHOICES, default=TIPO_CONCLUSAO_TOTAL)
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='parcelas_pagamento',
    )
    servicos = models.ManyToManyField(
        ServicoOrcamentoServico, blank=True,
        related_name='parcelas_pagamento_que_exigem',
    )

    class Meta:
        verbose_name = 'Parcela de pagamento (contrato)'
        verbose_name_plural = 'Parcelas de pagamento (contrato)'
        ordering = ['ordem_servico', 'numero_ordem']
        unique_together = [('ordem_servico', 'numero_ordem')]


class AtividadeExecucao(models.Model):
    STATUS_CHOICES = [
        ('AGENDADA', 'Agendada'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('PAUSADA', 'Pausada'),
        ('CONCLUIDA', 'Concluída'),
    ]

    nome = models.CharField(max_length=200)
    numero_ordem = models.PositiveSmallIntegerField(default=1)
    data_prevista_inicio = models.DateField(null=True, blank=True)
    data_prevista_conclusao = models.DateField(null=True, blank=True)
    data_inicio = models.DateTimeField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AGENDADA')
    ordem_servico = models.ForeignKey(
        OrdemServico, on_delete=models.CASCADE, related_name='atividades_execucao',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='subactividades',
    )
    trabalho_empreitada = models.ForeignKey(
        'TrabalhoEmpreitada', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='atividades_plano',
    )
    parcela = models.ForeignKey(
        ParcelaPagamentoOrcamento, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='atividades_execucao',
    )
    servicos_entregues = models.ManyToManyField(
        ServicoOrcamentoServico, blank=True, related_name='atividades_que_entregam',
    )

    class Meta:
        verbose_name = 'Actividade do plano de execução'
        verbose_name_plural = 'Actividades do plano de execução'
        # Evita recursão de ordering ao resolver FK para self ("parent")
        ordering = ['ordem_servico_id', 'parent_id', 'numero_ordem']


class TaxaServicoCategoria(models.Model):
    CATEGORIA_CHOICES = [
        ('OP', 'Operacional'),
        ('ADM', 'Administrativo'),
        ('TEC', 'Técnico'),
        ('GES', 'Gestão'),
        ('EXE', 'Executivo'),
    ]

    categoria = models.CharField(max_length=3, unique=True, choices=CATEGORIA_CHOICES)
    taxa_horaria = models.DecimalField(max_digits=10, decimal_places=2, default=500)
    descricao = models.CharField(max_length=100, blank=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Taxa de Serviço por Categoria'
        verbose_name_plural = 'Taxas de Serviço por Categoria'
        ordering = ['categoria']


class FormaPagamento(models.Model):
    nome = models.CharField(max_length=200, unique=True)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Forma de Pagamento'
        verbose_name_plural = 'Formas de Pagamento'
        ordering = ['-padrao', '-ativo', 'nome']


class PeriodoPagamento(models.Model):
    EVENTO_CHOICES = [
        ('ASSINATURA', 'Assinatura do Contrato'),
        ('INICIO', 'Início dos Serviços'),
        ('CONCLUSAO', 'Conclusão dos Serviços'),
        ('ENTREGA', 'Entrega do Serviço'),
    ]

    nome = models.CharField(max_length=100)
    percentual = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    dias_apos_evento = models.IntegerField(default=0)
    evento_referencia = models.CharField(max_length=50, choices=EVENTO_CHOICES, default='ASSINATURA')
    ordem = models.IntegerField(default=1)
    observacoes = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    forma_pagamento = models.ForeignKey(
        FormaPagamento, on_delete=models.CASCADE, related_name='periodos',
    )

    class Meta:
        verbose_name = 'Período de Pagamento'
        verbose_name_plural = 'Períodos de Pagamento'
        ordering = ['forma_pagamento', 'ordem']
        unique_together = [('forma_pagamento', 'ordem')]


class ConfiguracaoContratoServico(models.Model):
    nome = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    clausula4_obrigacoes = models.TextField(blank=True, null=True)
    clausula5_garantia = models.TextField(blank=True, null=True)
    clausula6_alteracoes = models.TextField(blank=True, null=True)
    clausula7_rescisao = models.TextField(blank=True, null=True)
    clausula8_confidencialidade = models.TextField(blank=True, null=True)
    clausula9_foro = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Contrato de Serviço'
        verbose_name_plural = 'Configurações de Contrato de Serviço'
        ordering = ['-padrao', '-ativo', 'nome']


class ConfiguracaoContratoEmpreitada(models.Model):
    nome = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    clausula4_obrigacoes = models.TextField(blank=True, null=True)
    clausula5_garantia = models.TextField(blank=True, null=True)
    clausula6_alteracoes = models.TextField(blank=True, null=True)
    clausula7_rescisao = models.TextField(blank=True, null=True)
    clausula8_confidencialidade = models.TextField(blank=True, null=True)
    clausula9_foro = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração de Contrato de Empreitada'
        verbose_name_plural = 'Configurações de Contrato de Empreitada'
        ordering = ['-padrao', '-ativo', 'nome']


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


class ParcelaPagamentoEmpreitada(models.Model):
    TIPO_ASSINATURA = 'ASSINATURA'
    TIPO_CONCLUSAO_TRABALHOS = 'CONCLUSAO_TRABALHOS'
    TIPO_CONCLUSAO_TOTAL = 'CONCLUSAO_TOTAL'
    TIPO_CHOICES = [
        (TIPO_ASSINATURA, 'À assinatura do contrato'),
        (TIPO_CONCLUSAO_TRABALHOS, 'Na conclusão dos trabalhos seleccionados'),
        (TIPO_CONCLUSAO_TOTAL, 'Na conclusão total dos trabalhos'),
    ]

    numero_ordem = models.PositiveSmallIntegerField()
    percentagem = models.PositiveSmallIntegerField()
    tipo = models.CharField(max_length=24, choices=TIPO_CHOICES, default=TIPO_CONCLUSAO_TOTAL)
    data_pago = models.DateTimeField(null=True, blank=True)
    contrato_empreitada = models.ForeignKey(
        ContratoEmpreitada, on_delete=models.CASCADE, related_name='parcelas_pagamento',
    )
    trabalhos = models.ManyToManyField(
        TrabalhoEmpreitada, blank=True, related_name='parcelas_pagamento_que_exigem',
    )

    class Meta:
        verbose_name = 'Parcela de pagamento (empreitada)'
        verbose_name_plural = 'Parcelas de pagamento (empreitada)'
        ordering = ['contrato_empreitada', 'numero_ordem']
        unique_together = [('contrato_empreitada', 'numero_ordem')]

    def valor_parcela(self):
        total = self.contrato_empreitada.valor_total
        if not total:
            return Decimal('0')
        return (total * Decimal(self.percentagem) / Decimal('100')).quantize(Decimal('0.01'))


class EquipeServico(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    lider = models.ForeignKey(
        'Funcionario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='equipes_lideradas',
    )
    membros = models.ManyToManyField('Funcionario', blank=True, related_name='equipes')

    class Meta:
        verbose_name = 'Equipe de Serviço'
        verbose_name_plural = 'Equipes de Serviço'
        ordering = ['nome']
