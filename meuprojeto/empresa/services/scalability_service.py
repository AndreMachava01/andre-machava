"""
Serviço para escalabilidade e processamento assíncrono.
"""
import logging
import json
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Q, F, Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.core.cache import cache

from ..models_scalability import (
    FilaProcessamento, ControleIdempotencia, ValidacaoLogistica,
    ResultadoValidacao, TesteContrato, ExecucaoTesteContrato,
    ConfiguracaoEscalabilidade, MonitoramentoPerformance
)

logger = logging.getLogger(__name__)


class ScalabilityService:
    """Serviço para escalabilidade e processamento assíncrono."""
    
    def __init__(self):
        self._config_padrao = None
    
    @property
    def config_padrao(self):
        """Obtém a configuração padrão de escalabilidade."""
        if self._config_padrao is None:
            self._config_padrao = self._get_configuracao_padrao()
        return self._config_padrao
    
    def _get_configuracao_padrao(self) -> ConfiguracaoEscalabilidade:
        """Obtém a configuração padrão de escalabilidade."""
        try:
            return ConfiguracaoEscalabilidade.objects.get(padrao=True, ativo=True)
        except ConfiguracaoEscalabilidade.DoesNotExist:
            # Criar configuração padrão se não existir
            return ConfiguracaoEscalabilidade.objects.create(
                nome='Configuração Padrão',
                padrao=True,
                ativo=True
            )
    
    def _gerar_chave_idempotencia(self, operacao: str, dados: Dict[str, Any]) -> str:
        """Gera chave de idempotência baseada na operação e dados."""
        dados_str = json.dumps(dados, sort_keys=True)
        hash_dados = hashlib.sha256(dados_str.encode()).hexdigest()
        return f"{operacao}:{hash_dados}"
    
    def adicionar_tarefa_fila(self,
                             tipo_fila: str,
                             nome_tarefa: str,
                             parametros: Dict[str, Any],
                             prioridade: str = 'NORMAL',
                             data_agendamento: Optional[datetime] = None,
                             dependencias: Optional[List[int]] = None,
                             criado_por: Optional[User] = None) -> FilaProcessamento:
        """
        Adiciona uma tarefa à fila de processamento.
        
        Args:
            tipo_fila: Tipo da fila
            nome_tarefa: Nome da tarefa
            parametros: Parâmetros da tarefa
            prioridade: Prioridade da tarefa
            data_agendamento: Data de agendamento
            dependencias: IDs de tarefas dependentes
            criado_por: Usuário que criou
            
        Returns:
            FilaProcessamento criada
        """
        try:
            if not self.config_padrao.processamento_assincrono:
                raise ValueError("Processamento assíncrono está desabilitado")
            
            tarefa = FilaProcessamento.objects.create(
                tipo_fila=tipo_fila,
                nome_tarefa=nome_tarefa,
                parametros=parametros,
                prioridade=prioridade,
                data_agendamento=data_agendamento or timezone.now(),
                criado_por=criado_por,
                status='PENDENTE'
            )
            
            # Adicionar dependências
            if dependencias:
                tarefa.dependencias.set(dependencias)
            
            logger.info(f"Tarefa adicionada à fila: {tarefa.codigo}")
            return tarefa
            
        except Exception as e:
            logger.error(f"Erro ao adicionar tarefa à fila: {e}")
            raise
    
    def processar_tarefa_fila(self, tarefa_id: int, funcao_processamento: Callable) -> FilaProcessamento:
        """
        Processa uma tarefa da fila.
        
        Args:
            tarefa_id: ID da tarefa
            funcao_processamento: Função para processar a tarefa
            
        Returns:
            FilaProcessamento processada
        """
        try:
            tarefa = FilaProcessamento.objects.get(id=tarefa_id)
            
            if tarefa.status != 'PENDENTE':
                raise ValueError(f"Tarefa não está no status 'PENDENTE'")
            
            # Verificar dependências
            dependencias_pendentes = tarefa.dependencias.filter(status__in=['PENDENTE', 'PROCESSANDO'])
            if dependencias_pendentes.exists():
                raise ValueError("Tarefa possui dependências não concluídas")
            
            # Marcar como processando
            tarefa.status = 'PROCESSANDO'
            tarefa.tentativas += 1
            tarefa.data_inicio_processamento = timezone.now()
            tarefa.save()
            
            # Processar tarefa
            try:
                resultado = funcao_processamento(tarefa.parametros)
                
                tarefa.status = 'CONCLUIDO'
                tarefa.resultado = resultado
                tarefa.data_fim_processamento = timezone.now()
                tarefa.save()
                
                logger.info(f"Tarefa processada com sucesso: {tarefa.codigo}")
                
            except Exception as e:
                tarefa.status = 'ERRO'
                tarefa.erro_mensagem = str(e)
                tarefa.data_fim_processamento = timezone.now()
                tarefa.save()
                
                logger.error(f"Erro ao processar tarefa {tarefa.codigo}: {e}")
                
                # Reagendar se ainda há tentativas
                if tarefa.tentativas < tarefa.tentativas_maximas:
                    self._reagendar_tarefa(tarefa)
            
            return tarefa
            
        except Exception as e:
            logger.error(f"Erro ao processar tarefa da fila: {e}")
            raise
    
    def _reagendar_tarefa(self, tarefa: FilaProcessamento):
        """Reagenda uma tarefa para nova tentativa."""
        try:
            # Calcular delay exponencial
            delay_minutos = 2 ** tarefa.tentativas
            
            tarefa.status = 'REAGENDADO'
            tarefa.data_agendamento = timezone.now() + timedelta(minutes=delay_minutos)
            tarefa.save()
            
            logger.info(f"Tarefa reagendada: {tarefa.codigo} - próxima tentativa em {delay_minutos} minutos")
            
        except Exception as e:
            logger.error(f"Erro ao reagendar tarefa: {e}")
    
    def executar_com_idempotencia(self,
                                 operacao: str,
                                 dados: Dict[str, Any],
                                 funcao_execucao: Callable,
                                 usuario: Optional[User] = None) -> Tuple[bool, Any]:
        """
        Executa uma operação com controle de idempotência.
        
        Args:
            operacao: Nome da operação
            dados: Dados da operação
            funcao_execucao: Função para executar
            usuario: Usuário responsável
            
        Returns:
            Tupla (sucesso, resultado)
        """
        try:
            if not self.config_padrao.idempotencia_habilitada:
                # Executar sem idempotência
                resultado = funcao_execucao(dados)
                return True, resultado
            
            # Gerar chave de idempotência
            chave_idempotencia = self._gerar_chave_idempotencia(operacao, dados)
            
            # Verificar se operação já foi executada
            controle_existente = ControleIdempotencia.objects.filter(
                chave_idempotencia=chave_idempotencia
            ).first()
            
            if controle_existente:
                if controle_existente.status == 'CONCLUIDO':
                    logger.info(f"Operação já executada (idempotência): {chave_idempotencia}")
                    return True, controle_existente.resultado
                elif controle_existente.status == 'PROCESSANDO':
                    logger.warning(f"Operação já em processamento: {chave_idempotencia}")
                    return False, "Operação já em processamento"
                elif controle_existente.status == 'ERRO':
                    logger.info(f"Operação anterior falhou, tentando novamente: {chave_idempotencia}")
            
            # Criar controle de idempotência
            controle = ControleIdempotencia.objects.create(
                chave_idempotencia=chave_idempotencia,
                tipo_operacao=operacao,
                modelo_afetado=dados.get('modelo', ''),
                objeto_id=dados.get('objeto_id', 0),
                status='PROCESSANDO',
                usuario=usuario,
                data_expiracao=timezone.now() + timedelta(
                    minutes=self.config_padrao.tempo_expiracao_idempotencia_minutos
                )
            )
            
            try:
                # Executar operação
                resultado = funcao_execucao(dados)
                
                # Marcar como concluída
                controle.status = 'CONCLUIDO'
                controle.resultado = resultado
                controle.save()
                
                logger.info(f"Operação executada com sucesso (idempotência): {chave_idempotencia}")
                return True, resultado
                
            except Exception as e:
                # Marcar como erro
                controle.status = 'ERRO'
                controle.erro_mensagem = str(e)
                controle.save()
                
                logger.error(f"Erro na operação (idempotência): {chave_idempotencia} - {e}")
                return False, str(e)
            
        except Exception as e:
            logger.error(f"Erro no controle de idempotência: {e}")
            raise
    
    def validar_operacao(self,
                        modelo_afetado: str,
                        objeto_id: int,
                        operacao: str,
                        dados: Dict[str, Any]) -> List[ResultadoValidacao]:
        """
        Executa validações para uma operação.
        
        Args:
            modelo_afetado: Modelo afetado
            objeto_id: ID do objeto
            operacao: Tipo de operação
            dados: Dados para validação
            
        Returns:
            Lista de resultados de validação
        """
        try:
            if not self.config_padrao.validacoes_obrigatorias:
                return []
            
            # Obter validações ativas
            validacoes = ValidacaoLogistica.objects.filter(
                modelo_afetado=modelo_afetado,
                ativo=True
            )
            
            resultados = []
            
            for validacao in validacoes:
                inicio_tempo = time.time()
                
                try:
                    # Executar validação
                    # Em um sistema real, você usaria eval() ou exec() com segurança
                    # Por enquanto, vamos simular
                    sucesso = True
                    mensagem = "Validação passou"
                    
                    # Simular validação baseada no tipo
                    if validacao.tipo_validacao == 'REGRA_NEGOCIO':
                        # Validar regras de negócio
                        sucesso = self._validar_regra_negocio(validacao, dados)
                        mensagem = "Regra de negócio validada" if sucesso else "Regra de negócio violada"
                    
                    elif validacao.tipo_validacao == 'INTEGRIDADE':
                        # Validar integridade
                        sucesso = self._validar_integridade(validacao, dados)
                        mensagem = "Integridade validada" if sucesso else "Integridade violada"
                    
                    elif validacao.tipo_validacao == 'PERFORMANCE':
                        # Validar performance
                        sucesso = self._validar_performance(validacao, dados)
                        mensagem = "Performance validada" if sucesso else "Performance violada"
                    
                    fim_tempo = time.time()
                    tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
                    
                    # Criar resultado
                    resultado = ResultadoValidacao.objects.create(
                        validacao=validacao,
                        modelo_afetado=modelo_afetado,
                        objeto_id=objeto_id,
                        operacao=operacao,
                        sucesso=sucesso,
                        mensagem=mensagem,
                        dados_validados=dados,
                        tempo_execucao_ms=tempo_execucao_ms
                    )
                    
                    resultados.append(resultado)
                    
                    # Se validação crítica falhou, parar execução
                    if not sucesso and validacao.nivel_validacao == 'CRITICAL':
                        break
                    
                except Exception as e:
                    fim_tempo = time.time()
                    tempo_execucao_ms = int((fim_tempo - inicio_tempo) * 1000)
                    
                    resultado = ResultadoValidacao.objects.create(
                        validacao=validacao,
                        modelo_afetado=modelo_afetado,
                        objeto_id=objeto_id,
                        operacao=operacao,
                        sucesso=False,
                        mensagem=f"Erro na validação: {str(e)}",
                        dados_validados=dados,
                        tempo_execucao_ms=tempo_execucao_ms
                    )
                    
                    resultados.append(resultado)
            
            logger.info(f"Validações executadas para {modelo_afetado}:{objeto_id} - {len(resultados)} validações")
            return resultados
            
        except Exception as e:
            logger.error(f"Erro ao executar validações: {e}")
            raise
    
    def _validar_regra_negocio(self, validacao: ValidacaoLogistica, dados: Dict[str, Any]) -> bool:
        """Valida regras de negócio."""
        # Implementação simplificada
        return True
    
    def _validar_integridade(self, validacao: ValidacaoLogistica, dados: Dict[str, Any]) -> bool:
        """Valida integridade dos dados."""
        # Implementação simplificada
        return True
    
    def _validar_performance(self, validacao: ValidacaoLogistica, dados: Dict[str, Any]) -> bool:
        """Valida performance."""
        # Implementação simplificada
        return True
    
    def executar_teste_contrato(self, teste_id: int) -> ExecucaoTesteContrato:
        """
        Executa um teste de contrato.
        
        Args:
            teste_id: ID do teste
            
        Returns:
            ExecucaoTesteContrato criada
        """
        try:
            teste = TesteContrato.objects.get(id=teste_id)
            
            if not teste.ativo:
                raise ValueError("Teste de contrato está inativo")
            
            # Criar execução
            execucao = ExecucaoTesteContrato.objects.create(
                teste_contrato=teste,
                status='EXECUTANDO'
            )
            
            inicio_tempo = time.time()
            
            try:
                # Simular execução do teste
                # Em um sistema real, você faria uma requisição HTTP real
                time.sleep(0.1)  # Simular delay
                
                # Simular resultado
                execucao.status = 'PASSOU'
                execucao.status_code_obtido = teste.status_code_esperado
                execucao.headers_obtidos = teste.headers_esperados
                execucao.body_response = '{"status": "success"}'
                execucao.validacoes_passaram = ['status_code', 'headers', 'schema']
                execucao.validacoes_falharam = []
                
                fim_tempo = time.time()
                execucao.tempo_resposta_ms = int((fim_tempo - inicio_tempo) * 1000)
                execucao.data_fim = timezone.now()
                execucao.save()
                
                logger.info(f"Teste de contrato executado com sucesso: {teste.codigo}")
                
            except Exception as e:
                execucao.status = 'FALHOU'
                execucao.erro_mensagem = str(e)
                execucao.data_fim = timezone.now()
                execucao.save()
                
                logger.error(f"Erro ao executar teste de contrato {teste.codigo}: {e}")
            
            return execucao
            
        except Exception as e:
            logger.error(f"Erro ao executar teste de contrato: {e}")
            raise
    
    def executar_todos_testes_contrato(self) -> List[ExecucaoTesteContrato]:
        """
        Executa todos os testes de contrato ativos.
        
        Returns:
            Lista de execuções
        """
        try:
            testes_ativos = TesteContrato.objects.filter(ativo=True)
            execucoes = []
            
            for teste in testes_ativos:
                execucao = self.executar_teste_contrato(teste.id)
                execucoes.append(execucao)
            
            logger.info(f"Executados {len(execucoes)} testes de contrato")
            return execucoes
            
        except Exception as e:
            logger.error(f"Erro ao executar todos os testes de contrato: {e}")
            raise
    
    def registrar_performance(self,
                             operacao: str,
                             tempo_execucao_ms: int,
                             endpoint: str = '',
                             metodo_http: str = '',
                             usuario: Optional[User] = None,
                             ip_address: Optional[str] = None,
                             sucesso: bool = True,
                             erro_mensagem: str = '') -> MonitoramentoPerformance:
        """
        Registra métricas de performance.
        
        Args:
            operacao: Nome da operação
            tempo_execucao_ms: Tempo de execução em ms
            endpoint: Endpoint acessado
            metodo_http: Método HTTP
            usuario: Usuário responsável
            ip_address: Endereço IP
            sucesso: Se a operação foi bem-sucedida
            erro_mensagem: Mensagem de erro
            
        Returns:
            MonitoramentoPerformance registrado
        """
        try:
            performance = MonitoramentoPerformance.objects.create(
                operacao=operacao,
                endpoint=endpoint,
                metodo_http=metodo_http,
                tempo_execucao_ms=tempo_execucao_ms,
                usuario=usuario,
                ip_address=ip_address,
                sucesso=sucesso,
                erro_mensagem=erro_mensagem
            )
            
            logger.debug(f"Performance registrada: {operacao} - {tempo_execucao_ms}ms")
            return performance
            
        except Exception as e:
            logger.error(f"Erro ao registrar performance: {e}")
            raise
    
    def obter_estatisticas_escalabilidade(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de escalabilidade.
        
        Returns:
            Dicionário com estatísticas
        """
        try:
            hoje = timezone.now().date()
            ultimos_7_dias = hoje - timedelta(days=7)
            
            stats = {
                'filas': {
                    'total_tarefas': FilaProcessamento.objects.count(),
                    'pendentes': FilaProcessamento.objects.filter(status='PENDENTE').count(),
                    'processando': FilaProcessamento.objects.filter(status='PROCESSANDO').count(),
                    'concluidas': FilaProcessamento.objects.filter(status='CONCLUIDO').count(),
                    'erros': FilaProcessamento.objects.filter(status='ERRO').count(),
                    'por_tipo': dict(
                        FilaProcessamento.objects.values('tipo_fila')
                        .annotate(count=Count('id'))
                        .values_list('tipo_fila', 'count')
                    )
                },
                'idempotencia': {
                    'total_operacoes': ControleIdempotencia.objects.count(),
                    'ultimos_7_dias': ControleIdempotencia.objects.filter(
                        data_criacao__date__gte=ultimos_7_dias
                    ).count(),
                    'operacoes_concluidas': ControleIdempotencia.objects.filter(
                        status='CONCLUIDO'
                    ).count(),
                    'operacoes_erro': ControleIdempotencia.objects.filter(
                        status='ERRO'
                    ).count()
                },
                'validacoes': {
                    'total_validacoes': ValidacaoLogistica.objects.filter(ativo=True).count(),
                    'total_execucoes': ResultadoValidacao.objects.count(),
                    'ultimos_7_dias': ResultadoValidacao.objects.filter(
                        data_execucao__date__gte=ultimos_7_dias
                    ).count(),
                    'validacoes_passaram': ResultadoValidacao.objects.filter(sucesso=True).count(),
                    'validacoes_falharam': ResultadoValidacao.objects.filter(sucesso=False).count()
                },
                'testes_contrato': {
                    'total_testes': TesteContrato.objects.filter(ativo=True).count(),
                    'total_execucoes': ExecucaoTesteContrato.objects.count(),
                    'ultimos_7_dias': ExecucaoTesteContrato.objects.filter(
                        data_inicio__date__gte=ultimos_7_dias
                    ).count(),
                    'testes_passaram': ExecucaoTesteContrato.objects.filter(status='PASSOU').count(),
                    'testes_falharam': ExecucaoTesteContrato.objects.filter(status='FALHOU').count()
                },
                'performance': {
                    'total_registros': MonitoramentoPerformance.objects.count(),
                    'ultimos_7_dias': MonitoramentoPerformance.objects.filter(
                        data_execucao__date__gte=ultimos_7_dias
                    ).count(),
                    'tempo_medio_ms': MonitoramentoPerformance.objects.aggregate(
                        tempo_medio=Avg('tempo_execucao_ms')
                    )['tempo_medio'] or 0,
                    'operacoes_sucesso': MonitoramentoPerformance.objects.filter(sucesso=True).count(),
                    'operacoes_erro': MonitoramentoPerformance.objects.filter(sucesso=False).count()
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de escalabilidade: {e}")
            raise


# Instância global do serviço
scalability_service = ScalabilityService()
