"""
Reverte a confirmação do último recebimento (Contas a receber).

- Coloca o último PendenteContaReceber CONFIRMADO de volta em PENDENTE.
- Remove os lançamentos financeiros criados na confirmação (Débito 22, Crédito 71.01 e,
  se existirem, CMV 61.01 e 21).
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Reverte a confirmação do último item de Contas a receber (volta a PENDENTE e remove lançamentos).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria revertido, sem alterar a base de dados.',
        )

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_financas import (
            PendenteContaReceber,
            LancamentoFinanceiro,
        )

        dry_run = options['dry_run']

        pendente = (
            PendenteContaReceber.objects.filter(estado='CONFIRMADO')
            .order_by('-data_confirmacao', '-id')
            .select_related('lancamento', 'lancamento__conta')
            .first()
        )

        if not pendente:
            self.stdout.write(self.style.WARNING('Nenhum recebimento confirmado encontrado.'))
            return

        l1 = pendente.lancamento
        if not l1:
            self.stdout.write(
                self.style.WARNING(
                    f'Pendente {pendente.id} ({pendente.credor}, {pendente.valor} MT) está CONFIRMADO mas sem lançamento associado. '
                    'A repor estado para PENDENTE apenas.'
                )
            )
            if not dry_run:
                with transaction.atomic():
                    pendente.estado = 'PENDENTE'
                    pendente.data_confirmacao = None
                    pendente.confirmado_por_id = None
                    pendente.lancamento_id = None
                    pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por_id', 'lancamento_id'])
            else:
                self.stdout.write('(dry-run: não alterado)')
            return

        # Par do lançamento: mesmo data, documento_ref, origem_tipo, origem_id, conta 71.01
        l2 = (
            LancamentoFinanceiro.objects.filter(
                data=l1.data,
                documento_ref=l1.documento_ref,
                origem_tipo=l1.origem_tipo,
                origem_id=l1.origem_id,
                conta__codigo='71.01',
            )
            .exclude(pk=l1.pk)
            .first()
        )

        ordem_id = None
        if pendente.origem_tipo == 'VENDAS_FATURA' and pendente.origem_id:
            ordem_id = pendente.origem_id
        elif pendente.origem_tipo == 'VENDAS_PARCELA' and pendente.origem_id:
            try:
                from meuprojeto.empresa.models_stock import ParcelaPagamentoOrcamento
                parcela = ParcelaPagamentoOrcamento.objects.filter(id=pendente.origem_id).values_list('ordem_servico_id', flat=True).first()
                ordem_id = parcela
            except Exception:
                pass

        self.stdout.write(
            f'Último recebimento confirmado: ID {pendente.id} — {pendente.credor}, {pendente.valor} MT '
            f'(data conf. {pendente.data_confirmacao})'
        )
        self.stdout.write(f'  Lançamento débito (22): ID {l1.id}')
        if l2:
            self.stdout.write(f'  Lançamento crédito (71.01): ID {l2.id}')
        if ordem_id:
            self.stdout.write(f'  Ordem vendas ID {ordem_id} — serão removidos lançamentos CMV (61.01, 21) se existirem.')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        with transaction.atomic():
            # Remover lançamentos CMV (61.01 e 21) associados à ordem de vendas
            if ordem_id:
                cmv_inv = LancamentoFinanceiro.objects.filter(
                    origem_tipo='VENDAS',
                    origem_id=ordem_id,
                    conta__codigo__in=['61.01', '21'],
                )
                n_cmv = cmv_inv.count()
                if n_cmv:
                    cmv_inv.delete()
                    self.stdout.write(f'  Removidos {n_cmv} lançamento(s) CMV/Inventário (61.01, 21).')

            if l2:
                l2.delete()
            l1.delete()

            pendente.estado = 'PENDENTE'
            pendente.data_confirmacao = None
            pendente.confirmado_por_id = None
            pendente.lancamento_id = None
            pendente.save(update_fields=['estado', 'data_confirmacao', 'confirmado_por_id', 'lancamento_id'])

        self.stdout.write(self.style.SUCCESS('Confirmação revertida. O item voltou a PENDENTE.'))
