from django.contrib import admin
from django.utils.html import format_html
from .models_rh import (
    Departamento, Cargo, Funcionario,
    TipoPresenca, Presenca, Feriado, HorasExtras,
    BeneficioSalarial, DescontoSalarial, Salario, SalarioBeneficio, SalarioDesconto,
    FolhaSalarial, FuncionarioFolha, BeneficioFolha, DescontoFolha, TransferenciaFuncionario
)

@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'tipo', 'sucursal', 'responsavel', 'ativo')
    list_filter = ('tipo', 'sucursal', 'ativo')
    search_fields = ('codigo', 'nome', 'responsavel')
    ordering = ('sucursal', 'nome')
    readonly_fields = ('codigo', 'data_criacao', 'data_atualizacao')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'codigo', 'tipo', 'descricao', 'sucursal', 'responsavel')
        }),
        ('Contato', {
            'fields': ('email_departamento', 'ramal')
        }),
        ('Financeiro', {
            'fields': ('orcamento', 'meta_anual')
        }),
        ('Status', {
            'fields': ('ativo', 'observacoes')
        }),
        ('Controle do Sistema', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('codigo_cargo', 'nome', 'nivel', 'categoria', 'departamento', 'ativo')
    list_filter = ('nivel', 'categoria', 'departamento', 'ativo')
    search_fields = ('codigo_cargo', 'nome')
    ordering = ('departamento', 'nivel', 'nome')
    readonly_fields = ('codigo_cargo', 'data_criacao', 'data_atualizacao')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'codigo_cargo', 'nivel', 'categoria', 'descricao', 'departamento')
        }),
        ('Carga Horária e Remuneração', {
            'fields': ('carga_horaria', 'salario_base', 'faixa_salarial_min', 'faixa_salarial_max')
        }),
        ('Requisitos e Competências', {
            'fields': ('requisitos_obrigatorios', 'requisitos_desejaveis', 'competencias')
        }),
        ('Saúde e Segurança', {
            'fields': ('riscos_ocupacionais', 'equipamentos_obrigatorios')
        }),
        ('Benefícios', {
            'fields': ('beneficios_especificos',)
        }),
        ('Status', {
            'fields': ('ativo', 'observacoes')
        }),
        ('Controle do Sistema', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ('codigo_funcionario', 'nome_completo', 'sucursal', 'departamento', 'cargo', 'status')
    list_filter = ('sucursal', 'departamento', 'cargo', 'status', 'tipo_contrato')
    search_fields = ('codigo_funcionario', 'nome_completo', 'nuit', 'bi')
    ordering = ('nome_completo',)
    readonly_fields = ('codigo_funcionario', 'data_criacao', 'data_atualizacao')
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'nome_completo', 'codigo_funcionario', 'data_nascimento', 'genero',
                'estado_civil', 'nacionalidade', 'naturalidade'
            )
        }),
        ('Documentos', {
            'fields': (
                'nuit', 'bi', 'data_emissao_bi', 'data_validade_bi', 'local_emissao_bi'
            )
        }),
        ('Contato', {
            'fields': (
                'email', 'telefone', 'telefone_alternativo', 'endereco',
                'bairro', 'cidade', 'provincia'
            )
        }),
        ('Dados Profissionais', {
            'fields': (
                'sucursal', 'departamento', 'cargo', 'tipo_contrato',
                'data_admissao', 'data_demissao', 'status'
            )
        }),
        ('Dados Bancários', {
            'fields': ('banco', 'agencia', 'conta', 'nib')
        }),
        ('Remuneração', {
            'fields': (
                'salario_atual',
            )
        }),
        ('Educação', {
            'fields': (
                'escolaridade', 'curso', 'instituicao_ensino', 'ano_conclusao'
            )
        }),
        ('Controle do Sistema', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )



@admin.register(TipoPresenca)
class TipoPresencaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'desconta_salario', 'cor_display', 'ativo')
    list_filter = ('desconta_salario', 'ativo')
    search_fields = ('nome', 'codigo')
    ordering = ('nome',)
    
    def cor_display(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            obj.cor, obj.cor
        )
    cor_display.short_description = 'Cor'


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'data', 'tipo', 'ativo', 'data_criacao')
    list_filter = ('tipo', 'ativo', 'data')
    search_fields = ('nome', 'descricao')
    date_hierarchy = 'data'
    ordering = ('data', 'nome')
    list_editable = ('ativo',)


@admin.register(Presenca)
class PresencaAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'data', 'tipo_presenca', 'horas_extras', 'tipo_cor')
    list_filter = ('tipo_presenca', 'data', 'funcionario__departamento')
    search_fields = ('funcionario__nome_completo', 'funcionario__codigo_funcionario', 'observacoes')
    raw_id_fields = ('funcionario',)
    date_hierarchy = 'data'
    ordering = ('-data', 'funcionario__nome_completo')
    
    def tipo_cor(self, obj):
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            obj.tipo_presenca.cor, obj.tipo_presenca.nome
        )
    tipo_cor.short_description = 'Tipo'


@admin.register(HorasExtras)
class HorasExtrasAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'data', 'tipo', 'quantidade_horas', 'valor_por_hora', 'valor_total', 'status_aprovacao', 'data_criacao')
    list_filter = ('tipo', 'data', 'data_aprovacao', 'funcionario__departamento', 'data_criacao')
    search_fields = ('funcionario__nome_completo', 'funcionario__codigo_funcionario', 'observacoes')
    raw_id_fields = ('funcionario', 'aprovado_por', 'criado_por')
    date_hierarchy = 'data'
    ordering = ('-data', '-data_criacao')
    readonly_fields = ('valor_total', 'data_criacao', 'data_atualizacao')
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('funcionario', 'data', 'tipo', 'observacoes')
        }),
        ('Horário', {
            'fields': ('hora_inicio', 'hora_fim', 'quantidade_horas')
        }),
        ('Valores', {
            'fields': ('valor_por_hora', 'valor_total')
        }),
        ('Aprovação', {
            'fields': ('data_aprovacao', 'aprovado_por'),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('criado_por', 'data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )
    
    def status_aprovacao(self, obj):
        if obj.data_aprovacao:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Aprovado</span>'
            )
        else:
            return format_html(
                '<span style="color: #ffc107; font-weight: bold;">⏳ Pendente</span>'
            )
    status_aprovacao.short_description = 'Status'
    status_aprovacao.admin_order_field = 'data_aprovacao'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Se é um novo registro
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(BeneficioSalarial)
class BeneficioSalarialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'tipo', 'tipo_valor', 'valor', 'fornecedor', 'ativo')
    list_filter = ('tipo', 'tipo_valor', 'ativo')
    search_fields = ('nome', 'codigo', 'fornecedor', 'observacoes')
    ordering = ('nome',)
    list_editable = ('ativo',)
    readonly_fields = ('codigo',)
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'codigo', 'tipo', 'tipo_valor', 'valor', 'base_calculo', 'base_calculo_personalizada')
        }),
        ('Informações do Fornecedor (Benefícios Não Monetários)', {
            'fields': ('fornecedor', 'localizacao', 'horario_funcionamento', 'limite_uso', 'documento_necessario'),
            'classes': ('collapse',)
        }),
        ('Contacto do Fornecedor', {
            'fields': ('contato_responsavel', 'telefone_contato', 'email_contato'),
            'classes': ('collapse',)
        }),
        ('Status e Observações', {
            'fields': ('ativo', 'observacoes')
        }),
    )


@admin.register(DescontoSalarial)
class DescontoSalarialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'codigo', 'tipo', 'tipo_valor', 'valor', 'aplicar_automaticamente', 'ativo')
    list_filter = ('tipo', 'tipo_valor', 'aplicar_automaticamente', 'ativo')
    search_fields = ('nome', 'codigo', 'observacoes')
    ordering = ('nome',)
    list_editable = ('ativo', 'aplicar_automaticamente')
    readonly_fields = ('codigo',)
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'codigo', 'tipo', 'tipo_valor', 'valor', 'base_calculo', 'base_calculo_personalizada')
        }),
        ('Regras de Isenção', {
            'fields': ('valor_minimo_isencao', 'valor_maximo_isencao', 'aplicar_automaticamente'),
            'description': 'Configure as regras de isenção e aplicação automática'
        }),
        ('Status e Observações', {
            'fields': ('ativo', 'observacoes')
        }),
    )


class SalarioBeneficioInline(admin.TabularInline):
    model = SalarioBeneficio
    extra = 0
    fields = ('beneficio', 'valor', 'observacoes')


class SalarioDescontoInline(admin.TabularInline):
    model = SalarioDesconto
    extra = 0
    fields = ('desconto', 'valor', 'observacoes')


@admin.register(Salario)
class SalarioAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'valor_base', 'salario_liquido_display', 'data_inicio', 'data_fim', 'status')
    list_filter = ('status', 'data_inicio', 'funcionario__departamento')
    search_fields = ('funcionario__nome_completo', 'funcionario__codigo_funcionario', 'observacoes')
    raw_id_fields = ('funcionario',)
    date_hierarchy = 'data_inicio'
    ordering = ('-data_inicio', 'funcionario__nome_completo')
    inlines = [SalarioBeneficioInline, SalarioDescontoInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('funcionario', 'valor_base', 'data_inicio', 'data_fim', 'status')
        }),
        ('Observações', {
            'fields': ('observacoes',)
        }),
    )
    
    def salario_liquido_display(self, obj):
        return f"{obj.salario_liquido:.2f} MT"
    salario_liquido_display.short_description = 'Salário Líquido'


@admin.register(SalarioBeneficio)
class SalarioBeneficioAdmin(admin.ModelAdmin):
    list_display = ('salario', 'beneficio', 'valor', 'data_aplicacao')
    list_filter = ('beneficio__tipo', 'data_aplicacao')
    search_fields = ('salario__funcionario__nome_completo', 'beneficio__nome')
    raw_id_fields = ('salario', 'beneficio')
    ordering = ('-data_aplicacao',)


@admin.register(SalarioDesconto)
class SalarioDescontoAdmin(admin.ModelAdmin):
    list_display = ('salario', 'desconto', 'valor', 'data_aplicacao')
    list_filter = ('desconto__tipo', 'data_aplicacao')
    search_fields = ('salario__funcionario__nome_completo', 'desconto__nome')
    raw_id_fields = ('salario', 'desconto')
    ordering = ('-data_aplicacao',)


# Folha Salarial Admins
class BeneficioFolhaInline(admin.TabularInline):
    model = BeneficioFolha
    extra = 0
    fields = ('beneficio', 'valor', 'observacoes')


class DescontoFolhaInline(admin.TabularInline):
    model = DescontoFolha
    extra = 0
    fields = ('desconto', 'valor', 'observacoes')


class FuncionarioFolhaInline(admin.TabularInline):
    model = FuncionarioFolha
    extra = 0
    fields = ('funcionario', 'salario_base', 'horas_trabalhadas', 'horas_extras', 'dias_trabalhados')
    readonly_fields = ('salario_bruto', 'total_beneficios', 'total_descontos', 'salario_liquido')


@admin.register(FolhaSalarial)
class FolhaSalarialAdmin(admin.ModelAdmin):
    list_display = ('mes_referencia', 'status', 'total_funcionarios', 'total_bruto', 'total_descontos', 'total_liquido', 'data_criacao')
    list_filter = ('status', 'mes_referencia', 'data_criacao')
    search_fields = ('mes_referencia', 'observacoes')
    readonly_fields = ('total_bruto', 'total_descontos', 'total_liquido', 'total_funcionarios', 'data_criacao', 'data_atualizacao')
    inlines = [FuncionarioFolhaInline]
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('mes_referencia', 'status', 'observacoes')
        }),
        ('Datas', {
            'fields': ('data_fechamento', 'data_pagamento')
        }),
        ('Totais', {
            'fields': ('total_bruto', 'total_descontos', 'total_liquido', 'total_funcionarios'),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        })
    )
    ordering = ('-mes_referencia',)


@admin.register(FuncionarioFolha)
class FuncionarioFolhaAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'folha', 'salario_base', 'salario_bruto', 'total_descontos', 'salario_liquido')
    list_filter = ('folha__mes_referencia', 'folha__status')
    search_fields = ('funcionario__nome_completo', 'folha__mes_referencia')
    raw_id_fields = ('funcionario', 'folha')
    readonly_fields = ('salario_bruto', 'total_beneficios', 'total_descontos', 'salario_liquido', 'data_criacao', 'data_atualizacao')
    inlines = [BeneficioFolhaInline, DescontoFolhaInline]
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('folha', 'funcionario', 'salario_base', 'observacoes')
        }),
        ('Horas e Dias', {
            'fields': ('horas_trabalhadas', 'horas_extras', 'dias_trabalhados')
        }),
        ('Cálculos', {
            'fields': ('salario_bruto', 'total_beneficios', 'total_descontos', 'salario_liquido'),
            'classes': ('collapse',)
        }),
        ('Sistema', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        })
    )
    ordering = ('-folha__mes_referencia', 'funcionario__nome_completo')


@admin.register(BeneficioFolha)
class BeneficioFolhaAdmin(admin.ModelAdmin):
    list_display = ('funcionario_folha', 'beneficio', 'valor')
    list_filter = ('beneficio__tipo', 'beneficio__tipo_valor')
    search_fields = ('funcionario_folha__funcionario__nome_completo', 'beneficio__nome')
    raw_id_fields = ('funcionario_folha', 'beneficio')


@admin.register(DescontoFolha)
class DescontoFolhaAdmin(admin.ModelAdmin):
    list_display = ('funcionario_folha', 'desconto', 'valor')
    list_filter = ('desconto__tipo', 'desconto__tipo_valor')
    search_fields = ('funcionario_folha__funcionario__nome_completo', 'desconto__nome')
    raw_id_fields = ('funcionario_folha', 'desconto')


@admin.register(TransferenciaFuncionario)
class TransferenciaFuncionarioAdmin(admin.ModelAdmin):
    list_display = [
        'funcionario', 'sucursal_origem', 'sucursal_destino', 
        'status', 'data_solicitacao', 'data_efetiva'
    ]
    list_filter = [
        'status', 'sucursal_origem', 'sucursal_destino', 
        'data_solicitacao', 'data_efetiva'
    ]
    search_fields = [
        'funcionario__nome_completo', 'funcionario__codigo_funcionario',
        'sucursal_origem__nome', 'sucursal_destino__nome',
        'motivo'
    ]
    ordering = ['-data_solicitacao']
    readonly_fields = [
        'data_criacao', 'data_atualizacao', 'data_aprovacao', 
        'data_implementacao', 'data_efetivacao'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'funcionario', 'status', 'data_solicitacao', 'data_efetiva'
            )
        }),
        ('Transferência', {
            'fields': (
                'sucursal_origem', 'departamento_origem',
                'sucursal_destino', 'departamento_destino', 'cargo_novo'
            )
        }),
        ('Motivo e Observações', {
            'fields': ('motivo', 'observacoes', 'motivo_rejeicao')
        }),
        ('Auditoria', {
            'fields': (
                'criado_por', 'aprovado_por', 'rejeitado_por',
                'data_aprovacao', 'data_implementacao', 'data_efetivacao',
                'data_criacao', 'data_atualizacao'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        
        # Se a transferência já foi aprovada, não permite edição de alguns campos
        if obj and obj.status in ['APROVADO', 'IMPLEMENTADO', 'EFETIVADO', 'REJEITADO']:
            readonly.extend(['funcionario', 'sucursal_origem', 'departamento_origem', 
                           'sucursal_destino', 'departamento_destino', 'cargo_novo'])
        
        return readonly