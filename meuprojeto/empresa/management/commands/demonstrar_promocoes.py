from django.core.management.base import BaseCommand
from meuprojeto.empresa.models_rh import Funcionario, Promocao, Cargo
from datetime import date
from decimal import Decimal


class Command(BaseCommand):
    help = 'Demonstra o sistema de promoções e aumentos'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== SISTEMA DE PROMOÇÕES E AUMENTOS ==='))
        
        # Verificar se há funcionários
        funcionarios = Funcionario.objects.filter(status='AT')
        if not funcionarios.exists():
            self.stdout.write(self.style.ERROR('Nenhum funcionário ativo encontrado'))
            return
        
        funcionario = funcionarios.first()
        self.stdout.write(f'\nFuncionário de exemplo: {funcionario.nome_completo}')
        self.stdout.write(f'Salário atual: {funcionario.salario_atual} MT')
        
        # Verificar se há cargos
        cargos = Cargo.objects.filter(ativo=True)
        if not cargos.exists():
            self.stdout.write(self.style.ERROR('Nenhum cargo ativo encontrado'))
            return
        
        cargo_atual = funcionario.cargo
        cargo_novo = cargos.exclude(id=cargo_atual.id).first() if cargo_atual else cargos.first()
        
        self.stdout.write(f'Cargo atual: {cargo_atual.nome if cargo_atual else "N/A"}')
        if cargo_novo:
            self.stdout.write(f'Cargo disponível para promoção: {cargo_novo.nome}')
        
        # Criar exemplo de promoção
        self.stdout.write('\n=== CRIANDO EXEMPLO DE PROMOÇÃO ===')
        
        promocao = Promocao.objects.create(
            funcionario=funcionario,
            tipo='PROMOCAO',
            salario_anterior=funcionario.salario_atual,
            salario_novo=funcionario.salario_atual * Decimal('1.2'),  # 20% de aumento
            cargo_anterior=cargo_atual,
            cargo_novo=cargo_novo,
            motivo='Excelente desempenho e resultados excepcionais',
            justificativa='Funcionário demonstrou competências excepcionais, liderança e contribuições significativas para o sucesso da empresa.',
            observacoes='Promoção recomendada pela equipe de gestão',
            data_solicitacao=date.today()
        )
        
        self.stdout.write(f'✅ Promoção criada: ID {promocao.id}')
        self.stdout.write(f'   Tipo: {promocao.get_tipo_display()}')
        self.stdout.write(f'   Status: {promocao.get_status_display()}')
        self.stdout.write(f'   Aumento: {promocao.valor_aumento} MT ({promocao.percentual_aumento}%)')
        
        # Demonstrar fluxo de aprovação
        self.stdout.write('\n=== FLUXO DE APROVAÇÃO ===')
        
        # Aprovar promoção
        if promocao.pode_aprovar:
            # Simular aprovação sem usuário
            promocao.status = 'APROVADO'
            promocao.data_aprovacao = date.today()
            promocao.save()
            self.stdout.write('✅ Promoção aprovada')
            self.stdout.write(f'   Status: {promocao.get_status_display()}')
            self.stdout.write(f'   Data de aprovação: {promocao.data_aprovacao}')
        
        # Implementar promoção
        if promocao.pode_implementar:
            if promocao.implementar():
                self.stdout.write('✅ Promoção implementada')
                self.stdout.write(f'   Status: {promocao.get_status_display()}')
                self.stdout.write(f'   Data de implementação: {promocao.data_implementacao}')
                
                # Verificar se o salário foi atualizado
                funcionario.refresh_from_db()
                self.stdout.write(f'   Novo salário do funcionário: {funcionario.salario_atual} MT')
            else:
                self.stdout.write('❌ Erro ao implementar promoção')
        
        # Demonstrar funcionalidades
        self.stdout.write('\n=== FUNCIONALIDADES DISPONÍVEIS ===')
        self.stdout.write('📊 Gestão completa de promoções e aumentos')
        self.stdout.write('🔄 Fluxo de aprovação (Pendente → Aprovado → Implementado)')
        self.stdout.write('📈 Cálculo automático de percentuais e valores')
        self.stdout.write('👔 Suporte a promoções de cargo')
        self.stdout.write('📝 Justificativas e motivações detalhadas')
        self.stdout.write('⏰ Controle de datas e prazos')
        self.stdout.write('👥 Rastreamento de aprovações')
        self.stdout.write('📋 Relatórios e estatísticas')
        self.stdout.write('🔍 Filtros e busca avançada')
        
        # Estatísticas
        total_promocoes = Promocao.objects.count()
        pendentes = Promocao.objects.filter(status='PENDENTE').count()
        aprovadas = Promocao.objects.filter(status='APROVADO').count()
        implementadas = Promocao.objects.filter(status='IMPLEMENTADO').count()
        
        self.stdout.write('\n=== ESTATÍSTICAS ===')
        self.stdout.write(f'Total de promoções: {total_promocoes}')
        self.stdout.write(f'Pendentes: {pendentes}')
        self.stdout.write(f'Aprovadas: {aprovadas}')
        self.stdout.write(f'Implementadas: {implementadas}')
        
        self.stdout.write(self.style.SUCCESS('\n🎉 SISTEMA DE PROMOÇÕES IMPLEMENTADO COM SUCESSO!'))
        self.stdout.write('Acesse: http://localhost:8000/rh/promocoes/')
