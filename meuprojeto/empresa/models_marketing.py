"""
Modelos para o módulo de Gestão de Marketing.
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal


class EstadoCampanha(models.TextChoices):
    RASCUNHO = 'RASCUNHO', 'Rascunho'
    PLANEADA = 'PLANEADA', 'Planeada'
    EM_CURSO = 'EM_CURSO', 'Em curso'
    CONCLUIDA = 'CONCLUIDA', 'Concluída'
    CANCELADA = 'CANCELADA', 'Cancelada'


class CampanhaMarketing(models.Model):
    """Campanhas de marketing"""
    nome = models.CharField(max_length=200, help_text='Nome da campanha')
    descricao = models.TextField(blank=True, help_text='Descrição e objetivos')
    estado = models.CharField(
        max_length=20,
        choices=EstadoCampanha.choices,
        default=EstadoCampanha.RASCUNHO,
        db_index=True
    )
    data_inicio = models.DateField(null=True, blank=True, help_text='Data de início prevista')
    data_fim = models.DateField(null=True, blank=True, help_text='Data de fim prevista')
    orcamento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text='Orçamento previsto (MT)'
    )
    canal = models.CharField(
        max_length=50,
        blank=True,
        help_text='Canal principal (ex: Redes sociais, Email, Imprensa)'
    )
    responsavel = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campanhas_marketing'
    )
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True, db_index=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Campanha de Marketing'
        verbose_name_plural = 'Campanhas de Marketing'
        ordering = ['-data_criacao']

    def __str__(self):
        return self.nome

    @property
    def esta_ativa(self):
        if self.estado != EstadoCampanha.EM_CURSO:
            return False
        hoje = timezone.now().date()
        if self.data_inicio and hoje < self.data_inicio:
            return False
        if self.data_fim and hoje > self.data_fim:
            return False
        return True


class EstadoPublicacao(models.TextChoices):
    RASCUNHO = 'RASCUNHO', 'Rascunho'
    AGENDADA = 'AGENDADA', 'Agendada'
    PUBLICADA = 'PUBLICADA', 'Publicada'
    CANCELADA = 'CANCELADA', 'Cancelada'


class PublicacaoRedesSociais(models.Model):
    """Publicações em redes sociais"""
    campanha = models.ForeignKey(
        CampanhaMarketing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publicacoes'
    )
    canal = models.CharField(max_length=80, help_text='Ex: Facebook, Instagram, LinkedIn')
    texto = models.TextField(help_text='Texto da publicação')
    imagem_url = models.URLField(blank=True, help_text='URL da imagem (opcional)')
    data_agendada = models.DateTimeField(null=True, blank=True, help_text='Data/hora de agendamento')
    data_publicada = models.DateTimeField(null=True, blank=True, help_text='Data/hora em que foi publicada')
    estado = models.CharField(
        max_length=20,
        choices=EstadoPublicacao.choices,
        default=EstadoPublicacao.RASCUNHO,
        db_index=True
    )
    link_post = models.URLField(blank=True, help_text='Link do post após publicação')
    responsavel = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='publicacoes_redes_sociais'
    )
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True, db_index=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Publicação em Rede Social'
        verbose_name_plural = 'Publicações em Redes Sociais'
        ordering = ['-data_agendada', '-data_criacao']

    def __str__(self):
        return f'{self.canal} - {self.texto[:50]}...'


class InvestimentoPublicidade(models.Model):
    """Investimento em publicidade e anúncios"""
    campanha = models.ForeignKey(
        CampanhaMarketing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investimentos'
    )
    canal = models.CharField(max_length=100, help_text='Ex: Facebook Ads, Google, Imprensa')
    descricao = models.CharField(max_length=200, blank=True, help_text='Descrição do investimento')
    valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Valor investido (MT)'
    )
    data_investimento = models.DateField(help_text='Data do investimento')
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True, db_index=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Investimento em Publicidade'
        verbose_name_plural = 'Investimentos em Publicidade'
        ordering = ['-data_investimento', '-data_criacao']

    def __str__(self):
        return f'{self.canal} - {self.valor} MT'
