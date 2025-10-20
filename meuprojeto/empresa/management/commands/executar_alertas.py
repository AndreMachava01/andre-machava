from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from meuprojeto.empresa.signals_alertas import criar_alertas_sistema, limpar_notificacoes_antigas
from meuprojeto.empresa.models_stock import NotificacaoStock

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Executa o sistema de alertas automáticos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpar-antigas',
            action='store_true',
            help='Remove notificações antigas (mais de 30 dias)',
        )
        parser.add_argument(
            '--apenas-sistema',
            action='store_true',
            help='Cria apenas alertas do sistema (resumo geral)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Iniciando sistema de alertas automáticos...')
        )
        
        try:
            if options['limpar_antigas']:
                self.stdout.write('Limpando notificações antigas...')
                limpar_notificacoes_antigas()
                self.stdout.write(
                    self.style.SUCCESS('Notificações antigas removidas com sucesso!')
                )
            
            if options['apenas_sistema']:
                self.stdout.write('Criando alertas do sistema...')
                criar_alertas_sistema()
                self.stdout.write(
                    self.style.SUCCESS('Alertas do sistema criados com sucesso!')
                )
            else:
                # Executar ambos
                self.stdout.write('Executando sistema completo de alertas...')
                criar_alertas_sistema()
                limpar_notificacoes_antigas()
                self.stdout.write(
                    self.style.SUCCESS('Sistema de alertas executado com sucesso!')
                )
            
            # Mostrar estatísticas
            total_notificacoes = NotificacaoStock.objects.count()
            notificacoes_nao_lidas = NotificacaoStock.objects.filter(lida=False).count()
            
            self.stdout.write(f'Total de notificações: {total_notificacoes}')
            self.stdout.write(f'Notificações não lidas: {notificacoes_nao_lidas}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao executar sistema de alertas: {e}')
            )
            logger.error(f"Erro no comando de alertas: {e}")
