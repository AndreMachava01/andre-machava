from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import TipoPresenca

class Command(BaseCommand):
    help = 'Criar tipos de presença padrão'

    def handle(self, *args, **options):
        tipos_presenca = [
            {
                'nome': 'Presente',
                'codigo': 'PR',
                'descricao': 'Funcionário presente no dia de trabalho',
                'desconta_salario': False,
                'cor': '#28a745',  # Verde
                'ativo': True
            },
            {
                'nome': 'Ausente',
                'codigo': 'AU',
                'descricao': 'Funcionário ausente sem justificativa',
                'desconta_salario': True,
                'cor': '#dc3545',  # Vermelho
                'ativo': True
            },
            {
                'nome': 'Falta Justificada',
                'codigo': 'FJ',
                'descricao': 'Falta com justificativa aceita',
                'desconta_salario': False,
                'cor': '#ffc107',  # Amarelo
                'ativo': True
            },
            {
                'nome': 'Falta Injustificada',
                'codigo': 'FI',
                'descricao': 'Falta sem justificativa ou não aceita',
                'desconta_salario': True,
                'cor': '#dc3545',  # Vermelho
                'ativo': True
            },
            {
                'nome': 'Licença',
                'codigo': 'LI',
                'descricao': 'Licença médica ou outros tipos de licença',
                'desconta_salario': False,
                'cor': '#17a2b8',  # Azul claro
                'ativo': True
            },
            {
                'nome': 'Férias',
                'codigo': 'FE',
                'descricao': 'Período de férias',
                'desconta_salario': False,
                'cor': '#6f42c1',  # Roxo
                'ativo': True
            },
            {
                'nome': 'Suspensão',
                'codigo': 'SU',
                'descricao': 'Suspensão disciplinar',
                'desconta_salario': True,
                'cor': '#6c757d',  # Cinza
                'ativo': True
            },
            {
                'nome': 'Atraso',
                'codigo': 'AT',
                'descricao': 'Chegou atrasado mas trabalhou',
                'desconta_salario': False,
                'cor': '#fd7e14',  # Laranja
                'ativo': True
            },
            {
                'nome': 'Outro',
                'codigo': 'OU',
                'descricao': 'Outras situações não especificadas',
                'desconta_salario': False,
                'cor': '#6c757d',  # Cinza
                'ativo': True
            }
        ]
        
        self.stdout.write("Criando tipos de presença padrão...")
        
        for tipo_data in tipos_presenca:
            tipo, created = TipoPresenca.objects.get_or_create(
                codigo=tipo_data['codigo'],
                defaults=tipo_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Criado: {tipo.nome}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"- Já existe: {tipo.nome}")
                )
        
        total = TipoPresenca.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"\nTotal de tipos de presença: {total}")
        )
