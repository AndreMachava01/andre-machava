from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from meuprojeto.empresa.models_rh import PerfilUsuario, Funcionario
from meuprojeto.empresa.models_base import Sucursal


class Command(BaseCommand):
    help = 'Cria perfis de usuário para usuários existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin',
            action='store_true',
            help='Torna todos os usuários administradores gerais',
        )

    def handle(self, *args, **options):
        self.stdout.write('Criando perfis de usuário...')
        
        # Obter primeira sucursal como padrão
        sucursal_padrao = Sucursal.objects.filter(ativa=True).first()
        
        if not sucursal_padrao:
            self.stdout.write(
                self.style.ERROR('Nenhuma sucursal ativa encontrada. Crie uma sucursal primeiro.')
            )
            return
        
        usuarios_sem_perfil = User.objects.filter(perfil__isnull=True)
        perfis_criados = 0
        
        for usuario in usuarios_sem_perfil:
            # Tentar encontrar funcionário correspondente
            funcionario = None
            try:
                funcionario = Funcionario.objects.get(email=usuario.email)
            except (Funcionario.DoesNotExist, Funcionario.MultipleObjectsReturned):
                pass
            
            # Criar perfil
            perfil = PerfilUsuario.objects.create(
                usuario=usuario,
                funcionario=funcionario,
                sucursal=funcionario.sucursal if funcionario else sucursal_padrao,
                is_admin_geral=options['admin'] or usuario.is_superuser,
                permissoes_stock=True,
                permissoes_rh=True
            )
            
            perfis_criados += 1
            self.stdout.write(
                f'Perfil criado para {usuario.username} - '
                f'Sucursal: {perfil.sucursal.nome} - '
                f'Admin: {perfil.is_admin_geral}'
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'{perfis_criados} perfis de usuário criados com sucesso!')
        )
        
        # Mostrar estatísticas
        total_usuarios = User.objects.count()
        total_perfis = PerfilUsuario.objects.count()
        admins_gerais = PerfilUsuario.objects.filter(is_admin_geral=True).count()
        
        self.stdout.write(f'\nEstatísticas:')
        self.stdout.write(f'Total de usuários: {total_usuarios}')
        self.stdout.write(f'Total de perfis: {total_perfis}')
        self.stdout.write(f'Administradores gerais: {admins_gerais}')
