# python manage.py desdobrar_despesas_rh
# python manage.py desdobrar_despesas_rh --data_inicio=2026-01-01 --data_fim=2026-02-28
# Lista cada item que compõe as despesas RH no período (Folha, Treinamentos, Empreitadas) para identificar a origem de cada valor.

from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Desdobra as despesas RH do período: lista cada folha, treinamento e empreitada (trabalho concluído) com valor.'

    def add_arguments(self, parser):
        parser.add_argument('--data_inicio', type=str, help='YYYY-MM-DD')
        parser.add_argument('--data_fim', type=str, help='YYYY-MM-DD')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_rh import FolhaSalarial, Treinamento, TrabalhoEmpreitada

        today = date.today()
        di_str = options.get('data_inicio') or (today - timedelta(days=365)).strftime('%Y-%m-%d')
        df_str = options.get('data_fim') or today.strftime('%Y-%m-%d')
        try:
            di = date.fromisoformat(di_str)
            df = date.fromisoformat(df_str)
        except ValueError:
            self.stdout.write(self.style.ERROR('Datas inválidas. Use YYYY-MM-DD.'))
            return

        self.stdout.write(f'Período: {di} a {df}\n')

        total_folha = Decimal('0.00')
        total_treinamento = Decimal('0.00')
        total_empreitada = Decimal('0.00')

        # Folhas (mês de referência no período)
        di_mes = date(di.year, di.month, 1)
        df_mes = date(df.year, df.month, 1)
        folhas = FolhaSalarial.objects.filter(
            mes_referencia__gte=di_mes,
            mes_referencia__lte=df_mes,
            status__in=['CALCULADA', 'FECHADA', 'PAGA'],
        ).order_by('mes_referencia')
        self.stdout.write('--- Folha (total encargos, mês ref. no período) ---')
        for fl in folhas:
            enc = fl.total_encargos or Decimal('0.00')
            total_folha += enc
            self.stdout.write(f"  {fl.mes_referencia.strftime('%Y-%m')}  {enc:.2f} MT  (status: {fl.status})")
        if not folhas:
            self.stdout.write('  (nenhuma)')
        self.stdout.write(f'  Subtotal Folha: {total_folha:.2f} MT\n')

        # Treinamentos concluídos no período
        treinos = Treinamento.objects.filter(
            status='CONCLUIDO',
            custo_total__gt=0,
            data_fim__gte=di,
            data_fim__lte=df,
        ).order_by('data_fim')
        self.stdout.write('--- Treinamentos concluídos no período ---')
        for t in treinos:
            val = t.custo_total or Decimal('0.00')
            total_treinamento += val
            self.stdout.write(f"  {t.data_fim}  {val:.2f} MT  {t.nome}")
        if not treinos:
            self.stdout.write('  (nenhum)')
        self.stdout.write(f'  Subtotal Treinamentos: {total_treinamento:.2f} MT\n')

        # Empreitadas (trabalhos por tarefa concluídos no período)
        trabalhos = TrabalhoEmpreitada.objects.filter(
            status='CONCLUIDO',
            valor_fixo__gt=0,
            data_conclusao__gte=di,
            data_conclusao__lte=df,
        ).select_related('prestador').order_by('data_conclusao')
        self.stdout.write('--- Empreitadas (trabalhos concluídos no período) ---')
        for trab in trabalhos:
            val = trab.valor_fixo or Decimal('0.00')
            total_empreitada += val
            nome = trab.prestador.nome if trab.prestador else 'N/A'
            self.stdout.write(f"  {trab.data_conclusao}  {val:.2f} MT  {nome} (id={trab.id})")
        if not trabalhos:
            self.stdout.write('  (nenhum)')
        self.stdout.write(f'  Subtotal Empreitadas: {total_empreitada:.2f} MT\n')

        total = total_folha + total_treinamento + total_empreitada
        self.stdout.write(self.style.SUCCESS(f'TOTAL despesas RH no período: {total:.2f} MT  (Folha {total_folha:.2f} + Treino {total_treinamento:.2f} + Empreitada {total_empreitada:.2f})'))
