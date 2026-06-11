# python manage.py estado_trabalho_ordem --codigo=OS-2026-000003
# Mostra se o trabalho da ordem foi iniciado: status da ordem e das atividades (etapas).

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Mostra o estado do trabalho de uma ordem de serviço (status e atividades/etapas).'

    def add_arguments(self, parser):
        parser.add_argument('--codigo', type=str, help='Código da ordem (ex: OS-2026-000003)')
        parser.add_argument('--id', type=int, help='ID da OrdemServico')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_stock import OrdemServico, AtividadeExecucao

        codigo = (options.get('codigo') or '').strip()
        pk = options.get('id')
        if not codigo and pk is None:
            self.stdout.write(self.style.ERROR('Indique --codigo=OS-2026-000003 ou --id=<pk>'))
            return
        if codigo:
            ordem = OrdemServico.objects.filter(codigo=codigo).prefetch_related('atividades_execucao').first()
        else:
            ordem = OrdemServico.objects.filter(pk=pk).prefetch_related('atividades_execucao').first()
        if not ordem:
            self.stdout.write(self.style.ERROR(f'Ordem não encontrada (codigo={codigo!r} ou id={pk}).'))
            return

        self.stdout.write(f'Ordem: {ordem.codigo} (id={ordem.id})')
        self.stdout.write(f'  Status: {ordem.get_status_display()} ({ordem.status})')
        self.stdout.write(f'  data_inicio (ordem): {ordem.data_inicio or "—"}')
        self.stdout.write(f'  data_conclusao (ordem): {ordem.data_conclusao or "—"}')

        atividades = list(ordem.atividades_execucao.all().order_by('numero_ordem', 'id'))
        if not atividades:
            self.stdout.write('  Etapas/actividades: nenhuma definida.')
        else:
            self.stdout.write(f'  Etapas/actividades: {len(atividades)}')
            for a in atividades:
                ini = f'  Início: {a.data_inicio}' if a.data_inicio else '  Início: —'
                fim = f' Conclusão: {a.data_conclusao}' if a.data_conclusao else ''
                self.stdout.write(f'    - {a.nome} | status={a.get_status_display()} | {ini}{fim}')

        # Trabalho iniciado = ordem não está só AGENDADA ou há alguma etapa iniciada/concluída
        ordem_iniciada = ordem.status in ('EM_ANDAMENTO', 'PAUSADA', 'CONCLUIDA') or ordem.data_inicio is not None
        alguma_etapa_iniciada = any(
            a.status in ('EM_ANDAMENTO', 'PAUSADA', 'CONCLUIDA') or a.data_inicio is not None
            for a in atividades
        )
        trabalho_iniciado = ordem_iniciada or alguma_etapa_iniciada

        if trabalho_iniciado:
            self.stdout.write(self.style.SUCCESS('Trabalho iniciado: sim (ordem ou pelo menos uma etapa já iniciada/concluída).'))
        else:
            self.stdout.write(self.style.WARNING('Trabalho iniciado: não (ordem agendada e nenhuma etapa com início registado).'))
