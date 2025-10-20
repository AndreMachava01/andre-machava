from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models_stock import (
    CategoriaProduto, Fornecedor, Receita, ItemReceita, Item,
    StockItem, TipoMovimentoStock, MovimentoItem,
    FornecedorProduto, OrdemCompra, ItemOrdemCompra,
    TransferenciaStock, ItemTransferencia,
    RequisicaoStock, ItemRequisicaoStock,
    RequisicaoCompraExterna, ItemRequisicaoCompraExterna,
    VeiculoInterno, ChecklistViatura
)

@admin.register(CategoriaProduto)
class CategoriaProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'codigo', 'tipo', 'ativa']
    list_filter = ['tipo', 'ativa', 'categoria_pai']
    search_fields = ['nome', 'codigo']
    ordering = ['nome']

@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'nuit', 'telefone', 'email', 'cidade', 'tipo_fornecedor', 
        'status', 'data_cadastro'
    ]
    list_filter = ['tipo_fornecedor', 'status', 'cidade', 'data_cadastro']
    search_fields = ['nome', 'nuit', 'email', 'cidade']
    ordering = ['nome']
    list_per_page = 20
    readonly_fields = ['data_cadastro']

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'nome', 'tipo', 'categoria', 'unidade_medida', 
        'preco_custo', 'estoque_minimo', 'estoque_maximo', 'status', 'data_cadastro'
    ]
    list_filter = ['tipo', 'categoria', 'status', 'unidade_medida', 'data_cadastro']
    search_fields = ['nome', 'codigo', 'codigo_barras', 'descricao']
    ordering = ['nome']
    list_per_page = 20
    readonly_fields = ['data_cadastro', 'data_atualizacao']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'codigo', 'codigo_barras', 'descricao', 'categoria', 'tipo')
        }),
        ('Preços e Medidas', {
            'fields': ('unidade_medida', 'preco_custo')
        }),
        ('Controle de Estoque', {
            'fields': ('estoque_minimo', 'estoque_maximo', 'status')
        }),
        ('Datas', {
            'fields': ('data_cadastro', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = [
        'item', 'sucursal', 'quantidade_atual', 'quantidade_reservada', 
        'quantidade_disponivel', 'data_atualizacao'
    ]
    list_filter = ['sucursal', 'item__categoria', 'item__tipo', 'data_atualizacao']
    search_fields = ['item__nome', 'item__codigo', 'sucursal__nome']
    ordering = ['item__nome', 'sucursal__nome']
    list_per_page = 20
    readonly_fields = ['data_atualizacao', 'quantidade_disponivel']

@admin.register(TipoMovimentoStock)
class TipoMovimentoStockAdmin(admin.ModelAdmin):
    list_display = ['nome', 'codigo', 'aumenta_estoque', 'ativo']
    list_filter = ['aumenta_estoque', 'ativo']
    search_fields = ['nome', 'codigo', 'descricao']
    ordering = ['nome']


@admin.register(MovimentoItem)
class MovimentoItemAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'item', 'sucursal', 'tipo_movimento', 'quantidade', 
        'preco_unitario', 'valor_total', 'data_movimento'
    ]
    list_filter = ['sucursal', 'tipo_movimento', 'data_movimento', 'item__categoria', 'item__tipo']
    search_fields = ['codigo', 'item__nome', 'item__codigo', 'observacoes']
    ordering = ['-data_movimento']
    list_per_page = 20
    readonly_fields = ['data_movimento', 'codigo', 'valor_total']

@admin.register(FornecedorProduto)
class FornecedorProdutoAdmin(admin.ModelAdmin):
    list_display = ['fornecedor', 'get_item_nome', 'get_item_codigo', 'preco_custo', 'ativo']
    list_filter = ['fornecedor', 'ativo', 'item__tipo', 'item__categoria']
    search_fields = ['fornecedor__nome', 'item__nome', 'item__codigo']
    ordering = ['fornecedor__nome', 'item__nome']
    readonly_fields = ['data_cadastro', 'data_atualizacao']
    
    def get_item_nome(self, obj):
        return obj.item.nome if obj.item else '-'
    get_item_nome.short_description = 'Item'
    
    def get_item_codigo(self, obj):
        return obj.item.codigo if obj.item else '-'
    get_item_codigo.short_description = 'Código'

@admin.register(TransferenciaStock)
class TransferenciaStockAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'suco_origem', 'sucura_destino', 'status', 'valor_total',
        'data_criacao', 'data_envio', 'data_recebimento'
    ]
    list_filter = ['status', 'data_criacao', 'sucursal_origem', 'sucursal_destino']
    search_fields = ['codigo', 'observacoes']
    ordering = ['-data_criacao']
    readonly_fields = ['data_criacao', 'codigo', 'valor_total']

@admin.register(ItemTransferencia)
class ItemTransferenciaAdmin(admin.ModelAdmin):
    list_display = ['transferencia', 'get_item_nome', 'quantidade_solicitada', 'valor_total']
    list_filter = ['transferencia__status', 'transferencia__data_criacao']
    
    def get_item_nome(self, obj):
        return obj.item.nome if obj.item else obj.produto.nome if obj.produto else '-'
    get_item_nome.short_description = 'Item'

@admin.register(RequisicaoStock)
class RequisicaoStockAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'sucursal_origem', 'get_sucursal_destino', 'status', 
        'valor_total', 'data_criacao', 'data_aprovacao'
    ]
    list_filter = ['status', 'data_criacao', 'sucursal_origem', 'tipo_requisicao']
    search_fields = ['codigo', 'observacoes']
    ordering = ['-data_criacao']
    readonly_fields = ['data_criacao', 'codigo', 'valor_total']
    
    def get_sucursal_destino(self, obj):
        return obj.sucursal_destino.nome if obj.sucursal_destino else obj.transferencia_associada.sucursal_destino.nome if obj.transferencia_associada else '-'
    get_sucursal_destino.short_description = 'Destino'

@admin.register(ItemRequisicaoStock)
class ItemRequisicaoStockAdmin(admin.ModelAdmin):
    list_display = ['requisicao', 'get_item_nome', 'quantidade_solicitada', 'quantidade_atendida', 'valor_total']
    list_filter = ['requisicao__status', 'requisicao__data_criacao']
    
    def get_item_nome(self, obj):
        return obj.item.nome if obj.item else '-'
    get_item_nome.short_description = 'Item'

@admin.register(RequisicaoCompraExterna)
class RequisicaoCompraExternaAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'sucursal_origem', 'status', 'valor_total', 
        'data_criacao', 'data_aprovacao'
    ]
    list_filter = ['status', 'data_criacao', 'sucursal_origem']
    search_fields = ['codigo', 'observacoes']
    ordering = ['-data_criacao']
    readonly_fields = ['data_criacao', 'codigo', 'valor_total']

@admin.register(ItemRequisicaoCompraExterna)
class ItemRequisicaoCompraExternaAdmin(admin.ModelAdmin):
    list_display = ['requisicao', 'get_item_nome', 'quantidade_solicitada', 'valor_total']
    list_filter = ['requisicao__status', 'requisicao__data_criacao']
    
    def get_item_nome(self, obj):
        return obj.item.nome if obj.item else '-'
    get_item_nome.short_description = 'Item'

@admin.register(OrdemCompra)
class OrdemCompraAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'fornecedor', 'sucursal_destino', 'status', 'valor_total',
        'data_criacao', 'data_envio', 'data_recebimento'
    ]
    list_filter = ['status', 'data_criacao', 'fornecedor', 'sucursal_destino']
    search_fields = ['codigo', 'numero_cotacao', 'numero_fatura', 'observacoes']
    ordering = ['-data_criacao']
    readonly_fields = ['data_criacao', 'codigo', 'valor_total']

@admin.register(ItemOrdemCompra)
class ItemOrdemCompraAdmin(admin.ModelAdmin):
    list_display = ['ordem_compra', 'get_item_nome', 'quantidade_solicitada', 'quantidade_recebida', 'valor_total']
    list_filter = ['ordem_compra__status', 'ordem_compra__data_criacao']
    
    def get_item_nome(self, obj):
        return obj.item.nome if obj.item else '-'
    get_item_nome.short_description = 'Item'


@admin.register(VeiculoInterno)
class VeiculoInternoAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'nome', 'placa', 'categoria', 'motorista_responsavel', 
        'status', 'quilometragem_atual', 'proxima_revisao'
    ]
    list_filter = ['categoria', 'status', 'ativo', 'data_cadastro']
    search_fields = ['nome', 'codigo', 'placa', 'motorista_responsavel']
    ordering = ['nome']
    list_per_page = 20
    readonly_fields = ['data_cadastro', 'codigo']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('codigo', 'nome', 'categoria', 'placa')
        }),
        ('Dados do Veículo', {
            'fields': ('marca', 'modelo', 'ano_fabricacao', 'capacidade_kg')
        }),
        ('Manutenção', {
            'fields': ('quilometragem_atual', 'proxima_revisao')
        }),
        ('Motorista', {
            'fields': ('motorista_responsavel', 'telefone_motorista')
        }),
        ('Custos', {
            'fields': ('custo_por_km', 'custo_fixo_mensal')
        }),
        ('Status', {
            'fields': ('status', 'ativo', 'observacoes')
        }),
    )


@admin.register(ChecklistViatura)
class ChecklistViaturaAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'veiculo', 'tipo', 'inspetor', 'data_inspecao', 
        'status_final', 'pontuacao_display'
    ]
    list_filter = [
        'tipo', 'status_final', 'ativo', 'data_inspecao', 
        'veiculo__categoria'
    ]
    search_fields = [
        'codigo', 'veiculo__nome', 'inspetor__username', 
        'motorista', 'local_inspecao'
    ]
    ordering = ['-data_inspecao']
    list_per_page = 20
    readonly_fields = ['data_criacao', 'codigo', 'status_final']
    
    def pontuacao_display(self, obj):
        return f"{obj.get_pontuacao_total()}%"
    pontuacao_display.short_description = 'Pontuação'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'veiculo', 'tipo', 'inspetor', 'motorista')
        }),
        ('Data e Local', {
            'fields': ('data_inspecao', 'local_inspecao', 'quilometragem')
        }),
        ('Sistema de Freios', {
            'fields': ('freios_funcionando', 'fluido_freio_ok', 'pastilhas_ok'),
            'classes': ('collapse',)
        }),
        ('Sistema de Direção', {
            'fields': ('direcao_funcionando', 'fluido_direcao_ok'),
            'classes': ('collapse',)
        }),
        ('Sistema Elétrico', {
            'fields': ('bateria_ok', 'alternador_ok', 'farois_funcionando', 'luzes_sinalizacao'),
            'classes': ('collapse',)
        }),
        ('Pneus e Rodas', {
            'fields': ('pneus_pressao_ok', 'pneus_desgaste_ok', 'rodas_ok'),
            'classes': ('collapse',)
        }),
        ('Motor e Fluidos', {
            'fields': ('motor_funcionando', 'oleo_motor_ok', 'agua_radiador_ok', 'combustivel_ok'),
            'classes': ('collapse',)
        }),
        ('Documentação', {
            'fields': ('documentos_ok', 'seguro_ok', 'licenciamento_ok'),
            'classes': ('collapse',)
        }),
        ('Limpeza e Aparência', {
            'fields': ('limpeza_interior', 'limpeza_exterior'),
            'classes': ('collapse',)
        }),
        ('Equipamentos de Segurança', {
            'fields': ('extintor_ok', 'triangulo_ok', 'macaco_ok', 'chave_roda_ok'),
            'classes': ('collapse',)
        }),
        ('Resultado', {
            'fields': ('status_final', 'observacoes', 'recomendacoes')
        }),
        ('Controle', {
            'fields': ('ativo', 'data_criacao'),
            'classes': ('collapse',)
        }),
    )