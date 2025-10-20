from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models_base import DadosEmpresa, Sucursal, validar_nuit, validar_telefone_moz
from .models_rh import Departamento, Cargo, Funcionario

class TipoSocietario(models.TextChoices):
    SA = 'SA', 'Sociedade Anónima'
    LDA = 'LDA', 'Sociedade por Quotas'
    SU = 'SU', 'Sociedade Unipessoal'
    ENI = 'ENI', 'Empresário em Nome Individual'
    SC = 'SC', 'Sociedade em Comandita'
    SNC = 'SNC', 'Sociedade em Nome Colectivo'
    COOP = 'COOP', 'Cooperativa'

class TipoSucursal(models.TextChoices):
    LOJA = 'LOJA', 'Loja'
    ARMAZEM = 'ARMZ', 'Armazém'
    FABRICA = 'FAB', 'Fábrica'
    ESCRITORIO = 'ESC', 'Escritório'
    LOJA_ARMZ = 'LJ_ARMZ', 'Loja e Armazém'
    LOJA_FAB = 'LJ_FAB', 'Loja e Fábrica'
    FAB_ARMZ = 'FAB_ARMZ', 'Fábrica e Armazém'
    MISTA = 'MISTA', 'Mista (Loja, Fábrica e Armazém)'

class Provincia(models.TextChoices):
    MAPUTO_CIDADE = 'MP', 'Maputo Cidade'
    MAPUTO = 'MA', 'Maputo Província'
    GAZA = 'GA', 'Gaza'
    INHAMBANE = 'IN', 'Inhambane'
    MANICA = 'MN', 'Manica'
    SOFALA = 'SO', 'Sofala'
    ZAMBEZIA = 'ZA', 'Zambézia'
    TETE = 'TE', 'Tete'
    NAMPULA = 'NA', 'Nampula'
    NIASSA = 'NI', 'Niassa'
    CABO_DELGADO = 'CD', 'Cabo Delgado'

class Funcionalidade(models.Model):
    nome = models.CharField(
        max_length=100,
        unique=True,
        help_text='Nome da funcionalidade do sistema'
    )
    codigo = models.CharField(
        max_length=50,
        unique=True,
        help_text='Código único da funcionalidade'
    )
    descricao = models.TextField(
        help_text='Descrição detalhada da funcionalidade'
    )
    modulo = models.CharField(
        max_length=50,
        help_text='Módulo do sistema a que pertence'
    )
    ativa = models.BooleanField(
        default=True,
        help_text='Indica se a funcionalidade está ativa no sistema'
    )

    class Meta:
        verbose_name = 'Funcionalidade'
        verbose_name_plural = 'Funcionalidades'
        ordering = ['modulo', 'nome']

    def __str__(self):
        return f"{self.modulo} - {self.nome}"

class PermissaoSucursal(models.Model):
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='permissoes',
        help_text='Sucursal a que se aplica esta permissão'
    )
    funcionalidade = models.ForeignKey(
        Funcionalidade,
        on_delete=models.CASCADE,
        help_text='Funcionalidade permitida'
    )
    nivel_acesso = models.IntegerField(
        choices=[
            (1, 'Visualização'),
            (2, 'Edição'),
            (3, 'Administração')
        ],
        default=1,
        help_text='Nível de acesso à funcionalidade'
    )
    data_concessao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data em que a permissão foi concedida'
    )
    concedido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        help_text='Usuário que concedeu a permissão'
    )
    observacoes = models.TextField(
        blank=True,
        null=True,
        help_text='Observações sobre a permissão'
    )

    class Meta:
        verbose_name = 'Permissão da Sucursal'
        verbose_name_plural = 'Permissões das Sucursais'
        unique_together = [['sucursal', 'funcionalidade']]
        ordering = ['sucursal', 'funcionalidade']

    def __str__(self):
        return f"{self.sucursal} - {self.funcionalidade} (Nível {self.nivel_acesso})"