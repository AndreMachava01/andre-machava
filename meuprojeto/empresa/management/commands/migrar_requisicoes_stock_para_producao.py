"""
Comando para migrar RequisicaoStock antigas de consumo para produção em RequisicaoProducao
"""
from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_stock import RequisicaoStock, RequisicaoProducao, ItemRequisicaoStock, ItemRequisicaoProducao
from django.db import transaction


class Command(BaseCommand):
    help = 'Migra RequisicaoStock antigas de consumo para produção em RequisicaoProducao'

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
        
        # Buscar RequisicaoStock de consumo (sucursal_destino = None)
        # que não são transferências e que parecem ser para produção
        requisicoes_consumo = RequisicaoStock.objects.filter(
            sucursal_destino__isnull=True
        ).select_related('sucursal_origem', 'criado_por', 'aprovado_por').prefetch_related('itens')
        
        total_migradas = 0
        total_erros = 0
        
        for req_stock in requisicoes_consumo:
            self.stdout.write(f'\nAnalisando: {req_stock.codigo}')
            self.stdout.write(f'  Status: {req_stock.status}')
            self.stdout.write(f'  Itens: {req_stock.itens.count()}')
            self.stdout.write(f'  Observações: {req_stock.observacoes[:100] if req_stock.observacoes else "N/A"}')
            
            # Verificar se já existe uma RequisicaoProducao com o mesmo código ou relacionada
            # Como não temos mais o campo ordem_producao em RequisicaoStock, vamos tentar
            # identificar pela observação ou criar uma nova RequisicaoProducao
            
            # Verificar se já foi migrada (verificar se existe RequisicaoProducao com código similar)
            codigo_producao = f"REQPROD{req_stock.codigo.replace('REQ', '')}"
            if RequisicaoProducao.objects.filter(codigo=codigo_producao).exists():
                self.stdout.write(self.style.WARNING(f'  [PULADO] Já existe RequisicaoProducao com código {codigo_producao}'))
                continue
            
            # Tentar encontrar ordem de produção nas observações
            ordem_producao = None
            if req_stock.observacoes:
                # Procurar por padrão "OP" seguido de números
                import re
                match = re.search(r'OP\d+', req_stock.observacoes)
                if match:
                    codigo_ordem = match.group()
                    from meuprojeto.empresa.models_stock import OrdemProducao
                    ordem_producao = OrdemProducao.objects.filter(codigo=codigo_ordem).first()
                    if ordem_producao:
                        self.stdout.write(f'  Ordem encontrada nas observações: {codigo_ordem}')
            
            # Se não encontrou ordem, pular esta requisição (RequisicaoProducao requer ordem_producao)
            if not ordem_producao:
                self.stdout.write(self.style.WARNING('  [PULADO] Nenhuma ordem de produção encontrada. RequisicaoProducao requer ordem_producao.'))
                continue
            
            if not dry_run:
                try:
                    with transaction.atomic():
                        # Criar RequisicaoProducao
                        req_producao = RequisicaoProducao(
                            codigo=codigo_producao,
                            ordem_producao=ordem_producao if ordem_producao else None,
                            sucursal_origem=req_stock.sucursal_origem,
                            status=req_stock.status if req_stock.status in ['PENDENTE', 'APROVADA', 'ATENDIDA', 'REJEITADA', 'CANCELADA'] else 'PENDENTE',
                            observacoes=f"Migrada de {req_stock.codigo}. {req_stock.observacoes or ''}",
                            data_criacao=req_stock.data_criacao,
                            data_aprovacao=req_stock.data_aprovacao if hasattr(req_stock, 'data_aprovacao') else None,
                            data_atendimento=req_stock.data_atendimento if hasattr(req_stock, 'data_atendimento') else None,
                            criado_por=req_stock.criado_por,
                            aprovado_por=req_stock.aprovado_por if hasattr(req_stock, 'aprovado_por') else None
                        )
                        req_producao.save()
                        
                        # Migrar itens
                        for item_stock in req_stock.itens.all():
                            ItemRequisicaoProducao.objects.create(
                                requisicao=req_producao,
                                item=item_stock.item,
                                quantidade_solicitada=item_stock.quantidade_solicitada,
                                quantidade_atendida=item_stock.quantidade_atendida,
                                observacoes=item_stock.observacoes or ''
                            )
                        
                        # Se encontrou ordem, associar
                        if ordem_producao:
                            ordem_producao.requisicao_material = req_producao
                            ordem_producao.requisicao_material_criada = True
                            ordem_producao.save(update_fields=['requisicao_material', 'requisicao_material_criada'])
                        
                        self.stdout.write(self.style.SUCCESS(f'  [OK] Migrada para {req_producao.codigo}'))
                        total_migradas += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  [ERRO] Erro ao migrar: {str(e)}'))
                    total_erros += 1
            else:
                self.stdout.write(self.style.WARNING(f'  [DRY-RUN] Criaria RequisicaoProducao {codigo_producao}'))
                total_migradas += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY-RUN] Total de requisições que seriam migradas: {total_migradas}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n[OK] Total de requisições migradas: {total_migradas}'))
            if total_erros > 0:
                self.stdout.write(self.style.ERROR(f'[ERRO] Total de erros: {total_erros}'))

