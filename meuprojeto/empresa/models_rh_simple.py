from django.db import models
from django.core.validators import RegexValidator
from .models_base import Sucursal

def validar_nuit(value):
    if not value.isdigit() or len(value) != 9:
        raise ValidationError('NUIT deve conter exatamente 9 dígitos.')
    return value

def validar_bi(value):
    if not value.isdigit() or len(value) != 13:
        raise ValidationError('BI deve conter exatamente 13 dígitos.')
    return value

def validar_telefone_moz(value):
    if not value.startswith('+258') or len(value) != 13:
        raise ValidationError('Telefone deve começar com +258 e ter 13 caracteres.')
    return value

class Departamento(models.Model):
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=10, unique=True)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='departamentos')
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    class Meta:
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        ordering = ['nome']

class Cargo(models.Model):
    nome = models.CharField(max_length=100)
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='cargos')
    salario_base = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.departamento.nome}"

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ['nome']

class Funcionario(models.Model):
    # Choices simplificados
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
    ]

    STATUS_CHOICES = [
        ('AT', 'Ativo'),
        ('IN', 'Inativo'),
    ]

    ESTADO_CIVIL_CHOICES = [
        ('S', 'Solteiro(a)'),
        ('C', 'Casado(a)'),
        ('D', 'Divorciado(a)'),
        ('V', 'Viúvo(a)'),
    ]

    TIPO_CONTRATO_CHOICES = [
        ('IND', 'Indeterminado'),
        ('DET', 'Determinado'),
        ('EST', 'Estágio'),
        ('TMP', 'Temporário'),
    ]

    ESCOLARIDADE_CHOICES = [
        ('FUN', 'Fundamental'),
        ('MED', 'Médio'),
        ('SUP', 'Superior'),
        ('POS', 'Pós-graduação'),
    ]

    # Informações Básicas
    nome_completo = models.CharField(max_length=200, help_text='Nome completo')
    data_nascimento = models.DateField(help_text='Data de nascimento')
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, help_text='Gênero')
    estado_civil = models.CharField(max_length=1, choices=ESTADO_CIVIL_CHOICES, help_text='Estado civil')
    nuit = models.CharField(max_length=9, unique=True, validators=[validar_nuit], help_text='NUIT (9 dígitos)')
    bi = models.CharField(max_length=13, unique=True, validators=[validar_bi], help_text='BI (13 dígitos)')

    # Contato
    email = models.EmailField(help_text='Email')
    telefone = models.CharField(max_length=13, validators=[validar_telefone_moz], help_text='Telefone (+258)')
    endereco = models.TextField(help_text='Endereço')

    # Informações Profissionais
    sucursal = models.ForeignKey(Sucursal, on_delete=models.CASCADE, related_name='funcionarios')
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE, related_name='funcionarios')
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE, related_name='funcionarios')
    data_admissao = models.DateField(help_text='Data de admissão')
    data_demissao = models.DateField(null=True, blank=True, help_text='Data de demissão')
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='AT')

    # Contrato e Remuneração
    tipo_contrato = models.CharField(max_length=3, choices=TIPO_CONTRATO_CHOICES, default='IND')
    salario_atual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Salário em MT')
    carga_horaria = models.IntegerField(default=40, help_text='Horas por semana')

    # Formação
    escolaridade = models.CharField(max_length=3, choices=ESCOLARIDADE_CHOICES, default='FUN')
    curso = models.CharField(max_length=100, blank=True, help_text='Curso/Formação')
    
    # Dados Bancários (opcionais)
    banco = models.CharField(max_length=100, blank=True, help_text='Banco')
    agencia = models.CharField(max_length=10, blank=True, help_text='Agência')
    conta = models.CharField(max_length=20, blank=True, help_text='Conta')
    
    # Metadados
    observacoes = models.TextField(blank=True, help_text='Observações')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.codigo_funcionario:
            # Gerar código automático: FUNC-YYYY-XXX
            from datetime import date
            ano = date.today().year
            ultimo_funcionario = Funcionario.objects.filter(
                codigo_funcionario__startswith=f'FUNC-{ano}'
            ).order_by('-codigo_funcionario').first()
            
            if ultimo_funcionario and ultimo_funcionario.codigo_funcionario:
                try:
                    ultimo_num = int(ultimo_funcionario.codigo_funcionario.split('-')[-1])
                    novo_num = ultimo_num + 1
                except (ValueError, IndexError):
                    novo_num = 1
            else:
                novo_num = 1
            
            self.codigo_funcionario = f"FUNC-{ano}-{novo_num:03d}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo_funcionario} - {self.nome_completo}"

    class Meta:
        verbose_name = 'Funcionário'
        verbose_name_plural = 'Funcionários'
        ordering = ['nome_completo']


