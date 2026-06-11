"""Auditoria de integração RH → Finanças (pendentes em falta)."""
from django.core.management.base import BaseCommand

from meuprojeto.empresa.services.rh_financas_sync import auditar_integracao_rh_financas


class Command(BaseCommand):
    help = 'Lista folhas/empreitadas RH sem pendente em Contas a pagar'

    def handle(self, *args, **options):
        resultado = auditar_integracao_rh_financas()
        self.stdout.write(self.style.SUCCESS('Auditoria RH ↔ Finanças'))
        self.stdout.write(f"Pendentes RH abertos: {resultado['pendentes_rh_abertos']}")
        self.stdout.write(
            f"Folhas fechadas sem pendente: {len(resultado['folhas_fechadas_sem_pendente'])}"
        )
        for fid in resultado['folhas_fechadas_sem_pendente'][:20]:
            self.stdout.write(f'  - folha_id={fid}')
        self.stdout.write(
            f"Empreitadas concluídas sem pendente: {len(resultado['empreitadas_concluidas_sem_pendente'])}"
        )
        for tid in resultado['empreitadas_concluidas_sem_pendente'][:20]:
            self.stdout.write(f'  - trabalho_id={tid}')
