from django.core.management.base import BaseCommand
from django.db import transaction
from meuprojeto.empresa.models_stock import CategoriaProduto, Item
from decimal import Decimal


class Command(BaseCommand):
    help = 'Cria categorias e serviços de exemplo para demonstração - Carpintaria e Serralharia'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Criando exemplos de categorias e servicos de Carpintaria e Serralharia...\n'))
        
        with transaction.atomic():
            # ============================================================
            # CATEGORIAS PRINCIPAIS
            # ============================================================
            
            # 1. Carpintaria
            cat_carpintaria, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_CARPINTARIA',
                defaults={
                    'nome': 'Carpintaria',
                    'tipo': 'SERVICO',
                    'descricao': 'Serviços de carpintaria e trabalhos em madeira',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] Categoria criada: {cat_carpintaria.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'[INFO] Categoria ja existe: {cat_carpintaria.nome}'))
            
            # 2. Serralharia
            cat_serralharia, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_SERRALHARIA',
                defaults={
                    'nome': 'Serralharia',
                    'tipo': 'SERVICO',
                    'descricao': 'Serviços de serralharia e trabalhos em metal',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] Categoria criada: {cat_serralharia.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'[INFO]  Categoria já existe: {cat_serralharia.nome}'))
            
            # 3. Instalação e Montagem
            cat_instalacao, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_INSTALACAO',
                defaults={
                    'nome': 'Instalação e Montagem',
                    'tipo': 'SERVICO',
                    'descricao': 'Instalação e montagem de produtos de carpintaria e serralharia',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] Categoria criada: {cat_instalacao.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'[INFO]  Categoria já existe: {cat_instalacao.nome}'))
            
            # 4. Manutenção e Reparação
            cat_manutencao, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_MANUTENCAO',
                defaults={
                    'nome': 'Manutenção e Reparação',
                    'tipo': 'SERVICO',
                    'descricao': 'Manutenção e reparação de produtos de carpintaria e serralharia',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] Categoria criada: {cat_manutencao.nome}'))
            else:
                self.stdout.write(self.style.WARNING(f'[INFO]  Categoria já existe: {cat_manutencao.nome}'))
            
            # ============================================================
            # SUBCATEGORIAS
            # ============================================================
            
            # Subcategorias de Carpintaria
            sub_carp_movelaria, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_CARP_MOVELARIA',
                defaults={
                    'nome': 'Móveis e Mobiliário',
                    'tipo': 'SERVICO',
                    'categoria_pai': cat_carpintaria,
                    'descricao': 'Fabricação de móveis e mobiliário em madeira',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Subcategoria criada: {sub_carp_movelaria.nome}'))
            
            sub_carp_portas_janelas, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_CARP_PORTAS',
                defaults={
                    'nome': 'Portas e Janelas',
                    'tipo': 'SERVICO',
                    'categoria_pai': cat_carpintaria,
                    'descricao': 'Fabricação e instalação de portas e janelas em madeira',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Subcategoria criada: {sub_carp_portas_janelas.nome}'))
            
            sub_carp_estruturas, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_CARP_ESTRUTURAS',
                defaults={
                    'nome': 'Estruturas em Madeira',
                    'tipo': 'SERVICO',
                    'categoria_pai': cat_carpintaria,
                    'descricao': 'Construção de estruturas e coberturas em madeira',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Subcategoria criada: {sub_carp_estruturas.nome}'))
            
            # Subcategorias de Serralharia
            sub_serr_portoes, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_SERR_PORTOES',
                defaults={
                    'nome': 'Portões e Grades',
                    'tipo': 'SERVICO',
                    'categoria_pai': cat_serralharia,
                    'descricao': 'Fabricação e instalação de portões e grades metálicas',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Subcategoria criada: {sub_serr_portoes.nome}'))
            
            sub_serr_estruturas, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_SERR_ESTRUTURAS',
                defaults={
                    'nome': 'Estruturas Metálicas',
                    'tipo': 'SERVICO',
                    'categoria_pai': cat_serralharia,
                    'descricao': 'Fabricação e montagem de estruturas metálicas',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Subcategoria criada: {sub_serr_estruturas.nome}'))
            
            sub_serr_acessorios, created = CategoriaProduto.objects.get_or_create(
                codigo='SERV_SERR_ACESSORIOS',
                defaults={
                    'nome': 'Acessórios e Ferragens',
                    'tipo': 'SERVICO',
                    'categoria_pai': cat_serralharia,
                    'descricao': 'Fabricação de acessórios e ferragens metálicas',
                    'ativa': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Subcategoria criada: {sub_serr_acessorios.nome}'))
            
            # ============================================================
            # SERVIÇOS DE EXEMPLO
            # ============================================================
            
            self.stdout.write(self.style.SUCCESS('\n Criando serviços de exemplo...\n'))
            
            # Serviços de Carpintaria (valores em Meticais - MZN)
            servicos_exemplo = [
                # Carpintaria - Móveis
                {
                    'nome': 'Armário de Cozinha',
                    'codigo': 'SERV-CARP-ARM-001',
                    'categoria': sub_carp_movelaria,
                    'descricao': 'Fabricação de armário de cozinha em madeira maciça com portas e gavetas',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('12000.00'),  # MT 12.000
                    'preco_venda': Decimal('35000.00'),  # MT 35.000
                },
                {
                    'nome': 'Mesa de Jantar',
                    'codigo': 'SERV-CARP-MESA-001',
                    'categoria': sub_carp_movelaria,
                    'descricao': 'Fabricação de mesa de jantar em madeira maciça com 6 lugares',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('15000.00'),  # MT 15.000
                    'preco_venda': Decimal('45000.00'),  # MT 45.000
                },
                {
                    'nome': 'Cama de Casal',
                    'codigo': 'SERV-CARP-CAMA-001',
                    'categoria': sub_carp_movelaria,
                    'descricao': 'Fabricação de cama de casal em madeira maciça com cabeceira',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('18000.00'),  # MT 18.000
                    'preco_venda': Decimal('55000.00'),  # MT 55.000
                },
                {
                    'nome': 'Estante de Livros',
                    'codigo': 'SERV-CARP-EST-001',
                    'categoria': sub_carp_movelaria,
                    'descricao': 'Fabricação de estante de livros em madeira com 5 prateleiras',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('8000.00'),  # MT 8.000
                    'preco_venda': Decimal('25000.00'),  # MT 25.000
                },
                # Carpintaria - Portas e Janelas
                {
                    'nome': 'Porta de Entrada',
                    'codigo': 'SERV-CARP-PORT-001',
                    'categoria': sub_carp_portas_janelas,
                    'descricao': 'Fabricação e instalação de porta de entrada em madeira maciça',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('20000.00'),  # MT 20.000
                    'preco_venda': Decimal('60000.00'),  # MT 60.000
                },
                {
                    'nome': 'Janela de Correr',
                    'codigo': 'SERV-CARP-JAN-001',
                    'categoria': sub_carp_portas_janelas,
                    'descricao': 'Fabricação e instalação de janela de correr em madeira',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('12000.00'),  # MT 12.000
                    'preco_venda': Decimal('35000.00'),  # MT 35.000
                },
                {
                    'nome': 'Porta de Interior',
                    'codigo': 'SERV-CARP-PORT-INT-001',
                    'categoria': sub_carp_portas_janelas,
                    'descricao': 'Fabricação e instalação de porta de interior em madeira',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('8000.00'),  # MT 8.000
                    'preco_venda': Decimal('25000.00'),  # MT 25.000
                },
                # Carpintaria - Estruturas
                {
                    'nome': 'Cobertura de Madeira',
                    'codigo': 'SERV-CARP-COB-001',
                    'categoria': sub_carp_estruturas,
                    'descricao': 'Construção de cobertura em madeira para varanda ou área externa',
                    'unidade_medida': 'M2',
                    'preco_custo': Decimal('5000.00'),  # MT 5.000/m²
                    'preco_venda': Decimal('15000.00'),  # MT 15.000/m²
                },
                {
                    'nome': 'Viga de Madeira',
                    'codigo': 'SERV-CARP-VIGA-001',
                    'categoria': sub_carp_estruturas,
                    'descricao': 'Fabricação de viga estrutural em madeira tratada',
                    'unidade_medida': 'M',
                    'preco_custo': Decimal('3000.00'),  # MT 3.000/m
                    'preco_venda': Decimal('8000.00'),  # MT 8.000/m
                },
                # Serralharia - Portões e Grades
                {
                    'nome': 'Portão de Entrada',
                    'codigo': 'SERV-SERR-PORT-001',
                    'categoria': sub_serr_portoes,
                    'descricao': 'Fabricação e instalação de portão de entrada em ferro',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('25000.00'),  # MT 25.000
                    'preco_venda': Decimal('75000.00'),  # MT 75.000
                },
                {
                    'nome': 'Grade de Proteção',
                    'codigo': 'SERV-SERR-GRADE-001',
                    'categoria': sub_serr_portoes,
                    'descricao': 'Fabricação e instalação de grade de proteção para janelas',
                    'unidade_medida': 'M2',
                    'preco_custo': Decimal('4000.00'),  # MT 4.000/m²
                    'preco_venda': Decimal('12000.00'),  # MT 12.000/m²
                },
                {
                    'nome': 'Portão Automático',
                    'codigo': 'SERV-SERR-PORT-AUTO-001',
                    'categoria': sub_serr_portoes,
                    'descricao': 'Fabricação e instalação de portão automático com motor',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('45000.00'),  # MT 45.000
                    'preco_venda': Decimal('150000.00'),  # MT 150.000
                },
                # Serralharia - Estruturas Metálicas
                {
                    'nome': 'Estrutura Metálica para Telhado',
                    'codigo': 'SERV-SERR-EST-TEL-001',
                    'categoria': sub_serr_estruturas,
                    'descricao': 'Fabricação e montagem de estrutura metálica para telhado',
                    'unidade_medida': 'M2',
                    'preco_custo': Decimal('6000.00'),  # MT 6.000/m²
                    'preco_venda': Decimal('18000.00'),  # MT 18.000/m²
                },
                {
                    'nome': 'Escada Metálica',
                    'codigo': 'SERV-SERR-ESC-001',
                    'categoria': sub_serr_estruturas,
                    'descricao': 'Fabricação e instalação de escada metálica interna ou externa',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('20000.00'),  # MT 20.000
                    'preco_venda': Decimal('60000.00'),  # MT 60.000
                },
                {
                    'nome': 'Mezanino Metálico',
                    'codigo': 'SERV-SERR-MEZ-001',
                    'categoria': sub_serr_estruturas,
                    'descricao': 'Fabricação e montagem de mezanino metálico',
                    'unidade_medida': 'M2',
                    'preco_custo': Decimal('8000.00'),  # MT 8.000/m²
                    'preco_venda': Decimal('25000.00'),  # MT 25.000/m²
                },
                # Serralharia - Acessórios
                {
                    'nome': 'Corrimão Metálico',
                    'codigo': 'SERV-SERR-CORR-001',
                    'categoria': sub_serr_acessorios,
                    'descricao': 'Fabricação e instalação de corrimão metálico para escadas',
                    'unidade_medida': 'M',
                    'preco_custo': Decimal('2500.00'),  # MT 2.500/m
                    'preco_venda': Decimal('8000.00'),  # MT 8.000/m
                },
                {
                    'nome': 'Portão de Ferro Artístico',
                    'codigo': 'SERV-SERR-ART-001',
                    'categoria': sub_serr_acessorios,
                    'descricao': 'Fabricação de portão de ferro com desenho artístico personalizado',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('35000.00'),  # MT 35.000
                    'preco_venda': Decimal('120000.00'),  # MT 120.000
                },
                # Instalação e Montagem
                {
                    'nome': 'Instalação de Porta',
                    'codigo': 'SERV-INST-PORT-001',
                    'categoria': cat_instalacao,
                    'descricao': 'Instalação de porta de madeira ou metal (mão de obra)',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('2000.00'),  # MT 2.000
                    'preco_venda': Decimal('6000.00'),  # MT 6.000
                },
                {
                    'nome': 'Montagem de Móvel',
                    'codigo': 'SERV-INST-MOV-001',
                    'categoria': cat_instalacao,
                    'descricao': 'Montagem e instalação de móvel de madeira no local',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('3000.00'),  # MT 3.000
                    'preco_venda': Decimal('8000.00'),  # MT 8.000
                },
                # Manutenção e Reparação
                {
                    'nome': 'Reparação de Porta',
                    'codigo': 'SERV-MAN-PORT-001',
                    'categoria': cat_manutencao,
                    'descricao': 'Reparação e ajuste de porta de madeira ou metal',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('2500.00'),  # MT 2.500
                    'preco_venda': Decimal('7000.00'),  # MT 7.000
                },
                {
                    'nome': 'Manutenção de Portão',
                    'codigo': 'SERV-MAN-PORTAO-001',
                    'categoria': cat_manutencao,
                    'descricao': 'Manutenção preventiva e reparação de portão metálico',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('3000.00'),  # MT 3.000
                    'preco_venda': Decimal('9000.00'),  # MT 9.000
                },
                {
                    'nome': 'Restauração de Móvel',
                    'codigo': 'SERV-MAN-REST-001',
                    'categoria': cat_manutencao,
                    'descricao': 'Restauração completa de móvel antigo em madeira',
                    'unidade_medida': 'UN',
                    'preco_custo': Decimal('5000.00'),  # MT 5.000
                    'preco_venda': Decimal('15000.00'),  # MT 15.000
                },
            ]
            
            servicos_criados = 0
            servicos_existentes = 0
            
            for servico_data in servicos_exemplo:
                servico, created = Item.objects.get_or_create(
                    codigo=servico_data['codigo'],
                    defaults={
                        'nome': servico_data['nome'],
                        'descricao': servico_data['descricao'],
                        'categoria': servico_data['categoria'],
                        'tipo': 'PRODUTO',
                        'produto_tipo': 'SERVICO',
                        'unidade_medida': servico_data['unidade_medida'],
                        'preco_custo': servico_data['preco_custo'],
                        'preco_venda': servico_data['preco_venda'],
                        'estoque_minimo': 0,
                        'estoque_maximo': 0,
                        'status': 'ATIVO',
                    }
                )
                
                if created:
                    servicos_criados += 1
                    self.stdout.write(self.style.SUCCESS(f'  [OK] Servico criado: {servico.nome}'))
                else:
                    # Atualizar valores para Meticais se ja existir
                    servico.preco_custo = servico_data['preco_custo']
                    servico.preco_venda = servico_data['preco_venda']
                    servico.descricao = servico_data['descricao']
                    servico.categoria = servico_data['categoria']
                    servico.save()
                    servicos_existentes += 1
                    self.stdout.write(self.style.WARNING(f'  [INFO] Servico atualizado: {servico.nome}'))
            
            # ============================================================
            # RESUMO
            # ============================================================
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS(' RESUMO'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS(f'\n[OK] Categorias principais: 4'))
            self.stdout.write(self.style.SUCCESS(f'[OK] Subcategorias: 6'))
            self.stdout.write(self.style.SUCCESS(f'[OK] Servicos criados: {servicos_criados}'))
            if servicos_existentes > 0:
                self.stdout.write(self.style.WARNING(f'[INFO] Servicos atualizados: {servicos_existentes}'))
            self.stdout.write(self.style.SUCCESS('\n Exemplos criados/atualizados com sucesso!'))
            self.stdout.write(self.style.SUCCESS('\nNOTA: Todos os precos estao em Meticais (MZN)'))
            self.stdout.write(self.style.SUCCESS('\n-> Acesse /producao/servicos/ para ver os servicos'))
            self.stdout.write(self.style.SUCCESS('-> Acesse /producao/servicos/categorias/ para ver as categorias\n'))
