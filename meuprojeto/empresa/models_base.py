from django.db import models, transaction
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .config_mocambique import TIPOS_SOCIETARIOS_MOZ, ACTIVIDADES_ECONOMICAS

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

def validar_nuit(value):
    """
    Valida NUIT (Número Único de Identificação Tributária) moçambicano
    Formato: 9 dígitos numéricos
    """
    if not value.isdigit() or len(value) != 9:
        raise ValidationError('NUIT deve conter exatamente 9 dígitos numéricos.')
    
    # Validação adicional: NUIT não pode ser todos zeros
    if value == '000000000':
        raise ValidationError('NUIT inválido.')
    
    return value

def validar_telefone_moz(value):
    """
    Valida número de telefone moçambicano
    Formato: +258XXXXXXXXX ou XXXXXXXXX (9 dígitos)
    """
    # Remove espaços e caracteres especiais
    clean_value = value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    # Se começar com +258, remove o código do país
    if clean_value.startswith('+258'):
        clean_value = clean_value[4:]
    
    # Se começar com 258, remove o código do país
    if clean_value.startswith('258'):
        clean_value = clean_value[3:]
    
    # Valida se tem exatamente 9 dígitos
    if not clean_value.isdigit() or len(clean_value) != 9:
        raise ValidationError('Número de telefone deve conter exatamente 9 dígitos (formato: +258XXXXXXXXX ou XXXXXXXXX).')
    
    # Valida se começa com 8 (celular) ou 2 (fixo)
    if not clean_value.startswith(('8', '2')):
        raise ValidationError('Número de telefone deve começar com 8 (celular) ou 2 (fixo).')
    
    return value

class DadosEmpresa(models.Model):
    nome = models.CharField(max_length=200)
    codigo_empresa = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text='Código único da empresa (gerado automaticamente)'
    )
    nuit = models.CharField(max_length=9, unique=True, validators=[validar_nuit])
    alvara = models.CharField(max_length=50, unique=True)
    data_constituicao = models.DateField()
    provincia = models.CharField(max_length=50)
    cidade = models.CharField(max_length=100)
    bairro = models.CharField(max_length=100)
    endereco = models.TextField()
    telefone = models.CharField(max_length=13, validators=[validar_telefone_moz])
    email = models.EmailField()
    website = models.URLField(blank=True, null=True)
    is_sede = models.BooleanField('É Sede', default=False)
    tipo_societario = models.CharField(
        max_length=20,
        choices=TIPOS_SOCIETARIOS_MOZ,
        default='LDA',
        help_text='Tipo societário conforme legislação moçambicana'
    )
    
    # Campos específicos para Moçambique
    numero_registro_comercial = models.CharField(
        'Número de Registo Comercial',
        max_length=50,
        blank=True,
        help_text='Número de Registo Comercial no Registo Nacional de Pessoas Colectivas'
    )
    data_registro_comercial = models.DateField(
        'Data de Registo Comercial',
        blank=True,
        null=True,
        help_text='Data de registo no Registo Nacional de Pessoas Colectivas'
    )
    actividade_principal = models.CharField(
        'Actividade Principal',
        max_length=20,
        choices=ACTIVIDADES_ECONOMICAS,
        blank=True,
        help_text='Actividade económica principal conforme classificação moçambicana'
    )
    capital_social = models.DecimalField(
        'Capital Social',
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text='Capital social em Meticais (MZN)'
    )
    
    # Campos de horário de expediente
    hora_inicio_expediente = models.TimeField(
        'Hora de Início do Expediente',
        default='08:00',
        help_text='Hora de início do expediente (formato HH:MM)'
    )
    hora_fim_expediente = models.TimeField(
        'Hora de Fim do Expediente',
        default='17:00',
        help_text='Hora de fim do expediente (formato HH:MM)'
    )
    duracao_almoco = models.DurationField(
        'Duração do Almoço',
        default='01:00:00',
        help_text='Duração da pausa para almoço (formato HH:MM:SS)'
    )
    dias_trabalho_semana = models.PositiveSmallIntegerField(
        'Dias de Trabalho por Semana',
        default=5,
        help_text='Número de dias de trabalho por semana'
    )
    horas_trabalho_dia = models.DurationField(
        'Horas de Trabalho por Dia',
        default='08:00:00',
        help_text='Número de horas de trabalho por dia (formato HH:MM:SS)'
    )

    def __str__(self):
        # Obter o sufixo do tipo societário
        tipo_societario_dict = dict(TIPOS_SOCIETARIOS_MOZ)
        sufixo = tipo_societario_dict.get(self.tipo_societario, self.tipo_societario)
        return f"{self.nome} {sufixo}"
    
    @property
    def tipo_sigla(self):
        """Retorna apenas a sigla do tipo societário"""
        return self.tipo_societario

    def gerar_codigo_empresa_sequencial(self):
        """
        Gera código da empresa no formato: NUMERO_SEQUENCIAL + NOME_EMPRESA
        Exemplo: 001Conception, 002Tecnologia, 003Comercial
        """
        # Buscar próxima sequência
        ultima_empresa = DadosEmpresa.objects.filter(
            codigo_empresa__regex=r'^\d{3}'
        ).order_by('-codigo_empresa').first()
        
        if ultima_empresa and ultima_empresa.codigo_empresa:
            try:
                # Extrair sequência (ex: 001Conception -> 1)
                sequencia = int(ultima_empresa.codigo_empresa[:3]) + 1
            except (ValueError, IndexError):
                sequencia = 1
        else:
            sequencia = 1
        
        # Limpar nome da empresa (remover espaços e caracteres especiais)
        nome_limpo = ''.join(c for c in self.nome if c.isalnum())
        
        return f"{sequencia:03d}{nome_limpo}"

    def save(self, *args, **kwargs):
        # Se for a primeira empresa, define como sede
        if not self.pk and not DadosEmpresa.objects.exists():
            self.is_sede = True
            
        # Se já existe um registro, mantém o código original
        if self.pk:
            # Usando select_for_update para evitar condições de corrida
            old_instance = DadosEmpresa.objects.select_for_update().get(pk=self.pk)
            # Força a manutenção do código original, independentemente do que vier no request
            self.codigo_empresa = old_instance.codigo_empresa
            
            # Se alguém tentou alterar o código, registra a tentativa
            if hasattr(self, '_codigo_empresa_original') and \
               self._codigo_empresa_original != old_instance.codigo_empresa:
                from django.contrib import messages
                from django.utils.safestring import mark_safe
                from django.contrib.admin.models import LogEntry, CHANGE
                from django.contrib.contenttypes.models import ContentType
                from django.contrib.admin.utils import construct_change_message
                
                # Registra a tentativa de alteração no log do admin
                LogEntry.objects.log_action(
                    user_id=1,  # ID do usuário admin
                    content_type_id=ContentType.objects.get_for_model(self).pk,
                    object_id=self.pk,
                    object_repr=str(self),
                    action_flag=CHANGE,
                    change_message=construct_change_message([], {'codigo_empresa': (old_instance.codigo_empresa, self._codigo_empresa_original)}),
                )
        # Se é um novo registro e não tem código, gera um
        elif not self.codigo_empresa:
            # Usando select_for_update para evitar duplicação de códigos
            with transaction.atomic():
                ultima_empresa = DadosEmpresa.objects.select_for_update().order_by('-id').first()
                if ultima_empresa and ultima_empresa.codigo_empresa:
                    try:
                        # Extrai o número do código e incrementa
                        ultimo_num = int(ultima_empresa.codigo_empresa[3:])  # Remove o prefixo e converte para inteiro
                        novo_num = ultimo_num + 1
                    except (ValueError, IndexError):
                        novo_num = 1
                else:
                    novo_num = 1
                
                # Formata o código com 3 dígitos
                self.codigo_empresa = f"EMP{novo_num:03d}"
        
        # Salva o modelo
        super().save(*args, **kwargs)
        
        # Garantir que o código foi salvo corretamente
        if not self.codigo_empresa:
            with transaction.atomic():
                self.codigo_empresa = self.gerar_codigo_empresa_sequencial()
                super().save(update_fields=['codigo_empresa'])
        
        # Limpa o cache do código original
        if hasattr(self, '_codigo_empresa_original'):
            delattr(self, '_codigo_empresa_original')
    
    class Meta:
        verbose_name = 'Dados da Empresa'
        verbose_name_plural = 'Dados das Empresas'

class Sucursal(models.Model):
    TIPO_CHOICES = [
        ('SEDE', 'Sede Principal'),
        ('FILIAL', 'Filial'),
        ('LOJA', 'Loja'),
        ('ARMAZEM', 'Armazém'),
        ('FABRICA', 'Fábrica'),
        ('ESCRITORIO', 'Escritório'),
        ('CENTRO_DIST', 'Centro de Distribuição'),
        ('POSTO_VENDA', 'Posto de Venda'),
    ]

    empresa_sede = models.ForeignKey(
        DadosEmpresa,
        on_delete=models.CASCADE,
        related_name='sucursais',
        verbose_name='Empresa Sede'
    )
    nome = models.CharField(
        max_length=200,
        help_text='Nome comercial da sucursal'
    )
    codigo = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text='Código único da sucursal (gerado automaticamente)'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='FILIAL',
        help_text='Tipo de estabelecimento'
    )
    alvara_comercial = models.CharField(
        max_length=50,
        help_text='Número do Alvará Comercial',
        blank=True
    )
    licenca_operacional = models.CharField(
        max_length=50,
        help_text='Número da Licença Operacional',
        blank=True
    )
    responsavel = models.CharField(
        max_length=200,
        help_text='Nome do responsável pela sucursal'
    )
    provincia = models.CharField(
        max_length=50,
        choices=Provincia.choices,
        help_text='Província onde a sucursal está localizada'
    )
    cidade = models.CharField(
        max_length=100,
        help_text='Cidade/Distrito onde a sucursal está localizada'
    )
    bairro = models.CharField(
        max_length=100,
        help_text='Bairro onde a sucursal está localizada'
    )
    endereco = models.TextField(
        help_text='Endereço completo (Av./Rua, Número, Referências)'
    )
    telefone = models.CharField(
        max_length=13,
        validators=[validar_telefone_moz],
        help_text='Número de telefone com código do país (+258)'
    )
    email = models.EmailField(
        help_text='Email de contato da sucursal'
    )
    data_abertura = models.DateField(
        help_text='Data de início das operações'
    )
    data_alvara = models.DateField(
        null=True,
        blank=True,
        help_text='Data de emissão do alvará'
    )
    data_licenca = models.DateField(
        null=True,
        blank=True,
        help_text='Data de emissão da licença operacional'
    )
    ativa = models.BooleanField(
        default=True,
        help_text='Indica se a sucursal está operacional'
    )
    nivel_operacional = models.IntegerField(
        default=1,
        help_text='Nível hierárquico da sucursal (1 = principal)'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações adicionais sobre a sucursal'
    )
    
    # Campos de horário de expediente (próprios da sucursal)
    hora_inicio_expediente = models.TimeField(
        'Hora de Início do Expediente',
        default='08:00',
        help_text='Hora de início do expediente (formato HH:MM)'
    )
    hora_fim_expediente = models.TimeField(
        'Hora de Fim do Expediente',
        default='17:00',
        help_text='Hora de fim do expediente (formato HH:MM)'
    )
    duracao_almoco = models.DurationField(
        'Duração do Almoço',
        default='01:00:00',
        help_text='Duração da pausa para almoço (formato HH:MM:SS)'
    )
    dias_trabalho_semana = models.PositiveSmallIntegerField(
        'Dias de Trabalho por Semana',
        default=5,
        help_text='Número de dias de trabalho por semana'
    )
    horas_trabalho_dia = models.DurationField(
        'Horas de Trabalho por Dia',
        default='08:00:00',
        help_text='Número de horas de trabalho por dia (formato HH:MM:SS)'
    )

    def __str__(self):
        return self.nome

    
    def get_hora_inicio_expediente(self):
        """Retorna a hora de início do expediente da sucursal"""
        return self.hora_inicio_expediente
    
    def get_hora_fim_expediente(self):
        """Retorna a hora de fim do expediente da sucursal"""
        return self.hora_fim_expediente
    
    def get_duracao_almoco(self):
        """Retorna a duração do almoço da sucursal"""
        return self.duracao_almoco
    
    def get_dias_trabalho_semana(self):
        """Retorna os dias de trabalho por semana da sucursal"""
        return self.dias_trabalho_semana
    
    def get_horas_trabalho_dia(self):
        """Retorna as horas de trabalho por dia da sucursal"""
        return self.horas_trabalho_dia
    
    def get_dias_trabalho_weekdays(self):
        """Retorna os dias da semana que são dias de trabalho (0=segunda, 6=domingo)"""
        dias_semana = self.dias_trabalho_semana
        
        if dias_semana == 5:
            # Segunda a sexta (0, 1, 2, 3, 4)
            return [0, 1, 2, 3, 4]
        elif dias_semana == 6:
            # Segunda a sábado (0, 1, 2, 3, 4, 5)
            return [0, 1, 2, 3, 4, 5]
        elif dias_semana == 7:
            # Todos os dias (0, 1, 2, 3, 4, 5, 6)
            return [0, 1, 2, 3, 4, 5, 6]
        else:
            # Padrão: segunda a sexta
            return [0, 1, 2, 3, 4]
    
    def is_workday(self, date_obj):
        """Verifica se uma data é dia de trabalho"""
        weekday = date_obj.weekday()
        return weekday in self.get_dias_trabalho_weekdays()
    
    def get_horario_dia(self, date_obj):
        """Retorna o horário específico para um dia da semana"""
        weekday = date_obj.weekday()
        try:
            return self.horarios_expediente.get(dia_semana=weekday, ativo=True)
        except HorarioExpediente.DoesNotExist:
            return None
    
    def get_dias_trabalho_detalhados(self):
        """Retorna os dias de trabalho com horários específicos"""
        return self.horarios_expediente.filter(ativo=True).order_by('dia_semana')
    
    def criar_horarios_padrao(self):
        """Cria horários padrão para todos os dias da semana"""
        from datetime import time, timedelta
        
        # Horários padrão
        horarios_padrao = [
            (0, 'Segunda-feira', time(8, 0), time(17, 0), timedelta(hours=1)),
            (1, 'Terça-feira', time(8, 0), time(17, 0), timedelta(hours=1)),
            (2, 'Quarta-feira', time(8, 0), time(17, 0), timedelta(hours=1)),
            (3, 'Quinta-feira', time(8, 0), time(17, 0), timedelta(hours=1)),
            (4, 'Sexta-feira', time(8, 0), time(17, 0), timedelta(hours=1)),
            (5, 'Sábado', time(8, 0), time(12, 0), timedelta(hours=0)),  # Sem almoço
            (6, 'Domingo', time(8, 0), time(12, 0), timedelta(hours=0)),  # Sem almoço
        ]
        
        # Criar horários para cada dia
        for dia_semana, nome, inicio, fim, almoco in horarios_padrao:
            # Verificar se já existe
            if not self.horarios_expediente.filter(dia_semana=dia_semana).exists():
                HorarioExpediente.objects.create(
                    sucursal=self,
                    dia_semana=dia_semana,
                    ativo=dia_semana < 5,  # Ativo apenas segunda a sexta
                    hora_inicio=inicio,
                    hora_fim=fim,
                    duracao_almoco=almoco
                )

    def save(self, *args, **kwargs):
        # Gerar código automaticamente se não foi fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_sucursal()
        super().save(*args, **kwargs)

    def gerar_codigo_sucursal(self):
        """
        Gera código da sucursal no formato: CODIGO_EMPRESA + INICIAIS_NOME + (SUCURSAL) + NUMERO_SEQUENCIAL
        Exemplo: 001CON(SUCURSAL)001, 001CON(SUCURSAL)002, 002TEC(SUCURSAL)001
        """
        if not self.empresa_sede:
            return "001XXX(SUCURSAL)001"
        
        # Obter código da empresa (primeiros 3 dígitos do código_empresa)
        codigo_empresa = self.empresa_sede.codigo_empresa[:3] if self.empresa_sede.codigo_empresa else "001"
        
        # Obter iniciais do nome da empresa (primeiras 3 letras, maiúsculas)
        nome_empresa = self.empresa_sede.nome.replace(' ', '').replace('-', '')
        iniciais = ''.join([c.upper() for c in nome_empresa if c.isalpha()])[:3]
        
        # Se não conseguir 3 letras, usar as disponíveis
        if len(iniciais) < 3:
            iniciais = iniciais.ljust(3, 'X')
        
        # Buscar próxima sequência para esta empresa
        prefixo = f"{codigo_empresa}{iniciais}(SUCURSAL)"
        ultima_sucursal = Sucursal.objects.filter(
            empresa_sede=self.empresa_sede,
            codigo__startswith=prefixo
        ).order_by('-codigo').first()
        
        if ultima_sucursal and ultima_sucursal.codigo:
            try:
                # Extrair sequência (ex: 001CON(SUCURSAL)001 -> 1)
                sequencia = int(ultima_sucursal.codigo[-3:]) + 1
            except (ValueError, IndexError):
                sequencia = 1
        else:
            sequencia = 1
        
        return f"{prefixo}{sequencia:03d}"

    class Meta:
        verbose_name = 'Sucursal'
        verbose_name_plural = 'Sucursais'
        ordering = ['nome']


# Signal para capturar o valor original do codigo_empresa antes do salvamento
@receiver(pre_save, sender=DadosEmpresa)
def capturar_codigo_empresa_original(sender, instance, **kwargs):
    """
    Captura o valor original do codigo_empresa antes de qualquer salvamento
    para garantir que não seja alterado
    """
    if instance.pk:
        try:
            original = DadosEmpresa.objects.get(pk=instance.pk)
            instance._codigo_empresa_original = original.codigo_empresa
        except DadosEmpresa.DoesNotExist:
            pass

# Signal para criar automaticamente a sucursal sede quando uma empresa sede é criada
@receiver(post_save, sender=DadosEmpresa)
def criar_sucursal_sede_automaticamente(sender, instance, created, **kwargs):
    """
    Cria automaticamente uma sucursal sede quando uma empresa é marcada como sede
    """
    if created and instance.is_sede:
        # Verificar se já existe uma sucursal sede para esta empresa
        if not Sucursal.objects.filter(empresa_sede=instance, tipo='SEDE').exists():
            # Gerar código da sucursal sede usando o novo formato
            codigo_empresa = instance.codigo_empresa[:3] if instance.codigo_empresa else "001"
            nome_empresa = instance.nome.replace(' ', '').replace('-', '')
            iniciais = ''.join([c.upper() for c in nome_empresa if c.isalpha()])[:3]
            
            # Se não conseguir 3 letras, usar as disponíveis
            if len(iniciais) < 3:
                iniciais = iniciais.ljust(3, 'X')
            
            codigo_sede = f"{codigo_empresa}{iniciais}(SUCURSAL)001"
            
            # Mapear a província da empresa para o formato da sucursal
            provincia_mapping = {
                'Maputo Cidade': 'MP',
                'Maputo Província': 'MA', 
                'Gaza': 'GA',
                'Inhambane': 'IN',
                'Manica': 'MN',
                'Sofala': 'SO',
                'Zambézia': 'ZA',
                'Tete': 'TE',
                'Nampula': 'NA',
                'Niassa': 'NI',
                'Cabo Delgado': 'CD'
            }
            
            provincia_sucursal = provincia_mapping.get(instance.provincia, 'MP')
            
            Sucursal.objects.create(
                empresa_sede=instance,
                nome=f"Sede - {instance.nome}",
                codigo=codigo_sede,
                tipo='SEDE',
                responsavel="Administrador",
                provincia=provincia_sucursal,
                cidade=instance.cidade,
                bairro=instance.bairro,
                endereco=instance.endereco,
                telefone=instance.telefone,
                email=instance.email,
                data_abertura=instance.data_constituicao,
                ativa=True
            )
