import django_filters
from django.db import models
from .models_rh import Funcionario

class FuncionarioFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='search_filter', label='Pesquisar')
    sucursal = django_filters.NumberFilter(field_name='sucursal__id', label='Sucursal')
    departamento = django_filters.NumberFilter(field_name='departamento__id', label='Departamento')
    cargo = django_filters.NumberFilter(field_name='cargo__id', label='Cargo')
    status = django_filters.ChoiceFilter(choices=Funcionario.STATUS_CHOICES, label='Status')

    class Meta:
        model = Funcionario
        fields = ['search', 'sucursal', 'departamento', 'cargo', 'status']

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            models.Q(nome_completo__icontains=value) |
            models.Q(codigo_funcionario__icontains=value) |
            models.Q(nuit__icontains=value) |
            models.Q(bi__icontains=value)
        )
