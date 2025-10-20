"""
Utilitários para integração automática de presenças
com módulos de férias e licenças
"""

from datetime import date, timedelta
from .models_rh import Funcionario, TipoPresenca, Presenca


class PresencaAutomatica:
    """
    Classe para gerenciar marcação automática de presenças
    """
    
    @staticmethod
    def marcar_ferias(funcionario_id, data_inicio, data_fim, observacoes=''):
        """
        Marcar férias automaticamente no calendário de presenças
        
        Args:
            funcionario_id (int): ID do funcionário
            data_inicio (date): Data de início das férias
            data_fim (date): Data de fim das férias
            observacoes (str): Observações adicionais
        
        Returns:
            dict: Resultado da operação
        """
        from .views import marcar_presencas_automaticas
        
        return marcar_presencas_automaticas(
            funcionario_id=funcionario_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            tipo_presenca_codigo='FE',
            observacoes=f"Férias aprovadas - {observacoes}".strip()
        )
    
    @staticmethod
    def marcar_licenca(funcionario_id, data_inicio, data_fim, observacoes=''):
        """
        Marcar licença automaticamente no calendário de presenças
        
        Args:
            funcionario_id (int): ID do funcionário
            data_inicio (date): Data de início da licença
            data_fim (date): Data de fim da licença
            observacoes (str): Observações adicionais
        
        Returns:
            dict: Resultado da operação
        """
        from .views import marcar_presencas_automaticas
        
        return marcar_presencas_automaticas(
            funcionario_id=funcionario_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            tipo_presenca_codigo='LI',
            observacoes=f"Licença aprovada - {observacoes}".strip()
        )
    
    @staticmethod
    def cancelar_ferias(funcionario_id, data_inicio, data_fim):
        """
        Cancelar férias e remover marcações automáticas
        
        Args:
            funcionario_id (int): ID do funcionário
            data_inicio (date): Data de início das férias canceladas
            data_fim (date): Data de fim das férias canceladas
        
        Returns:
            dict: Resultado da operação
        """
        from .views import remover_presencas_automaticas
        
        return remover_presencas_automaticas(
            funcionario_id=funcionario_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            tipo_presenca_codigo='FE'
        )
    
    @staticmethod
    def cancelar_licenca(funcionario_id, data_inicio, data_fim):
        """
        Cancelar licença e remover marcações automáticas
        
        Args:
            funcionario_id (int): ID do funcionário
            data_inicio (date): Data de início da licença cancelada
            data_fim (date): Data de fim da licença cancelada
        
        Returns:
            dict: Resultado da operação
        """
        from .views import remover_presencas_automaticas
        
        return remover_presencas_automaticas(
            funcionario_id=funcionario_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
            tipo_presenca_codigo='LI'
        )
    
    @staticmethod
    def verificar_conflitos(funcionario_id, data_inicio, data_fim):
        """
        Verificar se há conflitos de presenças no período
        
        Args:
            funcionario_id (int): ID do funcionário
            data_inicio (date): Data de início
            data_fim (date): Data de fim
        
        Returns:
            dict: Informações sobre conflitos encontrados
        """
        try:
            funcionario = Funcionario.objects.get(id=funcionario_id, status='AT')
            
            # Buscar presenças existentes no período
            presencas_existentes = Presenca.objects.filter(
                funcionario=funcionario,
                data__range=[data_inicio, data_fim]
            ).select_related('tipo_presenca')
            
            conflitos = []
            for presenca in presencas_existentes:
                conflitos.append({
                    'data': presenca.data,
                    'tipo_atual': presenca.tipo_presenca.nome,
                    'codigo_atual': presenca.tipo_presenca.codigo,
                    'observacoes': presenca.observacoes
                })
            
            return {
                'success': True,
                'tem_conflitos': len(conflitos) > 0,
                'conflitos': conflitos,
                'total_conflitos': len(conflitos)
            }
            
        except Funcionario.DoesNotExist:
            return {
                'success': False,
                'error': 'Funcionário não encontrado ou inativo'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def obter_resumo_presencas(funcionario_id, data_inicio, data_fim):
        """
        Obter resumo de presenças no período
        
        Args:
            funcionario_id (int): ID do funcionário
            data_inicio (date): Data de início
            data_fim (date): Data de fim
        
        Returns:
            dict: Resumo das presenças
        """
        try:
            funcionario = Funcionario.objects.get(id=funcionario_id, status='AT')
            
            # Buscar presenças no período
            presencas = Presenca.objects.filter(
                funcionario=funcionario,
                data__range=[data_inicio, data_fim]
            ).select_related('tipo_presenca')
            
            # Contar por tipo
            resumo = {}
            for presenca in presencas:
                tipo = presenca.tipo_presenca.nome
                if tipo not in resumo:
                    resumo[tipo] = 0
                resumo[tipo] += 1
            
            # Calcular dias úteis no período
            dias_uteis = 0
            data_atual = data_inicio
            while data_atual <= data_fim:
                if data_atual.weekday() < 5:  # Segunda a sexta
                    dias_uteis += 1
                data_atual += timedelta(days=1)
            
            return {
                'success': True,
                'funcionario': funcionario.nome_completo,
                'periodo': f"{data_inicio} a {data_fim}",
                'dias_uteis': dias_uteis,
                'presencas_registradas': len(presencas),
                'resumo_por_tipo': resumo
            }
            
        except Funcionario.DoesNotExist:
            return {
                'success': False,
                'error': 'Funcionário não encontrado ou inativo'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# Exemplos de uso para os módulos de férias e licenças:

def exemplo_uso_ferias():
    """
    Exemplo de como usar no módulo de férias
    """
    from datetime import date
    
    # Quando aprovar férias
    funcionario_id = 1
    data_inicio = date(2025, 10, 1)
    data_fim = date(2025, 10, 15)
    observacoes = "Férias anuais aprovadas pelo RH"
    
    resultado = PresencaAutomatica.marcar_ferias(
        funcionario_id=funcionario_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        observacoes=observacoes
    )
    
    if resultado['success']:
        print(f"✅ {resultado['sucessos']} dias de férias marcados automaticamente")
    else:
        print(f"❌ Erro: {resultado['error']}")


def exemplo_uso_licencas():
    """
    Exemplo de como usar no módulo de licenças
    """
    from datetime import date
    
    # Quando aprovar licença
    funcionario_id = 1
    data_inicio = date(2025, 9, 20)
    data_fim = date(2025, 9, 25)
    observacoes = "Licença médica aprovada"
    
    resultado = PresencaAutomatica.marcar_licenca(
        funcionario_id=funcionario_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        observacoes=observacoes
    )
    
    if resultado['success']:
        print(f"✅ {resultado['sucessos']} dias de licença marcados automaticamente")
    else:
        print(f"❌ Erro: {resultado['error']}")


def exemplo_verificar_conflitos():
    """
    Exemplo de como verificar conflitos antes de aprovar
    """
    from datetime import date
    
    funcionario_id = 1
    data_inicio = date(2025, 10, 1)
    data_fim = date(2025, 10, 15)
    
    resultado = PresencaAutomatica.verificar_conflitos(
        funcionario_id=funcionario_id,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
    
    if resultado['success']:
        if resultado['tem_conflitos']:
            print(f"⚠️ Encontrados {resultado['total_conflitos']} conflitos:")
            for conflito in resultado['conflitos']:
                print(f"  - {conflito['data']}: {conflito['tipo_atual']}")
        else:
            print("✅ Nenhum conflito encontrado")
    else:
        print(f"❌ Erro: {resultado['error']}")
