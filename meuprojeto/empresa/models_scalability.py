"""
Modelos para escalabilidade e processamento assíncrono.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import json
import hashlib


class FilaProcessamento(models.Model):
    """Filas para processamento assíncrono de tarefas logísticas."""
    
    TIPO_FILA_CHOICES = [
        ('COTACAO', 'Cotação'),
        ('RASTREAMENTO', 'Rastreamento'),
        ('NOTIFICACAO', 'Notificação'),
        ('RELATORIO', 'Relatório'),
        ('INTEGRACAO', 'Integração'),
        ('CUSTO', 'Custo'),
        ('FATURAMENTO', 'Faturamento'),
        ('METRICA', 'Métrica'),
    ]
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PROCESSANDO', 'Processando'),
        ('CONCLUIDO', 'Concluído'),
        ('ERRO', 'Erro'),
        ('CANCELADO', 'Cancelado'),
        ('REAGENDADO', 'Reagendado'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('NORMAL', 'Normal'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    codigo = models.CharField(max_length=50, unique=True)
    
    # Configuração da tarefa
    tipo_fila = models.CharField(max_length=20, choices=TIPO_FILA_CHOICES)
    nome_tarefa = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Parâmetros
    parametros = models.JSONField(default=dict)
    contexto = models.JSONField(default=dict)
    
    # Prioridade e agendamento
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='NORMAL')
    data_agendamento = models.DateTimeField(default=timezone.now)
    data_execucao_maxima = models.DateTimeField(null=True, blank=True)
    
    # Status e controle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    tentativas = models.PositiveIntegerField(default=0)
    tentativas_maximas = models.PositiveIntegerField(default=3)
    
    # Resultado
    resultado = models.JSONField(null=True, blank=True)
    erro_mensagem = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    # Timestamps
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_inicio_processamento = models.DateTimeField(null=True, blank=True)
    data_fim_processamento = models.DateTimeField(null=True, blank=True)
    
    # Dependências
    dependencias = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependentes'
    )
    
    # Usuário responsável
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas_criadas'
    )
    
    class Meta:
        verbose_name = "Fila de Processamento"
        verbose_name_plural = "Filas de Processamento"
        ordering = ['-prioridade', 'data_agendamento']
        indexes = [
            models.Index(fields=['tipo_fila', 'status']),
            models.Index(fields=['status', 'data_agendamento']),
            models.Index(fields=['prioridade', 'data_agendamento']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nome_tarefa}"
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._gerar_codigo_tarefa()
        super().save(*args, **kwargs)
    
    def _gerar_codigo_tarefa(self):
        """Gera código único para tarefa."""
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        count = FilaProcessamento.objects.filter(
            codigo__startswith=f"{self.tipo_fila}-{timestamp}"
        ).count()
        return f"{self.tipo_fila}-{timestamp}-{count + 1:03d}"


class ControleIdempotencia(models.Model):
    """Controle de idempotência para operações críticas."""
    
    # Chave única da operação
    chave_idempotencia = models.CharField(max_length=255, unique=True)
    
    # Tipo de operação
    tipo_operacao = models.CharField(max_length=50)
    modelo_afetado = models.CharField(max_length=50)
    objeto_id = models.PositiveIntegerField()
    
    # Estado da operação
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDENTE', 'Pendente'),
            ('PROCESSANDO', 'Processando'),
            ('CONCLUIDO', 'Concluído'),
            ('ERRO', 'Erro'),
        ],
        default='PENDENTE'
    )
    
    # Resultado
    resultado = models.JSONField(null=True, blank=True)
    erro_mensagem = models.TextField(blank=True)
    
    # Timestamps
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    data_expiracao = models.DateTimeField(null=True, blank=True)
    
    # Usuário responsável
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Controle de Idempotência"
        verbose_name_plural = "Controles de Idempotência"
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['tipo_operacao', 'modelo_afetado']),
            models.Index(fields=['status', 'data_criacao']),
            models.Index(fields=['chave_idempotencia']),
        ]
    
    def __str__(self):
        return f"{self.chave_idempotencia} - {self.tipo_operacao}"


class ValidacaoLogistica(models.Model):
    """Validações fortes para operações logísticas."""
    
    TIPO_VALIDACAO_CHOICES = [
        ('REGRA_NEGOCIO', 'Regra de Negócio'),
        ('INTEGRIDADE', 'Integridade'),
        ('PERFORMANCE', 'Performance'),
        ('SEGURANCA', 'Segurança'),
        ('COMPLIANCE', 'Compliance'),
    ]
    
    NIVEL_VALIDACAO_CHOICES = [
        ('INFO', 'Informativo'),
        ('WARNING', 'Aviso'),
        ('ERROR', 'Erro'),
        ('CRITICAL', 'Crítico'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configuração
    tipo_validacao = models.CharField(max_length=20, choices=TIPO_VALIDACAO_CHOICES)
    nivel_validacao = models.CharField(max_length=10, choices=NIVEL_VALIDACAO_CHOICES)
    
    # Regras
    modelo_afetado = models.CharField(max_length=50)
    campo_afetado = models.CharField(max_length=50, blank=True)
    regra_validacao = models.TextField(help_text="Código Python da regra de validação")
    
    # Configurações
    ativo = models.BooleanField(default=True)
    obrigatorio = models.BooleanField(default=False)
    mensagem_erro = models.TextField(blank=True)
    
    # Auditoria
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validacoes_criadas'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Validação Logística"
        verbose_name_plural = "Validações Logísticas"
        ordering = ['modelo_afetado', 'nivel_validacao', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ResultadoValidacao(models.Model):
    """Resultados de validações executadas."""
    
    # Relacionamentos
    validacao = models.ForeignKey(ValidacaoLogistica, on_delete=models.CASCADE, related_name='resultados')
    
    # Contexto da validação
    modelo_afetado = models.CharField(max_length=50)
    objeto_id = models.PositiveIntegerField()
    operacao = models.CharField(max_length=50)
    
    # Resultado
    sucesso = models.BooleanField()
    mensagem = models.TextField(blank=True)
    dados_validados = models.JSONField(default=dict)
    
    # Performance
    tempo_execucao_ms = models.PositiveIntegerField()
    
    # Timestamp
    data_execucao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Resultado de Validação"
        verbose_name_plural = "Resultados de Validação"
        ordering = ['-data_execucao']
        indexes = [
            models.Index(fields=['modelo_afetado', 'objeto_id']),
            models.Index(fields=['validacao', 'data_execucao']),
            models.Index(fields=['sucesso', 'data_execucao']),
        ]
    
    def __str__(self):
        return f"{self.validacao.nome} - {self.modelo_afetado} - {self.data_execucao}"


class TesteContrato(models.Model):
    """Testes de contrato para APIs e integrações."""
    
    TIPO_CONTRATO_CHOICES = [
        ('API_REST', 'API REST'),
        ('WEBHOOK', 'Webhook'),
        ('INTEGRACAO', 'Integração'),
        ('SERVICO', 'Serviço'),
    ]
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('EXECUTANDO', 'Executando'),
        ('PASSOU', 'Passou'),
        ('FALHOU', 'Falhou'),
        ('ERRO', 'Erro'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    
    # Configuração
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES)
    endpoint = models.CharField(max_length=200)
    metodo_http = models.CharField(max_length=10, default='GET')
    
    # Parâmetros do teste
    headers = models.JSONField(default=dict)
    parametros = models.JSONField(default=dict)
    body_request = models.TextField(blank=True)
    
    # Validações esperadas
    status_code_esperado = models.PositiveIntegerField(default=200)
    headers_esperados = models.JSONField(default=dict)
    schema_resposta = models.JSONField(default=dict)
    
    # Configurações
    ativo = models.BooleanField(default=True)
    timeout_segundos = models.PositiveIntegerField(default=30)
    retry_tentativas = models.PositiveIntegerField(default=3)
    
    # Auditoria
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='testes_contrato_criados'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Teste de Contrato"
        verbose_name_plural = "Testes de Contrato"
        ordering = ['tipo_contrato', 'nome']
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class ExecucaoTesteContrato(models.Model):
    """Execuções de testes de contrato."""
    
    # Relacionamentos
    teste_contrato = models.ForeignKey(TesteContrato, on_delete=models.CASCADE, related_name='execucoes')
    
    # Resultado da execução
    status = models.CharField(max_length=20, choices=TesteContrato.STATUS_CHOICES, default='PENDENTE')
    status_code_obtido = models.PositiveIntegerField(null=True, blank=True)
    headers_obtidos = models.JSONField(default=dict)
    body_response = models.TextField(blank=True)
    
    # Validações
    validacoes_passaram = models.JSONField(default=list)
    validacoes_falharam = models.JSONField(default=list)
    
    # Performance
    tempo_resposta_ms = models.PositiveIntegerField(null=True, blank=True)
    tentativas_realizadas = models.PositiveIntegerField(default=1)
    
    # Erro
    erro_mensagem = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    
    # Timestamps
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Execução de Teste de Contrato"
        verbose_name_plural = "Execuções de Teste de Contrato"
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['teste_contrato', 'data_inicio']),
            models.Index(fields=['status', 'data_inicio']),
        ]
    
    def __str__(self):
        return f"{self.teste_contrato.nome} - {self.data_inicio}"


class ConfiguracaoEscalabilidade(models.Model):
    """Configurações para escalabilidade e processamento assíncrono."""
    
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    
    # Configurações de filas
    processamento_assincrono = models.BooleanField(default=True)
    tamanho_maximo_fila = models.PositiveIntegerField(default=10000)
    timeout_processamento_segundos = models.PositiveIntegerField(default=300)
    retry_tentativas_maximas = models.PositiveIntegerField(default=3)
    
    # Configurações de idempotência
    idempotencia_habilitada = models.BooleanField(default=True)
    tempo_expiracao_idempotencia_minutos = models.PositiveIntegerField(default=60)
    
    # Configurações de validação
    validacoes_obrigatorias = models.BooleanField(default=True)
    validacoes_em_lote = models.BooleanField(default=True)
    timeout_validacao_segundos = models.PositiveIntegerField(default=30)
    
    # Configurações de testes
    testes_automaticos = models.BooleanField(default=True)
    intervalo_teste_minutos = models.PositiveIntegerField(default=60)
    alertas_falha_teste = models.BooleanField(default=True)
    
    # Configurações de performance
    cache_habilitado = models.BooleanField(default=True)
    tempo_cache_segundos = models.PositiveIntegerField(default=300)
    compressao_resposta = models.BooleanField(default=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)
    
    # Auditoria
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração Escalabilidade"
        verbose_name_plural = "Configurações Escalabilidade"
        ordering = ['-padrao', 'nome']
    
    def __str__(self):
        return f"{self.nome} {'(Padrão)' if self.padrao else ''}"
    
    def save(self, *args, **kwargs):
        # Garantir que apenas uma configuração seja padrão
        if self.padrao:
            ConfiguracaoEscalabilidade.objects.filter(padrao=True).update(padrao=False)
        super().save(*args, **kwargs)


class MonitoramentoPerformance(models.Model):
    """Monitoramento de performance do sistema."""
    
    # Identificação
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Contexto
    operacao = models.CharField(max_length=100)
    endpoint = models.CharField(max_length=200, blank=True)
    metodo_http = models.CharField(max_length=10, blank=True)
    
    # Métricas de performance
    tempo_execucao_ms = models.PositiveIntegerField()
    memoria_usada_mb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cpu_usage_percentual = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Métricas de banco
    queries_executadas = models.PositiveIntegerField(default=0)
    tempo_queries_ms = models.PositiveIntegerField(default=0)
    
    # Status
    sucesso = models.BooleanField(default=True)
    erro_mensagem = models.TextField(blank=True)
    
    # Usuário e contexto
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Timestamp
    data_execucao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Monitoramento de Performance"
        verbose_name_plural = "Monitoramento de Performance"
        ordering = ['-data_execucao']
        indexes = [
            models.Index(fields=['operacao', 'data_execucao']),
            models.Index(fields=['endpoint', 'data_execucao']),
            models.Index(fields=['sucesso', 'data_execucao']),
        ]
    
    def __str__(self):
        return f"{self.operacao} - {self.tempo_execucao_ms}ms - {self.data_execucao}"
