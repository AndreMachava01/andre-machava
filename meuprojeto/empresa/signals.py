from django.db.models.signals import post_save
from django.dispatch import receiver
from .models_rh import AvaliacaoDesempenho, CriterioAvaliado
from .models_stock import MovimentoItem, StockItem


@receiver(post_save, sender=CriterioAvaliado)
def actualizar_status_apos_criterio(sender, instance, created, **kwargs):
    """
    Actualiza o status da avaliação automaticamente quando um critério é avaliado
    """
    try:
        avaliacao = instance.avaliacao
        if avaliacao and avaliacao.status != 'CANCELADA':
            avaliacao.actualizar_status_automatico()
    except Exception as e:
        # Log do erro mas não interrompe o processo
        print(f"Erro ao actualizar status da avaliação {instance.avaliacao_id}: {e}")


@receiver(post_save, sender=AvaliacaoDesempenho)
def actualizar_status_apos_salvar(sender, instance, created, **kwargs):
    """
    Actualiza o status da avaliação automaticamente quando a avaliação é salva
    """
    try:
        if instance.status != 'CANCELADA':
            instance.actualizar_status_automatico()
    except Exception as e:
        # Log do erro mas não interrompe o processo
        print(f"Erro ao actualizar status da avaliação {instance.id}: {e}")


# Signal do sistema antigo - DESCONTINUADO
# # @receiver(post_save, sender=MovimentoStock)
def actualizar_estoque_apos_movimento_OLD(sender, instance, created, **kwargs):
    """
    Actualiza o estoque automaticamente quando um movimento é registrado
    """
    try:
        if created:  # Só executa quando o movimento é criado (não editado)
            produto = instance.produto
            sucursal = instance.sucursal
            quantidade = instance.quantidade
            tipo_movimento = instance.tipo_movimento
            
            # Obter ou criar o registro de estoque da sucursal
            stock_sucursal, created_stock = StockSucursal.objects.get_or_create(
                produto=produto,
                sucursal=sucursal,
                defaults={'quantidade_atual': 0, 'quantidade_reservada': 0}
            )
            
            # Actualizar a quantidade baseada no tipo de movimento
            if tipo_movimento.aumenta_estoque:
                # Entrada: aumenta o estoque
                stock_sucursal.quantidade_atual += quantidade
            else:
                # Saída: diminui o estoque
                stock_sucursal.quantidade_atual -= quantidade
                # Garantir que não fique negativo
                if stock_sucursal.quantidade_atual < 0:
                    stock_sucursal.quantidade_atual = 0
            
            stock_sucursal.save()
            
    except Exception as e:
        # Log do erro mas não interrompe o processo
        print(f"ERRO ao actualizar estoque para movimento {instance.id}: {e}")
        import traceback
        traceback.print_exc()


# Signal do sistema antigo - DESCONTINUADO
# @receiver(post_save, sender=MovimentoMaterial)
def actualizar_estoque_apos_movimento_material_OLD(sender, instance, created, **kwargs):
    """
    Actualiza o estoque automaticamente quando um movimento de material é registrado
    """
    try:
        if created:  # Só executa quando o movimento é criado (não editado)
            material = instance.material
            sucursal = instance.sucursal
            quantidade = instance.quantidade
            tipo_movimento = instance.tipo_movimento
            
            # Obter ou criar o registro de estoque da sucursal
            stock_material, created_stock = StockMaterial.objects.get_or_create(
                material=material,
                sucursal=sucursal,
                defaults={'quantidade_atual': 0, 'quantidade_reservada': 0}
            )
            
            # Actualizar a quantidade baseada no tipo de movimento
            if tipo_movimento.aumenta_estoque:
                # Entrada: aumenta o estoque
                stock_material.quantidade_atual += quantidade
            else:
                # Saída: diminui o estoque
                stock_material.quantidade_atual -= quantidade
                # Garantir que não fique negativo
                if stock_material.quantidade_atual < 0:
                    stock_material.quantidade_atual = 0
            
            stock_material.save()
            
    except Exception as e:
        # Log do erro mas não interrompe o processo
        print(f"ERRO ao actualizar estoque para movimento de material {instance.id}: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=MovimentoItem)
def actualizar_estoque_apos_movimento_item(sender, instance, created, **kwargs):
    """
    Actualiza o estoque automaticamente quando um movimento de item é registrado
    """
    try:
        if created:  # Só executa quando o movimento é criado (não editado)
            item = instance.item
            sucursal = instance.sucursal
            quantidade = instance.quantidade
            tipo_movimento = instance.tipo_movimento
            
            # Obter ou criar o registro de estoque da sucursal
            stock_item, created_stock = StockItem.objects.get_or_create(
                item=item,
                sucursal=sucursal,
                defaults={'quantidade_atual': 0, 'quantidade_reservada': 0}
            )
            
            # Actualizar a quantidade baseada no tipo de movimento
            if tipo_movimento.aumenta_estoque:
                # Entrada: aumenta o estoque
                stock_item.quantidade_atual += quantidade
            else:
                # Saída: diminui o estoque
                stock_item.quantidade_atual -= quantidade
                # Garantir que não fique negativo
                if stock_item.quantidade_atual < 0:
                    stock_item.quantidade_atual = 0
            
            stock_item.save()
            
    except Exception as e:
        # Log do erro mas não interrompe o processo
        print(f"ERRO ao actualizar estoque para movimento unificado {instance.id}: {e}")
        import traceback
        traceback.print_exc()
