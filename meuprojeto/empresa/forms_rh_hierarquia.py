"""Formulários do sub-módulo de hierarquia."""
from django import forms

from meuprojeto.empresa.models_rh import Cargo, Departamento, PosicaoHierarquica


class PosicaoHierarquicaForm(forms.ModelForm):
    departamentos = forms.ModelMultipleChoiceField(
        queryset=Departamento.objects.filter(ativo=True).order_by('nome'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=True,
    )
    cargos = forms.ModelMultipleChoiceField(
        queryset=Cargo.objects.filter(ativo=True).order_by('nome'),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=False,
    )

    class Meta:
        model = PosicaoHierarquica
        fields = ['nome', 'nivel', 'departamentos', 'cargos', 'posicao_superior', 'ativa']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'nivel': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'posicao_superior': forms.Select(attrs={'class': 'form-control'}),
            'ativa': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['posicao_superior'].queryset = PosicaoHierarquica.objects.filter(
            ativa=True,
        ).order_by('nivel', 'nome')
        self.fields['posicao_superior'].required = False
