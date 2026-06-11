# python manage.py despesas_rh_desdobramento [--dias=90]
# Lista cada linha que compõe as despesas RH no período (Folha, Treinamentos, Empreitadas) para ver a origem de cada valor.

from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Desdobra as despesas RH no período: Folha, Treinamentos, Empreitadas (trabalhos concluídos).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=365, help='Período em dias (default 365)')
        parser.add_argument('--data-fim', type=str, default=None, help='Data fim YYYY-MM-DD (default hoje)')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_rh import FolhaSalarial, Treinamento, TrabalhoEmpreitada

        dias = options['dias']
        data_fim_str = options.get('data_fim')
        if data_fim_str:
            try:
                df = date.fromisoformat(data_fim_str)
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Data inválida: {data_fim_str}'))
                return
        else:
            df = date.today()
        di = df - timedelta(days=dias)

        self.stdout.write(f'Período: {di} a {df}\n')

        total_folha = Decimal('0.00')
        total_treinamento = Decimal('0.00')
        total_empreitada = Decimal('0.00')

        # Folhas
        di_mes = date(di.year, di.month, 1)
        df_mes = date(df.year, df.month, 1)
        folhas = FolhaSalarial.objects.filter(
            mes_referencia__gte=di_mes,
            mes_referencia__lte=df_mes,
        ).filter(status__in=['CALCULADA', 'FECHADA', 'PAGA']).order_by('mes_referencia')
        self.stdout.write('--- Folha (total_encargos, mês ref. no período) ---')
        for fl in folhas:
            encargos = fl.total_encargos or Decimal('0.00')
            total_folha += encargos
            self.stdout.write(f'  {fl.mes_referencia}  id={fl.id}  status={fl.status}  ->  {encargos:.2f} MT')
        if not folhas:
            self.stdout.write('  (nenhuma)')
        self.stdout.write(f'  Subtotal Folha: {total_folha:.2f} MT\n')

        # Treinamentos
        treinamentos = Treinamento.objects.filter(
            status='CONCLUIDO',
            custo_total__gt=0,
            data_fim__gte=di,
            data_fim__lte=df,
        ).order_by('data_fim')
        self.stdout.write('--- Treinamentos concluídos no período ---')
        for t in treinamentos:
            val = t.custo_total or Decimal('0.00')
            total_treinamento += val
            self.stdout.write(f'  {t.data_fim}  id={t.id}  "{t.nome}"  →  {val:.2f} MT')
        if not treinamentos:
            self.stdout.write('  (nenhum)')
        self.stdout.write(f'  Subtotal Treinamentos: {total_treinamento:.2f} MT\n')

        # Empreitadas (trabalhos concluídos)
        trabalhos = TrabalhoEmpreitada.objects.filter(
            status='CONCLUIDO',
            valor_fixo__gt=0,
            data_conclusao__gte=di,
            data_conclusao__lte=df,
        ).select_related('prestador').order_by('data_conclusao')
        self.stdout.write('--- Empreitadas (trabalhos por tarefa concluídos no período) ---')
        for trab in trabalhos:
            val = trab.valor_fixo or Decimal('0.00')
            total_empreitada += val
            nome = trab.prestador.nome if trab.prestador else 'N/A'
            self.stdout.write(f'  {trab.data_conclusao}  id={trab.id}  {nome}  ->  {val:.2f} MT')
        if not trabalhos:
            self.stdout.write('  (nenhum)')
        self.stdout.write(f'  Subtotal Empreitadas (trab.): {total_empreitada:.2f} MT\n')

        total = total_folha + total_treinamento + total_empreitada
        self.stdout.write(self.style.SUCCESS(f'TOTAL despesas RH (dashboard) = {total:.2f} MT  (Folha {total_folha:.2f} + Treino {total_treinamento:.2f} + Empreitada trab. {total_empreitada:.2f})'))
        self.stdout.write('Os 700 MT que faltam para 5900 vêm de uma destas linhas acima (ex.: uma folha com total_encargos = 700).')
