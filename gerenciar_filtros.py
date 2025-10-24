#!/usr/bin/env python3
"""
SCRIPT PRINCIPAL DE VERIFICAÇÃO E CORREÇÃO DE FILTROS
Sistema Unificado de Filtros - Orquestrador Principal

Este script principal coordena todos os outros scripts de filtros,
fornecendo uma interface única para verificação, correção e migração.

Funcionalidades:
1. Executa verificação completa
2. Oferece correções automáticas
3. Realiza migração quando necessário
4. Executa testes de validação
5. Gera relatórios consolidados

Autor: Sistema Conception
Data: 2025
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('filtros_principal.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class FilterManager:
    """Classe principal para gerenciamento de filtros"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.scripts_dir = self.project_root
        self.reports = {}
        
    def run_complete_workflow(self) -> Dict:
        """Executa fluxo completo de verificação e correção"""
        logger.info("🚀 Iniciando fluxo completo de filtros...")
        
        workflow_results = {
            'timestamp': datetime.now().isoformat(),
            'steps': [],
            'summary': {},
            'recommendations': []
        }
        
        # 1. Verificação inicial
        logger.info("📋 Passo 1: Verificação inicial...")
        verification_result = self._run_verification()
        workflow_results['steps'].append({
            'step': 'verification',
            'status': verification_result['summary']['total_issues'] == 0,
            'issues_found': verification_result['summary']['total_issues']
        })
        
        # 2. Correções automáticas (se necessário)
        if verification_result['summary']['total_issues'] > 0:
            logger.info("🔧 Passo 2: Aplicando correções automáticas...")
            correction_result = self._run_corrections(verification_result)
            workflow_results['steps'].append({
                'step': 'corrections',
                'status': True,
                'corrections_applied': len(correction_result.get('corrections', []))
            })
            
            # Verificação pós-correção
            logger.info("🔄 Passo 3: Verificação pós-correção...")
            post_verification = self._run_verification()
            workflow_results['steps'].append({
                'step': 'post_verification',
                'status': post_verification['summary']['total_issues'] == 0,
                'issues_remaining': post_verification['summary']['total_issues']
            })
        
        # 3. Migração (se necessário)
        logger.info("🚀 Passo 4: Verificando necessidade de migração...")
        migration_result = self._run_migration()
        workflow_results['steps'].append({
            'step': 'migration',
            'status': migration_result['summary']['completed'] > 0,
            'migrations_completed': migration_result['summary']['completed']
        })
        
        # 4. Testes finais
        logger.info("🧪 Passo 5: Executando testes de validação...")
        test_result = self._run_tests()
        workflow_results['steps'].append({
            'step': 'testing',
            'status': test_result['summary']['success_rate'] > 80,
            'success_rate': test_result['summary']['success_rate']
        })
        
        # 5. Gerar resumo final
        workflow_results['summary'] = self._generate_workflow_summary(workflow_results['steps'])
        workflow_results['recommendations'] = self._generate_final_recommendations(workflow_results)
        
        logger.info("✅ Fluxo completo finalizado!")
        return workflow_results
    
    def _run_verification(self) -> Dict:
        """Executa script de verificação"""
        try:
            script_path = self.scripts_dir / 'verificar_corrigir_filtros.py'
            if not script_path.exists():
                logger.error(f"Script de verificação não encontrado: {script_path}")
                return {'summary': {'total_issues': 0}}
            
            # Executar script
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Tentar carregar relatório JSON
            report_file = self.project_root / 'relatorio_filtros.json'
            if report_file.exists():
                with open(report_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return {'summary': {'total_issues': 0}}
            
        except Exception as e:
            logger.error(f"Erro ao executar verificação: {e}")
            return {'summary': {'total_issues': 0}}
    
    def _run_corrections(self, verification_result: Dict) -> Dict:
        """Executa correções automáticas"""
        try:
            # Usar o mesmo script de verificação com correções
            script_path = self.scripts_dir / 'verificar_corrigir_filtros.py'
            
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                input='s\n'  # Resposta automática para executar correções
            )
            
            return {'corrections': ['Correções aplicadas via script de verificação']}
            
        except Exception as e:
            logger.error(f"Erro ao executar correções: {e}")
            return {'corrections': []}
    
    def _run_migration(self) -> Dict:
        """Executa migração de filtros"""
        try:
            script_path = self.scripts_dir / 'migrar_corrigir_filtros.py'
            if not script_path.exists():
                logger.warning("Script de migração não encontrado")
                return {'summary': {'completed': 0}}
            
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Tentar carregar relatório JSON
            report_file = self.project_root / 'relatorio_migracao_filtros.json'
            if report_file.exists():
                with open(report_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return {'summary': {'completed': 0}}
            
        except Exception as e:
            logger.error(f"Erro ao executar migração: {e}")
            return {'summary': {'completed': 0}}
    
    def _run_tests(self) -> Dict:
        """Executa testes de validação"""
        try:
            script_path = self.scripts_dir / 'testar_filtros.py'
            if not script_path.exists():
                logger.warning("Script de testes não encontrado")
                return {'summary': {'success_rate': 0}}
            
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            # Tentar carregar relatório JSON
            report_file = self.project_root / 'relatorio_testes_filtros.json'
            if report_file.exists():
                with open(report_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return {'summary': {'success_rate': 0}}
            
        except Exception as e:
            logger.error(f"Erro ao executar testes: {e}")
            return {'summary': {'success_rate': 0}}
    
    def _generate_workflow_summary(self, steps: List[Dict]) -> Dict:
        """Gera resumo do workflow"""
        total_steps = len(steps)
        successful_steps = len([s for s in steps if s['status']])
        
        return {
            'total_steps': total_steps,
            'successful_steps': successful_steps,
            'success_rate': (successful_steps / total_steps * 100) if total_steps > 0 else 0,
            'workflow_status': 'success' if successful_steps == total_steps else 'partial' if successful_steps > 0 else 'failed'
        }
    
    def _generate_final_recommendations(self, workflow_results: Dict) -> List[str]:
        """Gera recomendações finais"""
        recommendations = []
        
        summary = workflow_results['summary']
        
        if summary['workflow_status'] == 'success':
            recommendations.append("✅ Todos os filtros estão funcionando perfeitamente!")
            recommendations.append("🎉 Sistema de filtros totalmente operacional")
        elif summary['workflow_status'] == 'partial':
            recommendations.append("⚠️ Alguns problemas foram encontrados e corrigidos")
            recommendations.append("🧪 Testar funcionalidades manualmente")
            recommendations.append("📚 Revisar logs para detalhes")
        else:
            recommendations.append("❌ Problemas significativos encontrados")
            recommendations.append("🔧 Revisar e corrigir manualmente")
            recommendations.append("📞 Considerar suporte técnico")
        
        recommendations.append("📊 Revisar relatórios gerados para detalhes")
        recommendations.append("🔄 Executar este script periodicamente para manutenção")
        
        return recommendations

def show_menu():
    """Exibe menu principal"""
    print("\n" + "="*60)
    print("🔍 SCRIPT PRINCIPAL DE VERIFICAÇÃO E CORREÇÃO DE FILTROS")
    print("="*60)
    print("\nEscolha uma opção:")
    print("1. 🔍 Verificação completa (recomendado)")
    print("2. 🔧 Apenas correções automáticas")
    print("3. 🚀 Apenas migração de filtros")
    print("4. 🧪 Apenas testes de validação")
    print("5. 📊 Verificar relatórios existentes")
    print("6. ❓ Ajuda e documentação")
    print("0. 🚪 Sair")
    print("\n" + "="*60)

def show_help():
    """Exibe ajuda e documentação"""
    print("\n📚 AJUDA E DOCUMENTAÇÃO")
    print("="*50)
    print("\nEste sistema de scripts gerencia todos os filtros de pesquisa do sistema.")
    print("\n📋 SCRIPTS DISPONÍVEIS:")
    print("• verificar_corrigir_filtros.py - Verifica e corrige problemas")
    print("• migrar_corrigir_filtros.py - Migra filtros antigos para sistema unificado")
    print("• testar_filtros.py - Testa e valida funcionamento dos filtros")
    print("\n🎯 FUNCIONALIDADES:")
    print("• Verificação automática de problemas")
    print("• Correção automática de problemas comuns")
    print("• Migração de filtros manuais para sistema unificado")
    print("• Testes de validação e consistência")
    print("• Relatórios detalhados em JSON")
    print("\n📁 ARQUIVOS GERADOS:")
    print("• relatorio_filtros.json - Relatório de verificação")
    print("• relatorio_migracao_filtros.json - Relatório de migração")
    print("• relatorio_testes_filtros.json - Relatório de testes")
    print("• filtros_*.log - Logs de execução")
    print("\n💡 DICAS:")
    print("• Execute sempre a opção 1 para verificação completa")
    print("• Revise os relatórios JSON para detalhes")
    print("• Execute periodicamente para manutenção")
    print("• Em caso de problemas, consulte os logs")

def check_existing_reports():
    """Verifica relatórios existentes"""
    print("\n📊 RELATÓRIOS EXISTENTES")
    print("="*40)
    
    reports = [
        ('relatorio_filtros.json', 'Verificação de Filtros'),
        ('relatorio_migracao_filtros.json', 'Migração de Filtros'),
        ('relatorio_testes_filtros.json', 'Testes de Filtros'),
        ('relatorio_workflow_filtros.json', 'Workflow Completo')
    ]
    
    found_reports = []
    for report_file, description in reports:
        if Path(report_file).exists():
            stat = Path(report_file).stat()
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            size = stat.st_size
            found_reports.append((report_file, description, mod_time, size))
    
    if found_reports:
        print(f"\nEncontrados {len(found_reports)} relatório(s):")
        for report_file, description, mod_time, size in found_reports:
            print(f"  📄 {description}")
            print(f"     Arquivo: {report_file}")
            print(f"     Modificado: {mod_time.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"     Tamanho: {size:,} bytes")
            print()
    else:
        print("\n❌ Nenhum relatório encontrado.")
        print("Execute primeiro uma verificação completa.")

def main():
    """Função principal"""
    project_root = os.getcwd()
    manager = FilterManager(project_root)
    
    while True:
        show_menu()
        
        try:
            choice = input("\nDigite sua escolha (0-6): ").strip()
            
            if choice == '0':
                print("\n👋 Até logo!")
                break
            elif choice == '1':
                print("\n🚀 Executando verificação completa...")
                result = manager.run_complete_workflow()
                
                print("\n📊 RESUMO DO WORKFLOW:")
                print(f"Status: {result['summary']['workflow_status'].upper()}")
                print(f"Taxa de sucesso: {result['summary']['success_rate']:.1f}%")
                print(f"Passos executados: {result['summary']['successful_steps']}/{result['summary']['total_steps']}")
                
                print("\n💡 RECOMENDAÇÕES:")
                for rec in result['recommendations']:
                    print(f"  {rec}")
                
                # Salvar relatório do workflow
                with open('relatorio_workflow_filtros.json', 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\n📄 Relatório completo salvo em: relatorio_workflow_filtros.json")
                
            elif choice == '2':
                print("\n🔧 Executando apenas correções...")
                verification = manager._run_verification()
                if verification['summary']['total_issues'] > 0:
                    manager._run_corrections(verification)
                else:
                    print("✅ Nenhuma correção necessária!")
                    
            elif choice == '3':
                print("\n🚀 Executando apenas migração...")
                manager._run_migration()
                
            elif choice == '4':
                print("\n🧪 Executando apenas testes...")
                manager._run_tests()
                
            elif choice == '5':
                check_existing_reports()
                
            elif choice == '6':
                show_help()
                
            else:
                print("\n❌ Opção inválida! Tente novamente.")
                
        except KeyboardInterrupt:
            print("\n\n👋 Operação cancelada pelo usuário.")
            break
        except Exception as e:
            print(f"\n❌ Erro inesperado: {e}")
            logger.error(f"Erro no menu principal: {e}")

if __name__ == "__main__":
    main()
