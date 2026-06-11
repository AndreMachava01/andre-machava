"""
Comando para corrigir quantidades de requisições de produção que foram criadas
sem considerar o rendimento da receita.
"""
from django.core.management.base import BaseCommand
from django.db import transaction, models
from decimal import Decimal, ROUND_UP
from meuprojeto.empresa.models_stock import RequisicaoStock, ItemRequisicaoStock, OrdemProducao
import re


class Command(BaseCommand):
    help = 'Corrige quantidades de requisições de produção que não consideraram o rendimento'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra o que seria corrigido sem fazer alterações',
        )
        parser.add_argument(
            '--requisicao-id',
            type=int,
            help='ID específico da requisição a corrigir (opcional)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        requisicao_id = options.get('requisicao_id')
        
        # Buscar requisições de produção
        if requisicao_id:
            requisicoes = RequisicaoStock.objects.filter(id=requisicao_id)
        else:
            # Buscar requisições com ordem_producao OU com observações indicando ordem de produção
            requisicoes = RequisicaoStock.objects.filter(
                models.Q(ordem_producao__isnull=False) |
                models.Q(observacoes__icontains='Ordem de Produção')
            )
        
        if not requisicoes.exists():
            self.stdout.write(self.style.WARNING('Nenhuma requisição de produção encontrada.'))
            return
        
        self.stdout.write(f'Encontradas {requisicoes.count()} requisição(ões) de produção.\n')
        
        total_corrigidas = 0
        total_itens_corrigidos = 0
        
        for requisicao in requisicoes.select_related('ordem_producao', 'ordem_producao__receita'):
            ordem = requisicao.ordem_producao
            
            # Se não tem ordem associada, tentar encontrar pelas observações
            if not ordem and requisicao.observacoes:
                # Procurar código da ordem nas observações (ex: "OP2025110002")
                match = re.search(r'OP\d+', requisicao.observacoes)
                if match:
                    codigo_ordem = match.group(0)
                    try:
                        ordem = OrdemProducao.objects.get(codigo=codigo_ordem)
                        # Associar a ordem à requisição
                        if not dry_run:
                            requisicao.ordem_producao = ordem
                            requisicao.save()
                            self.stdout.write(self.style.SUCCESS(f'  [OK] Ordem {codigo_ordem} associada a requisicao'))
                        else:
                            self.stdout.write(self.style.WARNING(f'  [DRY-RUN] Seria associada ordem {codigo_ordem}'))
                    except OrdemProducao.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'  [ERRO] Ordem {codigo_ordem} nao encontrada'))
                        continue
            
            if not ordem or not ordem.receita:
                self.stdout.write(f'\nRequisição: {requisicao.codigo} (ID: {requisicao.id})')
                self.stdout.write(self.style.WARNING('  [AVISO] Sem ordem de producao associada'))
                continue
            
            # Calcular quantidades corretas
            rendimento = ordem.receita.rendimento if ordem.receita.rendimento > 0 else 1
            quantidade_lotes = Decimal(str(ordem.quantidade)) / Decimal(str(rendimento))
            
            self.stdout.write(f'\nRequisição: {requisicao.codigo} (ID: {requisicao.id})')
            self.stdout.write(f'  Ordem: {ordem.codigo}')
            self.stdout.write(f'  Quantidade da ordem: {ordem.quantidade}')
            self.stdout.write(f'  Rendimento da receita: {rendimento}')
            self.stdout.write(f'  Lotes necessários: {quantidade_lotes}')
            
            itens_corrigidos = 0
            
            for item_requisicao in requisicao.itens.select_related('item').all():
                if not item_requisicao.item:
                    continue
                
                # Buscar item na receita
                item_receita = ordem.receita.itens.filter(material=item_requisicao.item).first()
                if not item_receita:
                    continue
                
                # Calcular quantidade correta
                quantidade_correta = int((item_receita.quantidade * quantidade_lotes).quantize(Decimal('1'), rounding=ROUND_UP))
                
                if item_requisicao.quantidade_solicitada != quantidade_correta:
                    self.stdout.write(f'\n  Item: {item_requisicao.item.nome}')
                    self.stdout.write(f'    Quantidade atual (solicitada): {item_requisicao.quantidade_solicitada}')
                    self.stdout.write(f'    Quantidade correta: {quantidade_correta}')
                    self.stdout.write(f'    Quantidade atendida: {item_requisicao.quantidade_atendida}')
                    
                    # Se a quantidade atendida for maior que a correta, ajustar para a correta
                    if item_requisicao.quantidade_atendida > quantidade_correta:
                        self.stdout.write(f'    [AVISO] Quantidade atendida sera ajustada de {item_requisicao.quantidade_atendida} para {quantidade_correta}')
                    
                    if not dry_run:
                        with transaction.atomic():
                            item_requisicao.quantidade_solicitada = quantidade_correta
                            # Ajustar quantidade atendida se for maior que a correta
                            if item_requisicao.quantidade_atendida > quantidade_correta:
                                item_requisicao.quantidade_atendida = quantidade_correta
                            item_requisicao.save()
                            self.stdout.write(self.style.SUCCESS('    [OK] Corrigido'))
                    else:
                        self.stdout.write(self.style.WARNING('    [DRY-RUN] Seria corrigido'))
                    
                    itens_corrigidos += 1
            
            if itens_corrigidos > 0:
                total_corrigidas += 1
                total_itens_corrigidos += itens_corrigidos
            else:
                self.stdout.write('  [OK] Quantidades ja estao corretas')
        
        self.stdout.write(f'\n=== RESUMO ===')
        self.stdout.write(f'Requisições corrigidas: {total_corrigidas}')
        self.stdout.write(f'Itens corrigidos: {total_itens_corrigidos}')
        
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

