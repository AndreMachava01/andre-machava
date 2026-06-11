# python manage.py deletar_ordens_servico --codigos=OS-2025-000002,OS2025110001,OS-2025-000003
# Aceita códigos no formato exibido (OS/2025/000002) ou armazenado (OS-2025-000002, OS2025110001).

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Deleta ordens de serviço (OrdemServico) pelos códigos indicados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--codigos',
            type=str,
            required=True,
            help='Códigos separados por vírgula (ex: OS-2025-000002,OS2025110001,OS-2025-000003)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Apenas lista o que seria deletado, sem alterar.')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_stock import OrdemServico, ParcelaPagamentoOrcamento
        from meuprojeto.empresa.models_financas import PendenteContaReceber, LancamentoFinanceiro

        codigos_raw = (options['codigos'] or '').strip()
        dry_run = options.get('dry_run', False)
        if not codigos_raw:
            self.stdout.write(self.style.ERROR('Indique --codigos=...'))
            return

        codigos_busca = []
        for c in codigos_raw.split(','):
            c = c.strip()
            if not c:
                continue
            # Aceitar formato exibido OS/2025/000002 -> OS-2025-000002
            if '/' in c and '-' not in c:
                c = c.replace('/', '-')
            codigos_busca.append(c)

        ordens = list(OrdemServico.objects.filter(codigo__in=codigos_busca))
        if not ordens:
            self.stdout.write(self.style.WARNING(
                f'Nenhuma ordem encontrada com códigos: {codigos_busca}. '
                'Verifique se o código está correto (ex: OS-2025-000002 ou OS2025110001).'
            ))
            return

        ordem_ids = [o.id for o in ordens]
        parcela_ids = list(ParcelaPagamentoOrcamento.objects.filter(ordem_servico_id__in=ordem_ids).values_list('id', flat=True))

        for o in ordens:
            serv_nome = getattr(o.servico, 'nome', None) or '—'
            self.stdout.write(f'  {o.codigo} | {serv_nome} | {o.valor_total or 0} MT | {o.status}')

        pend_fatura = PendenteContaReceber.objects.filter(origem_tipo='VENDAS_FATURA', origem_id__in=ordem_ids)
        pend_parcela = PendenteContaReceber.objects.filter(origem_tipo='VENDAS_PARCELA', origem_id__in=parcela_ids)
        lancamentos = LancamentoFinanceiro.objects.filter(origem_tipo='VENDAS', origem_id__in=ordem_ids)
        n_pend = pend_fatura.count() + pend_parcela.count()
        n_lanc = lancamentos.count()
        if n_pend or n_lanc:
            self.stdout.write(self.style.WARNING(
                f'Existem {n_pend} pendente(s) de conta a receber e {n_lanc} lançamento(s) '
                'financeiros associados. Serão removidos para manter integridade.'
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY-RUN] Seriam deletadas {len(ordens)} ordem(ns). Execute sem --dry-run para confirmar.'))
            return

        with transaction.atomic():
            pend_fatura.delete()
            pend_parcela.delete()
            lancamentos.delete()
            for o in ordens:
                cod = o.codigo
                o.delete()
                self.stdout.write(self.style.SUCCESS(f'Deletada: {cod}'))

        self.stdout.write(self.style.SUCCESS(f'Total: {len(ordens)} ordem(ns) de serviço deletada(s).'))
