from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import BeneficioSalarial

class Command(BaseCommand):
    help = 'Cria benefício para horas extras'

    def handle(self, *args, **options):
        # Criar benefício para horas extras
        beneficio_horas_extras, created = BeneficioSalarial.objects.get_or_create(
            codigo='HE001',
            defaults={
                'nome': 'Horas Extras',
                'tipo': 'HE',
                'tipo_valor': 'PERCENTUAL',
                'valor': 50.00,  # 50% sobre o salário base por hora extra
                'base_calculo': 'SALARIO_BASE',
                'ativo': True,
                'observacoes': 'Pagamento de horas extras - 50% sobre o salário base por hora'
            }
        )

        if created:
            self.stdout.write(f'✅ Benefício criado: {beneficio_horas_extras.nome}')
        else:
            self.stdout.write(f'ℹ️  Benefício já existe: {beneficio_horas_extras.nome}')

        self.stdout.write(f'Configuração: {beneficio_horas_extras.tipo_valor} {beneficio_horas_extras.valor}% sobre {beneficio_horas_extras.base_calculo}')
