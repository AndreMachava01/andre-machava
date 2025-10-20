import os
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess

class Command(BaseCommand):
    help = 'Faz backup do banco de dados PostgreSQL'

    def handle(self, *args, **options):
        # Configurações do banco de dados
        db_settings = settings.DATABASES['default']
        
        # Data atual para o nome do arquivo
        date_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Diretório de backup
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Nome do arquivo de backup
        filename = f'backup_{date_str}.sql'
        backup_path = os.path.join(backup_dir, filename)
        
        # Configurar variáveis de ambiente para pg_dump
        env = dict(os.environ)
        env['PGPASSWORD'] = db_settings['PASSWORD']
        
        # Comando pg_dump
        cmd = [
            'pg_dump',
            '--host=' + db_settings['HOST'],
            '--port=' + str(db_settings['PORT']),
            '--username=' + db_settings['USER'],
            '--dbname=' + db_settings['NAME'],
            '--file=' + backup_path,
            '--format=p',  # Formato plain text SQL
            '--clean',     # Inclui comandos DROP
            '--if-exists', # Adiciona IF EXISTS nos DROPs
        ]
        
        try:
            # Executar o backup
            subprocess.run(cmd, env=env, check=True)
            self.stdout.write(
                self.style.SUCCESS(f'Backup criado com sucesso em {backup_path}')
            )
            
            # Listar backups antigos
            backups = sorted([
                f for f in os.listdir(backup_dir) 
                if f.startswith('backup_') and f.endswith('.sql')
            ])
            
            # Manter apenas os últimos 5 backups
            while len(backups) > 5:
                old_backup = os.path.join(backup_dir, backups.pop(0))
                os.remove(old_backup)
                self.stdout.write(
                    self.style.WARNING(f'Backup antigo removido: {old_backup}')
                )
                
        except subprocess.CalledProcessError as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao criar backup: {str(e)}')
            )
