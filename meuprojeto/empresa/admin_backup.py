from django.contrib import admin
from .models_base import DadosEmpresa, Sucursal
from .admin_rh import DepartamentoAdmin, CargoAdmin

from django.template.loader import render_to_string
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required

class SucursalInline(admin.StackedInline):
    model = Sucursal
    extra = 0
    readonly_fields = ['id', 'codigo']
    can_delete = True
    show_change_link = True
    template = 'admin/edit_inline/stacked.html'
    fieldsets = (
        ('Informações da Sucursal', {
            'fields': (('codigo', 'nome'), 'tipo', 'responsavel'),
            'classes': ('wide',)
        }),
        ('Localização', {
            'fields': ('provincia', 'cidade', 'bairro', 'endereco')
        }),
        ('Contacto', {
            'fields': ('telefone', 'email')
        }),
        ('Status', {
            'fields': ('data_abertura', 'ativa')
        }),
    )

    def get_queryset(self, request):
        # Ordena as sucursais por código
        return super().get_queryset(request).order_by('codigo')

    class Media:
        css = {
            'all': ('empresa/css/admin.css',)
        }
        js = ('empresa/js/sucursal_admin.js',)

@admin.register(DadosEmpresa)
class DadosEmpresaAdmin(admin.ModelAdmin):
    list_display = ['id', 'codigo_empresa', 'nome', 'tipo_societario', 'nuit', 'provincia', 'cidade', 'is_sede']
    list_filter = ['provincia', 'cidade', 'is_sede', 'tipo_societario']
    search_fields = ['codigo_empresa', 'nome', 'nuit', 'bairro', 'alvara']
    inlines = [SucursalInline]
    readonly_fields = ['codigo_empresa']
    list_display_links = ['id', 'codigo_empresa', 'nome']
    list_per_page = 25
    ordering = ['id']
    
    def get_context_data(self, request, obj=None):
        context = super().get_context_data(request, obj)
        return context

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('Informações Básicas', {
                'fields': (('codigo_empresa', 'nome'), ('tipo_societario', 'is_sede'), ('nuit', 'alvara'), ('data_constituicao',)),
                'classes': ('wide',)
            }),
            ('Registo Comercial (Moçambique)', {
                'fields': ('numero_registro_comercial', 'data_registro_comercial', 'actividade_principal', 'capital_social'),
                'classes': ('wide',)
            }),
            ('Localização', {
                'fields': ('provincia', 'cidade', 'bairro', 'endereco'),
                'classes': ('wide',)
            }),
            ('Contacto', {
                'fields': ('telefone', 'email', 'website'),
                'classes': ('wide',)
            }),
        ]
        return fieldsets

    def get_inline_instances(self, request, obj=None):
        # Só mostra a seção de sucursais se for uma sede
        if obj and obj.is_sede:
            return super().get_inline_instances(request, obj)
        return []

    def save_model(self, request, obj, form, change):
        # Se está marcando como sede e não era sede antes, criar sucursal automaticamente
        if obj.is_sede and not change:
            super().save_model(request, obj, form, change)
        else:
            super().save_model(request, obj, form, change)

    def codigo_empresa_display(self, obj):
        """Exibe o código da empresa de forma destacada"""
        return obj.codigo_empresa or "N/A"
    codigo_empresa_display.short_description = 'Código'
    codigo_empresa_display.admin_order_field = 'codigo_empresa'

    def nome_completo(self, obj):
        """Exibe o nome da empresa com o tipo societário"""
        from .config_mocambique import TIPOS_SOCIETARIOS_MOZ
        tipo_societario_dict = dict(TIPOS_SOCIETARIOS_MOZ)
        sufixo = tipo_societario_dict.get(obj.tipo_societario, obj.tipo_societario)
        return f"{obj.nome} {sufixo}"
    nome_completo.short_description = 'Nome da Empresa'
    nome_completo.admin_order_field = 'nome'


    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'empresa_sede', 'tipo', 'provincia', 'cidade', 'responsavel', 'ativa']
    list_filter = ['tipo', 'provincia', 'cidade', 'ativa', 'empresa_sede']
    search_fields = ['codigo', 'nome', 'responsavel', 'empresa_sede__nome']
    readonly_fields = ['codigo']
    list_display_links = ['codigo', 'nome']
    list_per_page = 25
    
    def get_queryset(self, request):
        # Ordena as sucursais por código
        return super().get_queryset(request).order_by('codigo')
    
    class Media:
        css = {
            'all': ('empresa/css/admin.css',)
        }