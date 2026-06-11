"""
Comando para recriar itens removidos de requisições de compra externa
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from meuprojeto.empresa.models_stock import (
    RequisicaoCompraExterna, ItemRequisicaoCompraExterna,
    OrdemCompra, ItemOrdemCompra
)


class Command(BaseCommand):
    help = 'Recria itens removidos de requisições de compra externa baseado nas ordens de compra'

    def add_arguments(self, parser):
        parser.add_argument(
            '--requisicao',
            type=str,
            help='Código da requisição específica para corrigir (opcional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a correção sem salvar alterações',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        req_codigo = options.get('requisicao')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Modo de simulação ativado'))
        
        self.stdout.write(self.style.SUCCESS('=== RECRIAÇÃO DE ITENS EM REQUISIÇÕES DE COMPRA ===\n'))
        
        # Buscar requisições
        if req_codigo:
            requisicoes = RequisicaoCompraExterna.objects.filter(codigo=req_codigo)
            if not requisicoes.exists():
                self.stdout.write(self.style.ERROR(f'Requisição {req_codigo} não encontrada.'))
                return
        else:
            # Buscar requisições que têm ordens mas não têm itens
            requisicoes = RequisicaoCompraExterna.objects.filter(
                ordens_compra__isnull=False
            ).distinct()
        
        if not requisicoes.exists():
            self.stdout.write(self.style.SUCCESS('Nenhuma requisição encontrada.'))
            return
        
        self.stdout.write(f'Encontradas {requisicoes.count()} requisição(ões) para verificar.\n')
        
        total_recriados = 0
        
        with transaction.atomic():
            for req in requisicoes:
                self.stdout.write(f'\n--- Processando Requisição: {req.codigo} ---')
                
                # Buscar ordens recebidas desta requisição
                ordens = OrdemCompra.objects.filter(
                    requisicao_origem=req,
                    status='RECEBIDA'
                )
                
                if not ordens.exists():
                    self.stdout.write(self.style.WARNING(f'  Nenhuma ordem recebida encontrada.'))
                    continue
                
                # Buscar todos os itens únicos das ordens
                itens_ordens = {}
                for ordem in ordens:
                    for item_ordem in ordem.itens.all():
                        if not item_ordem.produto:
                            continue
                        
                        item_id = item_ordem.produto.id
                        if item_id not in itens_ordens:
                            itens_ordens[item_id] = {
                                'item': item_ordem.produto,
                                'quantidade_solicitada': 0,
                                'quantidade_recebida': 0
                            }
                        
                        itens_ordens[item_id]['quantidade_solicitada'] += item_ordem.quantidade_solicitada
                        itens_ordens[item_id]['quantidade_recebida'] += item_ordem.quantidade_recebida
                
                # Verificar quais itens não existem na requisição
                for item_id, dados in itens_ordens.items():
                    item_req = ItemRequisicaoCompraExterna.objects.filter(
                        requisicao=req,
                        item=dados['item']
                    ).first()
                    
                    if not item_req:
                        # Item não existe na requisição, recriar
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Item: {dados["item"].nome} - Não encontrado na requisição'
                            )
                        )
                        self.stdout.write(f'    Quantidade Solicitada (ordens): {dados["quantidade_solicitada"]}')
                        self.stdout.write(f'    Quantidade Recebida (ordens): {dados["quantidade_recebida"]}')
                        
                        if not dry_run:
                            # Buscar observação original da requisição para manter rastreamento
                            observacoes_origem = ''
                            if req.observacoes and 'origem:' in req.observacoes.lower():
                                origem_part = req.observacoes.split('origem:')[-1].strip()
                                observacoes_origem = f'Item recriado após correção. Quantidade fixa para rastreamento do trabalho (origem: {origem_part})'
                            
                            item_req = ItemRequisicaoCompraExterna.objects.create(
                                requisicao=req,
                                item=dados['item'],
                                quantidade_solicitada=dados['quantidade_solicitada'],
                                quantidade_recebida=dados['quantidade_recebida'],
                                observacoes=observacoes_origem
                            )
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'    [RECRIADO] Item adicionado à requisição {req.codigo}'
                                )
                            )
                            total_recriados += 1
                        else:
                            self.stdout.write(self.style.WARNING('    [DRY-RUN] Seria recriado'))
                    else:
                        # Item existe, atualizar quantidade_recebida
                        if item_req.quantidade_recebida != dados['quantidade_recebida']:
                            self.stdout.write(
                                f'  Item: {dados["item"].nome} - Atualizar quantidade_recebida'
                            )
                            self.stdout.write(f'    Atual: {item_req.quantidade_recebida}, Correto: {dados["quantidade_recebida"]}')
                            
                            if not dry_run:
                                item_req.quantidade_recebida = dados['quantidade_recebida']
                                item_req.save()
                                
                                self.stdout.write(
                                    self.style.SUCCESS(f'    [ATUALIZADO] quantidade_recebida corrigida')
                                )
                            else:
                                self.stdout.write(self.style.WARNING('    [DRY-RUN] Seria atualizado'))
        
        # Resumo
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Total de itens recriados: {total_recriados}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n[DRY-RUN] Nenhuma alteração foi feita. '
                    'Execute sem --dry-run para aplicar as correções.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nCorreções aplicadas com sucesso!')
            )

