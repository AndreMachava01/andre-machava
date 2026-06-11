"""
MIXIN UNIFICADO PARA FILTROS DE BUSCA
Sistema oficial e único para filtros - substitui django-filters
Mixin Django para padronizar lógica de filtros em todas as views
"""

from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import HttpRequest
from django.shortcuts import render
from typing import Dict, Any, Optional, Tuple
import logging

from .filters_config import FilterProcessor, get_filter_config, FilterSetConfig

logger = logging.getLogger(__name__)


class UnifiedFilterMixin:
    """
    Mixin para padronizar filtros de busca em todas as views de listagem
    
    Uso:
        class MinhaListView(UnifiedFilterMixin, View):
            entity_name = 'produtos'
            template_name = 'minha_app/list.html'
            
            def get_queryset(self):
                return Item.objects.filter(tipo='PRODUTO')
    """
    
    # Configurações que devem ser sobrescritas nas classes filhas
    entity_name: str = None
    template_name: str = None
    extra_context: Dict[str, Any] = None
    
    def get_entity_name(self) -> str:
        """Retorna o nome da entidade para configuração de filtros"""
        if not self.entity_name:
            raise ValueError("entity_name deve ser definido na classe filha")
        return self.entity_name
    
    def get_template_name(self) -> str:
        """Retorna o nome do template"""
        if not self.template_name:
            raise ValueError("template_name deve ser definido na classe filha")
        return self.template_name
    
    def get_queryset(self) -> QuerySet:
        """
        Retorna o queryset base para filtros
        Deve ser sobrescrito nas classes filhas
        """
        raise NotImplementedError("get_queryset deve ser implementado na classe filha")
    
    def get_filter_config(self) -> Optional[FilterSetConfig]:
        """Obtém configuração de filtros para a entidade"""
        return get_filter_config(self.get_entity_name())
    
    def get_filter_choices(self) -> Dict[str, Any]:
        """
        Obtém choices dinâmicos para os filtros
        Deve ser sobrescrito nas classes filhas se necessário
        """
        return {}
    
    def get_extra_context(self) -> Dict[str, Any]:
        """Retorna contexto adicional para o template"""
        return self.extra_context or {}
    
    def apply_custom_filters(self, queryset: QuerySet, request: HttpRequest) -> QuerySet:
        """
        Aplica filtros customizados específicos da view
        Deve ser sobrescrito nas classes filhas se necessário
        """
        return queryset
    
    def get_pagination_size(self) -> int:
        """Retorna tamanho da paginação"""
        config = self.get_filter_config()
        return config.pagination_size if config else 20
    
    def process_filters(self, request: HttpRequest) -> Tuple[QuerySet, Dict[str, Any]]:
        """
        Processa todos os filtros e retorna queryset filtrado e contexto
        
        Returns:
            tuple: (queryset_filtrado, contexto_filtros)
        """
        try:
            # Obter queryset base
            queryset = self.get_queryset()
            
            # Obter configuração de filtros
            config = self.get_filter_config()
            if not config:
                logger.warning(f"Configuração de filtros não encontrada para: {self.get_entity_name()}")
                return queryset, {}
            
            # Criar processador de filtros
            processor = FilterProcessor(config, queryset)
            
            # Aplicar filtros padrão
            filtered_queryset, filter_context = processor.apply_filters(request.GET)
            
            # Aplicar filtros customizados
            filtered_queryset = self.apply_custom_filters(filtered_queryset, request)
            
            # Adicionar choices dinâmicos ao contexto
            choices = self.get_filter_choices()
            filter_context.update(choices)
            
            return filtered_queryset, filter_context
            
        except Exception as e:
            logger.error(f"Erro ao processar filtros para {self.get_entity_name()}: {e}")
            return self.get_queryset(), {}
    
    def paginate_queryset(self, queryset: QuerySet, request: HttpRequest) -> Tuple[Any, Dict[str, Any]]:
        """
        Aplica paginação ao queryset
        
        Returns:
            tuple: (page_obj, contexto_paginacao)
        """
        try:
            pagination_size = self.get_pagination_size()
            paginator = Paginator(queryset, pagination_size)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)
            
            pagination_context = {
                'page_obj': page_obj,
                'paginator': paginator,
                'is_paginated': page_obj.has_other_pages(),
            }
            
            return page_obj, pagination_context
            
        except Exception as e:
            logger.error(f"Erro na paginação para {self.get_entity_name()}: {e}")
            return None, {'page_obj': None, 'is_paginated': False}
    
    def get_context_data(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Monta contexto completo para o template
        
        Returns:
            dict: Contexto completo
        """
        try:
            # Processar filtros
            filtered_queryset, filter_context = self.process_filters(request)
            
            # Aplicar paginação
            page_obj, pagination_context = self.paginate_queryset(filtered_queryset, request)
            
            # Contexto base
            context = {
                'entity_name': self.get_entity_name(),
                'filter_config': self.get_filter_config(),
                'timestamp': int(__import__('time').time()),  # Cache busting
            }
            
            # Adicionar contextos específicos
            context.update(filter_context)
            context.update(pagination_context)
            context.update(self.get_extra_context())
            
            return context
            
        except Exception as e:
            logger.error(f"Erro ao montar contexto para {self.get_entity_name()}: {e}")
            return {
                'entity_name': self.get_entity_name(),
                'page_obj': None,
                'is_paginated': False,
                'error': str(e)
            }
    
    def render_list_view(self, request: HttpRequest):
        """
        Renderiza view de listagem com filtros unificados
        
        Returns:
            HttpResponse: Resposta renderizada
        """
        try:
            context = self.get_context_data(request)
            template_name = self.get_template_name()
            
            return render(request, template_name, context)
            
        except Exception as e:
            logger.error(f"Erro ao renderizar view de listagem para {self.get_entity_name()}: {e}")
            return render(request, self.get_template_name(), {
                'entity_name': self.get_entity_name(),
                'page_obj': None,
                'error': 'Erro ao carregar dados'
            })


class FilteredListView(UnifiedFilterMixin):
    """
    View base para listagens com filtros unificados
    
    Uso:
        class ProdutosListView(FilteredListView):
            entity_name = 'produtos'
            template_name = 'stock/produtos/main.html'
            
            def get_queryset(self):
                return Item.objects.filter(tipo='PRODUTO')
            
            def get_filter_choices(self):
                return {
                    'categorias': CategoriaProduto.objects.filter(ativa=True),
                    'status_choices': Item.STATUS_CHOICES,
                    'tipo_choices': Item.PRODUTO_TIPO_CHOICES,
                }
    """
    
    def get(self, request: HttpRequest):
        """Método GET para renderizar listagem com filtros"""
        return self.render_list_view(request)


class FilteredAPIView(UnifiedFilterMixin):
    """
    View base para APIs com filtros unificados
    
    Uso:
        class ProdutosAPIView(FilteredAPIView):
            entity_name = 'produtos'
            
            def get_queryset(self):
                return Item.objects.filter(tipo='PRODUTO')
            
            def get(self, request):
                queryset, context = self.process_filters(request)
                # Retornar dados serializados
    """
    
    def get_api_data(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Retorna dados para API
        
        Returns:
            dict: Dados serializados
        """
        try:
            filtered_queryset, filter_context = self.process_filters(request)
            
            # Serializar dados (implementar conforme necessário)
            data = {
                'results': list(filtered_queryset.values()),
                'filters_applied': filter_context,
                'total_count': filtered_queryset.count(),
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Erro na API para {self.get_entity_name()}: {e}")
            return {'error': str(e), 'results': []}
