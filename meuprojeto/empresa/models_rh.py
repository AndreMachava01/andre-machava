from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from .models_base import Sucursal

def validar_telefone_moz(value):
    """Valida telefone de Moçambique no formato +258XXXXXXXXX.

    Observações:
    - Permite valores vazios (None ou "") quando o campo é opcional (blank=True),
      evitando erro de validação em formulários onde o telefone é opcional.
    - Normaliza espaços em branco laterais antes da validação.
    """
    if value in (None, ''):
        return value
    value = value.strip()
    if not value.startswith('+258') or len(value) != 13:
        raise ValidationError('Telefone deve começar com +258 e ter 13 caracteres.')
    return value

class Departamento(models.Model):
    TIPO_CHOICES = [
        ('ADM', 'Administrativo'),
        ('FIN', 'Financeiro'),
        ('RH', 'Recursos Humanos'),
        ('COM', 'Comercial'),
        ('MKT', 'Marketing'),
        ('OPR', 'Operações'),
        ('LOG', 'Logística'),
        ('TI', 'Tecnologia de Informação'),
        ('JUR', 'Jurídico'),
        ('PROD', 'Produção'),
        ('MANUT', 'Manutenção'),
        ('QUAL', 'Qualidade'),
        ('COMP', 'Aprovisionamento'),
        ('ALM', 'Armazém'),
        ('EXP', 'Exportação'),
        ('IMP', 'Importação'),
        ('GOV', 'Governação'),
        ('AUD', 'Auditoria Interna'),
        ('SEG', 'Segurança'),
        ('SOC', 'Responsabilidade Social'),
        ('AMBI', 'Ambiente'),
        ('COMU', 'Comunicação'),
        ('PLAN', 'Planeamento'),
        ('MON', 'Monitoria e Avaliação'),
    ]

    nome = models.CharField(
        max_length=100,
        help_text='Nome do departamento'
    )
    codigo = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        help_text='Código único do departamento (gerado automaticamente)'
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default='ADM',
        help_text='Tipo/Área do departamento'
    )
    descricao = models.TextField(
        blank=True,
        help_text='Descrição das responsabilidades do departamento'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='departamentos',
        help_text='Sucursal à qual o departamento está vinculado'
    )
    responsavel = models.CharField(
        max_length=200,
        blank=True,
        help_text='Nome do responsável pelo departamento'
    )
    email_departamento = models.EmailField(
        blank=True,
        help_text='Email institucional do departamento'
    )
    ramal = models.CharField(
        max_length=10,
        blank=True,
        help_text='Número do ramal do departamento'
    )
    orcamento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Orçamento mensal do departamento'
    )
    meta_anual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Meta anual do departamento (quando aplicável)'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o departamento está ativo'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de criação do departamento'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        help_text='Data da última atualização'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações adicionais sobre o departamento'
    )

    def save(self, *args, **kwargs):
        """Override save para gerar código automaticamente"""
        if not self.codigo or self.codigo.strip() == '':
            # Gerar código do departamento: TIPO-XXX
            prefixo = self.tipo if hasattr(self, 'tipo') and self.tipo else 'ADM'
            
            # Encontra o próximo número sequencial disponível para esta sucursal
            ultimo = Departamento.objects.filter(
                sucursal=self.sucursal,
                codigo__startswith=prefixo
            ).order_by('-codigo').first()
            
            if ultimo and ultimo.codigo:
                try:
                    # Extrai o número do último código
                    ultimo_num = int(ultimo.codigo.split('-')[-1])
                    novo_num = ultimo_num + 1
                except (ValueError, IndexError):
                    novo_num = 1
            else:
                novo_num = 1
            
            # Gera o novo código
            self.codigo = f"{prefixo}-{novo_num:03d}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.sucursal.nome})"

    class Meta:
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        ordering = ['sucursal', 'nome']
        unique_together = ['codigo', 'sucursal']

class DepartamentoSucursal(models.Model):
    """Relacionamento entre departamentos e sucursais para permitir compartilhamento"""
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.CASCADE,
        related_name='sucursais_vinculadas',
        help_text='Departamento que pode ser usado em múltiplas sucursais'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='departamentos_vinculados',
        help_text='Sucursal onde o departamento pode ser usado'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o departamento está ativo nesta sucursal'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de vinculação do departamento à sucursal'
    )

    def __str__(self):
        return f"{self.departamento.nome} - {self.sucursal.nome}"

    class Meta:
        verbose_name = 'Departamento por Sucursal'
        verbose_name_plural = 'Departamentos por Sucursais'
        unique_together = ['departamento', 'sucursal']
        ordering = ['sucursal__nome', 'departamento__nome']

class Cargo(models.Model):
    NIVEL_CHOICES = [
        ('EST', 'Estagiário'),
        ('APR', 'Aprendiz'),
        ('AUX', 'Auxiliar'),
        ('ASS', 'Assistente'),
        ('ANA', 'Analista'),
        ('TCN', 'Técnico'),
        ('ESP', 'Especialista'),
        ('SUP', 'Supervisor'),
        ('CRD', 'Coordenador'),
        ('GER', 'Gestor'),
        ('DIR', 'Director'),
    ]

    CATEGORIA_CHOICES = [
        ('OP', 'Operacional'),
        ('ADM', 'Administrativo'),
        ('TEC', 'Técnico'),
        ('GES', 'Gestão'),
        ('EXE', 'Executivo'),
    ]

    nome = models.CharField(
        max_length=100,
        help_text='Nome do cargo'
    )
    nivel = models.CharField(
        max_length=3,
        choices=NIVEL_CHOICES,
        help_text='Nível hierárquico do cargo'
    )
    categoria = models.CharField(
        max_length=3,
        choices=CATEGORIA_CHOICES,
        default='OP',
        help_text='Categoria funcional do cargo'
    )
    codigo_cargo = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Código único do cargo (gerado automaticamente)'
    )
    descricao = models.TextField(
        blank=True,
        help_text='Descrição detalhada das responsabilidades do cargo'
    )
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.CASCADE,
        related_name='cargos',
        help_text='Departamento ao qual o cargo está vinculado'
    )
    carga_horaria = models.IntegerField(
        default=40,
        help_text='Carga horária semanal padrão'
    )
    salario_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Remuneração base do cargo'
    )
    faixa_salarial_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Valor mínimo da faixa salarial'
    )
    faixa_salarial_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Valor máximo da faixa salarial'
    )
    requisitos_obrigatorios = models.TextField(
        blank=True,
        help_text='Requisitos mínimos para ocupar o cargo'
    )
    requisitos_desejaveis = models.TextField(
        blank=True,
        help_text='Requisitos desejáveis para o cargo'
    )
    competencias = models.TextField(
        blank=True,
        help_text='Competências necessárias para o cargo'
    )
    riscos_ocupacionais = models.TextField(
        blank=True,
        help_text='Riscos ocupacionais associados ao cargo'
    )
    equipamentos_obrigatorios = models.TextField(
        blank=True,
        help_text='Equipamentos de proteção ou trabalho necessários'
    )
    beneficios_especificos = models.TextField(
        blank=True,
        help_text='Benefícios específicos para este cargo'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o cargo está ativo'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de criação do cargo'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        help_text='Data da última atualização'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações adicionais sobre o cargo'
    )

    def save(self, *args, **kwargs):
        if not self.codigo_cargo:
            # Gerar código do cargo: DEPT-NIVEL-XXX
            ultimo_cargo = Cargo.objects.filter(
                departamento=self.departamento,
                nivel=self.nivel
            ).order_by('-codigo_cargo').first()

            if ultimo_cargo and ultimo_cargo.codigo_cargo:
                try:
                    ultimo_num = int(ultimo_cargo.codigo_cargo.split('-')[-1])
                    novo_num = ultimo_num + 1
                except (ValueError, IndexError):
                    novo_num = 1
            else:
                novo_num = 1

            self.codigo_cargo = f"{self.departamento.codigo[:3]}-{self.nivel}-{novo_num:03d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} {self.get_nivel_display()} - {self.departamento.nome}"

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ['departamento', 'nivel', 'nome']
        unique_together = ['nome', 'nivel', 'departamento']

class Funcionario(models.Model):
    STATUS_CHOICES = [
        ('AT', 'Ativo'),
        ('AF', 'Afastado'),
        ('FE', 'Férias'),
        ('IN', 'Inativo'),
    ]

    ESTADO_CIVIL_CHOICES = [
        ('S', 'Solteiro(a)'),
        ('C', 'Casado(a)'),
        ('D', 'Divorciado(a)'),
        ('V', 'Viúvo(a)'),
        ('U', 'União Estável'),
    ]

    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('O', 'Outro'),
    ]

    TIPO_CONTRATO_CHOICES = [
        ('EFT', 'Efectivo'),
        ('TMP', 'Temporário'),
        ('EST', 'Estágio'),
        ('APR', 'Aprendiz'),
        ('TER', 'Terceirizado'),
        ('PRS', 'Prestador de Serviços'),
    ]

    ESCOLARIDADE_CHOICES = [
        ('EPI', 'Ensino Primário Incompleto'),
        ('EPC', 'Ensino Primário Completo'),
        ('ESI', 'Ensino Secundário Incompleto'),
        ('ESC', 'Ensino Secundário Completo'),
        ('ETI', 'Ensino Técnico Incompleto'),
        ('ETC', 'Ensino Técnico Completo'),
        ('EUI', 'Ensino Universitário Incompleto'),
        ('EUC', 'Ensino Universitário Completo'),
        ('PGI', 'Pós-Graduação Incompleta'),
        ('PGC', 'Pós-Graduação Completa'),
        ('MES', 'Mestrado'),
        ('DOU', 'Doutoramento'),
    ]

    # Informações Básicas
    nome_completo = models.CharField(max_length=200, help_text='Nome completo do trabalhador')
    codigo_funcionario = models.CharField(max_length=7, unique=True, blank=True, help_text='Código único do trabalhador (gerado automaticamente)')
    data_nascimento = models.DateField(null=True, blank=True, help_text='Data de nascimento')
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, null=True, blank=True, help_text='Género')
    estado_civil = models.CharField(max_length=1, choices=ESTADO_CIVIL_CHOICES, null=True, blank=True, help_text='Estado civil')
    nacionalidade = models.CharField(max_length=100, null=True, blank=True, help_text='Nacionalidade')
    naturalidade = models.CharField(max_length=100, null=True, blank=True, help_text='Cidade natal')

    # Documentos
    nuit = models.CharField(max_length=9, unique=True, null=True, blank=True, help_text='Número de NUIT')
    bi = models.CharField(max_length=13, unique=True, null=True, blank=True, help_text='Número do BI')
    data_emissao_bi = models.DateField(null=True, blank=True, help_text='Data de emissão do BI')
    data_validade_bi = models.DateField(null=True, blank=True, help_text='Data de validade do BI')
    local_emissao_bi = models.CharField(max_length=100, null=True, blank=True, help_text='Local de emissão do BI')
    
    # Contato
    email = models.EmailField(blank=True, help_text='Email pessoal')
    telefone = models.CharField(max_length=13, validators=[validar_telefone_moz], null=True, blank=True, help_text='Telefone (+258XXXXXXXXX)')
    telefone_alternativo = models.CharField(max_length=13, blank=True, validators=[validar_telefone_moz], help_text='Telefone alternativo')
    endereco = models.CharField(max_length=200, null=True, blank=True, help_text='Endereço residencial')
    bairro = models.CharField(max_length=100, null=True, blank=True, help_text='Bairro')
    cidade = models.CharField(max_length=100, null=True, blank=True, help_text='Cidade')
    provincia = models.CharField(max_length=100, null=True, blank=True, help_text='Província')

    # Dados Profissionais
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT, related_name='funcionarios')
    departamento = models.ForeignKey(Departamento, on_delete=models.PROTECT, related_name='funcionarios')
    cargo = models.ForeignKey(Cargo, on_delete=models.PROTECT, related_name='funcionarios')
    tipo_contrato = models.CharField(max_length=3, choices=TIPO_CONTRATO_CHOICES, null=True, blank=True, help_text='Tipo de contrato')
    data_admissao = models.DateField(help_text='Data de admissão')
    data_demissao = models.DateField(null=True, blank=True, help_text='Data de demissão')
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='AT', help_text='Status atual')
    
    # Dados Bancários
    banco = models.CharField(max_length=100, null=True, blank=True, help_text='Nome do banco')
    agencia = models.CharField(max_length=10, null=True, blank=True, help_text='Número da agência')
    conta = models.CharField(max_length=20, null=True, blank=True, help_text='Número da conta')
    nib = models.CharField(max_length=21, unique=True, null=True, blank=True, help_text='Número de NIB')

    # Remuneração
    salario_atual = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Salário atual do funcionário (FONTE PRINCIPAL)')
    
    # Benefícios e Descontos (Configuração Base)
    beneficios = models.ManyToManyField(
        'BeneficioSalarial', 
        blank=True, 
        related_name='funcionarios_beneficiarios',
        help_text='Benefícios aos quais o funcionário está sujeito'
    )
    descontos = models.ManyToManyField(
        'DescontoSalarial', 
        blank=True, 
        related_name='funcionarios_descontados',
        help_text='Descontos aos quais o funcionário está sujeito'
    )

    # Educação
    escolaridade = models.CharField(max_length=3, choices=ESCOLARIDADE_CHOICES, null=True, blank=True, help_text='Nível de escolaridade')
    curso = models.CharField(max_length=100, blank=True, help_text='Curso de formação')
    instituicao_ensino = models.CharField(max_length=100, blank=True, help_text='Instituição de ensino')
    ano_conclusao = models.IntegerField(null=True, blank=True, help_text='Ano de conclusão')

    # Controle do Sistema
    data_criacao = models.DateTimeField(auto_now_add=True, help_text='Data de criação do registro')
    data_atualizacao = models.DateTimeField(auto_now=True, help_text='Data da última atualização')

    def save(self, *args, **kwargs):
        # Flag para controlar se deve criar histórico
        criar_historico = False
        salario_anterior = None
        
        # Normalizar campos opcionais únicos para evitar duplicidade de string vazia ('')
        # Armazenar como NULL (None) quando o usuário não informar valor
        if hasattr(self, 'nuit') and (self.nuit == '' or self.nuit is None):
            self.nuit = None
        if hasattr(self, 'bi') and (self.bi == '' or self.bi is None):
            self.bi = None
        if hasattr(self, 'nib') and (self.nib == '' or self.nib is None):
            self.nib = None
        
        # Se já existe um registro com ID, mantém o código original
        if self.id:
            old_self = Funcionario.objects.filter(id=self.id).first()
            if old_self and old_self.codigo_funcionario:
                self.codigo_funcionario = old_self.codigo_funcionario
            
            # Verificar se o salário mudou para criar histórico
            if old_self and old_self.salario_atual != self.salario_atual and self.salario_atual > 0:
                criar_historico = True
                # Buscar salário ativo atual
                salario_anterior = Salario.objects.filter(
                    funcionario=self,
                    status='AT'
                ).first()
        # Se não tem código, gera um novo
        elif not self.codigo_funcionario:
            ultimo_funcionario = Funcionario.objects.order_by('-codigo_funcionario').first()
            
            if ultimo_funcionario and ultimo_funcionario.codigo_funcionario:
                try:
                    ultimo_num = int(ultimo_funcionario.codigo_funcionario[4:])
                    novo_num = ultimo_num + 1
                except (ValueError, IndexError):
                    novo_num = 1
            else:
                novo_num = 1
            
            self.codigo_funcionario = f"CONS{novo_num:03d}"
        
        super().save(*args, **kwargs)
        
        # Criar histórico APÓS salvar o funcionário
        if criar_historico and salario_anterior:
            # Finalizar salário anterior
            salario_anterior.status = 'IN'
            salario_anterior.data_fim = self.data_atualizacao.date()
            salario_anterior.observacoes = f"Alterado de {salario_anterior.valor_base} para {self.salario_atual} MT"
            salario_anterior.save()
            
            # Criar novo registro de salário
            Salario.objects.create(
                funcionario=self,
                valor_base=self.salario_atual,
                data_inicio=self.data_atualizacao.date(),
                status='AT',
                observacoes=f"Alteração de {salario_anterior.valor_base} para {self.salario_atual} MT"
            )
        elif not self.id and self.salario_atual > 0:
            # Se é um novo funcionário com salário, criar registro na tabela Salario
            Salario.objects.create(
                funcionario=self,
                valor_base=self.salario_atual,
                data_inicio=self.data_admissao,
                status='AT',
                observacoes='Salário inicial do funcionário'
            )

    def get_salario_atual(self):
        """Obtém o salário atual do funcionário (fonte principal: campo salario_atual)"""
        return self.salario_atual or 0
    
    def get_salario_base(self):
        """Alias para get_salario_atual() para compatibilidade"""
        return self.get_salario_atual()
    
    def get_historico_salarios(self):
        """Obtém o histórico completo de salários do funcionário"""
        return Salario.objects.filter(funcionario=self).order_by('-data_inicio')
    
    def get_ultima_alteracao_salario(self):
        """Obtém informações da última alteração de salário"""
        ultimo_salario = self.get_historico_salarios().first()
        if ultimo_salario:
            return {
                'data_alteracao': ultimo_salario.data_inicio,
                'valor_anterior': ultimo_salario.observacoes,
                'valor_atual': ultimo_salario.valor_base,
                'observacoes': ultimo_salario.observacoes
            }
        return None
    
    def get_auditoria_salarios(self):
        """Obtém auditoria completa de alterações de salário"""
        historico = self.get_historico_salarios()
        auditoria = []
        
        for salario in historico:
            auditoria.append({
                'data_inicio': salario.data_inicio,
                'data_fim': salario.data_fim,
                'valor': salario.valor_base,
                'status': salario.get_status_display(),
                'observacoes': salario.observacoes,
                'data_criacao': salario.data_criacao,
                'data_atualizacao': salario.data_atualizacao
            })
        
        return auditoria
    
    def reverter_para_salario_anterior(self):
        """Reverte para o salário anterior (se existir)"""
        salario_anterior = Salario.objects.filter(
            funcionario=self,
            status='IN'
        ).order_by('-data_fim').first()
        
        if salario_anterior:
            # Atualizar salario_atual
            self.salario_atual = salario_anterior.valor_base
            self.save()
            
            # Reativar salário anterior
            salario_anterior.status = 'AT'
            salario_anterior.data_fim = None
            salario_anterior.observacoes = f"Reversão para salário anterior de {salario_anterior.valor_base} MT"
            salario_anterior.save()
            
            return True
        return False
    
    def sincronizar_salario_atual(self):
        """Sincroniza o salário - agora apenas valida consistência"""
        # Este método agora é apenas para compatibilidade
        # O salário é sempre obtido da tabela Salario
        pass
    
    def validar_consistencia_salario(self):
        """Valida se o salário está consistente entre todas as fontes"""
        salario_funcionario = self.salario_atual or 0
        salario_cargo = self.cargo.salario_base if self.cargo else 0
        
        inconsistencias = []
        if salario_funcionario != salario_cargo:
            inconsistencias.append(f"Funcionario.salario_atual ({salario_funcionario}) ≠ Cargo.salario_base ({salario_cargo})")
        
        return {
            'consistente': len(inconsistencias) == 0,
            'salario_funcionario': salario_funcionario,
            'salario_cargo': salario_cargo,
            'inconsistencias': inconsistencias
        }
    
    def get_remuneracao_por_hora(self, mes_referencia=None):
        """Calcula a remuneração por hora do funcionário"""
        from datetime import date, timedelta
        
        if not mes_referencia:
            mes_referencia = date.today().replace(day=1)
        
        # Buscar folha do mês
        folha = FolhaSalarial.objects.filter(mes_referencia=mes_referencia).first()
        if not folha:
            return None
        
        # Buscar funcionário na folha
        funcionario_folha = FuncionarioFolha.objects.filter(
            folha=folha, 
            funcionario=self
        ).first()
        
        if not funcionario_folha or funcionario_folha.horas_trabalhadas <= 0:
            return None
        
        # Calcular remuneração por hora
        remuneracao_por_hora = funcionario_folha.salario_base / funcionario_folha.horas_trabalhadas
        
        return {
            'remuneracao_por_hora': round(remuneracao_por_hora, 2),
            'salario_base': funcionario_folha.salario_base,
            'horas_trabalhadas': funcionario_folha.horas_trabalhadas,
            'dias_trabalhados': funcionario_folha.dias_trabalhados,
            'mes_referencia': mes_referencia
        }
    
    def get_remuneracao_por_dia(self, mes_referencia=None):
        """Calcula a remuneração por dia do funcionário"""
        from datetime import date
        
        if not mes_referencia:
            mes_referencia = date.today().replace(day=1)
        
        # Buscar folha do mês
        folha = FolhaSalarial.objects.filter(mes_referencia=mes_referencia).first()
        if not folha:
            return None
        
        # Buscar funcionário na folha
        funcionario_folha = FuncionarioFolha.objects.filter(
            folha=folha, 
            funcionario=self
        ).first()
        
        if not funcionario_folha or funcionario_folha.dias_trabalhados <= 0:
            return None
        
        # Calcular remuneração por dia
        remuneracao_por_dia = funcionario_folha.salario_base / funcionario_folha.dias_trabalhados
        
        return {
            'remuneracao_por_dia': round(remuneracao_por_dia, 2),
            'salario_base': funcionario_folha.salario_base,
            'dias_trabalhados': funcionario_folha.dias_trabalhados,
            'mes_referencia': mes_referencia
        }
    
    def get_remuneracao_por_hora_teorica(self):
        """Calcula a remuneração por hora teórica baseada no horário de expediente"""
        if not self.sucursal:
            return None
        
        # Obter horários de expediente
        horas_por_dia = self.sucursal.get_horas_trabalho_dia()
        dias_por_mes = self.sucursal.get_dias_trabalho_semana() * 4  # Aproximação de 4 semanas por mês
        
        if not horas_por_dia or not dias_por_mes:
            return None
        
        # Converter horas_por_dia para decimal
        if isinstance(horas_por_dia, str):
            horas_decimal = float(horas_por_dia.split(':')[0]) + float(horas_por_dia.split(':')[1]) / 60
        elif hasattr(horas_por_dia, 'total_seconds'):
            # Se for timedelta, converter para horas
            horas_decimal = horas_por_dia.total_seconds() / 3600
        else:
            horas_decimal = float(horas_por_dia)
        
        # Calcular horas mensais teóricas
        horas_mensais_teoricas = horas_decimal * dias_por_mes
        
        if horas_mensais_teoricas <= 0:
            return None
        
        # Calcular remuneração por hora teórica
        remuneracao_por_hora = float(self.get_salario_atual()) / horas_mensais_teoricas
        
        return {
            'remuneracao_por_hora_teorica': round(remuneracao_por_hora, 2),
            'salario_atual': self.get_salario_atual(),
            'horas_por_dia': horas_decimal,
            'dias_por_mes': dias_por_mes,
            'horas_mensais_teoricas': round(horas_mensais_teoricas, 2)
        }

    def __str__(self):
        return f"{self.codigo_funcionario} - {self.nome_completo}"

    class Meta:
        verbose_name = 'Trabalhador'
        verbose_name_plural = 'Trabalhadores'
        ordering = ['nome_completo']



# ===== GESTÃO DE LOCALIZAÇÃO =====

class Provincia(models.Model):
    """Modelo para gerenciar províncias de Moçambique"""
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Província")
    codigo = models.CharField(max_length=3, unique=True, verbose_name="Código")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Província"
        verbose_name_plural = "Províncias"
        ordering = ['nome']
    
    def __str__(self):
        return self.nome


class Cidade(models.Model):
    """Modelo para gerenciar cidades de Moçambique"""
    nome = models.CharField(max_length=100, verbose_name="Nome da Cidade")
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código")
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE, related_name='cidades', verbose_name="Província")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        ordering = ['provincia__nome', 'nome']
        unique_together = ['nome', 'provincia']
    
    def __str__(self):
        return f"{self.nome} - {self.provincia.nome}"


class Bairro(models.Model):
    """Modelo para gerenciar bairros de Moçambique"""
    nome = models.CharField(max_length=100, verbose_name="Nome do Bairro")
    codigo = models.CharField(max_length=15, unique=True, verbose_name="Código")
    cidade = models.ForeignKey(Cidade, on_delete=models.CASCADE, related_name='bairros', verbose_name="Cidade")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Bairro"
        verbose_name_plural = "Bairros"
        ordering = ['cidade__provincia__nome', 'cidade__nome', 'nome']
        unique_together = ['nome', 'cidade']
    
    def __str__(self):
        return f"{self.nome} - {self.cidade.nome}"


# ===== GESTÃO DE PRESENÇAS =====

class TipoPresenca(models.Model):
    """Tipos de presença (Presente, Ausente, Atraso, etc.)"""
    TIPO_CHOICES = [
        ('PR', 'Presente'),
        ('AU', 'Ausente'),
        ('FJ', 'Falta Justificada'),
        ('FI', 'Falta Injustificada'),
        ('LI', 'Licença'),
        ('FE', 'Férias'),
        ('SU', 'Suspensão'),
        ('AT', 'Atraso'),
        ('FD', 'Feriado'),
        ('OU', 'Outro'),
    ]
    
    nome = models.CharField(max_length=100, help_text='Nome do tipo de presença')
    codigo = models.CharField(max_length=2, choices=TIPO_CHOICES, unique=True, help_text='Código único do tipo')
    descricao = models.TextField(blank=True, help_text='Descrição do tipo de presença')
    desconta_salario = models.BooleanField(default=False, help_text='Se este tipo desconta da remuneração')
    cor = models.CharField(max_length=7, default='#28a745', help_text='Cor para exibição (código hexadecimal)')
    ativo = models.BooleanField(default=True, help_text='Se o tipo está ativo')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Tipo de Presença'
        verbose_name_plural = 'Tipos de Presenças'
        ordering = ['nome']


class Feriado(models.Model):
    """Feriados nacionais, regionais e da empresa"""
    TIPO_CHOICES = [
        ('NACIONAL', 'Feriado Nacional'),
        ('REGIONAL', 'Feriado Regional'),
        ('EMPRESA', 'Feriado da Empresa'),
        ('MUNICIPAL', 'Feriado Municipal'),
    ]
    
    nome = models.CharField(max_length=100, help_text='Nome do feriado')
    data = models.DateField(help_text='Data do feriado')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='NACIONAL', help_text='Tipo do feriado')
    descricao = models.TextField(blank=True, help_text='Descrição do feriado')
    ativo = models.BooleanField(default=True, help_text='Feriado ativo')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} - {self.data}"

    class Meta:
        verbose_name = 'Feriado'
        verbose_name_plural = 'Feriados'
        ordering = ['data', 'nome']
        unique_together = ['data', 'nome']


class Presenca(models.Model):
    """Registro de presenças dos trabalhadores"""
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='presencas')
    data = models.DateField(help_text='Data da presença')
    tipo_presenca = models.ForeignKey(TipoPresenca, on_delete=models.PROTECT, help_text='Tipo de presença')
    hora_inicio = models.TimeField(blank=True, null=True, help_text='Hora de início do trabalho')
    hora_fim = models.TimeField(blank=True, null=True, help_text='Hora de fim do trabalho')
    observacoes = models.TextField(blank=True, help_text='Observações sobre a presença')
    justificativa = models.TextField(blank=True, help_text='Justificação para faltas ou atrasos')
    aprovado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, help_text='Usuário que aprovou a justificação')
    data_aprovacao = models.DateTimeField(null=True, blank=True, help_text='Data de aprovação da justificação')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.data} - {self.tipo_presenca.nome}"

    class Meta:
        verbose_name = 'Presença'
        verbose_name_plural = 'Presenças'
        ordering = ['-data', 'funcionario__codigo_funcionario']
        unique_together = ['funcionario', 'data']  # Um funcionário só pode ter uma presença por dia


class HorasExtras(models.Model):
    """
    Modelo completo para gestão de horas extras
    """
    TIPO_CHOICES = [
        ('DI', 'Diurno'),
        ('NO', 'Noturno'),
        ('EX', 'Extraordinário'),
    ]
    
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='horas_extras')
    data = models.DateField()
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, default='DI')
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()
    quantidade_horas = models.DecimalField(max_digits=5, decimal_places=2)
    valor_por_hora = models.DecimalField(max_digits=10, decimal_places=2)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    observacoes = models.TextField(blank=True, null=True)
    data_aprovacao = models.DateTimeField(blank=True, null=True)
    aprovado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='horas_extras_aprovadas')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='horas_extras_criadas')
    
    class Meta:
        verbose_name = 'Horas Extras'
        verbose_name_plural = 'Horas Extras'
        unique_together = ('funcionario', 'data', 'tipo')
        ordering = ['-data', '-data_criacao']
    
    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.data} - {self.get_tipo_display()}"
    
    def save(self, *args, **kwargs):
        # Calcular valor total automaticamente
        self.valor_total = self.quantidade_horas * self.valor_por_hora
        super().save(*args, **kwargs)
    
    def calcular_valor_total(self):
        """Calcula o valor total das horas extras"""
        return self.quantidade_horas * self.valor_por_hora
    
    def marcar_aprovado(self, usuario_aprovador):
        """Marca as horas extras como aprovadas"""
        self.data_aprovacao = timezone.now()
        self.aprovado_por = usuario_aprovador
        self.save()
    
    def calcular_valor_por_hora_automatico(self):
        """Calcula o valor por hora das horas extras baseado no tipo e vencimento do funcionário"""
        # Obter vencimento por hora do funcionário
        remuneracao_hora = self.funcionario.get_remuneracao_por_hora_teorica()
        if not remuneracao_hora:
            remuneracao_hora = self.funcionario.get_remuneracao_por_hora()
        
        if not remuneracao_hora:
            return None
        
        valor_hora_base = remuneracao_hora.get('remuneracao_por_hora_teorica') or remuneracao_hora.get('remuneracao_por_hora')
        
        if not valor_hora_base:
            return None
        
        # Definir percentuais por tipo de hora extra
        percentuais = {
            'DI': 0.50,  # 50% para horas extras diurnas
            'NO': 1.00,  # 100% para horas extras noturnas
            'EX': 1.00,  # 100% para trabalho extraordinário
        }
        
        percentual = percentuais.get(self.tipo, 0.50)  # Default 50%
        valor_hora_extra = valor_hora_base * percentual
        
        return {
            'valor_hora_base': valor_hora_base,
            'percentual': percentual,
            'valor_hora_extra': valor_hora_extra,
            'tipo_display': self.get_tipo_display()
        }
    
    @classmethod
    def determinar_tipo_automatico(cls, funcionario, data, hora_inicio, hora_fim):
        """
        Determina automaticamente o tipo de horas extras baseado em regras de negócio
        Retorna: (tipo_principal, justificativa, sugestao_misto)
        """
        from datetime import time, datetime, date, timedelta
        from .models_rh import Feriado
        
        sucursal = funcionario.sucursal
        
        # 1. VERIFICAR SE É FERIADO
        if Feriado.objects.filter(data=data, ativo=True).exists():
            return 'EX', 'Feriado - Trabalho Extraordinário', None
        
        # 2. VERIFICAR SE É FINAL DE SEMANA
        if data.weekday() >= 5:  # Sábado=5, Domingo=6
            return 'EX', 'Fim de Semana - Trabalho Extraordinário', None
        
        # 3. VERIFICAR SE É DIA DE TRABALHO DA SUCURSAL
        if not sucursal.is_workday(data):
            return 'EX', 'Dia não trabalhado - Trabalho Extraordinário', None
        
        # 4. VERIFICAR HORÁRIO (DIURNO vs NOTURNO vs MISTO)
        # Diurno: início do expediente até 20h (fim do expediente até 20h)
        # Noturno: 20h até início do expediente (20h até início do expediente)
        if isinstance(hora_inicio, str):
            hora_inicio_time = time.fromisoformat(hora_inicio)
        else:
            hora_inicio_time = hora_inicio
            
        if isinstance(hora_fim, str):
            hora_fim_time = time.fromisoformat(hora_fim)
        else:
            hora_fim_time = hora_fim
        
        # Calcular horas em cada período
        def calcular_horas_por_periodo(hora_inicio, hora_fim):
            # Horários padrão baseados no dia da semana
            # Segunda a Sexta: 8h-17h, Sábado: 8h-12h, Domingo: não trabalha
            weekday = data.weekday()
            
            if weekday < 5:  # Segunda a Sexta
                diurno_inicio = time(8, 0)
                diurno_fim = time(20, 0)  # Até 20h é diurno
                noturno_inicio = time(20, 0)
                noturno_fim = time(8, 0)  # 20h até 8h é noturno
            elif weekday == 5:  # Sábado
                diurno_inicio = time(8, 0)
                diurno_fim = time(20, 0)
                noturno_inicio = time(20, 0)
                noturno_fim = time(8, 0)
            else:  # Domingo
                # Domingo é considerado trabalho extraordinário
                diurno_inicio = time(8, 0)
                diurno_fim = time(20, 0)
                noturno_inicio = time(20, 0)
                noturno_fim = time(8, 0)
            
            horas_diurnas = 0
            horas_noturnas = 0
            
            # Se o trabalho começa e termina no mesmo dia
            if hora_inicio <= hora_fim:
                # Período diurno (6h-20h)
                if hora_inicio < diurno_fim and hora_fim > diurno_inicio:
                    inicio_diurno = max(hora_inicio, diurno_inicio)
                    fim_diurno = min(hora_fim, diurno_fim)
                    horas_diurnas = (datetime.combine(date.today(), fim_diurno) - 
                                   datetime.combine(date.today(), inicio_diurno)).total_seconds() / 3600
                
                # Período noturno (20h-6h do dia seguinte)
                if hora_inicio < noturno_fim or hora_fim > noturno_inicio:
                    if hora_inicio < noturno_fim:  # Começa antes da meia-noite
                        inicio_noturno = max(hora_inicio, noturno_inicio)
                        fim_noturno = time(23, 59, 59)
                        horas_noturnas += (datetime.combine(date.today(), fim_noturno) - 
                                         datetime.combine(date.today(), inicio_noturno)).total_seconds() / 3600
                    
                    if hora_fim > noturno_inicio:  # Termina depois das 20h
                        inicio_noturno = noturno_inicio
                        fim_noturno = min(hora_fim, time(23, 59, 59))
                        horas_noturnas += (datetime.combine(date.today(), fim_noturno) - 
                                         datetime.combine(date.today(), inicio_noturno)).total_seconds() / 3600
            
            # Se o trabalho cruza a meia-noite (trabalho noturno)
            else:
                # Período noturno completo
                horas_noturnas = (datetime.combine(date.today(), hora_fim) + 
                                timedelta(days=1) - 
                                datetime.combine(date.today(), hora_inicio)).total_seconds() / 3600
            
            return max(0, horas_diurnas), max(0, horas_noturnas)
        
        # Calcular horas por período
        horas_diurnas, horas_noturnas = calcular_horas_por_periodo(hora_inicio_time, hora_fim_time)
        
        # Determinar tipo baseado na predominância
        sugestao_misto = None
        
        if horas_noturnas > horas_diurnas:
            if horas_diurnas > 0:
                # Sugerir registro misto se a diferença não for muito grande
                if horas_diurnas >= 1.0:  # Pelo menos 1 hora diurna
                    # Horário padrão baseado no dia da semana
                    weekday = data.weekday()
                    if weekday < 5:  # Segunda a Sexta
                        inicio_expediente = '08:00'
                    elif weekday == 5:  # Sábado
                        inicio_expediente = '08:00'
                    else:  # Domingo
                        inicio_expediente = '08:00'
                    
                    sugestao_misto = {
                        'diurno': {'horas': horas_diurnas, 'inicio': inicio_expediente, 'fim': '20:00'},
                        'noturno': {'horas': horas_noturnas, 'inicio': '20:00', 'fim': inicio_expediente}
                    }
                return 'MISTO', f'Horas Mistas ({horas_diurnas:.1f}h diurnas + {horas_noturnas:.1f}h noturnas)', sugestao_misto
            else:
                return 'NO', f'Horário Noturno ({horas_noturnas:.1f}h)', None
        elif horas_diurnas > 0:
            if horas_noturnas > 0:
                # Sugerir registro misto se a diferença não for muito grande
                if horas_noturnas >= 1.0:  # Pelo menos 1 hora noturna
                    # Horário padrão baseado no dia da semana
                    weekday = data.weekday()
                    if weekday < 5:  # Segunda a Sexta
                        inicio_expediente = '08:00'
                    elif weekday == 5:  # Sábado
                        inicio_expediente = '08:00'
                    else:  # Domingo
                        inicio_expediente = '08:00'
                    
                    sugestao_misto = {
                        'diurno': {'horas': horas_diurnas, 'inicio': inicio_expediente, 'fim': '20:00'},
                        'noturno': {'horas': horas_noturnas, 'inicio': '20:00', 'fim': inicio_expediente}
                    }
                return 'MISTO', f'Horas Mistas ({horas_diurnas:.1f}h diurnas + {horas_noturnas:.1f}h noturnas)', sugestao_misto
            else:
                return 'DI', f'Horário Diurno ({horas_diurnas:.1f}h)', None
        else:
            # Fallback para horário noturno se não conseguir calcular
            return 'NO', 'Horário Noturno (cálculo automático)', None

    @classmethod
    def calcular_horas_extras_mistas(cls, funcionario, data, hora_inicio, hora_fim):
        """
        Calcula horas extras mistas com percentuais separados
        Retorna: {'diurno': {...}, 'noturno': {...}, 'total': {...}}
        """
        from datetime import time, datetime, date, timedelta
        
        # Converter strings para time se necessário
        if isinstance(hora_inicio, str):
            hora_inicio_time = time.fromisoformat(hora_inicio)
        else:
            hora_inicio_time = hora_inicio
            
        if isinstance(hora_fim, str):
            hora_fim_time = time.fromisoformat(hora_fim)
        else:
            hora_fim_time = hora_fim
        
        # Calcular horas por período
        def calcular_horas_por_periodo(hora_inicio, hora_fim):
            weekday = data.weekday()
            
            if weekday < 5:  # Segunda a Sexta
                diurno_inicio = time(8, 0)
                diurno_fim = time(20, 0)
                noturno_inicio = time(20, 0)
                noturno_fim = time(8, 0)
            elif weekday == 5:  # Sábado
                diurno_inicio = time(8, 0)
                diurno_fim = time(20, 0)
                noturno_inicio = time(20, 0)
                noturno_fim = time(8, 0)
            else:  # Domingo
                diurno_inicio = time(8, 0)
                diurno_fim = time(20, 0)
                noturno_inicio = time(20, 0)
                noturno_fim = time(8, 0)
            
            horas_diurnas = 0
            horas_noturnas = 0
            
            # Se o trabalho começa e termina no mesmo dia
            if hora_inicio <= hora_fim:
                # Período diurno
                if hora_inicio < diurno_fim and hora_fim > diurno_inicio:
                    inicio_diurno = max(hora_inicio, diurno_inicio)
                    fim_diurno = min(hora_fim, diurno_fim)
                    horas_diurnas = (datetime.combine(date.today(), fim_diurno) - 
                                   datetime.combine(date.today(), inicio_diurno)).total_seconds() / 3600
                
                # Período noturno
                if hora_fim > noturno_inicio:
                    inicio_noturno = max(hora_inicio, noturno_inicio)
                    fim_noturno = min(hora_fim, time(23, 59, 59))
                    if inicio_noturno < fim_noturno:
                        horas_noturnas = (datetime.combine(date.today(), fim_noturno) - 
                                         datetime.combine(date.today(), inicio_noturno)).total_seconds() / 3600
            
            # Se o trabalho cruza a meia-noite
            else:
                horas_noturnas = (datetime.combine(date.today(), hora_fim) + 
                                timedelta(days=1) - 
                                datetime.combine(date.today(), hora_inicio)).total_seconds() / 3600
            
            return max(0, horas_diurnas), max(0, horas_noturnas)
        
        # Calcular horas por período
        horas_diurnas, horas_noturnas = calcular_horas_por_periodo(hora_inicio_time, hora_fim_time)
        
        # Obter remuneração por hora do funcionário
        remuneracao_hora = funcionario.get_remuneracao_por_hora_teorica()
        if not remuneracao_hora:
            remuneracao_hora = funcionario.get_remuneracao_por_hora()
        
        if not remuneracao_hora:
            return None
        
        valor_hora_base = remuneracao_hora.get('remuneracao_por_hora_teorica') or remuneracao_hora.get('remuneracao_por_hora')
        
        if not valor_hora_base:
            return None
        
        # Calcular valores para cada período
        resultado = {
            'diurno': None,
            'noturno': None,
            'total': {
                'horas_totais': horas_diurnas + horas_noturnas,
                'valor_total': 0
            }
        }
        
        # Período Diurno (50%)
        if horas_diurnas > 0:
            valor_hora_diurno = valor_hora_base * 0.50  # 50%
            valor_total_diurno = horas_diurnas * valor_hora_diurno
            
            resultado['diurno'] = {
                'horas': horas_diurnas,
                'valor_por_hora': valor_hora_diurno,
                'valor_total': valor_total_diurno,
                'percentual': 0.50,
                'tipo': 'DI',
                'tipo_display': 'Diurno'
            }
            resultado['total']['valor_total'] += valor_total_diurno
        
        # Período Noturno (100%)
        if horas_noturnas > 0:
            valor_hora_noturno = valor_hora_base * 1.00  # 100%
            valor_total_noturno = horas_noturnas * valor_hora_noturno
            
            resultado['noturno'] = {
                'horas': horas_noturnas,
                'valor_por_hora': valor_hora_noturno,
                'valor_total': valor_total_noturno,
                'percentual': 1.00,
                'tipo': 'NO',
                'tipo_display': 'Noturno'
            }
            resultado['total']['valor_total'] += valor_total_noturno
        
        return resultado


class BeneficioSalarial(models.Model):
    """Modelo para gerenciar benefícios salariais"""
    TIPO_CHOICES = [
        # Benefícios Monetários
        ('SB', 'Subsídio de Alimentação'),
        ('ST', 'Subsídio de Transporte'),
        ('SH', 'Subsídio de Habitação'),
        ('BO', 'Bónus'),
        ('PR', 'Prémio'),
        ('CO', 'Comissão'),
        ('HE', 'Horas Extras'),
        # Benefícios Não Monetários
        ('PS', 'Plano de Saúde'),
        ('GI', 'Acesso ao Ginásio'),
        ('ES', 'Estacionamento'),
        ('RE', 'Refeições'),
        ('TR', 'Transporte Empresarial'),
        ('ED', 'Educação/Formação'),
        ('TE', 'Tecnologia/Equipamentos'),
        ('FE', 'Férias Extras'),
        ('FL', 'Flexibilidade Horária'),
        ('HO', 'Home Office'),
        ('OU', 'Outro'),
    ]
    
    TIPO_VALOR_CHOICES = [
        ('FIXO', 'Valor Fixo'),
        ('PERCENTUAL', 'Percentual'),
        ('NAO_MONETARIO', 'Não Monetário'),
    ]
    
    BASE_CALCULO_CHOICES = [
        ('SALARIO_BASE', 'Salário Base'),
        ('SALARIO_BRUTO', 'Salário Bruto'),
        ('SALARIO_LIQUIDO', 'Salário Líquido'),
        ('REMUNERACAO_TOTAL', 'Remuneração Total'),
        ('HORAS_TRABALHADAS', 'Horas Trabalhadas'),
        ('DIAS_TRABALHADOS', 'Dias Trabalhados'),
        ('PRODUCAO', 'Produção'),
        ('VENDAS', 'Vendas'),
        ('OUTRO', 'Outro'),
    ]
    
    nome = models.CharField(max_length=100, verbose_name="Nome do Benefício")
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código")
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, verbose_name="Tipo")
    tipo_valor = models.CharField(max_length=15, choices=TIPO_VALOR_CHOICES, default='FIXO', verbose_name="Tipo de Valor")
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Valor")
    base_calculo = models.CharField(max_length=20, choices=BASE_CALCULO_CHOICES, default='SALARIO_BASE', verbose_name="Base de Cálculo")
    base_calculo_personalizada = models.CharField(max_length=50, blank=True, verbose_name="Base de Cálculo Personalizada")
    
    # Campos específicos para benefícios não monetários
    fornecedor = models.CharField(max_length=100, blank=True, verbose_name="Fornecedor/Prestador")
    localizacao = models.CharField(max_length=200, blank=True, verbose_name="Localização")
    horario_funcionamento = models.CharField(max_length=100, blank=True, verbose_name="Horário de Funcionamento")
    limite_uso = models.CharField(max_length=100, blank=True, verbose_name="Limite de Uso")
    documento_necessario = models.CharField(max_length=200, blank=True, verbose_name="Documentos Necessários")
    contato_responsavel = models.CharField(max_length=100, blank=True, verbose_name="Contacto do Responsável")
    telefone_contato = models.CharField(max_length=20, blank=True, verbose_name="Telefone de Contacto")
    email_contato = models.EmailField(blank=True, verbose_name="Email de Contacto")
    
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Benefício"
        verbose_name_plural = "Benefícios"
        ordering = ['nome']
    
    def save(self, *args, **kwargs):
        # Se não houver código ou estiver vazio, gera um código automático
        if not self.codigo or self.codigo.strip() == '':
            # Pega o prefixo baseado no tipo
            prefixo = self.tipo if hasattr(self, 'tipo') and self.tipo else 'BN'
            
            # Encontra o próximo número sequencial disponível
            ultimo = BeneficioSalarial.objects.filter(
                codigo__startswith=prefixo
            ).order_by('-codigo').first()
            
            if ultimo and ultimo.codigo.startswith(prefixo):
                try:
                    # Tenta extrair o número e incrementar
                    num = int(ultimo.codigo[len(prefixo):]) + 1
                except (ValueError, IndexError):
                    # Se não conseguir extrair o número, começa do 1
                    num = 1
            else:
                # Primeiro item deste tipo
                num = 1
                
            # Formata o código (ex: SA001, HE005, etc.)
            self.codigo = f"{prefixo}{num:03d}"
        
        super().save(*args, **kwargs)
    
    @property
    def is_nao_monetario(self):
        """Verifica se é um benefício não monetário"""
        return self.tipo_valor == 'NAO_MONETARIO'
    
    @property
    def is_monetario(self):
        """Verifica se é um benefício monetário"""
        return self.tipo_valor in ['FIXO', 'PERCENTUAL']
    
    def get_tipo_display_detailed(self):
        """Retorna o tipo com indicação se é monetário ou não"""
        tipo_display = self.get_tipo_display()
        if self.is_nao_monetario:
            return f"{tipo_display} (Não Monetário)"
        return f"{tipo_display} (Monetário)"
    
    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class DescontoSalarial(models.Model):
    """Modelo para gerenciar descontos salariais"""
    TIPO_CHOICES = [
        ('IR', 'Imposto de Renda'),
        ('IN', 'INSS Moçambique'),
        ('SS', 'Segurança Social'),
        ('EM', 'Empréstimo'),
        ('AD', 'Adiantamento'),
        ('FA', 'Falta'),
        ('AT', 'Atraso'),
        ('OU', 'Outro'),
    ]
    
    TIPO_VALOR_CHOICES = [
        ('FIXO', 'Valor Fixo'),
        ('PERCENTUAL', 'Percentual'),
        ('NAO_MONETARIO', 'Não Monetário'),
    ]
    
    BASE_CALCULO_CHOICES = [
        ('SALARIO_BASE', 'Salário Base'),
        ('SALARIO_BRUTO', 'Salário Bruto'),
        ('SALARIO_LIQUIDO', 'Salário Líquido'),
        ('REMUNERACAO_TOTAL', 'Remuneração Total'),
        ('HORAS_TRABALHADAS', 'Horas Trabalhadas'),
        ('DIAS_TRABALHADOS', 'Dias Trabalhados'),
        ('PRODUCAO', 'Produção'),
        ('VENDAS', 'Vendas'),
        ('OUTRO', 'Outro'),
    ]
    
    nome = models.CharField(max_length=100, verbose_name="Nome do Desconto")
    codigo = models.CharField(max_length=10, unique=True, verbose_name="Código")
    tipo = models.CharField(max_length=2, choices=TIPO_CHOICES, verbose_name="Tipo")
    tipo_valor = models.CharField(max_length=15, choices=TIPO_VALOR_CHOICES, default='FIXO', verbose_name="Tipo de Valor")
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Valor")
    base_calculo = models.CharField(max_length=20, choices=BASE_CALCULO_CHOICES, default='SALARIO_BASE', verbose_name="Base de Cálculo")
    base_calculo_personalizada = models.CharField(max_length=50, blank=True, verbose_name="Base de Cálculo Personalizada")
    
    # Campos para isenções e faixas
    valor_minimo_isencao = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Valor Mínimo para Isenção",
        help_text="Valor mínimo do salário para aplicar o desconto (ex: 19000 para IRPS)"
    )
    valor_maximo_isencao = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Valor Máximo para Isenção",
        help_text="Valor máximo do salário para isenção total (opcional)"
    )
    aplicar_automaticamente = models.BooleanField(
        default=False, 
        verbose_name="Aplicar Automaticamente",
        help_text="Se deve ser aplicado automaticamente na folha de salário"
    )
    
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    
    class Meta:
        verbose_name = "Desconto Salarial"
        verbose_name_plural = "Descontos Salariais"
        ordering = ['nome']
    
    def save(self, *args, **kwargs):
        # Se não houver código ou estiver vazio, gera um código automático
        if not self.codigo or self.codigo.strip() == '':
            # Pega o prefixo baseado no tipo
            prefixo = self.tipo if hasattr(self, 'tipo') and self.tipo else 'DC'
            
            # Encontra o próximo número sequencial disponível
            ultimo = DescontoSalarial.objects.filter(
                codigo__startswith=prefixo
            ).order_by('-codigo').first()
            
            if ultimo and ultimo.codigo.startswith(prefixo):
                try:
                    # Tenta extrair o número e incrementar
                    num = int(ultimo.codigo[len(prefixo):]) + 1
                except (ValueError, IndexError):
                    # Se não conseguir extrair o número, começa do 1
                    num = 1
            else:
                # Primeiro item deste tipo
                num = 1
                
            # Formata o código (ex: IR001, IN002, etc.)
            self.codigo = f"{prefixo}{num:03d}"
        
        super().save(*args, **kwargs)
    
    def calcular_valor_desconto(self, salario_base, salario_bruto, salario_liquido):
        """Calcula o valor do desconto baseado no tipo e base de cálculo"""
        
        # Verificar se deve aplicar o desconto (isenção)
        if not self.deve_aplicar_desconto(salario_bruto):
            return Decimal('0.00')
        
        # Determinar base de cálculo
        if self.base_calculo == 'SALARIO_BASE':
            base = salario_base
        elif self.base_calculo == 'SALARIO_BRUTO':
            base = salario_bruto
        elif self.base_calculo == 'SALARIO_LIQUIDO':
            base = salario_liquido
        else:
            base = salario_bruto  # Padrão
        
        # Calcular valor do desconto
        if self.tipo_valor == 'FIXO':
            return Decimal(str(self.valor))
        elif self.tipo_valor == 'PERCENTUAL':
            percentual = Decimal(str(self.valor)) / Decimal('100')
            return Decimal(str(base)) * percentual
        else:
            return Decimal('0.00')
    
    def deve_aplicar_desconto(self, salario_bruto):
        """Verifica se o desconto deve ser aplicado baseado nas regras de isenção"""
        # Se não há valor mínimo de isenção, sempre aplica
        if self.valor_minimo_isencao <= 0:
            return True
        
        # Se o salário é menor que o valor mínimo, não aplica (isenção)
        if Decimal(str(salario_bruto)) < Decimal(str(self.valor_minimo_isencao)):
            return False
        
        # Se há valor máximo de isenção e o salário é maior, não aplica
        if self.valor_maximo_isencao > 0 and Decimal(str(salario_bruto)) > Decimal(str(self.valor_maximo_isencao)):
            return False
        
        return True
    
    def get_descricao_isencao(self):
        """Retorna descrição das regras de isenção"""
        if Decimal(str(self.valor_minimo_isencao)) <= 0:
            return "Sem isenção"
        
        if Decimal(str(self.valor_maximo_isencao)) > 0:
            return f"Isento até {self.valor_minimo_isencao} MT e acima de {self.valor_maximo_isencao} MT"
        else:
            return f"Isento até {self.valor_minimo_isencao} MT"
    
    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class Salario(models.Model):
    """Modelo para gerenciar salários dos funcionários"""
    STATUS_CHOICES = [
        ('AT', 'Ativo'),
        ('IN', 'Inativo'),
        ('SU', 'Suspenso'),
    ]
    
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, verbose_name="Funcionário")
    valor_base = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Base")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de Fim")
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='AT', verbose_name="Status")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = "Salário"
        verbose_name_plural = "Salários"
        ordering = ['-data_inicio', 'funcionario']
    
    def save(self, *args, **kwargs):
        """Override save para validações adicionais"""
        super().save(*args, **kwargs)
        
        # Validações podem ser adicionadas aqui no futuro
        pass
    
    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.valor_base} MT"
    
    @property
    def salario_liquido(self):
        """Calcula o salário líquido considerando benefícios e descontos"""
        total_beneficios = sum([b.valor for b in self.beneficios.all()])
        total_descontos = sum([d.valor for d in self.descontos.all()])
        return self.valor_base + total_beneficios - total_descontos


class SalarioBeneficio(models.Model):
    """Modelo para associar benefícios aos salários"""
    salario = models.ForeignKey(Salario, on_delete=models.CASCADE, related_name='beneficios', verbose_name="Salário")
    beneficio = models.ForeignKey(BeneficioSalarial, on_delete=models.CASCADE, verbose_name="Benefício")
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Valor")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_aplicacao = models.DateField(auto_now_add=True, verbose_name="Data de Aplicação")
    
    class Meta:
        verbose_name = "Benefício do Salário"
        verbose_name_plural = "Benefícios do Salário"
        unique_together = ['salario', 'beneficio']
    
    def __str__(self):
        return f"{self.salario.funcionario.nome_completo} - {self.beneficio.nome}"


class SalarioDesconto(models.Model):
    """Modelo para associar descontos aos salários"""
    salario = models.ForeignKey(Salario, on_delete=models.CASCADE, related_name='descontos', verbose_name="Salário")
    desconto = models.ForeignKey(DescontoSalarial, on_delete=models.CASCADE, verbose_name="Desconto")
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Valor")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_aplicacao = models.DateField(auto_now_add=True, verbose_name="Data de Aplicação")
    
    class Meta:
        verbose_name = "Desconto do Salário"
        verbose_name_plural = "Descontos do Salário"
        unique_together = ['salario', 'desconto']
    
    def __str__(self):
        return f"{self.salario.funcionario.nome_completo} - {self.desconto.nome}"


class Treinamento(models.Model):
    """Modelo para gerenciar treinamentos e formações"""
    
    TIPO_CHOICES = [
        ('INTERNO', 'Interno'),
        ('EXTERNO', 'Externo'),
        ('ONLINE', 'Online'),
        ('PRESENCIAL', 'Presencial'),
        ('HIBRIDO', 'Híbrido'),
    ]
    
    STATUS_CHOICES = [
        ('PLANEJADO', 'Planificado'),
        ('EM_ANDAMENTO', 'Em Curso'),
        ('CONCLUIDO', 'Concluído'),
        ('CANCELADO', 'Cancelado'),
        ('ADIADO', 'Adiado'),
    ]
    
    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    # Informações básicas
    nome = models.CharField(max_length=200, verbose_name="Nome do Treinamento")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='INTERNO', verbose_name="Tipo")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANEJADO', verbose_name="Status")
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default='MEDIA', verbose_name="Prioridade")
    
    # Datas
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Fim")
    data_limite_inscricao = models.DateField(blank=True, null=True, verbose_name="Data Limite de Inscrição")
    
    # Local e instrutor
    local = models.CharField(max_length=200, blank=True, verbose_name="Local")
    instrutor = models.CharField(max_length=200, blank=True, verbose_name="Instrutor/Facilitador")
    instituicao = models.CharField(max_length=200, blank=True, verbose_name="Instituição/Fornecedor")
    
    # Capacidade e custos
    capacidade_maxima = models.PositiveIntegerField(default=20, verbose_name="Capacidade Máxima")
    custo_por_participante = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Custo por Participante")
    custo_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Custo Total")
    
    # Requisitos e objetivos
    requisitos = models.TextField(blank=True, verbose_name="Requisitos")
    objetivos = models.TextField(blank=True, verbose_name="Objetivos")
    conteudo_programatico = models.TextField(blank=True, verbose_name="Conteúdo Programático")
    
    # Certificação
    emite_certificado = models.BooleanField(default=True, verbose_name="Emite Certificado")
    carga_horaria = models.PositiveIntegerField(default=0, verbose_name="Carga Horária (horas)")
    
    # Controle
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Treinamento'
        verbose_name_plural = 'Treinamentos'
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.nome} - {self.get_status_display()}"
    
    @property
    def duracao_dias(self):
        """Calcula a duração em dias"""
        if self.data_inicio and self.data_fim:
            return (self.data_fim - self.data_inicio).days + 1
        return 0
    
    @property
    def vagas_disponiveis(self):
        """Calcula vagas disponíveis"""
        inscritos = self.inscricoes.filter(status='CONFIRMADA').count()
        return max(0, self.capacidade_maxima - inscritos)
    
    @property
    def percentual_preenchimento(self):
        """Calcula percentual de preenchimento"""
        if self.capacidade_maxima > 0:
            inscritos = self.inscricoes.filter(status='CONFIRMADA').count()
            return (inscritos / self.capacidade_maxima) * 100
        return 0


class InscricaoTreinamento(models.Model):
    """Modelo para gerenciar inscrições em treinamentos"""
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('CONFIRMADA', 'Confirmada'),
        ('CANCELADA', 'Cancelada'),
        ('CONCLUIDA', 'Concluída'),
        ('FALTOSA', 'Faltosa'),
    ]
    
    treinamento = models.ForeignKey(Treinamento, on_delete=models.CASCADE, related_name='inscricoes', verbose_name="Treinamento")
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, verbose_name="Funcionário")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE', verbose_name="Status")
    
    # Avaliação
    nota_final = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Nota Final")
    frequencia_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="Frequência (%)")
    aprovado = models.BooleanField(default=False, verbose_name="Aprovado")
    
    # Observações
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_inscricao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Inscrição")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = 'Inscrição em Treinamento'
        verbose_name_plural = 'Inscrições em Treinamentos'
        unique_together = ['treinamento', 'funcionario']
        ordering = ['-data_inscricao']
    
    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.treinamento.nome}"
    
    def calcular_aprovacao(self):
        """Calcula se o funcionário foi aprovado baseado na nota e frequência"""
        if self.nota_final and self.frequencia_percentual:
            self.aprovado = (
                self.nota_final >= 7.0 and 
                self.frequencia_percentual >= 75.0
            )
            self.save()
        return self.aprovado


class CriterioAvaliacao(models.Model):
    """Modelo para critérios de avaliação de desempenho"""
    nome = models.CharField(max_length=200, verbose_name="Nome do Critério")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    peso = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name="Peso")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Critério de Avaliação"
        verbose_name_plural = "Critérios de Avaliação"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} (Peso: {self.peso})"


class AvaliacaoDesempenho(models.Model):
    """Modelo para avaliações de desempenho de funcionários"""
    TIPO_CHOICES = [
        ('ANUAL', 'Avaliação Anual'),
        ('SEMESTRAL', 'Avaliação Semestral'),
        ('TRIMESTRAL', 'Avaliação Trimestral'),
        ('MENSAL', 'Avaliação Mensal'),
        ('PERIODICA', 'Avaliação Periódica'),
        ('ESPECIAL', 'Avaliação Especial'),
    ]
    
    STATUS_CHOICES = [
        ('PLANEJADA', 'Planificada'),
        ('EM_ANDAMENTO', 'Em Curso'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    CLASSIFICACAO_CHOICES = [
        ('EXCELENTE', 'Excelente'),
        ('MUITO_BOM', 'Muito Bom'),
        ('BOM', 'Bom'),
        ('SATISFATORIO', 'Satisfatório'),
        ('REGULAR', 'Regular'),
        ('INSATISFATORIO', 'Insatisfatório'),
    ]

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='avaliacoes', verbose_name="Funcionário")
    avaliador = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='avaliacoes_realizadas', verbose_name="Avaliador")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='ANUAL', verbose_name="Tipo de Avaliação")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANEJADA', verbose_name="Status")
    
    # Período da avaliação
    data_inicio = models.DateField(verbose_name="Data de Início do Período")
    data_fim = models.DateField(verbose_name="Data de Fim do Período")
    data_avaliacao = models.DateField(blank=True, null=True, verbose_name="Data da Avaliação")
    
    # Resultados
    nota_geral = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Nota Geral")
    classificacao = models.CharField(max_length=50, choices=CLASSIFICACAO_CHOICES, blank=True, verbose_name="Classificação")
    
    # Metas e objetivos
    metas_estabelecidas = models.TextField(blank=True, verbose_name="Metas Estabelecidas")
    metas_alcancadas = models.TextField(blank=True, verbose_name="Metas Alcançadas")
    pontos_fortes = models.TextField(blank=True, verbose_name="Pontos Fortes")
    pontos_melhoria = models.TextField(blank=True, verbose_name="Pontos de Melhoria")
    
    # Observações
    observacoes_avaliador = models.TextField(blank=True, verbose_name="Observações do Avaliador")
    observacoes_funcionario = models.TextField(blank=True, verbose_name="Observações do Funcionário")
    plano_desenvolvimento = models.TextField(blank=True, verbose_name="Plano de Desenvolvimento")
    
    # Controle
    aprovada = models.BooleanField(default=False, verbose_name="Aprovada")
    data_aprovacao = models.DateTimeField(blank=True, null=True, verbose_name="Data de Aprovação")
    aprovada_por = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, blank=True, null=True, related_name='avaliacoes_aprovadas', verbose_name="Aprovada por")
    
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Avaliação de Desempenho"
        verbose_name_plural = "Avaliações de Desempenho"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.get_tipo_display()} ({self.data_inicio.year})"

    @property
    def duracao_dias(self):
        """Retorna a duração do período em dias"""
        if self.data_inicio and self.data_fim:
            return (self.data_fim - self.data_inicio).days + 1
        return 0

    @property
    def status_display(self):
        """Retorna o status formatado"""
        return self.get_status_display()

    def calcular_nota_geral(self):
        """Calcula a nota geral baseada nos critérios avaliados"""
        criterios = self.criterios_avaliados.all()
        if not criterios.exists():
            return None
        
        total_peso = sum(c.criterio.peso for c in criterios)
        if total_peso == 0:
            return None
        
        nota_ponderada = sum(c.nota * c.criterio.peso for c in criterios)
        return round(nota_ponderada / total_peso, 2)

    def definir_classificacao(self):
        """Define a classificação baseada na nota geral"""
        if not self.nota_geral:
            return ""
        
        if self.nota_geral >= 9.0:
            return "EXCELENTE"
        elif self.nota_geral >= 8.0:
            return "MUITO_BOM"
        elif self.nota_geral >= 7.0:
            return "BOM"
        elif self.nota_geral >= 6.0:
            return "SATISFATORIO"
        elif self.nota_geral >= 5.0:
            return "REGULAR"
        else:
            return "INSATISFATORIO"

    def actualizar_status_automatico(self):
        """Actualiza o status automaticamente baseado em critérios"""
        from django.utils import timezone
        from datetime import date
        
        hoje = timezone.now().date()
        status_anterior = self.status
        
        # Se está cancelada, não alterar
        if self.status == 'CANCELADA':
            return False
            
        # Se a data de início chegou e ainda está planificada
        if self.status == 'PLANEJADA' and self.data_inicio <= hoje:
            self.status = 'EM_ANDAMENTO'
            self.data_avaliacao = hoje
            self.save(update_fields=['status', 'data_avaliacao'])
            return True
            
        # Se está em andamento e a data fim passou
        elif self.status == 'EM_ANDAMENTO' and self.data_fim < hoje:
            # Verificar se tem critérios avaliados
            criterios_avaliados = self.criterios_avaliados.exists()
            if criterios_avaliados:
                self.status = 'CONCLUIDA'
                if not self.data_avaliacao:
                    self.data_avaliacao = hoje
                self.save(update_fields=['status', 'data_avaliacao'])
                return True
                
        # Se tem nota geral e critérios avaliados, pode ser concluída
        elif (self.status == 'EM_ANDAMENTO' and 
              self.nota_geral is not None and 
              self.criterios_avaliados.exists()):
            self.status = 'CONCLUIDA'
            if not self.data_avaliacao:
                self.data_avaliacao = hoje
            self.save(update_fields=['status', 'data_avaliacao'])
            return True
            
        return False

    def pode_ser_concluida(self):
        """Verifica se a avaliação pode ser concluída"""
        return (
            self.status in ['PLANEJADA', 'EM_ANDAMENTO'] and
            self.nota_geral is not None and
            self.criterios_avaliados.exists()
        )

    def marcar_como_concluida(self):
        """Marca a avaliação como concluída se os critérios forem atendidos"""
        if self.pode_ser_concluida():
            from django.utils import timezone
            self.status = 'CONCLUIDA'
            if not self.data_avaliacao:
                self.data_avaliacao = timezone.now().date()
            self.save(update_fields=['status', 'data_avaliacao'])
            return True
        return False


class CriterioAvaliado(models.Model):
    """Modelo para critérios específicos avaliados em uma avaliação"""
    avaliacao = models.ForeignKey(AvaliacaoDesempenho, on_delete=models.CASCADE, related_name='criterios_avaliados', verbose_name="Avaliação")
    criterio = models.ForeignKey(CriterioAvaliacao, on_delete=models.CASCADE, verbose_name="Critério")
    nota = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Nota")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    data_avaliacao = models.DateTimeField(auto_now_add=True, verbose_name="Data da Avaliação")

    class Meta:
        verbose_name = "Critério Avaliado"
        verbose_name_plural = "Critérios Avaliados"
        unique_together = ['avaliacao', 'criterio']

    def __str__(self):
        return f"{self.avaliacao.funcionario.nome_completo} - {self.criterio.nome}: {self.nota}"

    @property
    def nota_ponderada(self):
        """Retorna a nota ponderada pelo peso do critério"""
        return round(self.nota * self.criterio.peso, 2)


class FolhaSalarial(models.Model):
    """Modelo para gerenciar folhas de pagamento"""
    
    STATUS_CHOICES = [
        ('ABERTA', 'Aberta'),
        ('FECHADA', 'Fechada'),
        ('PAGA', 'Paga'),
    ]
    
    mes_referencia = models.DateField(verbose_name="Mês de Referência")
    data_fechamento = models.DateField(null=True, blank=True, verbose_name="Data de Fechamento")
    data_pagamento = models.DateField(null=True, blank=True, verbose_name="Data de Pagamento")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ABERTA', verbose_name="Status")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")
    total_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Total Bruto")
    total_descontos = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Total Descontos")
    total_liquido = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Total Líquido")
    total_funcionarios = models.IntegerField(default=0, verbose_name="Total de Funcionários")
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Folha Salarial"
        verbose_name_plural = "Folhas Salariais"
        unique_together = ['mes_referencia']

    def __str__(self):
        return f"Folha {self.mes_referencia.strftime('%m/%Y')} - {self.get_status_display()}"

    def calcular_totais(self):
        """Calcula os totais da folha baseado nos funcionários"""
        funcionarios_folha = self.funcionarios_folha.all()
        
        # Calcular horas trabalhadas para cada funcionário
        for funcionario_folha in funcionarios_folha:
            funcionario_folha.calcular_horas_trabalhadas()
            funcionario_folha.calcular_salario()
        
        # Recalcular totais
        self.total_bruto = sum(f.salario_bruto for f in funcionarios_folha)
        self.total_descontos = sum(f.total_descontos for f in funcionarios_folha)
        self.total_liquido = sum(f.salario_liquido for f in funcionarios_folha)
        self.total_funcionarios = funcionarios_folha.count()
        
        self.save()

    def validar_antes_fechar(self):
        """Valida se a folha pode ser fechada"""
        from datetime import date
        from django.db.models import Q
        
        erros = []
        avisos = []
        
        # 1. Verificar se há funcionários na folha
        funcionarios_folha = self.funcionarios_folha.all()
        if not funcionarios_folha.exists():
            erros.append("Não há funcionários na folha")
            return {'valido': False, 'erros': erros, 'avisos': avisos}
        
        # 2. Verificar se todos os funcionários têm salário base
        funcionarios_sem_salario = funcionarios_folha.filter(salario_base__lte=0)
        if funcionarios_sem_salario.exists():
            erros.append(f"Funcionários sem salário: {', '.join([f.nome_completo for f in funcionarios_sem_salario])}")
        
        # 3. Verificar se todos os funcionários têm dados de presença
        funcionarios_sem_presenca = []
        for func_folha in funcionarios_folha:
            if func_folha.dias_trabalhados == 0 and func_folha.horas_trabalhadas == 0:
                funcionarios_sem_presenca.append(func_folha.funcionario.nome_completo)
        
        if funcionarios_sem_presenca:
            avisos.append(f"Funcionários sem presenças registradas: {', '.join(funcionarios_sem_presenca)}")
        
        # 4. Verificar se há funcionários com salário líquido negativo
        funcionarios_salario_negativo = funcionarios_folha.filter(salario_liquido__lt=0)
        if funcionarios_salario_negativo.exists():
            avisos.append(f"Funcionários com salário líquido negativo: {', '.join([f.nome_completo for f in funcionarios_salario_negativo])}")
        
        # 5. Verificar se os totais estão calculados
        if self.total_bruto == 0 and self.total_liquido == 0:
            avisos.append("Totais da folha não foram calculados")
        
        # 6. Verificar se há funcionários ativos que não estão na folha
        funcionarios_ativos = Funcionario.objects.filter(status='AT')
        funcionarios_na_folha = set(func_folha.funcionario.id for func_folha in funcionarios_folha)
        funcionarios_ativos_ids = set(funcionario.id for funcionario in funcionarios_ativos)
        funcionarios_faltando = funcionarios_ativos_ids - funcionarios_na_folha
        
        if funcionarios_faltando:
            funcionarios_faltando_nomes = [Funcionario.objects.get(id=fid).nome_completo for fid in funcionarios_faltando]
            avisos.append(f"Funcionários ativos não incluídos na folha: {', '.join(funcionarios_faltando_nomes)}")
        
        return {
            'valido': len(erros) == 0,
            'erros': erros,
            'avisos': avisos,
            'total_funcionarios': funcionarios_folha.count(),
            'funcionarios_sem_salario': funcionarios_sem_salario.count(),
            'funcionarios_sem_presenca': len(funcionarios_sem_presenca),
            'funcionarios_salario_negativo': funcionarios_salario_negativo.count()
        }

    def fechar_folha(self, user=None, observacoes=''):
        """Fecha a folha com validações"""
        from datetime import date
        
        # Validar antes de fechar
        validacao = self.validar_antes_fechar()
        
        if not validacao['valido']:
            raise ValidationError(f"Não é possível fechar a folha: {'; '.join(validacao['erros'])}")
        
        # Recalcular totais antes de fechar
        self.calcular_totais()
        
        # Fechar a folha
        self.status = 'FECHADA'
        self.data_fechamento = date.today()
        
        if observacoes:
            if self.observacoes:
                self.observacoes += f"\n\nFechamento: {observacoes}"
            else:
                self.observacoes = f"Fechamento: {observacoes}"
        
        self.save()
        
        return {
            'sucesso': True,
            'data_fechamento': self.data_fechamento,
            'avisos': validacao['avisos'],
            'total_bruto': self.total_bruto,
            'total_liquido': self.total_liquido,
            'total_funcionarios': self.total_funcionarios
        }

    def reabrir_folha(self, user=None, motivo=''):
        """Reabre uma folha fechada"""
        if self.status != 'FECHADA':
            raise ValidationError("Apenas folhas fechadas podem ser reabertas")
        
        self.status = 'ABERTA'
        self.data_fechamento = None
        
        if motivo:
            if self.observacoes:
                self.observacoes += f"\n\nReabertura: {motivo}"
            else:
                self.observacoes = f"Reabertura: {motivo}"
        
        self.save()
        
        return {
            'sucesso': True,
            'status': self.status,
            'motivo': motivo
        }

    def marcar_como_paga(self, data_pagamento=None, observacoes=''):
        """Marca a folha como paga"""
        from datetime import date
        
        if self.status != 'FECHADA':
            raise ValidationError("Apenas folhas fechadas podem ser marcadas como pagas")
        
        self.status = 'PAGA'
        self.data_pagamento = data_pagamento or date.today()
        
        if observacoes:
            if self.observacoes:
                self.observacoes += f"\n\nPagamento: {observacoes}"
            else:
                self.observacoes = f"Pagamento: {observacoes}"
        
        self.save()
        
        return {
            'sucesso': True,
            'data_pagamento': self.data_pagamento,
            'status': self.status
        }

    def pode_editar(self):
        """Verifica se a folha pode ser editada"""
        return self.status == 'ABERTA'

    def pode_fechar(self):
        """Verifica se a folha pode ser fechada"""
        return self.status == 'ABERTA'

    def pode_reabrir(self):
        """Verifica se a folha pode ser reaberta"""
        return self.status == 'FECHADA'

    def pode_marcar_paga(self):
        """Verifica se a folha pode ser marcada como paga"""
        return self.status == 'FECHADA'

    def get_resumo_fechamento(self):
        """Retorna resumo para fechamento"""
        funcionarios_folha = self.funcionarios_folha.all()
        
        return {
            'mes_referencia': self.mes_referencia.strftime('%B/%Y'),
            'total_funcionarios': funcionarios_folha.count(),
            'total_bruto': self.total_bruto,
            'total_descontos': self.total_descontos,
            'total_liquido': self.total_liquido,
            'funcionarios_sem_presenca': sum(1 for f in funcionarios_folha if f.dias_trabalhados == 0),
            'funcionarios_salario_negativo': funcionarios_folha.filter(salario_liquido__lt=0).count(),
            'status': self.get_status_display()
        }


class Promocao(models.Model):
    """Modelo para gerenciar promoções e aumentos de salário"""
    TIPO_CHOICES = [
        ('PROMOCAO', 'Promoção de Cargo'),
        ('AUMENTO', 'Aumento Salarial'),
        ('BONUS', 'Bônus'),
        ('AJUSTE', 'Ajuste Salarial'),
        ('REVISAO', 'Revisão Anual'),
        ('MERITO', 'Aumento por Mérito'),
        ('INFLACAO', 'Ajuste por Inflação'),
        ('OUTRO', 'Outro'),
    ]
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
        ('IMPLEMENTADO', 'Implementado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, verbose_name="Funcionário")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE', verbose_name="Status")
    
    # Salários
    salario_anterior = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Salário Anterior")
    salario_novo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Salário Novo")
    percentual_aumento = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Percentual de Aumento (%)")
    valor_aumento = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Valor do Aumento")
    
    # Cargos (para promoções)
    cargo_anterior = models.ForeignKey('Cargo', on_delete=models.SET_NULL, null=True, blank=True, related_name='promocoes_anteriores', verbose_name="Cargo Anterior")
    cargo_novo = models.ForeignKey('Cargo', on_delete=models.SET_NULL, null=True, blank=True, related_name='promocoes_novas', verbose_name="Cargo Novo")
    
    # Datas
    data_solicitacao = models.DateField(verbose_name="Data da Solicitação")
    data_aprovacao = models.DateField(null=True, blank=True, verbose_name="Data da Aprovação")
    data_implementacao = models.DateField(null=True, blank=True, verbose_name="Data da Implementação")
    data_efetivacao = models.DateField(null=True, blank=True, verbose_name="Data da Efetivação")
    
    # Motivação e justificativa
    motivo = models.TextField(verbose_name="Motivo da Promoção/Aumento")
    justificativa = models.TextField(blank=True, verbose_name="Justificativa Detalhada")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    
    # Aprovação
    aprovado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='promocoes_aprovadas', verbose_name="Aprovado por")
    rejeitado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='promocoes_rejeitadas', verbose_name="Rejeitado por")
    motivo_rejeicao = models.TextField(blank=True, verbose_name="Motivo da Rejeição")
    
    # Controle
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = "Promoção/Aumento"
        verbose_name_plural = "Promoções/Aumentos"
        ordering = ['-data_solicitacao', 'funcionario']
    
    def save(self, *args, **kwargs):
        """Override save para calcular percentual e valor do aumento"""
        if self.salario_anterior and self.salario_novo:
            self.valor_aumento = self.salario_novo - self.salario_anterior
            if self.salario_anterior > 0:
                self.percentual_aumento = (self.valor_aumento / self.salario_anterior) * 100
        super().save(*args, **kwargs)
    
    def aprovar(self, user):
        """Aprova a promoção/aumento"""
        from datetime import date
        self.status = 'APROVADO'
        self.data_aprovacao = date.today()
        self.aprovado_por = user
        self.save()
    
    def rejeitar(self, user, motivo):
        """Rejeita a promoção/aumento"""
        self.status = 'REJEITADO'
        self.rejeitado_por = user
        self.motivo_rejeicao = motivo
        self.save()
    
    def implementar(self):
        """Implementa a promoção/aumento"""
        from datetime import date
        if self.status == 'APROVADO':
            # Atualizar salário do funcionário
            self.funcionario.salario_atual = self.salario_novo
            
            # Atualizar cargo se for promoção
            if self.cargo_novo:
                self.funcionario.cargo = self.cargo_novo
            
            self.funcionario.save()
            
            # Atualizar status da promoção
            self.status = 'IMPLEMENTADO'
            self.data_implementacao = date.today()
            self.data_efetivacao = date.today()
            self.save()
            
            return True
        return False
    
    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.get_tipo_display()} ({self.get_status_display()})"
    
    @property
    def dias_pendente(self):
        """Calcula quantos dias está pendente"""
        from datetime import date
        if self.status == 'PENDENTE':
            return (date.today() - self.data_solicitacao).days
        return 0
    
    @property
    def pode_aprovar(self):
        """Verifica se pode ser aprovada"""
        return self.status == 'PENDENTE'
    
    @property
    def pode_implementar(self):
        """Verifica se pode ser implementada"""
        return self.status == 'APROVADO'


class PerfilUsuario(models.Model):
    """Perfil de usuário vinculado a funcionário e sucursal"""
    usuario = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuário'
    )
    funcionario = models.ForeignKey(
        'Funcionario',
        on_delete=models.CASCADE,
        related_name='perfil_usuario',
        verbose_name='Funcionário',
        null=True,
        blank=True
    )
    sucursal = models.ForeignKey(
        'Sucursal',
        on_delete=models.PROTECT,
        related_name='usuarios',
        verbose_name='Sucursal',
        null=True,
        blank=True
    )
    is_admin_geral = models.BooleanField(
        default=False,
        verbose_name='Administrador Geral',
        help_text='Acesso total a todas as sucursais'
    )
    permissoes_stock = models.BooleanField(
        default=True,
        verbose_name='Acesso ao Stock',
        help_text='Pode acessar módulo de stock'
    )
    permissoes_rh = models.BooleanField(
        default=True,
        verbose_name='Acesso ao RH',
        help_text='Pode acessar módulo de RH'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'
        ordering = ['usuario__username']

    def __str__(self):
        return f"{self.usuario.username} - {self.sucursal.nome if self.sucursal else 'Sem Sucursal'}"

    @property
    def pode_acessar_todas_sucursais(self):
        """Verifica se o usuário pode acessar todas as sucursais"""
        return self.is_admin_geral or self.usuario.is_superuser

    def get_sucursais_permitidas(self):
        """Retorna as sucursais que o usuário pode acessar"""
        if self.pode_acessar_todas_sucursais:
            from .models_base import Sucursal
            return Sucursal.objects.filter(ativa=True)
        elif self.sucursal:
            return [self.sucursal]
        else:
            return []


class TransferenciaFuncionario(models.Model):
    """Transferência de funcionário entre sucursais/departamentos"""
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
        ('IMPLEMENTADO', 'Implementado'),
        ('CANCELADO', 'Cancelado'),
    ]

    funcionario = models.ForeignKey('Funcionario', on_delete=models.CASCADE, verbose_name='Funcionário')
    # Origem
    sucursal_origem = models.ForeignKey('Sucursal', on_delete=models.PROTECT, related_name='transferencias_origem', verbose_name='Sucursal de Origem')
    departamento_origem = models.ForeignKey('Departamento', on_delete=models.PROTECT, related_name='transferencias_origem', verbose_name='Departamento de Origem')
    # Destino
    sucursal_destino = models.ForeignKey('Sucursal', on_delete=models.PROTECT, related_name='transferencias_destino', verbose_name='Sucursal de Destino')
    departamento_destino = models.ForeignKey('Departamento', on_delete=models.PROTECT, related_name='transferencias_destino', verbose_name='Departamento de Destino')
    cargo_novo = models.ForeignKey('Cargo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Novo Cargo (opcional)')

    # Datas e status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_solicitacao = models.DateField()
    data_aprovacao = models.DateField(null=True, blank=True)
    data_implementacao = models.DateField(null=True, blank=True)
    data_efetivacao = models.DateField(null=True, blank=True)
    data_efetiva = models.DateField(verbose_name='Data Efetiva da Transferência')

    # Descrição
    motivo = models.TextField(verbose_name='Motivo da Transferência')
    observacoes = models.TextField(blank=True)
    motivo_rejeicao = models.TextField(blank=True)

    # Auditoria
    criado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferencias_criadas')
    aprovado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferencias_aprovadas')
    rejeitado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferencias_rejeitadas')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transferência de Funcionário'
        verbose_name_plural = 'Transferências de Funcionários'
        ordering = ['-data_solicitacao']

    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.sucursal_origem} → {self.sucursal_destino} ({self.get_status_display()})"

    @property
    def pode_aprovar(self):
        return self.status == 'PENDENTE'

    @property
    def pode_implementar(self):
        return self.status == 'APROVADO'

class FuncionarioFolha(models.Model):
    """Modelo para funcionários na folha de pagamento"""
    
    folha = models.ForeignKey(FolhaSalarial, on_delete=models.CASCADE, related_name='funcionarios_folha', verbose_name="Folha")
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, verbose_name="Funcionário")
    salario_base = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Salário Base", help_text="SOMENTE LEITURA - Populado automaticamente da tabela Salario")
    salario_bruto = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Salário Bruto")
    total_beneficios = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total Benefícios")
    total_descontos = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Total Descontos")
    desconto_faltas = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Desconto por Faltas")
    salario_liquido = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Salário Líquido")
    horas_trabalhadas = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Horas Trabalhadas")
    horas_extras = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name="Horas Extras")
    dias_trabalhados = models.IntegerField(default=0, verbose_name="Dias Trabalhados")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Funcionário na Folha"
        verbose_name_plural = "Funcionários na Folha"
        unique_together = ['folha', 'funcionario']

    def __str__(self):
        return f"{self.funcionario.nome_completo} - {self.folha.mes_referencia.strftime('%m/%Y')}"

    def save(self, *args, **kwargs):
        """Override save para proteger salario_base"""
        # Sincronizar salario_base com a tabela Salario antes de salvar
        if self.funcionario:
            self.salario_base = self.funcionario.get_salario_atual()
        super().save(*args, **kwargs)
    
    def calcular_salario(self):
        """
        Calcula o salário completo do funcionário para a folha de pagamento.
        
        Este método é crítico para o sistema de RH e executa os seguintes cálculos:
        
        1. Salário Bruto = Salário Base + Benefícios + Horas Extras
        2. Descontos Manuais = Soma dos descontos aplicados manualmente
        3. Desconto por Faltas = Calculado baseado nas presenças do mês
        4. Descontos Automáticos = IRPS, INSS e outros descontos automáticos
        5. Salário Líquido = Salário Bruto - Total de Descontos
        
        IMPORTANTE: Todos os cálculos usam Decimal para precisão financeira.
        
        Returns:
            None (atualiza os campos do objeto)
            
        Raises:
            ValueError: Se houver erro nos cálculos de horas extras
            DatabaseError: Se houver problema ao salvar no banco
        """
        from datetime import timedelta
        from django.db.models import Sum
        
        # Sincronizar salario_base antes de calcular
        self.salario_base = self.funcionario.get_salario_atual()
        
        # Calcular horas trabalhadas e horas extras
        self.calcular_horas_trabalhadas()
        
        # Calcular benefícios
        beneficios = BeneficioFolha.objects.filter(funcionario_folha=self)
        self.total_beneficios = sum(b.valor for b in beneficios)
        
        # Calcular valor total das horas extras do mês
        primeiro_dia = self.folha.mes_referencia.replace(day=1)
        ultimo_dia = (primeiro_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        horas_extras_valor = HorasExtras.objects.filter(
            funcionario=self.funcionario,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia
        ).aggregate(
            total_valor=Sum('valor_total')
        )['total_valor'] or 0
        
        # Salário bruto = base + benefícios + horas extras
        self.salario_bruto = Decimal(str(self.salario_base)) + Decimal(str(self.total_beneficios)) + Decimal(str(horas_extras_valor))
        
        # Calcular descontos manuais
        descontos = DescontoFolha.objects.filter(funcionario_folha=self)
        self.total_descontos = Decimal(str(sum(d.valor for d in descontos)))
        
        # Calcular desconto por faltas não justificadas
        self.desconto_faltas = Decimal(str(self.calcular_desconto_faltas()))
        self.total_descontos = Decimal(str(self.total_descontos)) + Decimal(str(self.desconto_faltas))
        
        # Aplicar descontos automáticos (percentuais e com isenções)
        descontos_automaticos = self.calcular_descontos_automaticos()
        self.total_descontos = Decimal(str(self.total_descontos)) + Decimal(str(descontos_automaticos))
        
        # Salário líquido = bruto - descontos (incluindo faltas e automáticos)
        self.salario_liquido = Decimal(str(self.salario_bruto)) - Decimal(str(self.total_descontos))
        
        self.save()
    
    def calcular_desconto_faltas(self):
        """Calcula desconto por faltas não justificadas"""
        from datetime import timedelta
        from django.db.models import Q
        
        # Obter presenças do mês da folha
        primeiro_dia = self.folha.mes_referencia.replace(day=1)
        ultimo_dia = (primeiro_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Contar faltas que descontam salário
        presencas_faltas = Presenca.objects.filter(
            funcionario=self.funcionario,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia,
            tipo_presenca__desconta_salario=True
        )
        
        total_faltas = presencas_faltas.count()
        
        if total_faltas == 0:
            return 0
        
        # Calcular valor por dia de falta
        # Assumindo que o funcionário deveria trabalhar todos os dias úteis do mês
        dias_uteis_mes = self.calcular_dias_uteis_mes()
        
        if dias_uteis_mes == 0:
            return 0
        
        # Valor por dia = salário base / dias úteis do mês
        valor_por_dia = Decimal(str(self.salario_base)) / Decimal(str(dias_uteis_mes))
        
        # Desconto total = valor por dia × número de faltas
        desconto_total = valor_por_dia * Decimal(str(total_faltas))
        
        return round(desconto_total, 2)
    
    def calcular_dias_uteis_mes(self):
        """Calcula quantos dias úteis há no mês da folha"""
        from datetime import timedelta
        import calendar
        
        # Obter primeiro e último dia do mês
        primeiro_dia = self.folha.mes_referencia.replace(day=1)
        ultimo_dia = calendar.monthrange(
            self.folha.mes_referencia.year, 
            self.folha.mes_referencia.month
        )[1]
        ultimo_dia = self.folha.mes_referencia.replace(day=ultimo_dia)
        
        # Contar dias úteis (segunda a sexta)
        dias_uteis = 0
        data_atual = primeiro_dia
        
        while data_atual <= ultimo_dia:
            # 0 = segunda, 6 = domingo
            if data_atual.weekday() < 5:  # Segunda a sexta
                dias_uteis += 1
            data_atual += timedelta(days=1)
        
        return dias_uteis
    
    def calcular_descontos_automaticos(self):
        """
        Calcula descontos automáticos incluindo INSS e IRPS como cálculos nativos.
        
        INSS e IRPS são calculados automaticamente sem depender de configuração
        na tabela DescontoSalarial, tornando-os nativos do sistema.
        """
        
        total_descontos_automaticos = Decimal('0.00')
        
        # 1. CALCULAR INSS (3% do salário bruto) - NATIVO
        inss_valor = self.get_inss_valor()
        if inss_valor > 0:
            # Verificar se já existe desconto INSS manual
            inss_existente = DescontoFolha.objects.filter(
                funcionario_folha=self,
                desconto__codigo='IN001'
            ).first()
            
            if not inss_existente:
                # Buscar ou criar desconto INSS (evitar duplicatas)
                desconto_inss, created = DescontoSalarial.objects.get_or_create(
                    codigo='IN001',
                    defaults={
                        'nome': 'INSS Moçambique',
                        'tipo': 'IN',
                        'tipo_valor': 'PERCENTUAL',
                        'valor': Decimal('3.00'),
                        'base_calculo': 'SALARIO_BRUTO',
                        'ativo': False,  # Não aparece na lista de descontos
                        'aplicar_automaticamente': False,  # Não é automático, é nativo
                        'valor_minimo_isencao': Decimal('0.00')
                    }
                )
                
                # Criar desconto automático na folha
                DescontoFolha.objects.create(
                    funcionario_folha=self,
                    desconto=desconto_inss,
                    valor=inss_valor,
                    observacoes="INSS automático - 3% do salário bruto"
                )
                total_descontos_automaticos += inss_valor
        
        # 2. CALCULAR IRPS (conforme legislação moçambicana) - NATIVO
        irps_valor = self.get_irps_valor()
        if irps_valor > 0:
            # Verificar se já existe desconto IRPS manual
            irps_existente = DescontoFolha.objects.filter(
                funcionario_folha=self,
                desconto__codigo='IR001'
            ).first()
            
            if not irps_existente:
                # Buscar ou criar desconto IRPS (evitar duplicatas)
                desconto_irps, created = DescontoSalarial.objects.get_or_create(
                    codigo='IR001',
                    defaults={
                        'nome': 'IRPS Moçambique',
                        'tipo': 'IR',
                        'tipo_valor': 'PERCENTUAL',
                        'valor': Decimal('0.00'),  # Não usado, cálculo específico
                        'base_calculo': 'SALARIO_BRUTO',
                        'ativo': False,  # Não aparece na lista de descontos
                        'aplicar_automaticamente': False,  # Não é automático, é nativo
                        'valor_minimo_isencao': Decimal('19000.00')
                    }
                )
                
                # Criar desconto automático na folha
                DescontoFolha.objects.create(
                    funcionario_folha=self,
                    desconto=desconto_irps,
                    valor=irps_valor,
                    observacoes=f"IRPS automático - {self.get_irps_taxa_display()}"
                )
                total_descontos_automaticos += irps_valor
        
        # 3. CALCULAR OUTROS DESCONTOS AUTOMÁTICOS (não INSS/IRPS)
        descontos_automaticos = DescontoSalarial.objects.filter(
            ativo=True,
            aplicar_automaticamente=True
        ).exclude(codigo__in=['IN001', 'IR001'])  # Excluir INSS e IRPS
        
        for desconto in descontos_automaticos:
            valor_desconto = desconto.calcular_valor_desconto(
                self.salario_base,
                self.salario_bruto,
                self.salario_liquido
            )
            
            # Verificar se já existe um desconto manual para este tipo
            desconto_existente = DescontoFolha.objects.filter(
                funcionario_folha=self,
                desconto=desconto
            ).first()
            
            if not desconto_existente and valor_desconto > 0:
                # Criar desconto automático na folha
                DescontoFolha.objects.create(
                    funcionario_folha=self,
                    desconto=desconto,
                    valor=valor_desconto,
                    observacoes=f"Desconto automático aplicado - {desconto.get_descricao_isencao()}"
                )
                total_descontos_automaticos += Decimal(str(valor_desconto))
        
        return total_descontos_automaticos
    
    def calcular_horas_trabalhadas(self):
        """Calcula horas trabalhadas baseadas nos horários de expediente e presenças"""
        from datetime import datetime, time, timedelta
        from django.db.models import Q
        
        # Obter horários de expediente da sucursal do funcionário
        sucursal = self.funcionario.sucursal
        hora_inicio = sucursal.get_hora_inicio_expediente()
        hora_fim = sucursal.get_hora_fim_expediente()
        duracao_almoco = sucursal.get_duracao_almoco()
        horas_por_dia = sucursal.get_horas_trabalho_dia()
        
        # Converter para timedelta para cálculos
        if isinstance(horas_por_dia, str):
            horas_por_dia = timedelta(hours=float(horas_por_dia.split(':')[0]), 
                                    minutes=float(horas_por_dia.split(':')[1]))
        
        # Obter presenças do mês da folha
        primeiro_dia = self.folha.mes_referencia.replace(day=1)
        ultimo_dia = (primeiro_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        presencas = Presenca.objects.filter(
            funcionario=self.funcionario,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia,
            tipo_presenca__codigo='PR'  # Apenas presenças normais
        )
        
        # Calcular horas trabalhadas
        total_horas = 0
        total_horas_extras = 0
        dias_trabalhados = 0
        
        for presenca in presencas:
            # Horas normais do dia
            horas_dia = horas_por_dia.total_seconds() / 3600  # Converter para horas
            total_horas += horas_dia
            dias_trabalhados += 1
        
        # Calcular horas extras do modelo HorasExtras
        from django.db.models import Sum
        horas_extras_registradas = HorasExtras.objects.filter(
            funcionario=self.funcionario,
            data__gte=primeiro_dia,
            data__lte=ultimo_dia
        ).aggregate(
            total_horas=Sum('quantidade_horas'),
            total_valor=Sum('valor_total')
        )
        
        total_horas_extras = float(horas_extras_registradas['total_horas'] or 0)
        
        # Atualizar campos
        self.horas_trabalhadas = round(total_horas, 2)
        self.horas_extras = round(total_horas_extras, 2)
        self.dias_trabalhados = dias_trabalhados
        
        self.save()


class BeneficioFolha(models.Model):
    """Modelo para benefícios aplicados na folha"""
    
    funcionario_folha = models.ForeignKey(FuncionarioFolha, on_delete=models.CASCADE, related_name='beneficios_folha', verbose_name="Funcionário")
    beneficio = models.ForeignKey(BeneficioSalarial, on_delete=models.CASCADE, verbose_name="Benefício")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Benefício na Folha"
        verbose_name_plural = "Benefícios na Folha"
        unique_together = ['funcionario_folha', 'beneficio']

    def __str__(self):
        return f"{self.funcionario_folha.funcionario.nome_completo} - {self.beneficio.nome}"


class DescontoFolha(models.Model):
    """Modelo para descontos aplicados na folha"""
    
    funcionario_folha = models.ForeignKey(FuncionarioFolha, on_delete=models.CASCADE, related_name='descontos_folha', verbose_name="Funcionário")
    desconto = models.ForeignKey(DescontoSalarial, on_delete=models.CASCADE, verbose_name="Desconto")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    observacoes = models.TextField(blank=True, null=True, verbose_name="Observações")

    class Meta:
        verbose_name = "Desconto na Folha"
        verbose_name_plural = "Descontos na Folha"
        unique_together = ['funcionario_folha', 'desconto']

    def __str__(self):
        return f"{self.funcionario_folha.funcionario.nome_completo} - {self.desconto.nome}"


# Adicionar métodos para o canhoto no modelo FuncionarioFolha
def get_inss_valor(self):
    """Calcula o valor do INSS (3% do salário bruto)"""
    return Decimal(str(self.salario_bruto)) * Decimal('0.03')

def get_irps_valor(self):
    """
    Calcula o valor do IRPS (Imposto sobre Rendimento das Pessoas Singulares) 
    conforme a legislação moçambicana.
    
    Implementa a Lei n.º 33/2007 com alterações até Lei n.º 19/2017 e 
    Decreto 56/2018, incluindo:
    
    - Mínimo não tributável: 228.000 MT/ano (19.000 MT/mês)
    - Escalões progressivos de tributação
    - Parcelas de abatimento para correção da progressividade
    
    Escalões IRPS Moçambique 2025:
    - Até 42.000 MT: 10% (sem abatimento)
    - 42.001 - 168.000 MT: 15% (abatimento: 2.100 MT)
    - 168.001 - 504.000 MT: 20% (abatimento: 10.500 MT)
    - 504.001 - 1.512.000 MT: 25% (abatimento: 35.700 MT)
    - Acima de 1.512.000 MT: 32% (abatimento: 141.540 MT)
    
    Args:
        self: Instância de FuncionarioFolha
        
    Returns:
        Decimal: Valor mensal do IRPS em MT
        
    Example:
        >>> funcionario_folha.salario_bruto = 42300  # MT/mês
        >>> irps = funcionario_folha.get_irps_valor()
        >>> print(f"IRPS mensal: {irps} MT")  # ~3685 MT
    """
    
    # Converter salário bruto mensal para anual
    rendimento_anual_bruto = Decimal(str(self.salario_bruto)) * Decimal('12')
    
    # Mínimo não tributável (isenção): 228.000 MT por ano (até 19.000 MT/mês)
    minimo_nao_tributavel = Decimal('228000')
    
    # Calcular rendimento colectável anual
    rendimento_colectavel = rendimento_anual_bruto - minimo_nao_tributavel
    
    # Se rendimento colectável <= 0, então está isento
    if rendimento_colectavel <= Decimal('0'):
        return Decimal('0.00')
    
    # Tabela IRPS Moçambique (Art. 54)
    # Escalão | Taxa Marginal | Parcela a abater
    if rendimento_colectavel <= Decimal('42000'):
        # Até 42.000 MT
        taxa = Decimal('10')
        parcela_abater = Decimal('0')
    elif rendimento_colectavel <= Decimal('168000'):
        # 42.001 – 168.000 MT
        taxa = Decimal('15')
        parcela_abater = Decimal('2100')
    elif rendimento_colectavel <= Decimal('504000'):
        # 168.001 – 504.000 MT
        taxa = Decimal('20')
        parcela_abater = Decimal('10500')
    elif rendimento_colectavel <= Decimal('1512000'):
        # 504.001 – 1.512.000 MT
        taxa = Decimal('25')
        parcela_abater = Decimal('35700')
    else:
        # Acima de 1.512.000 MT
        taxa = Decimal('32')
        parcela_abater = Decimal('141540')
    
    # Calcular IRPS anual: (RC × Taxa) - PA
    irps_anual = (rendimento_colectavel * taxa / Decimal('100')) - parcela_abater
    
    # Garantir que não seja negativo
    if irps_anual < 0:
        irps_anual = Decimal('0')
    
    # Converter para mensal
    irps_mensal = irps_anual / Decimal('12')
    
    return irps_mensal.quantize(Decimal('0.01'))
    
    # Fallback (não deveria chegar aqui)
    return Decimal('0.00')

def get_irps_taxa_display(self):
    """Retorna a taxa do IRPS baseada na faixa de rendimento colectável"""
    
    # Converter salário bruto mensal para anual
    rendimento_anual_bruto = Decimal(str(self.salario_bruto)) * Decimal('12')
    
    # Mínimo não tributável (isenção): 228.000 MT por ano (até 19.000 MT/mês)
    minimo_nao_tributavel = Decimal('228000')
    
    # Calcular rendimento colectável anual
    rendimento_colectavel = rendimento_anual_bruto - minimo_nao_tributavel
    
    # Se rendimento colectável <= 0, então está isento
    if rendimento_colectavel <= Decimal('0'):
        return "Isento"
    
    # Tabela IRPS Moçambique (Art. 54)
    if rendimento_colectavel <= Decimal('42000'):
        return "10%"
    elif rendimento_colectavel <= Decimal('168000'):
        return "15%"
    elif rendimento_colectavel <= Decimal('504000'):
        return "20%"
    elif rendimento_colectavel <= Decimal('1512000'):
        return "25%"
    else:
        return "32%"
    
    return "0%"

def get_desconto_adicional_valor(self):
    """Calcula o valor do desconto adicional (2% do salário bruto)"""
    return Decimal(str(self.salario_bruto)) * Decimal('0.02')

def get_horas_extras_valor(self):
    """Calcula o valor das horas extras"""
    from datetime import timedelta
    from django.db.models import Sum
    
    # Calcular valor total das horas extras do mês
    primeiro_dia = self.folha.mes_referencia.replace(day=1)
    ultimo_dia = (primeiro_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    horas_extras_valor = HorasExtras.objects.filter(
        funcionario=self.funcionario,
        data__gte=primeiro_dia,
        data__lte=ultimo_dia
    ).aggregate(
        total_valor=Sum('valor_total')
    )['total_valor'] or 0
    
    return Decimal(str(horas_extras_valor))

# Adicionar os métodos ao modelo FuncionarioFolha
FuncionarioFolha.get_inss_valor = get_inss_valor
FuncionarioFolha.get_irps_valor = get_irps_valor
FuncionarioFolha.get_irps_taxa_display = get_irps_taxa_display
FuncionarioFolha.get_desconto_adicional_valor = get_desconto_adicional_valor
FuncionarioFolha.get_horas_extras_valor = get_horas_extras_valor

