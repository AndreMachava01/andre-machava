import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

from .models_stock import (
    NotificacaoStock, StockItem, MovimentoItem, 
    RequisicaoStock, RequisicaoCompraExterna
)

logger = logging.getLogger(__name__)

@receiver(post_save, sender=StockItem)
def verificar_estoque_baixo(sender, instance, created, **kwargs):
    """Verifica se o estoque está baixo após atualização"""
    try:
        if instance.item and instance.item.estoque_minimo:
            if instance.quantidade_atual <= instance.item.estoque_minimo:
                # Criar notificação de estoque baixo
                NotificacaoStock.objects.create(
                    tipo='stock_baixo',
                    titulo=f'Estoque Baixo: {instance.item.nome}',
                    mensagem=f'O item {instance.item.nome} ({instance.item.codigo}) está com estoque baixo na sucursal {instance.sucursal.nome}. Quantidade atual: {instance.quantidade_atual}, Mínimo: {instance.item.estoque_minimo}',
                    url=f'/stock/requisicoes/verificar-stock-baixo/',
                    usuario_destinatario=None  # Notificação geral
                )
                logger.info(f"Alerta de estoque baixo criado para {instance.item.nome}")
    except Exception as e:
        logger.error(f"Erro ao verificar estoque baixo: {e}")

@receiver(post_save, sender=MovimentoItem)
def verificar_movimentacao_sem_usuario(sender, instance, created, **kwargs):
    """Verifica se a movimentação foi criada sem usuário"""
    try:
        if created and not instance.usuario:
            # Criar notificação de auditoria
            NotificacaoStock.objects.create(
                tipo='movimentacao_sem_usuario',
                titulo='Movimentação sem Usuário',
                mensagem=f'Movimentação {instance.codigo} foi registrada sem usuário responsável. Item: {instance.item.nome}, Quantidade: {instance.quantidade}',
                url=f'/stock/movimentos/',
                usuario_destinatario=None  # Notificação geral
            )
            logger.info(f"Alerta de movimentação sem usuário criado para {instance.codigo}")
    except Exception as e:
        logger.error(f"Erro ao verificar movimentação sem usuário: {e}")

@receiver(post_save, sender=RequisicaoStock)
def verificar_requisicao_pendente(sender, instance, created, **kwargs):
    """Verifica se há requisições pendentes há muito tempo"""
    try:
        if instance.status == 'PENDENTE':
            # Verificar se está pendente há mais de 7 dias
            if instance.data_criacao < timezone.now() - timedelta(days=7):
                NotificacaoStock.objects.create(
                    tipo='requisicao_antiga',
                    titulo=f'Requisição Antiga: {instance.codigo}',
                    mensagem=f'A requisição {instance.codigo} está pendente há mais de 7 dias. Data de criação: {instance.data_criacao.strftime("%d/%m/%Y")}',
                    url=f'/stock/requisicoes/{instance.id}/',
                    usuario_destinatario=None  # Notificação geral
                )
                logger.info(f"Alerta de requisição antiga criado para {instance.codigo}")
    except Exception as e:
        logger.error(f"Erro ao verificar requisição pendente: {e}")

@receiver(post_save, sender=RequisicaoCompraExterna)
def verificar_requisicao_externa_pendente(sender, instance, created, **kwargs):
    """Verifica se há requisições externas pendentes há muito tempo"""
    try:
        if instance.status == 'PENDENTE':
            # Verificar se está pendente há mais de 7 dias
            if instance.data_criacao < timezone.now() - timedelta(days=7):
                NotificacaoStock.objects.create(
                    tipo='requisicao_antiga',
                    titulo=f'Compra Externa Antiga: {instance.codigo}',
                    mensagem=f'A compra externa {instance.codigo} está pendente há mais de 7 dias. Data de criação: {instance.data_criacao.strftime("%d/%m/%Y")}',
                    url=f'/stock/requisicoes/compra-externa/{instance.id}/',
                    usuario_destinatario=None  # Notificação geral
                )
                logger.info(f"Alerta de compra externa antiga criado para {instance.codigo}")
    except Exception as e:
        logger.error(f"Erro ao verificar requisição externa pendente: {e}")

def criar_alertas_sistema():
    """Função para criar alertas do sistema (chamada manual ou por cron)"""
    try:
        # Verificar estoque baixo geral
        estoque_baixo_count = StockItem.objects.filter(
            quantidade_atual__lte=F('item__estoque_minimo')
        ).count()
        
        if estoque_baixo_count > 0:
            NotificacaoStock.objects.create(
                tipo='sistema',
                titulo=f'Resumo: {estoque_baixo_count} Itens com Estoque Baixo',
                mensagem=f'Existem {estoque_baixo_count} itens com estoque abaixo do mínimo. Verifique a lista completa.',
                url='/stock/requisicoes/verificar-stock-baixo/',
                usuario_destinatario=None
            )
        
        # Verificar movimentações sem usuário
        movimentacoes_sem_usuario = MovimentoItem.objects.filter(
            usuario__isnull=True
        ).count()
        
        if movimentacoes_sem_usuario > 0:
            NotificacaoStock.objects.create(
                tipo='sistema',
                titulo=f'Auditoria: {movimentacoes_sem_usuario} Movimentações sem Usuário',
                mensagem=f'Existem {movimentacoes_sem_usuario} movimentações sem usuário registrado. Verifique a auditoria.',
                url='/stock/movimentos/',
                usuario_destinatario=None
            )
        
        # Verificar requisições antigas
        requisicoes_antigas = (
            RequisicaoStock.objects.filter(
                status='PENDENTE',
                data_criacao__lt=timezone.now() - timedelta(days=7)
            ).count() +
            RequisicaoCompraExterna.objects.filter(
                status='PENDENTE',
                data_criacao__lt=timezone.now() - timedelta(days=7)
            ).count()
        )
        
        if requisicoes_antigas > 0:
            NotificacaoStock.objects.create(
                tipo='sistema',
                titulo=f'Urgente: {requisicoes_antigas} Requisições Antigas',
                mensagem=f'Existem {requisicoes_antigas} requisições pendentes há mais de 7 dias. Ação necessária.',
                url='/stock/requisicoes/',
                usuario_destinatario=None
            )
        
        logger.info("Alertas do sistema criados com sucesso")
        
    except Exception as e:
        logger.error(f"Erro ao criar alertas do sistema: {e}")

def limpar_notificacoes_antigas():
    """Remove notificações antigas (mais de 30 dias)"""
    try:
        data_limite = timezone.now() - timedelta(days=30)
        notificacoes_removidas = NotificacaoStock.objects.filter(
            data_criacao__lt=data_limite,
            lida=True
        ).delete()
        
        logger.info(f"Removidas {notificacoes_removidas[0]} notificações antigas")
        
    except Exception as e:
        logger.error(f"Erro ao limpar notificações antigas: {e}")
