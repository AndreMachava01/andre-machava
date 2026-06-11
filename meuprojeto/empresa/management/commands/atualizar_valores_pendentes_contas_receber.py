"""
Recalcula o valor dos PendenteContaReceber de origem VENDAS_PARCELA para usar
o total COM IVA (igual ao contrato). Corrige pendentes criados antes da alteração
que usavam total sem IVA.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from meuprojeto.empresa.models_financas import PendenteContaReceber
from meuprojeto.empresa.models_stock import ParcelaPagamentoOrcamento
from meuprojeto.empresa.parcelas_vendas_utils import _valor_total_com_iva_ordem


class Command(BaseCommand):
    help = 'Atualiza o valor dos pendentes de conta a receber (VENDAS_PARCELA) para total com IVA (igual ao contrato)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria alterado sem gravar',
        )
        parser.add_argument(
            '--todos',
            action='store_true',
            help='Alterar também pendentes já CONFIRMADOS ou REJEITADOS (por defeito só PENDENTE)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        todos = options['todos']

        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será gravada.'))

        qs = PendenteContaReceber.objects.filter(origem_tipo='VENDAS_PARCELA', origem_id__isnull=False)
        if not todos:
            qs = qs.filter(estado='PENDENTE')
        pendentes = list(qs.select_related())

        self.stdout.write(f'Encontrados {len(pendentes)} pendente(s) de parcela para processar.')

        atualizados = 0
        erros = 0

        for pendente in pendentes:
            try:
                parcela = ParcelaPagamentoOrcamento.objects.select_related('ordem_servico').filter(
                    id=pendente.origem_id
                ).first()
                if not parcela or not parcela.ordem_servico:
                    self.stdout.write(self.style.WARNING(f'  Pendente {pendente.id}: parcela ou ordem não encontrada.'))
                    erros += 1
                    continue

                ordem = parcela.ordem_servico
                valor_total_iva = _valor_total_com_iva_ordem(ordem)
                if valor_total_iva <= 0:
                    self.stdout.write(self.style.WARNING(f'  Pendente {pendente.id}: ordem {ordem.codigo} sem valor total.'))
                    erros += 1
                    continue

                novo_valor = valor_total_iva * Decimal(parcela.percentagem) / Decimal('100')
                if novo_valor <= 0:
                    continue

                valor_antigo = pendente.valor
                if abs(valor_antigo - novo_valor) < Decimal('0.01'):
                    self.stdout.write(f'  Pendente {pendente.id} ({ordem.codigo}, parcela {parcela.numero_ordem}): já correto {valor_antigo:.2f} MT')
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.NOTICE(
                            f'  [DRY-RUN] Pendente {pendente.id} ({ordem.codigo}, parcela {parcela.numero_ordem}): '
                            f'{valor_antigo:.2f} MT -> {novo_valor:.2f} MT'
                        )
                    )
                else:
                    with transaction.atomic():
                        pendente.valor = novo_valor
                        pendente.save(update_fields=['valor'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Pendente {pendente.id} ({ordem.codigo}, parcela {parcela.numero_ordem}): '
                            f'{valor_antigo:.2f} MT -> {novo_valor:.2f} MT'
                        )
                    )
                atualizados += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Pendente {pendente.id}: erro — {e}'))
                erros += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Concluído: {atualizados} valor(es) atualizado(s), {erros} erro(s).'))
        if dry_run and atualizados:
            self.stdout.write(self.style.WARNING('Execute sem --dry-run para aplicar as alterações.'))
