from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models_rh import Funcionario

class FuncionarioForm(forms.ModelForm):
    class Meta:
        model = Funcionario
        fields = '__all__'
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'data_emissao_bi': forms.DateInput(attrs={'type': 'date'}),
            'data_validade_bi': forms.DateInput(attrs={'type': 'date'}),
            'data_admissao': forms.DateInput(attrs={'type': 'date'}),
            'data_demissao': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_nuit(self):
        nuit = self.cleaned_data.get('nuit')
        if nuit:
            if not nuit.isdigit():
                raise ValidationError('NUIT deve conter apenas números.')
            if len(nuit) != 9:
                raise ValidationError('NUIT deve ter exatamente 9 dígitos.')
            if Funcionario.objects.exclude(id=self.instance.id).filter(nuit=nuit).exists():
                raise ValidationError('Este NUIT já está registrado para outro funcionário.')
        return nuit

    def clean_bi(self):
        bi = self.cleaned_data.get('bi')
        if bi:
            if len(bi) != 13:
                raise ValidationError('BI deve ter exatamente 13 caracteres.')
            if Funcionario.objects.exclude(id=self.instance.id).filter(bi=bi).exists():
                raise ValidationError('Este BI já está registrado para outro funcionário.')
        return bi

    def clean_nib(self):
        nib = self.cleaned_data.get('nib')
        if nib:
            if not nib.isdigit():
                raise ValidationError('NIB deve conter apenas números.')
            if len(nib) != 21:
                raise ValidationError('NIB deve ter exatamente 21 dígitos.')
            if Funcionario.objects.exclude(id=self.instance.id).filter(nib=nib).exists():
                raise ValidationError('Este NIB já está registrado para outro funcionário.')
        return nib

    def clean_telefone(self):
        telefone = self.cleaned_data.get('telefone')
        if telefone:
            if not telefone.startswith('+258'):
                raise ValidationError('Telefone deve começar com +258')
            if len(telefone) != 13:
                raise ValidationError('Telefone deve ter 13 caracteres (+258XXXXXXXX)')
            numero = telefone[4:]
            if not numero.isdigit():
                raise ValidationError('Telefone deve conter apenas números após +258')
        return telefone

    def clean_telefone_alternativo(self):
        telefone = self.cleaned_data.get('telefone_alternativo')
        if telefone:
            if not telefone.startswith('+258'):
                raise ValidationError('Telefone deve começar com +258')
            if len(telefone) != 13:
                raise ValidationError('Telefone deve ter 13 caracteres (+258XXXXXXXX)')
            numero = telefone[4:]
            if not numero.isdigit():
                raise ValidationError('Telefone deve conter apenas números após +258')
        return telefone

    def clean_data_nascimento(self):
        data_nascimento = self.cleaned_data.get('data_nascimento')
        if data_nascimento:
            hoje = timezone.now().date()
            idade = hoje.year - data_nascimento.year - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
            if idade < 18:
                raise ValidationError('O funcionário deve ter pelo menos 18 anos.')
            if idade > 100:
                raise ValidationError('Data de nascimento inválida.')
        return data_nascimento

    def clean_data_validade_bi(self):
        data_validade = self.cleaned_data.get('data_validade_bi')
        data_emissao = self.cleaned_data.get('data_emissao_bi')
        if data_validade and data_emissao:
            if data_validade <= data_emissao:
                raise ValidationError('A data de validade deve ser posterior à data de emissão.')
        return data_validade

    def clean_data_demissao(self):
        data_demissao = self.cleaned_data.get('data_demissao')
        data_admissao = self.cleaned_data.get('data_admissao')
        if data_demissao and data_admissao:
            if data_demissao <= data_admissao:
                raise ValidationError('A data de demissão deve ser posterior à data de admissão.')
        return data_demissao

    def clean_ano_conclusao(self):
        ano_conclusao = self.cleaned_data.get('ano_conclusao')
        if ano_conclusao:
            ano_atual = timezone.now().year
            if ano_conclusao < 1950:
                raise ValidationError('Ano de conclusão inválido.')
            if ano_conclusao > ano_atual:
                raise ValidationError('O ano de conclusão não pode ser no futuro.')
        return ano_conclusao

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        data_demissao = cleaned_data.get('data_demissao')

        if status == 'IN' and not data_demissao:
            self.add_error('data_demissao', 'Data de demissão é obrigatória para funcionários inativos.')
        elif status != 'IN' and data_demissao:
            self.add_error('status', 'Status deve ser Inativo quando há data de demissão.')

        return cleaned_data
