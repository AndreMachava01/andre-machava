"""
Reinicia o início da execução de uma ordem de serviço (OS):
- Limpa data_inicio e data_conclusao da ordem
- Coloca a ordem em status AGENDADA
- Para todas as actividades do plano de execução: limpa data_inicio/data_conclusao e status AGENDADA

Uso: python manage.py reiniciar_execucao_ordem_servico OS/2026/000003 [--dry-run] [--yes]
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Reinicia o início da execução de uma ordem de serviço (limpa datas e repõe estado).'

    def add_arguments(self, parser):
        parser.add_argument(
            'codigo',
            type=str,
            help='Código da ordem de serviço (ex.: OS/2026/000003)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Só mostrar o que seria alterado.')
        parser.add_argument('--yes', action='store_true', help='Não pedir confirmação.')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_stock import OrdemServico, AtividadeExecucao

        codigo = (options['codigo'] or '').strip()
        dry_run = options['dry_run']
        yes = options['yes']

        if not codigo:
            self.stdout.write(self.style.ERROR('Indique o código da ordem (ex.: OS/2026/000003).'))
            return

        # Na BD o código está com hífens (OS-2026-000003); na UI pode vir com barras (OS/2026/000003)
        codigo_bd = codigo.replace('/', '-')

        try:
            ordem = OrdemServico.objects.get(codigo=codigo_bd)
        except OrdemServico.DoesNotExist:
            try:
                ordem = OrdemServico.objects.get(codigo=codigo)
            except OrdemServico.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Ordem de serviço com código {codigo!r} não encontrada.'))
                return

        atividades = list(ordem.atividades_execucao.all().order_by('parent_id', 'numero_ordem', 'id'))
        n_atv = len(atividades)

        self.stdout.write(
            f'Ordem: {ordem.codigo} (id={ordem.id})\n'
            f'  Status actual: {ordem.get_status_display()}\n'
            f'  data_inicio: {ordem.data_inicio}\n'
            f'  data_conclusao: {ordem.data_conclusao}\n'
            f'  Actividades do plano: {n_atv}'
        )
        for a in atividades[:15]:
            self.stdout.write(f'    - {a.nome} (id={a.id}) status={a.status}')
        if n_atv > 15:
            self.stdout.write(f'    ... e mais {n_atv - 15}')

        if not dry_run and not yes:
            confirm = input('Reiniciar execução (limpar datas e repor AGENDADA)? [y/N]: ')
            if confirm.strip().lower() != 'y':
                self.stdout.write('Operação cancelada.')
                return

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run: nenhuma alteração feita.'))
            return

        with transaction.atomic():
            # Actividades: limpar datas e status AGENDADA
            AtividadeExecucao.objects.filter(ordem_servico=ordem).update(
                data_inicio=None,
                data_conclusao=None,
                status='AGENDADA',
            )
            # Ordem: limpar datas e status AGENDADA
            ordem.data_inicio = None
            ordem.data_conclusao = None
            ordem.status = 'AGENDADA'
            ordem.save(update_fields=['data_inicio', 'data_conclusao', 'status'])

        self.stdout.write(self.style.SUCCESS(
            f'Execução reiniciada: ordem {ordem.codigo} e {n_atv} actividade(s) repostas para estado inicial (AGENDADA, sem datas).'
        ))
