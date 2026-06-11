"""
Serviço para gestão de custos e faturamento logístico.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models_cost_billing import (
    CentroCusto, TipoCusto, CustoLogistico, RateioCusto,
    FaturamentoFrete, ItemFaturamento, ConfiguracaoFaturamento
)
from ..models_stock import RastreamentoEntrega, Transportadora, VeiculoInterno
from ..models_base import Sucursal

logger = logging.getLogger(__name__)

STATUS_RASTREAMENTO_FATURAVEL = ('ENTREGUE',)


def _endereco_sucursal(sucursal: Sucursal) -> str:
    partes = [
        sucursal.endereco,
        sucursal.bairro,
        sucursal.cidade,
        sucursal.get_provincia_display() if sucursal.provincia else '',
    ]
    return ', '.join(p for p in partes if p)


def _cliente_dados_sucursal(sucursal: Sucursal, documento_origem: str = '') -> Dict[str, str]:
    empresa = sucursal.empresa_sede
    nuit = (empresa.nuit if empresa and empresa.nuit else '') or ''
    documento = documento_origem or sucursal.codigo or nuit or '—'
    return {
        'nome': sucursal.nome,
        'documento': documento,
        'nuit': nuit,
        'endereco': _endereco_sucursal(sucursal),
        'email': sucursal.email or '',
    }


def chave_documento_origem(rastreamento: RastreamentoEntrega) -> Tuple[str, int]:
    """Agrupa rastreamentos pelo documento logístico de origem."""
    if rastreamento.transferencia_id:
        return ('TRANSFERENCIA', rastreamento.transferencia_id)
    if rastreamento.ordem_compra_id:
        return ('ORDEM_COMPRA', rastreamento.ordem_compra_id)
    return ('RASTREAMENTO', rastreamento.id)


def rotulo_documento_origem(rastreamento: RastreamentoEntrega) -> str:
    if rastreamento.transferencia_id:
        return f"Transferência {rastreamento.transferencia.codigo}"
    if rastreamento.ordem_compra_id:
        return f"Ordem de compra {rastreamento.ordem_compra.codigo}"
    return f"Rastreamento {rastreamento.codigo_rastreamento}"


def cliente_dados_de_rastreamento(rastreamento: RastreamentoEntrega) -> Dict[str, str]:
    """
    Dados de faturação a partir do documento de origem.
    Transferências e ordens de compra facturam a sucursal de destino.
    """
    if rastreamento.transferencia_id:
        sucursal = rastreamento.transferencia.sucursal_destino
        return _cliente_dados_sucursal(
            sucursal,
            documento_origem=rastreamento.transferencia.codigo,
        )
    if rastreamento.ordem_compra_id:
        sucursal = rastreamento.ordem_compra.sucursal_destino
        return _cliente_dados_sucursal(
            sucursal,
            documento_origem=rastreamento.ordem_compra.codigo,
        )
    return {
        'nome': rastreamento.destinatario_nome,
        'documento': rastreamento.codigo_rastreamento,
        'nuit': '',
        'endereco': ', '.join(
            p for p in (
                rastreamento.endereco_entrega,
                rastreamento.cidade_entrega,
                rastreamento.provincia_entrega,
            ) if p
        ) or '—',
        'email': '',
    }


def observacoes_documento_origem(rastreamento: RastreamentoEntrega) -> str:
    return f"Documento de origem: {rotulo_documento_origem(rastreamento)}"


DEFAULT_TIPOS_CUSTO = (
    ('FRETE', 'Frete', 'FRETE', 'Custos de transporte e entrega'),
    ('COMB', 'Combustível', 'COMBUSTIVEL', 'Abastecimento de frota'),
    ('MANUT', 'Manutenção', 'MANUTENCAO', 'Manutenção de veículos'),
    ('PED', 'Pedágio', 'PEDAGIO', 'Taxas de estrada'),
    ('SEG', 'Seguro', 'SEGURO', 'Seguros logísticos'),
    ('MULTA', 'Multa', 'MULTA', 'Multas e penalidades'),
    ('OUT', 'Outros', 'OUTROS', 'Despesas diversas'),
)

DEFAULT_CENTROS_CUSTO = (
    ('LOG', 'Logística Geral', 'DEPARTAMENTO', 'Centro principal de logística'),
    ('TRANS', 'Transporte', 'DEPARTAMENTO', 'Operações de transporte'),
    ('ENT', 'Entregas', 'DEPARTAMENTO', 'Custos de última milha'),
    ('REG-SUL', 'Regional Sul', 'REGIONAL', 'Operações na região sul'),
)


def garantir_catalogo_inicial():
    """Cria tipos e centros de custo padrão se o catálogo estiver vazio."""
    if not TipoCusto.objects.exists():
        for codigo, nome, categoria, descricao in DEFAULT_TIPOS_CUSTO:
            TipoCusto.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nome': nome,
                    'categoria': categoria,
                    'descricao': descricao,
                    'ativo': True,
                },
            )
        logger.info('Catálogo de tipos de custo inicial criado.')

    if not CentroCusto.objects.exists():
        for codigo, nome, tipo, descricao in DEFAULT_CENTROS_CUSTO:
            CentroCusto.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nome': nome,
                    'tipo': tipo,
                    'descricao': descricao,
                    'ativo': True,
                },
            )
        logger.info('Catálogo de centros de custo inicial criado.')


class CostBillingService:
    """Serviço para gestão de custos e faturamento logístico."""
    
    def __init__(self):
        self._config_padrao = None
        garantir_catalogo_inicial()
    
    def garantir_catalogo(self):
        """Expõe inicialização do catálogo para views."""
        garantir_catalogo_inicial()
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de faturamento."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoFaturamento:
        """Obtém a configuração padrão de faturamento."""
        try:
            return ConfiguracaoFaturamento.objects.get(padrao=True, ativo=True)
        except ConfiguracaoFaturamento.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoFaturamento.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def registrar_custo_logistico(self,
                                rastreamento_id: Optional[int],
                                tipo_custo_id: int,
                                centro_custo_id: int,
                                descricao: str,
                                valor: Decimal,
                                data_custo: Optional[date] = None,
                                numero_documento: str = '',
                                arquivo_comprovante=None,
                                criado_por_id: Optional[int] = None) -> CustoLogistico:
        """
        Registra um novo custo logístico.
        
        Args:
            rastreamento_id: ID do rastreamento (opcional)
            tipo_custo_id: ID do tipo de custo
            centro_custo_id: ID do centro de custo
            descricao: Descrição do custo
            valor: Valor do custo
            data_custo: Data do custo
            numero_documento: Número do documento
            arquivo_comprovante: Arquivo de comprovante
            criado_por_id: ID do usuário que criou
            
        Returns:
            CustoLogistico criado
        """
        try:
            tipo_custo = TipoCusto.objects.get(id=tipo_custo_id)
            centro_custo = CentroCusto.objects.get(id=centro_custo_id)
            
            custo = CustoLogistico.objects.create(
                rastreamento_entrega_id=rastreamento_id,
                tipo_custo=tipo_custo,
                centro_custo=centro_custo,
                descricao=descricao,
                valor=valor,
                data_custo=data_custo or timezone.now().date(),
                numero_documento=numero_documento,
                arquivo_comprovante=arquivo_comprovante,
                criado_por_id=criado_por_id,
                status='PENDENTE'
            )
            
            # Aplicar rateio automático se configurado
            if tipo_custo.rateio_automatico:
                self._aplicar_rateio_automatico(custo)
            
            logger.info(f"Custo logístico registrado: {custo.codigo}")
            return custo
            
        except Exception as e:
            logger.error(f"Erro ao registrar custo logístico: {e}")
            raise
    
    def _aplicar_rateio_automatico(self, custo: CustoLogistico):
        """Aplica rateio automático baseado no tipo de custo."""
        try:
            # Obter centros de custo relacionados
            centros_relacionados = self._obter_centros_relacionados(custo.centro_custo)
            
            if not centros_relacionados:
                return
            
            # Calcular valor por centro
            valor_por_centro = custo.valor / len(centros_relacionados)
            percentual_por_centro = Decimal('100.00') / len(centros_relacionados)
            
            for centro in centros_relacionados:
                RateioCusto.objects.create(
                    custo_logistico=custo,
                    centro_custo_destino=centro,
                    valor_rateado=valor_por_centro,
                    percentual_rateio=percentual_por_centro,
                    criterio_rateio='AUTOMATICO',
                    status='APROVADO'
                )
            
            custo.status = 'RATEADO'
            custo.valor_rateado = custo.valor
            custo.percentual_rateio = Decimal('100.00')
            custo.save()
            
            logger.info(f"Rateio automático aplicado para custo {custo.codigo}")
            
        except Exception as e:
            logger.error(f"Erro ao aplicar rateio automático: {e}")
    
    def _obter_centros_relacionados(self, centro_origem: CentroCusto) -> List[CentroCusto]:
        """Obtém centros de custo relacionados para rateio."""
        # Por enquanto, retornar centros do mesmo tipo
        return CentroCusto.objects.filter(
            tipo=centro_origem.tipo,
            ativo=True
        ).exclude(id=centro_origem.id)
    
    def aprovar_custo_logistico(self,
                               custo_id: int,
                               aprovado_por_id: int,
                               observacoes: str = '') -> CustoLogistico:
        """
        Aprova um custo logístico.
        
        Args:
            custo_id: ID do custo
            aprovado_por_id: ID do usuário que aprovou
            observacoes: Observações da aprovação
            
        Returns:
            CustoLogistico aprovado
        """
        try:
            custo = CustoLogistico.objects.get(id=custo_id)
            
            if custo.status != 'PENDENTE':
                raise ValueError("Custo não está no status 'PENDENTE'")
            
            custo.status = 'APROVADO'
            custo.aprovado_por_id = aprovado_por_id
            custo.data_aprovacao = timezone.now()
            custo.observacoes_aprovacao = observacoes
            custo.save()
            custo = CustoLogistico.objects.select_related(
                'centro_custo',
                'tipo_custo',
                'rastreamento_entrega__transportadora',
            ).get(pk=custo.pk)

            try:
                from .logistica_financas_sync import criar_pendente_pagar_custo
                criar_pendente_pagar_custo(custo)
            except Exception:
                logger.exception('Falha ao criar pendente financeiro para custo %s', custo.codigo)
            
            logger.info(f"Custo logístico aprovado: {custo.codigo}")
            return custo
            
        except Exception as e:
            logger.error(f"Erro ao aprovar custo logístico: {e}")
            raise
    
    def rejeitar_custo_logistico(self,
                                custo_id: int,
                                rejeitado_por_id: int,
                                motivo_rejeicao: str) -> CustoLogistico:
        """
        Rejeita um custo logístico.
        
        Args:
            custo_id: ID do custo
            rejeitado_por_id: ID do usuário que rejeitou
            motivo_rejeicao: Motivo da rejeição
            
        Returns:
            CustoLogistico rejeitado
        """
        try:
            custo = CustoLogistico.objects.get(id=custo_id)
            
            if custo.status != 'PENDENTE':
                raise ValueError("Custo não está no status 'PENDENTE'")
            
            custo.status = 'REJEITADO'
            custo.aprovado_por_id = rejeitado_por_id
            custo.data_aprovacao = timezone.now()
            custo.observacoes_aprovacao = motivo_rejeicao
            custo.save()

            try:
                from .logistica_financas_sync import rejeitar_pendente_pagar_custo
                rejeitar_pendente_pagar_custo(custo.id)
            except Exception:
                logger.exception('Falha ao rejeitar pendente financeiro do custo %s', custo.codigo)
            
            logger.info(f"Custo logístico rejeitado: {custo.codigo}")
            return custo
            
        except Exception as e:
            logger.error(f"Erro ao rejeitar custo logístico: {e}")
            raise
    
    def criar_rateio_manual(self,
                           custo_id: int,
                           rateios: List[Dict[str, Any]],
                           criado_por_id: Optional[int] = None) -> List[RateioCusto]:
        """
        Cria rateio manual para um custo.
        
        Args:
            custo_id: ID do custo
            rateios: Lista de rateios com centro_custo_id, valor_rateado, percentual_rateio
            criado_por_id: ID do usuário que criou
            
        Returns:
            Lista de RateioCusto criados
        """
        try:
            custo = CustoLogistico.objects.get(id=custo_id)
            
            # Validar total dos rateios
            total_rateado = sum(Decimal(str(r['valor_rateado'])) for r in rateios)
            if abs(total_rateado - custo.valor) > Decimal('0.01'):
                raise ValueError("Total dos rateios deve ser igual ao valor do custo")
            
            rateios_criados = []
            
            for rateio_data in rateios:
                centro_custo = CentroCusto.objects.get(id=rateio_data['centro_custo_id'])
                
                rateio = RateioCusto.objects.create(
                    custo_logistico=custo,
                    centro_custo_destino=centro_custo,
                    valor_rateado=Decimal(str(rateio_data['valor_rateado'])),
                    percentual_rateio=Decimal(str(rateio_data['percentual_rateio'])),
                    criterio_rateio='MANUAL',
                    status='PENDENTE'
                )
                
                rateios_criados.append(rateio)
            
            # Atualizar custo
            custo.valor_rateado = total_rateado
            custo.percentual_rateio = Decimal('100.00')
            custo.status = 'RATEADO'
            custo.save()
            
            logger.info(f"Rateio manual criado para custo {custo.codigo}")
            return rateios_criados
            
        except Exception as e:
            logger.error(f"Erro ao criar rateio manual: {e}")
            raise
    
    def _obter_rastreamentos_faturaveis(self, rastreamentos_ids: List[int]):
        rastreamentos = RastreamentoEntrega.objects.filter(
            id__in=rastreamentos_ids,
            status_atual__in=STATUS_RASTREAMENTO_FATURAVEL,
            custo_envio__gt=0,
        ).select_related(
            'transferencia__sucursal_destino__empresa_sede',
            'ordem_compra__sucursal_destino__empresa_sede',
        ).annotate(
            _qtd_faturas=Count('itens_faturamento'),
        ).filter(_qtd_faturas=0)

        if not rastreamentos.exists():
            raise ValueError(
                "Nenhum rastreamento elegível encontrado "
                "(entregue, com custo de envio e ainda não faturado)."
            )
        return rastreamentos

    def _criar_faturamento_frete(
        self,
        *,
        cliente_dados: Dict[str, Any],
        rastreamentos,
        periodo_inicio: date,
        periodo_fim: date,
        emitido_por_id: Optional[int],
        observacoes: str,
        desconto_percentual: Decimal,
    ) -> FaturamentoFrete:
        config = self.config_padrao

        if desconto_percentual > config.desconto_maximo_percentual:
            raise ValueError(f"Desconto máximo permitido: {config.desconto_maximo_percentual}%")

        valor_total = Decimal('0.00')
        for rastreamento in rastreamentos:
            custo_frete = rastreamento.custo_envio or Decimal('0.00')
            if custo_frete <= 0:
                raise ValueError(
                    f"Rastreamento {rastreamento.codigo_rastreamento} sem custo de envio válido."
                )
            valor_total += custo_frete

        valor_desconto = valor_total * (desconto_percentual / Decimal('100.00'))
        valor_liquido = valor_total - valor_desconto

        faturamento = FaturamentoFrete.objects.create(
            serie_fatura=config.serie_padrao,
            cliente_nome=cliente_dados['nome'],
            cliente_documento=cliente_dados['documento'],
            cliente_endereco=cliente_dados['endereco'],
            cliente_email=cliente_dados.get('email', ''),
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            data_emissao=timezone.now().date(),
            data_vencimento=timezone.now().date() + timedelta(days=config.prazo_pagamento_dias),
            valor_total=valor_total,
            valor_desconto=valor_desconto,
            valor_liquido=valor_liquido,
            observacoes=observacoes,
            instrucoes_pagamento=config.incluir_instrucoes_pagamento,
            emitido_por_id=emitido_por_id,
            status='RASCUNHO',
        )

        for rastreamento in rastreamentos:
            custo_frete = rastreamento.custo_envio or Decimal('0.00')
            ItemFaturamento.objects.create(
                faturamento=faturamento,
                rastreamento_entrega=rastreamento,
                descricao=f"Frete - {rastreamento.codigo_rastreamento}",
                quantidade=1,
                valor_unitario=custo_frete,
                valor_total=custo_frete,
                data_servico=(
                    rastreamento.data_entrega_realizada.date()
                    if rastreamento.data_entrega_realizada
                    else rastreamento.data_criacao.date()
                ),
            )

        logger.info("Faturamento gerado: %s", faturamento.numero_fatura)
        return faturamento

    def gerar_faturamentos_frete(
        self,
        rastreamentos_ids: List[int],
        periodo_inicio: date,
        periodo_fim: date,
        emitido_por_id: Optional[int] = None,
        observacoes: str = '',
        desconto_percentual: Decimal = Decimal('0.00'),
    ) -> List[FaturamentoFrete]:
        """
        Gera uma fatura por documento de origem (transferência ou ordem de compra).
        Os dados do cliente são obtidos da sucursal de destino do documento.
        """
        try:
            rastreamentos = list(self._obter_rastreamentos_faturaveis(rastreamentos_ids))

            grupos: Dict[Tuple[str, int], list] = {}
            for rastreamento in rastreamentos:
                grupos.setdefault(chave_documento_origem(rastreamento), []).append(rastreamento)

            faturas: List[FaturamentoFrete] = []
            for grupo in grupos.values():
                referencia = grupo[0]
                cliente_dados = cliente_dados_de_rastreamento(referencia)
                obs_doc = observacoes_documento_origem(referencia)
                obs_final = obs_doc
                if observacoes:
                    obs_final = f"{observacoes}\n{obs_doc}"

                fatura = self._criar_faturamento_frete(
                    cliente_dados=cliente_dados,
                    rastreamentos=grupo,
                    periodo_inicio=periodo_inicio,
                    periodo_fim=periodo_fim,
                    emitido_por_id=emitido_por_id,
                    observacoes=obs_final,
                    desconto_percentual=desconto_percentual,
                )
                faturas.append(fatura)

            return faturas

        except Exception as e:
            logger.error(f"Erro ao gerar faturamentos: {e}")
            raise

    def gerar_faturamento_frete(
        self,
        rastreamentos_ids: List[int],
        periodo_inicio: date,
        periodo_fim: date,
        emitido_por_id: Optional[int] = None,
        observacoes: str = '',
        desconto_percentual: Decimal = Decimal('0.00'),
    ) -> FaturamentoFrete:
        """Gera uma única fatura quando todos os rastreamentos partilham o mesmo documento."""
        faturas = self.gerar_faturamentos_frete(
            rastreamentos_ids=rastreamentos_ids,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            emitido_por_id=emitido_por_id,
            observacoes=observacoes,
            desconto_percentual=desconto_percentual,
        )
        if len(faturas) != 1:
            raise ValueError(
                "Os rastreamentos seleccionados pertencem a documentos diferentes. "
                "Use gerar_faturamentos_frete para gerar uma fatura por documento."
            )
        return faturas[0]

    def recalcular_faturamento_frete(self, faturamento_id: int) -> FaturamentoFrete:
        """
        Actualiza itens e totais da fatura com base no custo_envio actual dos rastreamentos.
        Mantém o percentual de desconto original.
        """
        try:
            faturamento = FaturamentoFrete.objects.prefetch_related(
                'itens__rastreamento_entrega',
            ).get(id=faturamento_id)

            if faturamento.status in ('PAGO', 'CANCELADO'):
                raise ValueError(
                    "Faturas pagas ou canceladas não podem ser recalculadas."
                )

            if not faturamento.itens.exists():
                raise ValueError("Fatura sem itens para recalcular.")

            if faturamento.valor_total and faturamento.valor_total > 0:
                pct_desconto = (
                    faturamento.valor_desconto / faturamento.valor_total * Decimal('100.00')
                )
            else:
                pct_desconto = Decimal('0.00')

            valor_total = Decimal('0.00')
            for item in faturamento.itens.all():
                custo_frete = item.rastreamento_entrega.custo_envio or Decimal('0.00')
                if custo_frete <= 0:
                    raise ValueError(
                        f"Rastreamento {item.rastreamento_entrega.codigo_rastreamento} "
                        "sem custo de envio válido."
                    )
                item.valor_unitario = custo_frete
                item.valor_total = custo_frete * item.quantidade
                item.save(update_fields=['valor_unitario', 'valor_total'])
                valor_total += item.valor_total

            valor_desconto = (
                valor_total * pct_desconto / Decimal('100.00')
            ).quantize(Decimal('0.01'))
            valor_liquido = valor_total - valor_desconto

            primeiro = faturamento.itens.select_related(
                'rastreamento_entrega__transferencia__sucursal_destino__empresa_sede',
                'rastreamento_entrega__ordem_compra__sucursal_destino__empresa_sede',
            ).first().rastreamento_entrega
            cliente = cliente_dados_de_rastreamento(primeiro)

            faturamento.cliente_nome = cliente['nome']
            faturamento.cliente_documento = cliente['documento']
            faturamento.cliente_endereco = cliente['endereco']
            faturamento.cliente_email = cliente.get('email', '')
            faturamento.valor_total = valor_total
            faturamento.valor_desconto = valor_desconto
            faturamento.valor_liquido = valor_liquido
            faturamento.save(update_fields=[
                'cliente_nome', 'cliente_documento', 'cliente_endereco', 'cliente_email',
                'valor_total', 'valor_desconto', 'valor_liquido',
            ])

            try:
                from .logistica_financas_sync import criar_ou_actualizar_pendente_receber_fatura
                criar_ou_actualizar_pendente_receber_fatura(faturamento)
            except Exception:
                logger.exception(
                    'Falha ao sincronizar pendente financeiro da fatura %s',
                    faturamento.numero_fatura,
                )

            logger.info(
                "Faturamento recalculado: %s (total=%s, líquido=%s)",
                faturamento.numero_fatura,
                valor_total,
                valor_liquido,
            )
            return faturamento

        except FaturamentoFrete.DoesNotExist:
            raise
        except Exception as e:
            logger.error(f"Erro ao recalcular faturamento: {e}")
            raise
    
    def enviar_faturamento(self, faturamento_id: int) -> FaturamentoFrete:
        """
        Envia faturamento para o cliente.
        
        Args:
            faturamento_id: ID do faturamento
            
        Returns:
            FaturamentoFrete enviado
        """
        try:
            faturamento = FaturamentoFrete.objects.get(id=faturamento_id)
            
            if faturamento.status != 'RASCUNHO':
                raise ValueError("Faturamento não está no status 'RASCUNHO'")

            with transaction.atomic():
                faturamento.status = 'ENVIADO'
                faturamento.save(update_fields=['status'])
                try:
                    from .logistica_financas_sync import criar_ou_actualizar_pendente_receber_fatura
                    criar_ou_actualizar_pendente_receber_fatura(faturamento)
                except Exception:
                    logger.exception(
                        'Falha ao criar pendente em Contas a receber para %s',
                        faturamento.numero_fatura,
                    )

            logger.info(f"Faturamento enviado: {faturamento.numero_fatura}")
            return faturamento
            
        except Exception as e:
            logger.error(f"Erro ao enviar faturamento: {e}")
            raise
    
    def marcar_faturamento_pago(self, faturamento_id: int, data_pagamento: Optional[date] = None) -> FaturamentoFrete:
        """
        Marca faturamento como pago.
        
        Args:
            faturamento_id: ID do faturamento
            data_pagamento: Data do pagamento
            
        Returns:
            FaturamentoFrete marcado como pago
        """
        try:
            faturamento = FaturamentoFrete.objects.get(id=faturamento_id)
            
            if faturamento.status not in ['ENVIADO', 'VENCIDO']:
                raise ValueError("Faturamento não pode ser marcado como pago")
            
            faturamento.status = 'PAGO'
            faturamento.data_pagamento = data_pagamento or timezone.now().date()
            faturamento.save()
            
            logger.info(f"Faturamento marcado como pago: {faturamento.numero_fatura}")
            return faturamento
            
        except Exception as e:
            logger.error(f"Erro ao marcar faturamento como pago: {e}")
            raise
    
    def obter_estatisticas_custos(self,
                                 data_inicio: Optional[date] = None,
                                 data_fim: Optional[date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de custos.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = CustoLogistico.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_custo__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_custo__lte=data_fim)
        
        stats = {
            'total_custos': queryset.count(),
            'valor_total': queryset.aggregate(
                total=Sum('valor')
            )['total'] or Decimal('0.00'),
            'custos_pendentes': queryset.filter(status='PENDENTE').count(),
            'custos_aprovados': queryset.filter(status='APROVADO').count(),
            'custos_rateados': queryset.filter(status='RATEADO').count(),
            'custos_por_tipo': dict(queryset.values('tipo_custo__nome').annotate(
                count=Count('id'),
                valor=Sum('valor')
            ).values_list('tipo_custo__nome', 'valor')),
            'custos_por_centro': dict(queryset.values('centro_custo__nome').annotate(
                count=Count('id'),
                valor=Sum('valor')
            ).values_list('centro_custo__nome', 'valor')),
        }
        
        return stats
    
    def obter_estatisticas_faturamento(self,
                                      data_inicio: Optional[date] = None,
                                      data_fim: Optional[date] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de faturamento.
        
        Args:
            data_inicio: Data de início do período
            data_fim: Data de fim do período
            
        Returns:
            Dicionário com estatísticas
        """
        queryset = FaturamentoFrete.objects.all()
        
        if data_inicio:
            queryset = queryset.filter(data_emissao__gte=data_inicio)
        
        if data_fim:
            queryset = queryset.filter(data_emissao__lte=data_fim)
        
        stats = {
            'total_faturas': queryset.count(),
            'valor_total_faturado': queryset.aggregate(
                total=Sum('valor_liquido')
            )['total'] or Decimal('0.00'),
            'faturas_pagas': queryset.filter(status='PAGO').count(),
            'faturas_pendentes': queryset.filter(status='ENVIADO').count(),
            'faturas_vencidas': queryset.filter(status='VENCIDO').count(),
            'valor_pendente': queryset.filter(
                status__in=['ENVIADO', 'VENCIDO']
            ).aggregate(
                total=Sum('valor_liquido')
            )['total'] or Decimal('0.00'),
            'valor_pago': queryset.filter(status='PAGO').aggregate(
                total=Sum('valor_liquido')
            )['total'] or Decimal('0.00'),
        }
        
        return stats


# Instância global do serviço
cost_billing_service = CostBillingService()
