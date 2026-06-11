"""
Comando para remover RequisicaoStock duplicadas que foram migradas para RequisicaoProducao
"""
from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_stock import RequisicaoStock, RequisicaoProducao
from django.db import transaction
import re


class Command(BaseCommand):
    help = 'Remove RequisicaoStock duplicadas que foram migradas para RequisicaoProducao'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria feito sem fazer alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será feita'))
        
        # Buscar todas as RequisicaoProducao
        requisicoes_producao = RequisicaoProducao.objects.all()
        
        # Criar um dicionário de códigos migrados
        codigos_migrados = {}
        for req_prod in requisicoes_producao:
            # Extrair número do código REQPROD####
            match = re.search(r'REQPROD(\d+)', req_prod.codigo)
            if match:
                numero = match.group(1)
                codigo_stock = f"REQ{numero.zfill(4)}"
                codigos_migrados[codigo_stock] = req_prod.codigo
        
        self.stdout.write(f'\nCódigos migrados encontrados: {len(codigos_migrados)}')
        for codigo_stock, codigo_prod in codigos_migrados.items():
            self.stdout.write(f'  {codigo_stock} -> {codigo_prod}')
        
        # Buscar RequisicaoStock que foram migradas
        requisicoes_duplicadas = RequisicaoStock.objects.filter(
            codigo__in=list(codigos_migrados.keys())
        )
        
        total_removidas = 0
        
        for req_stock in requisicoes_duplicadas:
            codigo_prod = codigos_migrados.get(req_stock.codigo)
            self.stdout.write(f'\n{req_stock.codigo}:')
            self.stdout.write(f'  Status: {req_stock.status}')
            self.stdout.write(f'  Itens: {req_stock.itens.count()}')
            self.stdout.write(f'  Migrada para: {codigo_prod}')
            
            if not dry_run:
                try:
                    with transaction.atomic():
                        # Verificar se a RequisicaoProducao existe
                        req_prod = RequisicaoProducao.objects.filter(codigo=codigo_prod).first()
                        if req_prod:
                            # Verificar se tem os mesmos itens
                            itens_stock = req_stock.itens.count()
                            itens_prod = req_prod.itens.count()
                            
                            if itens_stock == itens_prod:
                                # Remover RequisicaoStock
                                req_stock.delete()
                                self.stdout.write(self.style.SUCCESS(f'  [OK] Removida (duplicada de {codigo_prod})'))
                                total_removidas += 1
                            else:
                                self.stdout.write(self.style.WARNING(f'  [AVISO] Número de itens diferente ({itens_stock} vs {itens_prod}). Não removida.'))
                        else:
                            self.stdout.write(self.style.ERROR(f'  [ERRO] RequisicaoProducao {codigo_prod} não encontrada.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  [ERRO] Erro ao remover: {str(e)}'))
            else:
                self.stdout.write(self.style.WARNING(f'  [DRY-RUN] Seria removida'))
                total_removidas += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY-RUN] Total de requisições que seriam removidas: {total_removidas}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n[OK] Total de requisições removidas: {total_removidas}'))

