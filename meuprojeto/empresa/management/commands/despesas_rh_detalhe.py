# python manage.py despesas_rh_detalhe
# Lista cada linha que compõe as despesas RH no período (folha, treinamentos, empreitadas) para ver de onde vem cada valor.

from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Lista o detalhe das despesas RH no período (folha, treinamentos, empreitadas) para identificar a origem de cada valor.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=365, help='Período em dias (default 365)')
        parser.add_argument('--data-fim', type=str, help='Data fim YYYY-MM-DD (default: hoje)')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_rh import FolhaSalarial, Treinamento, TrabalhoEmpreitada

        hoje = date.today()
        df = options.get('data_fim')
        if df:
            try:
                df = date.fromisoformat(df)
            except ValueError:
                self.stdout.write(self.style.ERROR('data_fim inválida. Use YYYY-MM-DD.'))
                return
        else:
            df = hoje
        dias = options.get('dias', 365)
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
            enc = fl.total_encargos or Decimal('0.00')
            total_folha += enc
            self.stdout.write(f'  {fl.mes_referencia.strftime("%Y-%m")}  {enc:.2f} MT  (status={fl.status})')
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
            self.stdout.write(f'  {t.data_fim}  {val:.2f} MT  {t.nome[:50]}')
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
            self.stdout.write(f'  {trab.data_conclusao}  {val:.2f} MT  ID={trab.id}  {nome[:40]}')
        if not trabalhos:
            self.stdout.write('  (nenhum)')
        self.stdout.write(f'  Subtotal Empreitadas: {total_empreitada:.2f} MT\n')

        total = total_folha + total_treinamento + total_empreitada
        self.stdout.write(self.style.SUCCESS(f'TOTAL despesas RH = {total:.2f} MT  (Folha {total_folha:.2f} + Treino {total_treinamento:.2f} + Empreitada {total_empreitada:.2f})'))
