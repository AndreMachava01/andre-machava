from django.core.management.base import BaseCommand
from django.utils import timezone
from meuprojeto.empresa.models_rh import AvaliacaoDesempenho
from datetime import date


class Command(BaseCommand):
    help = 'Actualiza o status das avaliações de desempenho automaticamente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria actualizado sem fazer alterações',
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['PLANEJADA', 'EM_ANDAMENTO', 'CONCLUIDA', 'CANCELADA'],
            help='Actualizar apenas avaliações com status específico',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        status_filter = options.get('status')
        
        self.stdout.write(
            self.style.SUCCESS('Iniciando actualização automática de status das avaliações...')
        )
        
        # Filtrar avaliações
        avaliacoes = AvaliacaoDesempenho.objects.all()
        if status_filter:
            avaliacoes = avaliacoes.filter(status=status_filter)
        
        # Excluir avaliações canceladas
        avaliacoes = avaliacoes.exclude(status='CANCELADA')
        
        total_avaliacoes = avaliacoes.count()
        actualizadas = 0
        
        self.stdout.write(f'Encontradas {total_avaliacoes} avaliações para verificar...')
        
        for avaliacao in avaliacoes:
            status_anterior = avaliacao.status
            
            if dry_run:
                # Simular actualização
                if avaliacao.actualizar_status_automatico():
                    self.stdout.write(
                        f'[DRY-RUN] Avaliação {avaliacao.id} seria actualizada de {status_anterior} para {avaliacao.status}'
                    )
                    actualizadas += 1
            else:
                # Actualizar realmente
                if avaliacao.actualizar_status_automatico():
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Avaliação {avaliacao.id} actualizada de {status_anterior} para {avaliacao.status}'
                        )
                    )
                    actualizadas += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY-RUN] {actualizadas} avaliações seriam actualizadas')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Actualização concluída! {actualizadas} avaliações foram actualizadas.')
            )
            
        # Estatísticas adicionais
        self.mostrar_estatisticas()

    def mostrar_estatisticas(self):
        """Mostra estatísticas das avaliações"""
        hoje = timezone.now().date()
        
        stats = {
            'PLANEJADA': AvaliacaoDesempenho.objects.filter(status='PLANEJADA').count(),
            'EM_ANDAMENTO': AvaliacaoDesempenho.objects.filter(status='EM_ANDAMENTO').count(),
            'CONCLUIDA': AvaliacaoDesempenho.objects.filter(status='CONCLUIDA').count(),
            'CANCELADA': AvaliacaoDesempenho.objects.filter(status='CANCELADA').count(),
        }
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('ESTATÍSTICAS ATUAIS DAS AVALIAÇÕES:')
        self.stdout.write('='*50)
        
        for status, count in stats.items():
            status_display = dict(AvaliacaoDesempenho.STATUS_CHOICES)[status]
            self.stdout.write(f'{status_display}: {count}')
        
        # Avaliações vencidas
        vencidas = AvaliacaoDesempenho.objects.filter(
            status='EM_ANDAMENTO',
            data_fim__lt=hoje
        ).count()
        
        if vencidas > 0:
            self.stdout.write(
                self.style.WARNING(f'\n⚠️  {vencidas} avaliações vencidas (data fim < hoje)')
            )
        
        # Avaliações que podem ser concluídas
        podem_concluir = AvaliacaoDesempenho.objects.filter(
            status__in=['PLANEJADA', 'EM_ANDAMENTO'],
            nota_geral__isnull=False
        ).filter(
            criterios_avaliados__isnull=False
        ).distinct().count()
        
        if podem_concluir > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ {podem_concluir} avaliações podem ser concluídas automaticamente')
            )
