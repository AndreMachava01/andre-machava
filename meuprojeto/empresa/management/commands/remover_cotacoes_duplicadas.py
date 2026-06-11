from django.core.management.base import BaseCommand
from empresa.models_stock import OrdemServico
from collections import defaultdict
from decimal import Decimal


class Command(BaseCommand):
    help = 'Remove cotações duplicadas mantendo apenas a mais recente de cada grupo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria removido sem deletar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Buscar todas as cotações
        orcamentos = OrdemServico.objects.filter(
            codigo__startswith='COT'
        ).select_related('cliente').prefetch_related(
            'servicos_orcamento__servico',
            'ordens_servico_geradas'
        ).order_by('-data_criacao')
        
        # Agrupar por chave única (cliente, serviço, data, valor)
        duplicados = defaultdict(list)
        
        for orcamento in orcamentos:
            # Identificar cliente
            cliente_id = None
            cliente_nome = None
            if orcamento.cliente:
                cliente_id = orcamento.cliente.id
                cliente_nome = orcamento.cliente.nome
            else:
                cliente_nome = (orcamento.nome_cliente_pagamento or '').strip().lower()
            
            # Identificar primeiro serviço
            servico_id = None
            if orcamento.servicos_orcamento.exists():
                primeiro_servico = orcamento.servicos_orcamento.first()
                servico_id = primeiro_servico.servico.id if primeiro_servico.servico else None
            elif orcamento.servico:
                servico_id = orcamento.servico.id
            
            # Calcular valor total
            try:
                valor_total = float(orcamento.valor_total_com_itens)
            except:
                valor_total = float(orcamento.valor_total or 0)
            
            # Criar chave única
            chave = (
                cliente_id,
                cliente_nome,
                servico_id,
                orcamento.data_agendada.date() if orcamento.data_agendada else None,
                round(valor_total, 2)
            )
            
            duplicados[chave].append(orcamento)
        
        # Identificar duplicatas
        removidas = 0
        grupos_processados = []
        
        for chave, grupo in duplicados.items():
            if len(grupo) > 1:
                # Ordenar por: 1) não tem ordem gerada, 2) mais recente
                grupo_ordenado = sorted(
                    grupo,
                    key=lambda x: (
                        OrdemServico.objects.filter(
                            codigo__startswith='OS',
                            orcamento_origem=x
                        ).exists(),  # False primeiro (não tem ordem)
                        -x.data_criacao.timestamp()  # Mais recente primeiro
                    )
                )
                
                # Manter o primeiro (melhor candidato)
                manter = grupo_ordenado[0]
                
                # Identificar os que serão removidos
                para_remover = []
                for duplicado in grupo_ordenado[1:]:
                    # Verificar se tem ordem de serviço gerada
                    tem_ordem = OrdemServico.objects.filter(
                        codigo__startswith='OS',
                        orcamento_origem=duplicado
                    ).exists()
                    
                    if not tem_ordem:
                        para_remover.append(duplicado)
                
                if para_remover:
                    grupos_processados.append({
                        'mantido': manter,
                        'remover': para_remover,
                        'total': len(para_remover)
                    })
                    
                    if not dry_run:
                        for duplicado in para_remover:
                            self.stdout.write(
                                f"Removendo: {duplicado.codigo} (duplicado de {manter.codigo})"
                            )
                            duplicado.delete()
                            removidas += 1
                    else:
                        for duplicado in para_remover:
                            self.stdout.write(
                                f"[DRY-RUN] Removeria: {duplicado.codigo} (duplicado de {manter.codigo})"
                            )
                            removidas += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\n[DRY-RUN] Total de cotações que seriam removidas: {removidas}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nTotal de cotações removidas: {removidas}')
            )
        
        return removidas




