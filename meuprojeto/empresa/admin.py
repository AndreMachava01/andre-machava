from django.contrib import admin
from .models import DadosEmpresa, Sucursal

from django.template.loader import render_to_string
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required

class SucursalInline(admin.StackedInline):
    model = Sucursal
    extra = 0
    readonly_fields = ['codigo']
    can_delete = True
    show_change_link = True
    template = 'admin/edit_inline/stacked.html'
    fieldsets = (
        ('Informações da Sucursal', {
            'fields': (('nome', 'codigo'), 'tipo', 'responsavel'),
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
    list_display = ['nome', 'tipo_societario', 'nuit', 'provincia', 'cidade', 'telefone', 'email', 'is_sede', 'total_sucursais']
    list_filter = ['provincia', 'cidade', 'is_sede']
    search_fields = ['nome', 'nuit', 'bairro', 'alvara']
    inlines = [SucursalInline]
    
    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ('Informações Básicas', {
                'fields': (('nome', 'tipo_societario'), ('nuit', 'alvara'), ('is_sede', 'data_constituicao')),
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

    def total_sucursais(self, obj):
        if obj.is_sede:
            return obj.sucursais.count()
        return '-'
    total_sucursais.short_description = 'Total de Sucursais'

    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }

# Removendo o registro separado da Sucursal do admin
# As sucursais só podem ser gerenciadas através da empresa sede
try:
    admin.site.unregister(Sucursal)
except admin.sites.NotRegistered:
    pass
