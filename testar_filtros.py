#!/usr/bin/env python3
"""
SCRIPT DE TESTE E VALIDAÇÃO DE FILTROS
Sistema Unificado de Filtros - Testes Automatizados

Este script testa e valida o funcionamento dos filtros após migração,
verificando se todas as funcionalidades estão operacionais.

Funcionalidades:
1. Testa configurações de filtros
2. Valida templates migrados
3. Verifica consistência de dados
4. Testa funcionalidades JavaScript
5. Gera relatório de testes

Autor: Sistema Conception
Data: 2025
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('filtros_testes.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Representa resultado de um teste"""
    test_name: str
    status: str  # 'pass', 'fail', 'skip'
    message: str
    details: Optional[Dict] = None

class FilterTester:
    """Classe principal para testes de filtros"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.templates_dir = self.project_root / 'templates'
        self.filters_config_file = self.project_root / 'meuprojeto' / 'empresa' / 'filters_config.py'
        self.test_results: List[TestResult] = []
        
    def run_all_tests(self) -> Dict:
        """Executa todos os testes"""
        logger.info("🧪 Iniciando testes de filtros...")
        
        # 1. Testar estrutura de arquivos
        self._test_file_structure()
        
        # 2. Testar configurações
        self._test_filter_configurations()
        
        # 3. Testar templates
        self._test_templates()
        
        # 4. Testar consistência
        self._test_consistency()
        
        # 5. Testar funcionalidades específicas
        self._test_specific_functionality()
        
        # 6. Gerar relatório
        report = self._generate_test_report()
        
        logger.info("✅ Testes concluídos!")
        return report
    
    def _test_file_structure(self):
        """Testa estrutura de arquivos necessários"""
        logger.info("📁 Testando estrutura de arquivos...")
        
        required_files = [
            self.templates_dir / 'includes' / 'filters_unified.html',
            self.filters_config_file,
            self.project_root / 'meuprojeto' / 'empresa' / 'mixins.py'
        ]
        
        for file_path in required_files:
            test_name = f"file_exists_{file_path.name}"
            if file_path.exists():
                self.test_results.append(TestResult(
                    test_name=test_name,
                    status='pass',
                    message=f"Arquivo {file_path.name} encontrado"
                ))
            else:
                self.test_results.append(TestResult(
                    test_name=test_name,
                    status='fail',
                    message=f"Arquivo {file_path.name} não encontrado"
                ))
    
    def _test_filter_configurations(self):
        """Testa configurações de filtros"""
        logger.info("⚙️ Testando configurações de filtros...")
        
        if not self.filters_config_file.exists():
            self.test_results.append(TestResult(
                test_name="config_file_exists",
                status='fail',
                message="Arquivo filters_config.py não encontrado"
            ))
            return
        
        try:
            with open(self.filters_config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Testar sintaxe Python
            try:
                compile(content, str(self.filters_config_file), 'exec')
                self.test_results.append(TestResult(
                    test_name="config_syntax",
                    status='pass',
                    message="Sintaxe Python válida"
                ))
            except SyntaxError as e:
                self.test_results.append(TestResult(
                    test_name="config_syntax",
                    status='fail',
                    message=f"Erro de sintaxe: {e}"
                ))
            
            # Testar classes necessárias
            required_classes = ['FilterType', 'FilterConfig', 'FilterSetConfig', 'UnifiedFilterRegistry', 'FilterProcessor']
            for class_name in required_classes:
                if f"class {class_name}" in content:
                    self.test_results.append(TestResult(
                        test_name=f"class_{class_name.lower()}",
                        status='pass',
                        message=f"Classe {class_name} encontrada"
                    ))
                else:
                    self.test_results.append(TestResult(
                        test_name=f"class_{class_name.lower()}",
                        status='fail',
                        message=f"Classe {class_name} não encontrada"
                    ))
            
            # Testar configurações registradas
            import re
            config_pattern = r'(\w+_config)\s*=\s*FilterSetConfig\s*\('
            configs = re.findall(config_pattern, content)
            
            self.test_results.append(TestResult(
                test_name="configurations_count",
                status='pass',
                message=f"{len(configs)} configurações encontradas",
                details={'configurations': configs}
            ))
            
        except Exception as e:
            self.test_results.append(TestResult(
                test_name="config_analysis",
                status='fail',
                message=f"Erro ao analisar configurações: {e}"
            ))
    
    def _test_templates(self):
        """Testa templates com filtros"""
        logger.info("📄 Testando templates...")
        
        templates_with_filters = []
        
        for template_file in self.templates_dir.rglob('*.html'):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if 'filters_unified.html' in content:
                    templates_with_filters.append(str(template_file))
                    
                    # Testar sintaxe do template
                    test_name = f"template_syntax_{template_file.name}"
                    if '{%' in content and '%}' in content:
                        # Verificar se tem entity_name
                        if 'entity_name=' in content:
                            self.test_results.append(TestResult(
                                test_name=test_name,
                                status='pass',
                                message=f"Template {template_file.name} com sintaxe válida"
                            ))
                        else:
                            self.test_results.append(TestResult(
                                test_name=test_name,
                                status='fail',
                                message=f"Template {template_file.name} sem entity_name"
                            ))
                    else:
                        self.test_results.append(TestResult(
                            test_name=test_name,
                            status='fail',
                            message=f"Template {template_file.name} sem sintaxe Django"
                        ))
                    
            except Exception as e:
                self.test_results.append(TestResult(
                    test_name=f"template_error_{template_file.name}",
                    status='fail',
                    message=f"Erro ao ler {template_file.name}: {e}"
                ))
        
        self.test_results.append(TestResult(
            test_name="templates_with_filters",
            status='pass',
            message=f"{len(templates_with_filters)} templates com filtros encontrados",
            details={'templates': templates_with_filters}
        ))
    
    def _test_consistency(self):
        """Testa consistência entre templates e configurações"""
        logger.info("🔄 Testando consistência...")
        
        if not self.filters_config_file.exists():
            return
        
        try:
            with open(self.filters_config_file, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # Extrair configurações
            import re
            config_pattern = r'(\w+_config)\s*=\s*FilterSetConfig\s*\('
            configs = re.findall(config_pattern, config_content)
            
            # Extrair entidades dos templates
            entity_names = set()
            for template_file in self.templates_dir.rglob('*.html'):
                try:
                    with open(template_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if 'filters_unified.html' in content:
                        entity_match = re.search(r'entity_name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                        if entity_match:
                            entity_names.add(entity_match.group(1))
                            
                except Exception:
                    continue
            
            # Verificar se cada entidade tem configuração
            missing_configs = []
            for entity_name in entity_names:
                config_name = f"{entity_name}_config"
                if config_name not in configs:
                    missing_configs.append(entity_name)
            
            if missing_configs:
                self.test_results.append(TestResult(
                    test_name="consistency_check",
                    status='fail',
                    message=f"Configurações faltantes para: {', '.join(missing_configs)}"
                ))
            else:
                self.test_results.append(TestResult(
                    test_name="consistency_check",
                    status='pass',
                    message="Todas as entidades têm configurações"
                ))
                
        except Exception as e:
            self.test_results.append(TestResult(
                test_name="consistency_analysis",
                status='fail',
                message=f"Erro na análise de consistência: {e}"
            ))
    
    def _test_specific_functionality(self):
        """Testa funcionalidades específicas"""
        logger.info("🔍 Testando funcionalidades específicas...")
        
        # Testar template unificado
        unified_template = self.templates_dir / 'includes' / 'filters_unified.html'
        if unified_template.exists():
            try:
                with open(unified_template, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Testar elementos necessários
                required_elements = [
                    'filters-section-professional',
                    'search-input',
                    'form-select',
                    'btn-filter',
                    'btn-clear-filters',
                    'toggleFilters',
                    'clearFilters'
                ]
                
                for element in required_elements:
                    if element in content:
                        self.test_results.append(TestResult(
                            test_name=f"unified_template_{element}",
                            status='pass',
                            message=f"Elemento {element} encontrado"
                        ))
                    else:
                        self.test_results.append(TestResult(
                            test_name=f"unified_template_{element}",
                            status='fail',
                            message=f"Elemento {element} não encontrado"
                        ))
                
            except Exception as e:
                self.test_results.append(TestResult(
                    test_name="unified_template_read",
                    status='fail',
                    message=f"Erro ao ler template unificado: {e}"
                ))
        
        # Testar CSS e JavaScript
        self._test_css_javascript()
    
    def _test_css_javascript(self):
        """Testa CSS e JavaScript dos filtros"""
        logger.info("🎨 Testando CSS e JavaScript...")
        
        unified_template = self.templates_dir / 'includes' / 'filters_unified.html'
        if not unified_template.exists():
            return
        
        try:
            with open(unified_template, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Testar CSS
            css_elements = [
                '.filters-section-professional',
                '.search-input',
                '.filter-group',
                '.btn-filter',
                '@media'
            ]
            
            for element in css_elements:
                if element in content:
                    self.test_results.append(TestResult(
                        test_name=f"css_{element.replace('.', '').replace('@', '')}",
                        status='pass',
                        message=f"CSS {element} encontrado"
                    ))
                else:
                    self.test_results.append(TestResult(
                        test_name=f"css_{element.replace('.', '').replace('@', '')}",
                        status='fail',
                        message=f"CSS {element} não encontrado"
                    ))
            
            # Testar JavaScript
            js_functions = [
                'initializeFilters',
                'clearFilters',
                'toggleFilters',
                'addEventListener'
            ]
            
            for func in js_functions:
                if func in content:
                    self.test_results.append(TestResult(
                        test_name=f"js_{func}",
                        status='pass',
                        message=f"Função JavaScript {func} encontrada"
                    ))
                else:
                    self.test_results.append(TestResult(
                        test_name=f"js_{func}",
                        status='fail',
                        message=f"Função JavaScript {func} não encontrada"
                    ))
                    
        except Exception as e:
            self.test_results.append(TestResult(
                test_name="css_js_analysis",
                status='fail',
                message=f"Erro ao analisar CSS/JS: {e}"
            ))
    
    def _generate_test_report(self) -> Dict:
        """Gera relatório dos testes"""
        logger.info("📊 Gerando relatório de testes...")
        
        # Estatísticas
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == 'pass'])
        failed_tests = len([r for r in self.test_results if r.status == 'fail'])
        skipped_tests = len([r for r in self.test_results if r.status == 'skip'])
        
        # Agrupar por categoria
        tests_by_category = {}
        for result in self.test_results:
            category = result.test_name.split('_')[0]
            if category not in tests_by_category:
                tests_by_category[category] = []
            tests_by_category[category].append(result)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'skipped': skipped_tests,
                'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            'tests_by_category': tests_by_category,
            'all_results': [
                {
                    'test_name': r.test_name,
                    'status': r.status,
                    'message': r.message,
                    'details': r.details
                }
                for r in self.test_results
            ],
            'recommendations': self._generate_test_recommendations()
        }
        
        return report
    
    def _generate_test_recommendations(self) -> List[str]:
        """Gera recomendações baseadas nos testes"""
        recommendations = []
        
        failed_tests = [r for r in self.test_results if r.status == 'fail']
        
        if not failed_tests:
            recommendations.append("✅ Todos os testes passaram! Sistema de filtros funcionando corretamente.")
            return recommendations
        
        # Recomendações baseadas nos testes que falharam
        failed_categories = set(test.test_name.split('_')[0] for test in failed_tests)
        
        if 'file' in failed_categories:
            recommendations.append("🔧 Verificar estrutura de arquivos necessários")
        
        if 'config' in failed_categories:
            recommendations.append("⚙️ Corrigir configurações de filtros")
        
        if 'template' in failed_categories:
            recommendations.append("📄 Revisar templates com problemas")
        
        if 'consistency' in failed_categories:
            recommendations.append("🔄 Sincronizar templates e configurações")
        
        if 'css' in failed_categories or 'js' in failed_categories:
            recommendations.append("🎨 Verificar CSS e JavaScript dos filtros")
        
        recommendations.append("🧪 Executar testes novamente após correções")
        recommendations.append("📚 Documentar problemas encontrados")
        
        return recommendations

def main():
    """Função principal do script"""
    print("🧪 SCRIPT DE TESTE E VALIDAÇÃO DE FILTROS")
    print("=" * 50)
    
    # Obter diretório do projeto
    project_root = os.getcwd()
    logger.info(f"Diretório do projeto: {project_root}")
    
    # Executar testes
    tester = FilterTester(project_root)
    report = tester.run_all_tests()
    
    # Exibir resumo
    print("\n📊 RESUMO DOS TESTES:")
    print(f"Total de testes: {report['summary']['total_tests']}")
    print(f"Testes aprovados: {report['summary']['passed']}")
    print(f"Testes falharam: {report['summary']['failed']}")
    print(f"Testes ignorados: {report['summary']['skipped']}")
    print(f"Taxa de sucesso: {report['summary']['success_rate']:.1f}%")
    
    # Exibir testes por categoria
    print("\n📋 TESTES POR CATEGORIA:")
    for category, tests in report['tests_by_category'].items():
        passed = len([t for t in tests if t.status == 'pass'])
        total = len(tests)
        print(f"  {category.upper()}: {passed}/{total} ({passed/total*100:.1f}%)")
    
    # Exibir testes que falharam
    failed_tests = [r for r in tester.test_results if r.status == 'fail']
    if failed_tests:
        print("\n❌ TESTES QUE FALHARAM:")
        for test in failed_tests:
            print(f"  - {test.test_name}: {test.message}")
    
    # Exibir recomendações
    print("\n💡 RECOMENDAÇÕES:")
    for recommendation in report['recommendations']:
        print(f"  {recommendation}")
    
    # Salvar relatório
    report_file = 'relatorio_testes_filtros.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Relatório salvo em: {report_file}")
    print("✅ Testes concluídos!")

if __name__ == "__main__":
    main()
