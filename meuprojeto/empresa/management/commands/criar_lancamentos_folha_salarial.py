# Uso:
#   python manage.py criar_lancamentos_folha_salarial
#     → Processa todas as folhas fechadas/pagas que ainda não têm lançamentos financeiros.
#   python manage.py criar_lancamentos_folha_salarial --folha=123
#     → Cria lançamentos apenas para a folha com ID 123 (se fechada e sem lançamentos).

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Cria lançamentos financeiros (62.01 + 33) para folhas salariais fechadas que ainda não os têm.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--folha',
            type=int,
            default=None,
            help='ID da folha salarial. Se omitido, processa todas as folhas fechadas/pagas sem lançamentos.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas lista as folhas que seriam processadas, sem criar lançamentos.',
        )

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_rh import FolhaSalarial
        from meuprojeto.empresa.models_financas import Conta, LancamentoFinanceiro

        folha_id = options.get('folha')
        dry_run = options.get('dry_run', False)

        if folha_id is not None:
            try:
                folha = FolhaSalarial.objects.get(id=folha_id)
            except FolhaSalarial.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Folha salarial com ID {folha_id} não encontrada.'))
                return
            if folha.status not in ('FECHADA', 'PAGA'):
                self.stdout.write(
                    self.style.ERROR(f'Folha {folha_id} não está fechada/paga (status={folha.status}). Só se criam lançamentos para folhas fechadas.')
                )
                return
            folhas = [folha]
        else:
            # Folhas fechadas ou pagas que ainda não têm lançamento RH
            com_lancamento_ids = set(
                LancamentoFinanceiro.objects.filter(origem_tipo='RH')
                .values_list('origem_id', flat=True)
                .distinct()
            )
            folhas = list(
                FolhaSalarial.objects.filter(status__in=('FECHADA', 'PAGA'))
                .exclude(id__in=com_lancamento_ids)
                .order_by('mes_referencia')
            )

        if not folhas:
            self.stdout.write(self.style.SUCCESS('Nenhuma folha fechada sem lançamentos para processar.'))
            return

        if dry_run:
            self.stdout.write(f'[DRY-RUN] Seriam processadas {len(folhas)} folha(s):')
            for f in folhas:
                valor = f.total_liquido or f.total_bruto or Decimal('0')
                self.stdout.write(f'  ID={f.id} mes_referencia={f.mes_referencia} total_liquido={valor} status={f.status}')
            return

        criados = 0
        erros = 0
        for folha in folhas:
            valor = getattr(folha, 'total_liquido', None) or getattr(folha, 'total_bruto', None) or Decimal('0.00')
            if isinstance(valor, (int, float)):
                valor = Decimal(str(valor))
            if not valor or valor <= 0:
                self.stdout.write(
                    self.style.WARNING(f'Folha ID={folha.id} ({folha.mes_referencia}): total_liquido/bruto é zero; ignorada.')
                )
                continue
            if LancamentoFinanceiro.objects.filter(origem_tipo='RH', origem_id=folha.id).exists():
                self.stdout.write(self.style.WARNING(f'Folha ID={folha.id} já tem lançamentos; ignorada.'))
                continue
            try:
                with transaction.atomic():
                    data_mov = folha.data_fechamento or folha.mes_referencia
                    descricao = f"Folha {folha.mes_referencia}"
                    doc_ref = f"Folha-{folha.mes_referencia}"
                    conta_pessoal, _ = Conta.objects.get_or_create(
                        codigo='62.01',
                        defaults={'nome': 'Pessoal (folha)', 'tipo': 'DESPESA', 'ativo': True, 'ordem': 0},
                    )
                    conta_obrigacoes, _ = Conta.objects.get_or_create(
                        codigo='33',
                        defaults={'nome': 'Estado e outros credores', 'tipo': 'PASSIVO', 'ativo': True, 'ordem': 0},
                    )
                    LancamentoFinanceiro.objects.create(
                        data=data_mov,
                        conta=conta_pessoal,
                        valor=-valor,
                        descricao=descricao,
                        documento_ref=doc_ref,
                        origem_tipo='RH',
                        origem_id=folha.id,
                        criado_por=None,
                    )
                    LancamentoFinanceiro.objects.create(
                        data=data_mov,
                        conta=conta_obrigacoes,
                        valor=valor,
                        descricao=descricao,
                        documento_ref=doc_ref,
                        origem_tipo='RH',
                        origem_id=folha.id,
                        criado_por=None,
                    )
                criados += 1
                self.stdout.write(self.style.SUCCESS(f'Lançamentos criados para folha ID={folha.id} ({folha.mes_referencia}), valor={valor} MT.'))
            except Exception as e:
                erros += 1
                self.stdout.write(self.style.ERROR(f'Erro na folha ID={folha.id}: {e}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Concluído: {criados} folha(s) com lançamentos criados.'))
        if erros:
            self.stdout.write(self.style.ERROR(f'{erros} folha(s) com erro.'))
