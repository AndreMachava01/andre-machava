from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User

from .models_base import DadosEmpresa, Sucursal

class CategoriaProduto(models.Model):
    """Categorias de produtos e materiais para organização"""
    TIPO_CHOICES = [
        ('PRODUTO', 'Produto'),
        ('MATERIAL', 'Material'),
        ('SERVICO', 'Serviço'),
        ('AMBOS', 'Produto e Material'),
        ('TODOS', 'Todos (Produto, Material e Serviço)'),
    ]
    
    nome = models.CharField(
        max_length=100,
        help_text='Nome da categoria'
    )
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da categoria'
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default='AMBOS',
        help_text='Tipo de categoria (Produto, Material ou Ambos)'
    )
    descricao = models.TextField(
        blank=True,
        help_text='Descrição da categoria'
    )
    categoria_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategorias',
        help_text='Categoria pai (para hierarquia)'
    )
    ativa = models.BooleanField(
        default=True,
        help_text='Indica se a categoria está ativa'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de criação da categoria'
    )

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"
    
    def get_tipo_display_color(self):
        """Retorna cor para exibição do tipo"""
        colors = {
            'PRODUTO': 'success',
            'MATERIAL': 'info',
            'SERVICO': 'warning',
            'AMBOS': 'primary',
            'TODOS': 'dark',
        }
        return colors.get(self.tipo, 'light')
    
    def pode_usar_para_produtos(self):
        """Verifica se a categoria pode ser usada para produtos"""
        return self.tipo in ['PRODUTO', 'AMBOS', 'TODOS']
    
    def pode_usar_para_materiais(self):
        """Verifica se a categoria pode ser usada para materiais"""
        return self.tipo in ['MATERIAL', 'AMBOS', 'TODOS']


class Item(models.Model):
    """Modelo unificado para produtos e materiais"""
    TIPO_CHOICES = [
        ('PRODUTO', 'Produto'),
        ('MATERIAL', 'Material'),
    ]
    
    # Campos específicos de produto
    PRODUTO_TIPO_CHOICES = [
        ('PRODUTO_FINAL', 'Produto Final'),
        ('PRODUTO_COMPRADO', 'Produto Comprado'),
        ('SERVICO', 'Serviço'),
    ]
    
    # Campos específicos de material
    MATERIAL_TIPO_CHOICES = [
        ('MATERIA_PRIMA', 'Matéria-Prima'),
        ('INSUMO', 'Insumo'),
        ('COMPONENTE', 'Componente'),
        ('EMBALAGEM', 'Embalagem'),
        ('ACESSORIO', 'Acessório'),
        ('FERRAMENTA', 'Ferramenta'),
        ('EQUIPAMENTO', 'Equipamento'),
        ('OUTRO', 'Outro'),
    ]
    
    UNIDADE_CHOICES = [
        ('UN', 'Unidade'),
        ('KG', 'Quilograma'),
        ('G', 'Grama'),
        ('L', 'Litro'),
        ('ML', 'Mililitro'),
        ('M', 'Metro'),
        ('CM', 'Centímetro'),
        ('M2', 'Metro Quadrado'),
        ('M3', 'Metro Cúbico'),
        ('CX', 'Caixa'),
        ('PC', 'Peça'),
        ('DZ', 'Dúzia'),
        ('GR', 'Grosa'),
        ('ROL', 'Rolo'),
        ('FOL', 'Folha'),
        ('BAR', 'Barra'),
        ('TUB', 'Tubo'),
    ]

    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
        ('ESGOTADO', 'Esgotado'),
        ('DESCONTINUADO', 'Descontinuado'),
    ]

    # Campos principais
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        help_text='Tipo do item (Produto ou Material)'
    )
    nome = models.CharField(
        max_length=200,
        help_text='Nome do item'
    )
    codigo = models.CharField(
        max_length=50,
        unique=True,
        help_text='Código único do item'
    )
    codigo_barras = models.CharField(
        max_length=50,
        blank=True,
        help_text='Código de barras do item'
    )
    descricao = models.TextField(
        blank=True,
        help_text='Descrição detalhada do item'
    )
    categoria = models.ForeignKey(
        CategoriaProduto,
        on_delete=models.PROTECT,
        related_name='itens',
        help_text='Categoria do item'
    )
    unidade_medida = models.CharField(
        max_length=10,
        choices=UNIDADE_CHOICES,
        default='UN',
        help_text='Unidade de medida do item'
    )
    preco_custo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Preço de custo do item'
    )
    estoque_minimo = models.PositiveIntegerField(
        default=0,
        help_text='Quantidade mínima em estoque'
    )
    estoque_maximo = models.PositiveIntegerField(
        default=0,
        help_text='Quantidade máxima em estoque'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ATIVO',
        help_text='Status do item'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de cadastro do item'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        help_text='Data da última atualização'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre o item'
    )
    
    # Campos específicos de produto
    produto_tipo = models.CharField(
        max_length=20,
        choices=PRODUTO_TIPO_CHOICES,
        null=True,
        blank=True,
        help_text='Tipo específico do produto'
    )
    preco_venda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Preço de venda do produto'
    )
    margem_lucro = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Margem de lucro em percentagem'
    )
    
    # Campos específicos de material
    material_tipo = models.CharField(
        max_length=20,
        choices=MATERIAL_TIPO_CHOICES,
        null=True,
        blank=True,
        help_text='Tipo específico do material'
    )
    
    # Fornecedor principal
    fornecedor_principal = models.ForeignKey(
        'Fornecedor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='itens_principais',
        help_text='Fornecedor principal do item'
    )

    class Meta:
        verbose_name = 'Item'
        verbose_name_plural = 'Itens'
        ordering = ['nome']

    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.get_tipo_display()})"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        
        # Validações específicas por tipo
        if self.tipo == 'PRODUTO':
            if not self.produto_tipo:
                self.produto_tipo = 'PRODUTO_FINAL'
            if not self.preco_venda:
                self.preco_venda = self.preco_custo
        elif self.tipo == 'MATERIAL':
            if not self.material_tipo:
                self.material_tipo = 'MATERIA_PRIMA'
        
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático para o item"""
        if self.tipo == 'PRODUTO':
            total_produtos = Item.objects.filter(tipo='PRODUTO').count()
            proximo_numero = total_produtos + 1
            return f"PROD{proximo_numero:04d}"
        else:  # MATERIAL
            total_materiais = Item.objects.filter(tipo='MATERIAL').count()
            proximo_numero = total_materiais + 1
            return f"MAT{proximo_numero:04d}"

    def get_tipo_display_color(self):
        """Retorna cor para exibição do tipo"""
        colors = {
            'PRODUTO': 'primary',
            'MATERIAL': 'success',
        }
        return colors.get(self.tipo, 'light')
    
    def get_tipo_especifico_display(self):
        """Retorna o tipo específico do item"""
        if self.tipo == 'PRODUTO':
            return dict(self.PRODUTO_TIPO_CHOICES).get(self.produto_tipo, 'N/A')
        else:
            return dict(self.MATERIAL_TIPO_CHOICES).get(self.material_tipo, 'N/A')
    
    def calcular_margem_lucro(self):
        """Calcula margem de lucro se não definida"""
        if self.tipo == 'PRODUTO' and self.preco_venda and self.preco_custo:
            if not self.margem_lucro:
                margem = ((self.preco_venda - self.preco_custo) / self.preco_custo) * 100
                self.margem_lucro = margem
                self.save(update_fields=['margem_lucro'])
            return self.margem_lucro
        return 0
    
    def pode_usar_para_servicos(self):
        """Verifica se a categoria pode ser usada para serviços"""
        return self.tipo in ['SERVICO', 'TODOS']

class Fornecedor(models.Model):
    """Fornecedores de produtos"""
    TIPO_CHOICES = [
        ('PESSOA_FISICA', 'Pessoa Física'),
        ('PESSOA_JURIDICA', 'Pessoa Jurídica'),
    ]
    
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
        ('SUSPENSO', 'Suspenso'),
    ]

    nome = models.CharField(
        max_length=200,
        help_text='Nome ou razão social do fornecedor'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='PESSOA_JURIDICA',
        help_text='Tipo de fornecedor'
    )
    nuit = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Número de Identificação Única do Trabalhador (NUIT)'
    )
    email = models.EmailField(
        blank=True,
        help_text='Email de contato'
    )
    telefone = models.CharField(
        max_length=13,
        blank=True,
        help_text='Número de telefone com código do país (+258)'
    )
    website = models.URLField(
        blank=True,
        help_text='Website do fornecedor'
    )
    endereco = models.TextField(
        blank=True,
        help_text='Endereço completo'
    )
    cidade = models.CharField(
        max_length=100,
        blank=True,
        help_text='Cidade'
    )
    provincia = models.CharField(
        max_length=50,
        blank=True,
        help_text='Província'
    )
    codigo_postal = models.CharField(
        max_length=10,
        blank=True,
        help_text='Código postal'
    )
    pais = models.CharField(
        max_length=50,
        default='Moçambique',
        help_text='País'
    )
    limite_credito = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Limite de crédito em MT'
    )
    prazo_pagamento = models.PositiveIntegerField(
        default=0,
        help_text='Prazo de pagamento em dias'
    )
    desconto_padrao = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Desconto padrão em percentagem'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ATIVO',
        help_text='Status do fornecedor'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o fornecedor está ativo'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de cadastro do fornecedor'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre o fornecedor'
    )

    class Meta:
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome']

    def __str__(self):
        return self.nome

# MODELO PRODUTO REMOVIDO - DADOS MIGRADOS PARA MODELO ITEM UNIFICADO

# MODELO MATERIAL REMOVIDO - DADOS MIGRADOS PARA MODELO ITEM UNIFICADO

class Receita(models.Model):
    """Receitas para produção de produtos usando materiais"""
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
        ('TESTE', 'Em Teste'),
        ('APROVADA', 'Aprovada'),
        ('REJEITADA', 'Rejeitada'),
    ]

    produto = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='receitas',
        help_text='Produto que será produzido'
    )
    nome = models.CharField(
        max_length=200,
        help_text='Nome da receita'
    )
    codigo = models.CharField(
        max_length=50,
        unique=True,
        help_text='Código único da receita'
    )
    descricao = models.TextField(
        blank=True,
        help_text='Descrição da receita'
    )
    versao = models.CharField(
        max_length=10,
        default='1.0',
        help_text='Versão da receita'
    )
    rendimento = models.PositiveIntegerField(
        default=1,
        help_text='Quantidade de produtos produzidos por lote'
    )
    unidade_rendimento = models.CharField(
        max_length=20,
        default='UN',
        help_text='Unidade de medida do rendimento'
    )
    tempo_producao_horas = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Tempo de produção em horas'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ATIVA',
        help_text='Status da receita'
    )
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de criação da receita'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        help_text='Data da última atualização'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a receita'
    )

    class Meta:
        verbose_name = 'Receita'
        verbose_name_plural = 'Receitas'
        ordering = ['produto__nome', 'nome']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático baseado no produto e sequência"""
        # Prefixo baseado no produto
        if self.produto:
            # Usa as primeiras letras do nome do produto
            nome_produto = self.produto.nome.replace(' ', '').upper()
            prefixo = nome_produto[:3] if len(nome_produto) >= 3 else nome_produto
        else:
            prefixo = 'REC'
        
        # Conta receitas existentes com o mesmo prefixo
        ultimo_numero = Receita.objects.filter(
            codigo__startswith=prefixo
        ).count()
        
        # Gera próximo número
        proximo_numero = ultimo_numero + 1
        
        # Formato: ABC001, XYZ001, etc.
        return f"{prefixo}{proximo_numero:03d}"

    def calcular_custo_total(self):
        """Calcula o custo total da receita"""
        total = Decimal('0.00')
        for item in self.itens.all():
            total += item.calcular_custo_item()
        return total

    def calcular_custo_por_produto(self):
        """Calcula o custo por unidade do produto"""
        if self.rendimento > 0:
            return self.calcular_custo_total() / Decimal(str(self.rendimento))
        return Decimal('0.00')

class ItemReceita(models.Model):
    """Itens (materiais) que compõem uma receita"""
    receita = models.ForeignKey(
        Receita,
        on_delete=models.CASCADE,
        related_name='itens',
        help_text='Receita'
    )
    material = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='receitas_utilizadas',
        help_text='Material utilizado'
    )
    quantidade = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Quantidade do material necessária'
    )
    unidade_medida = models.CharField(
        max_length=10,
        choices=Item.UNIDADE_CHOICES,
        help_text='Unidade de medida'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre este item'
    )

    class Meta:
        verbose_name = 'Item da Receita'
        verbose_name_plural = 'Itens da Receita'
        unique_together = ['receita', 'material']

    def __str__(self):
        return f"{self.receita.nome} - {self.material.nome}"

    def calcular_custo_item(self):
        """Calcula o custo deste item da receita"""
        return self.quantidade * self.material.preco_custo

class StockMaterial(models.Model):
    """Stock de materiais por sucursal"""
    material = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='stocks_material_antigo',
        help_text='Material'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='stocks_materiais',
        help_text='Sucursal'
    )
    quantidade_atual = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text='Quantidade atual em estoque'
    )
    quantidade_reservada = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text='Quantidade reservada para produção'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        help_text='Data da última atualização'
    )

    class Meta:
        verbose_name = 'Stock de Material'
        verbose_name_plural = 'Stocks de Materiais'
        unique_together = ['material', 'sucursal']

    def __str__(self):
        return f"{self.material.nome} - {self.sucursal.nome}"

    def quantidade_disponivel(self):
        """Retorna a quantidade disponível para uso"""
        return self.quantidade_atual - self.quantidade_reservada


class StockItem(models.Model):
    """Estoque unificado para produtos e materiais por sucursal"""
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='stocks_sucursais',
        help_text='Item (produto ou material)'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='stocks_item',
        help_text='Sucursal'
    )
    quantidade_atual = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text='Quantidade atual em estoque'
    )
    quantidade_reservada = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text='Quantidade reservada (não disponível)'
    )
    localizacao = models.CharField(
        max_length=100,
        blank=True,
        help_text='Localização física do item na sucursal'
    )
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        help_text='Data da última atualização do estoque'
    )

    class Meta:
        verbose_name = 'Stock de Item'
        verbose_name_plural = 'Stocks de Itens'
        unique_together = ['item', 'sucursal']
        ordering = ['item__nome']
        indexes = [
            models.Index(fields=['item', 'sucursal']),
            models.Index(fields=['quantidade_atual']),
            models.Index(fields=['data_atualizacao']),
            models.Index(fields=['item', 'quantidade_atual']),
        ]

    def __str__(self):
        return f"{self.item.nome} - {self.sucursal.nome} ({self.quantidade_atual})"

    @property
    def quantidade_disponivel(self):
        """Quantidade disponível para uso"""
        return self.quantidade_atual - self.quantidade_reservada

    @property
    def status_estoque(self):
        """Status do estoque baseado na quantidade mínima"""
        if self.quantidade_atual <= self.item.estoque_minimo:
            return 'BAIXO'
        elif self.quantidade_atual >= self.item.estoque_maximo:
            return 'ALTO'
        else:
            return 'NORMAL'


# StockSucursal removido - dados migrados para StockItem (modelo unificado)

class TipoMovimentoStock(models.Model):
    """Tipos de movimentação de stock"""
    nome = models.CharField(
        max_length=100,
        help_text='Nome do tipo de movimento'
    )
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único do tipo de movimento'
    )
    descricao = models.TextField(
        blank=True,
        help_text='Descrição do tipo de movimento'
    )
    aumenta_estoque = models.BooleanField(
        default=True,
        help_text='Indica se este tipo de movimento aumenta o estoque'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o tipo de movimento está ativo'
    )

    class Meta:
        verbose_name = 'Tipo de Movimento de Stock'
        verbose_name_plural = 'Tipos de Movimento de Stock'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class MovimentoItem(models.Model):
    """Movimentações unificadas de stock para produtos e materiais"""
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da movimentação'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='movimentos',
        help_text='Item movimentado (produto ou material)'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='movimentos_item',
        help_text='Sucursal onde ocorreu o movimento'
    )
    tipo_movimento = models.ForeignKey(
        TipoMovimentoStock,
        on_delete=models.PROTECT,
        related_name='movimentos_item',
        help_text='Tipo de movimento'
    )
    quantidade = models.PositiveIntegerField(
        help_text='Quantidade movimentada'
    )
    preco_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Preço unitário do item no movimento'
    )
    valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Valor total do movimento'
    )
    data_movimento = models.DateTimeField(
        default=timezone.now,
        help_text='Data e hora do movimento'
    )
    referencia = models.CharField(
        max_length=100,
        blank=True,
        help_text='Referência do movimento (ex: número da nota fiscal)'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre o movimento'
    )
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        help_text='Usuário que registrou o movimento'
    )

    class Meta:
        verbose_name = 'Movimento de Item'
        verbose_name_plural = 'Movimentos de Itens'
        ordering = ['-data_movimento']
        indexes = [
            models.Index(fields=['item', 'sucursal']),
            models.Index(fields=['data_movimento']),
            models.Index(fields=['tipo_movimento']),
            models.Index(fields=['item', 'data_movimento']),
            models.Index(fields=['sucursal', 'data_movimento']),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.item.nome} - {self.tipo_movimento.nome} ({self.quantidade})"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        
        # Calcula valor total automaticamente
        self.valor_total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático para movimentação"""
        total_movimentos = MovimentoItem.objects.count()
        proximo_numero = total_movimentos + 1
        return f"MOV{proximo_numero:04d}"

    def atualizar_stock_sucursal(self):
        """Atualiza o stock da sucursal após o movimento"""
        stock_item, created = StockItem.objects.get_or_create(
            item=self.item,
            sucursal=self.sucursal,
            defaults={'quantidade_atual': 0, 'quantidade_reservada': 0}
        )
        
        if self.tipo_movimento.aumenta_estoque:
            stock_item.quantidade_atual += self.quantidade
        else:
            stock_item.quantidade_atual -= self.quantidade
            # Garantir que não fique negativo
            if stock_item.quantidade_atual < 0:
                stock_item.quantidade_atual = 0
            
        stock_item.save()

class MovimentoStock(models.Model):
    """Movimentações de stock de produtos"""
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da movimentação'
    )
    produto = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='movimentos_stock',
        help_text='Produto movimentado'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='movimentos_stock',
        help_text='Sucursal onde ocorreu o movimento'
    )
    tipo_movimento = models.ForeignKey(
        TipoMovimentoStock,
        on_delete=models.PROTECT,
        related_name='movimentos',
        help_text='Tipo de movimento'
    )
    quantidade = models.PositiveIntegerField(
        help_text='Quantidade movimentada'
    )
    preco_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Preço unitário do produto no movimento'
    )
    valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Valor total do movimento'
    )
    data_movimento = models.DateTimeField(
        default=timezone.now,
        help_text='Data e hora do movimento'
    )
    referencia = models.CharField(
        max_length=100,
        blank=True,
        help_text='Referência do movimento (ex: número da nota fiscal)'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre o movimento'
    )
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        help_text='Usuário que registrou o movimento'
    )

    class Meta:
        verbose_name = 'Movimento de Stock (Produto)'
        verbose_name_plural = 'Movimentos de Stock (Produtos)'
        ordering = ['-data_movimento']

    def __str__(self):
        return f"{self.codigo} - {self.produto.nome} - {self.tipo_movimento.nome} ({self.quantidade})"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        
        # Calcula valor total automaticamente
        self.valor_total = self.quantidade * self.preco_unitario
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático para movimentação de produto"""
        # Contar movimentações existentes (produtos + materiais)
        total_movimentos = MovimentoItem.objects.count()
        proximo_numero = total_movimentos + 1
        return f"MOV{proximo_numero:04d}"


# MovimentoMaterial removido - dados migrados para MovimentoItem (modelo unificado)


class NotificacaoStock(models.Model):
    """Sistema de notificações para eventos importantes do stock"""
    TIPOS_NOTIFICACAO = [
        ('stock_baixo', 'Stock Baixo'),
        ('requisicao_pendente', 'Requisição Pendente'),
        ('movimentacao_sem_usuario', 'Movimentação sem Usuário'),
        ('requisicao_antiga', 'Requisição Antiga'),
        ('sistema', 'Sistema'),
        ('info', 'Informação'),
        ('warning', 'Aviso'),
        ('error', 'Erro'),
    ]
    
    tipo = models.CharField(
        max_length=30,
        choices=TIPOS_NOTIFICACAO,
        help_text='Tipo da notificação'
    )
    titulo = models.CharField(
        max_length=200,
        help_text='Título da notificação'
    )
    mensagem = models.TextField(
        help_text='Mensagem detalhada'
    )
    url = models.URLField(
        blank=True,
        help_text='URL para ação relacionada'
    )
    usuario_destinatario = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Usuário destinatário (null = todos)'
    )
    lida = models.BooleanField(
        default=False,
        help_text='Se a notificação foi lida'
    )
    data_criacao = models.DateTimeField(
        default=timezone.now,
        help_text='Data de criação da notificação'
    )
    data_leitura = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data em que foi lida'
    )
    prioridade = models.IntegerField(
        default=1,
        help_text='Prioridade (1=baixa, 2=média, 3=alta, 4=crítica)'
    )
    dados_extras = models.JSONField(
        default=dict,
        blank=True,
        help_text='Dados adicionais em formato JSON'
    )

    class Meta:
        verbose_name = 'Notificação de Stock'
        verbose_name_plural = 'Notificações de Stock'
        ordering = ['-prioridade', '-data_criacao']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo}"

    def marcar_como_lida(self, usuario=None):
        """Marcar notificação como lida"""
        self.lida = True
        self.data_leitura = timezone.now()
        self.save()

    @classmethod
    def criar_notificacao(cls, tipo, titulo, mensagem, url='', usuario_destinatario=None, prioridade=1, dados_extras=None):
        """Criar uma nova notificação"""
        return cls.objects.create(
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            url=url,
            usuario_destinatario=usuario_destinatario,
            prioridade=prioridade,
            dados_extras=dados_extras or {}
        )

    @classmethod
    def obter_notificacoes_nao_lidas(cls, usuario=None):
        """Obter notificações não lidas para um usuário"""
        queryset = cls.objects.filter(lida=False)
        if usuario:
            queryset = queryset.filter(
                models.Q(usuario_destinatario=usuario) | 
                models.Q(usuario_destinatario__isnull=True)
            )
        return queryset.order_by('-prioridade', '-data_criacao')

    @classmethod
    def contar_notificacoes_nao_lidas(cls, usuario=None):
        """Contar notificações não lidas para um usuário"""
        return cls.obter_notificacoes_nao_lidas(usuario).count()


class InventarioFisico(models.Model):
    """Inventário físico - contagem manual de stock"""
    STATUS_CHOICES = [
        ('PLANEJADO', 'Planejado'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('CONCLUIDO', 'Concluído'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único do inventário'
    )
    nome = models.CharField(
        max_length=200,
        help_text='Nome/descrição do inventário'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='inventarios_fisicos',
        help_text='Sucursal onde será realizado o inventário'
    )
    data_inicio = models.DateTimeField(
        help_text='Data e hora de início do inventário'
    )
    data_fim = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora de conclusão do inventário'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PLANEJADO',
        help_text='Status do inventário'
    )
    usuario_responsavel = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='inventarios_responsavel',
        help_text='Usuário responsável pelo inventário'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre o inventário'
    )
    data_criacao = models.DateTimeField(
        default=timezone.now,
        help_text='Data de criação do inventário'
    )
    usuario_criador = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventarios_criados',
        help_text='Usuário que criou o inventário'
    )

    class Meta:
        verbose_name = 'Inventário Físico'
        verbose_name_plural = 'Inventários Físicos'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.sucursal.nome})"

    def gerar_codigo_automatico(self):
        """Gera código automático para inventário"""
        total_inventarios = InventarioFisico.objects.count()
        proximo_numero = total_inventarios + 1
        return f"INV{proximo_numero:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        super().save(*args, **kwargs)

    @property
    def total_itens(self):
        """Total de itens no inventário"""
        return self.itens_inventario.count()

    @property
    def itens_contados(self):
        """Itens já contados"""
        return self.itens_inventario.filter(quantidade_contada__isnull=False).count()

    @property
    def progresso_percentual(self):
        """Progresso do inventário em percentual"""
        if self.total_itens == 0:
            return 0
        return round((self.itens_contados / self.total_itens) * 100, 2)


class ItemInventario(models.Model):
    """Item individual do inventário físico"""
    inventario = models.ForeignKey(
        InventarioFisico,
        on_delete=models.CASCADE,
        related_name='itens_inventario',
        help_text='Inventário ao qual pertence este item'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='itens_inventario',
        help_text='Item sendo inventariado'
    )
    quantidade_sistema = models.PositiveIntegerField(
        help_text='Quantidade registrada no sistema'
    )
    quantidade_contada = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Quantidade contada fisicamente'
    )
    diferenca = models.IntegerField(
        default=0,
        help_text='Diferença entre contado e sistema (contado - sistema)'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a contagem'
    )
    data_contagem = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora da contagem'
    )
    usuario_contador = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Usuário que fez a contagem'
    )
    
    # Campos para controle de múltiplas contagens
    numero_contagem = models.PositiveIntegerField(
        default=0,
        help_text='Número da contagem atual (1, 2 ou 3)'
    )
    precisa_recontagem = models.BooleanField(
        default=False,
        help_text='Indica se o item precisa ser recontado'
    )
    contagem_finalizada = models.BooleanField(
        default=False,
        help_text='Indica se as 3 contagens foram finalizadas'
    )

    class Meta:
        verbose_name = 'Item do Inventário'
        verbose_name_plural = 'Itens do Inventário'
        unique_together = ['inventario', 'item']
        ordering = ['item__nome']

    def __str__(self):
        return f"{self.inventario.codigo} - {self.item.nome}"
    
    @property
    def tem_diferenca(self):
        """Verifica se há diferença entre contado e sistema"""
        if self.quantidade_contada is None:
            return False
        return self.quantidade_contada != self.quantidade_sistema
    
    @property
    def pode_recontar(self):
        """Verifica se pode fazer nova contagem"""
        return self.numero_contagem < 3 and not self.contagem_finalizada


class HistoricoContagem(models.Model):
    """Histórico de todas as contagens realizadas"""
    item_inventario = models.ForeignKey(
        ItemInventario,
        on_delete=models.CASCADE,
        related_name='historico_contagens',
        help_text='Item do inventário'
    )
    numero_contagem = models.PositiveIntegerField(
        help_text='Número da contagem (1, 2 ou 3)'
    )
    quantidade_contada = models.PositiveIntegerField(
        help_text='Quantidade contada nesta contagem'
    )
    diferenca = models.IntegerField(
        help_text='Diferença entre contado e sistema'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações desta contagem'
    )
    data_contagem = models.DateTimeField(
        help_text='Data e hora da contagem'
    )
    usuario_contador = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        help_text='Usuário que fez a contagem'
    )
    
    class Meta:
        verbose_name = 'Histórico de Contagem'
        verbose_name_plural = 'Histórico de Contagens'
        ordering = ['-data_contagem']
    
    def __str__(self):
        return f"{self.item_inventario.item.nome} - Contagem {self.numero_contagem}"
    
    def calcular_diferenca(self):
        """Calcula a diferença entre quantidade contada e sistema"""
        if self.quantidade_contada is not None:
            self.diferenca = self.quantidade_contada - self.item_inventario.quantidade_sistema
        else:
            self.diferenca = 0
        return self.diferenca

    def save(self, *args, **kwargs):
        self.calcular_diferenca()
        super().save(*args, **kwargs)


class AjusteInventario(models.Model):
    """Ajustes de stock baseados em inventário físico"""
    TIPO_AJUSTE_CHOICES = [
        ('INVENTARIO', 'Inventário Físico'),
        ('PERDA', 'Perda'),
        ('DANIFICADO', 'Danificado'),
        ('VENCIDO', 'Vencido'),
        ('OUTROS', 'Outros'),
    ]
    
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único do ajuste'
    )
    inventario = models.ForeignKey(
        InventarioFisico,
        on_delete=models.CASCADE,
        related_name='ajustes',
        null=True,
        blank=True,
        help_text='Inventário que gerou este ajuste'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='ajustes_inventario',
        help_text='Item ajustado'
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name='ajustes_inventario',
        help_text='Sucursal do ajuste'
    )
    tipo_ajuste = models.CharField(
        max_length=20,
        choices=TIPO_AJUSTE_CHOICES,
        default='INVENTARIO',
        help_text='Tipo do ajuste'
    )
    quantidade_anterior = models.PositiveIntegerField(
        help_text='Quantidade antes do ajuste'
    )
    quantidade_nova = models.PositiveIntegerField(
        help_text='Quantidade após o ajuste'
    )
    diferenca = models.IntegerField(
        help_text='Diferença (nova - anterior)'
    )
    motivo = models.TextField(
        help_text='Motivo do ajuste'
    )
    data_ajuste = models.DateTimeField(
        default=timezone.now,
        help_text='Data e hora do ajuste'
    )
    usuario_ajuste = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='ajustes_inventario',
        help_text='Usuário que fez o ajuste'
    )
    aprovado = models.BooleanField(
        default=False,
        help_text='Se o ajuste foi aprovado'
    )
    usuario_aprovacao = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajustes_aprovados',
        help_text='Usuário que aprovou o ajuste'
    )
    data_aprovacao = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data de aprovação'
    )

    class Meta:
        verbose_name = 'Ajuste de Inventário'
        verbose_name_plural = 'Ajustes de Inventário'
        ordering = ['-data_ajuste']

    def __str__(self):
        return f"{self.codigo} - {self.item.nome} ({self.diferenca:+d})"

    def gerar_codigo_automatico(self):
        """Gera código automático para ajuste"""
        total_ajustes = AjusteInventario.objects.count()
        proximo_numero = total_ajustes + 1
        return f"AJUSTE{proximo_numero:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        self.diferenca = self.quantidade_nova - self.quantidade_anterior
        super().save(*args, **kwargs)

    def aplicar_ajuste(self):
        """Aplica o ajuste no stock da sucursal"""
        if not self.aprovado:
            return False
        
        try:
            stock_item, created = StockItem.objects.get_or_create(
                item=self.item,
                sucursal=self.sucursal,
                defaults={'quantidade_atual': 0, 'quantidade_reservada': 0}
            )
            stock_item.quantidade_atual = self.quantidade_nova
            stock_item.save()
            
            # Criar movimento de ajuste
            from .models_stock import MovimentoItem, TipoMovimentoStock
            
            tipo_ajuste, created = TipoMovimentoStock.objects.get_or_create(
                nome='Ajuste de Inventário',
                defaults={
                    'descricao': 'Ajuste baseado em inventário físico',
                    'aumenta_estoque': True
                }
            )
            
            MovimentoItem.objects.create(
                codigo=f"AJ{self.codigo}",
                item=self.item,
                sucursal=self.sucursal,
                tipo_movimento=tipo_ajuste,
                quantidade=abs(self.diferenca),
                preco_unitario=0,  # Ajuste não tem preço
                valor_total=0,
                referencia=self.codigo,
                observacoes=f"Ajuste de inventário: {self.motivo}",
                usuario=self.usuario_ajuste
            )
            
            return True
        except Exception as e:
            print(f"Erro ao aplicar ajuste: {e}")
            return False


class FornecedorProduto(models.Model):
    """Relacionamento entre fornecedores e produtos/materiais"""
    fornecedor = models.ForeignKey(
        Fornecedor,
        on_delete=models.CASCADE,
        related_name='produtos_fornecidos',
        help_text='Fornecedor'
    )
    produto = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='fornecedores_produto',
        help_text='Produto fornecido',
        null=True,
        blank=True
    )
    material = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='fornecedores_material',
        help_text='Material fornecido',
        null=True,
        blank=True
    )
    preco_fornecedor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Preço praticado pelo fornecedor'
    )
    prazo_entrega = models.PositiveIntegerField(
        default=0,
        help_text='Prazo de entrega em dias'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o fornecedor está ativo para este produto'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de cadastro da relação'
    )

    class Meta:
        verbose_name = 'Fornecedor por Produto'
        verbose_name_plural = 'Fornecedores por Produtos'
        unique_together = [
            ['fornecedor', 'produto'],
            ['fornecedor', 'material']
        ]
        ordering = ['fornecedor__nome', 'produto__nome']

    def clean(self):
        """Validação: deve ter produto OU material, não ambos"""
        if not self.produto and not self.material:
            raise ValidationError('Deve especificar um produto ou material.')
        if self.produto and self.material:
            raise ValidationError('Não pode especificar produto e material ao mesmo tempo.')
    
    @property
    def item(self):
        """Retorna o produto ou material associado"""
        return self.produto or self.material
    
    @property
    def tipo_item(self):
        """Retorna o tipo do item: 'Produto' ou 'Material'"""
        return 'Produto' if self.produto else 'Material'

    def __str__(self):
        item_nome = self.produto.nome if self.produto else self.material.nome
        return f"{self.fornecedor.nome} - {item_nome}"


class OrdemCompra(models.Model):
    """Ordens de compra externa"""
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('ENVIADA', 'Enviada'),
        ('APROVADA', 'Aprovada'),
        ('GUARDADA', 'Guardada'),
        ('RECEBIDA', 'Recebida'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    codigo = models.CharField(max_length=20, unique=True, help_text='Código único da ordem')
    numero_cotacao = models.CharField(max_length=50, help_text='Número da cotação do fornecedor')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, help_text='Fornecedor', null=True, blank=True)
    requisicao_origem = models.ForeignKey(
        'RequisicaoCompraExterna', 
        on_delete=models.CASCADE, 
        related_name='ordens_compra',
        help_text='Requisição que originou esta ordem',
        null=True, blank=True
    )
    sucursal_destino = models.ForeignKey(
        Sucursal, 
        on_delete=models.CASCADE, 
        help_text='Sucursal que receberá os produtos'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RASCUNHO')
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_envio = models.DateTimeField(null=True, blank=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(help_text='Observações adicionais')
    criado_por = models.ForeignKey(User, on_delete=models.CASCADE, help_text='Usuário que criou a ordem', null=True, blank=True)
    aprovado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordens_aprovadas')
    
    # Campos externos obrigatórios
    contato_externo = models.CharField(max_length=100, help_text='Nome do contato externo', default='N/A')
    empresa_externa = models.CharField(max_length=100, help_text='Nome da empresa externa', default='N/A')
    email_externo = models.CharField(max_length=100, help_text='Email do contato externo', default='N/A')
    telefone_externo = models.CharField(max_length=20, help_text='Telefone do contato externo', default='N/A')
    tipo = models.CharField(max_length=50, help_text='Tipo da ordem', default='COMPRA_EXTERNA')
    cotacao_aprovada = models.TextField(help_text='Cotação aprovada', default='')
    numero_fatura = models.CharField(max_length=50, help_text='Número da fatura', default='PENDENTE')
    data_cotacao = models.DateTimeField(null=True, blank=True, help_text='Data da cotação')
    data_fatura = models.DateField(null=True, blank=True, help_text='Data da fatura')
    
    class Meta:
        verbose_name = 'Ordem de Compra'
        verbose_name_plural = 'Ordens de Compra'
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.codigo} - {self.fornecedor.nome}"
    
    @property
    def valor_total(self):
        """Calcula o valor total da ordem de compra"""
        return sum(item.preco_total for item in self.itens.all())
    
    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)
    
    def gerar_codigo(self):
        """Gera código único para a ordem de compra"""
        from django.db import transaction
        import time
        
        with transaction.atomic():
            # Buscar o último código existente que segue o padrão COMP####
            ultima_ordem = OrdemCompra.objects.filter(
                codigo__regex=r'^COMP\d{4}$'
            ).order_by('-codigo').first()
            
            if ultima_ordem:
                # Extrair número do último código
                try:
                    ultimo_numero = int(ultima_ordem.codigo[4:])
                    proximo_numero = ultimo_numero + 1
                except (ValueError, IndexError):
                    proximo_numero = 1
            else:
                proximo_numero = 1
            
            # Verificar se o código já existe e incrementar se necessário
            tentativas = 0
            while tentativas < 100:  # Limite de tentativas
                codigo_tentativa = f"COMP{proximo_numero:04d}"
                if not OrdemCompra.objects.filter(codigo=codigo_tentativa).exists():
                    return codigo_tentativa
                proximo_numero += 1
                tentativas += 1
            
            # Se chegou ao limite de tentativas, usar timestamp
            timestamp = int(time.time())
            return f"COMP{timestamp}"
    
    @property
    def valor_total(self):
        """Calcula o valor total da ordem de compra"""
        total = Decimal('0.00')
        for item in self.itens.all():
            if item.preco_unitario:
                total += item.quantidade_solicitada * item.preco_unitario
        return total


class HistoricoEnvioEmail(models.Model):
    """Histórico de envios de email para ordens de compra"""
    STATUS_CHOICES = [
        ('ENVIADO', 'Enviado'),
        ('FALHOU', 'Falhou'),
        ('PENDENTE', 'Pendente'),
    ]
    
    ordem_compra = models.ForeignKey(
        OrdemCompra, 
        on_delete=models.CASCADE, 
        related_name='historico_envios',
        help_text='Ordem de compra relacionada'
    )
    email_destinatario = models.EmailField(help_text='Email do destinatário')
    assunto = models.CharField(max_length=200, help_text='Assunto do email')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    data_envio = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    enviado_por = models.ForeignKey(User, on_delete=models.CASCADE, help_text='Usuário que enviou')
    mensagem_erro = models.TextField(blank=True, null=True, help_text='Mensagem de erro se falhou')
    sendgrid_message_id = models.CharField(max_length=100, blank=True, null=True, help_text='ID da mensagem no SendGrid')
    anexo_pdf = models.FileField(upload_to='emails/pdfs/', blank=True, null=True, help_text='PDF anexado')
    
    class Meta:
        verbose_name = 'Histórico de Envio de Email'
        verbose_name_plural = 'Histórico de Envios de Email'
        ordering = ['-data_envio']
    
    def __str__(self):
        return f"{self.ordem_compra.codigo} - {self.email_destinatario} - {self.get_status_display()}"


class ItemOrdemCompra(models.Model):
    """Itens de uma ordem de compra"""
    ordem_compra = models.ForeignKey(
        OrdemCompra, 
        on_delete=models.CASCADE, 
        related_name='itens',
        help_text='Ordem de compra'
    )
    produto = models.ForeignKey(
        Item, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text='Produto'
    )
    quantidade_solicitada = models.PositiveIntegerField(
        help_text='Quantidade solicitada na ordem'
    )
    quantidade_recebida = models.PositiveIntegerField(
        default=0,
        help_text='Quantidade efetivamente recebida'
    )
    preco_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Preço unitário acordado'
    )
    observacoes = models.TextField(
        help_text='Observações sobre o item',
        default=''
    )
    categoria = models.CharField(
        max_length=100,
        help_text='Categoria do item',
        default='Geral'
    )
    descricao = models.CharField(
        max_length=200,
        help_text='Descrição do item',
        default='Item sem descrição'
    )
    especificacoes = models.TextField(
        help_text='Especificações técnicas',
        default='Sem especificações'
    )
    
    class Meta:
        verbose_name = 'Item da Ordem de Compra'
        verbose_name_plural = 'Itens da Ordem de Compra'
        unique_together = [['ordem_compra', 'produto']]
    
    @property
    def preco_total(self):
        """Calcula o preço total"""
        if self.preco_unitario:
            return self.quantidade_solicitada * self.preco_unitario
        return 0
    
    @property
    def tipo_item(self):
        """Retorna o tipo do item: 'Produto' ou 'Material'"""
        return 'Produto' if self.produto else 'Material'
    
    def __str__(self):
        item_nome = self.produto.nome if self.produto else self.descricao
        return f"{self.ordem_compra.codigo} - {item_nome}"


class TransferenciaStock(models.Model):
    """Transferências de stock entre sucursais"""
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('PENDENTE', 'Pendente'),
        ('ENVIADA', 'Enviada'),
        ('RECEBIDA', 'Recebida'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da transferência'
    )
    sucursal_origem = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='transferencias_enviadas',
        help_text='Sucursal de origem'
    )
    sucursal_destino = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='transferencias_recebidas',
        help_text='Sucursal de destino'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='RASCUNHO',
        help_text='Status da transferência'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a transferência'
    )
    
    # Datas importantes
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_envio = models.DateTimeField(null=True, blank=True)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    
    # Usuários responsáveis
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='transferencias_stock_criadas',
        help_text='Usuário que criou a transferência'
    )
    confirmado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferencias_stock_confirmadas',
        help_text='Usuário que confirmou o recebimento'
    )

    def __str__(self):
        return f"TRF-{self.codigo} - {self.sucursal_origem.nome} → {self.sucursal_destino.nome}"

    @property
    def valor_total(self):
        """Calcula o valor total da transferência (solicitado)"""
        return sum(item.valor_total for item in self.itens.all())
    
    @property
    def valor_recebido(self):
        """Calcula o valor total da transferência recebida"""
        return sum(item.valor_recebido for item in self.itens.all())

    class Meta:
        verbose_name = 'Transferência de Stock'
        verbose_name_plural = 'Transferências de Stock'
        ordering = ['-data_criacao']

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gerar código simples até corrigir método completo
            import time
            self.codigo = f"TRF{int(time.time())}"
        super().save(*args, **kwargs)

    @property
    def pode_cancelar(self):
        """Verifica se a transferência pode ser cancelada"""
        return self.status in ['PENDENTE', 'ENVIADA']

    @property
    def pode_receber(self):
        """Verifica se a transferência pode ser recebida"""
        return self.status == 'ENVIADA'
    
    @property
    def tem_itens(self):
        """Verifica se a transferência tem itens"""
        return self.itens.exists()
    
    def promover_para_pendente(self):
        """Promove transferência de RASCUNHO para PENDENTE quando tem itens"""
        if self.status == 'RASCUNHO' and self.tem_itens:
            self.status = 'PENDENTE'
            self.save()
            return True
        return False


class ItemTransferencia(models.Model):
    """Itens de uma transferência de stock (SISTEMA UNIFICADO)"""
    transferencia = models.ForeignKey(
        TransferenciaStock,
        on_delete=models.CASCADE,
        related_name='itens',
        help_text='Transferência a que pertence este item'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Item a ser transferido (produto ou material)'
    )
    quantidade_solicitada = models.PositiveIntegerField(
        help_text='Quantidade solicitada para transferência'
    )
    quantidade_recebida = models.PositiveIntegerField(
        default=0,
        help_text='Quantidade efetivamente recebida'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre este item'
    )

    def __str__(self):
        nome = self.item.nome if self.item else 'Item não definido'
        return f"{nome} - {self.quantidade_solicitada} unidades"

    class Meta:
        verbose_name = 'Item de Transferência'
        verbose_name_plural = 'Itens de Transferência'
        unique_together = [['transferencia', 'item']]

    @property
    def quantidade_pendente(self):
        """Quantidade ainda pendente de recebimento"""
        return self.quantidade_solicitada - self.quantidade_recebida

    @property
    def totalmente_recebido(self):
        """Verifica se o item foi totalmente recebido"""
        return self.quantidade_recebida >= self.quantidade_solicitada

    @property
    def valor_total(self):
        """Calcula o valor total do item (solicitado)"""
        preco = self.item.preco_custo if self.item else 0
        return self.quantidade_solicitada * preco
    
    @property
    def valor_recebido(self):
        """Calcula o valor total do item recebido"""
        preco = self.item.preco_custo if self.item else 0
        return self.quantidade_recebida * preco


# =============================================================================
# MODELOS DE REQUISIÇÕES DE STOCK
# =============================================================================

class RequisicaoStock(models.Model):
    """Requisições de stock entre sucursais"""
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('PENDENTE', 'Pendente'),
        ('APROVADA', 'Aprovada'),
        ('REJEITADA', 'Rejeitada'),
        ('ATENDIDA', 'Atendida'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da requisição'
    )
    sucursal_origem = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='requisicoes_enviadas',
        help_text='Sucursal que solicita'
    )
    sucursal_destino = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='requisicoes_recebidas',
        null=True,
        blank=True,
        help_text='Sucursal que fornece (será definida quando adicionar itens)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='RASCUNHO',
        help_text='Status da requisição'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a requisição'
    )
    
    # Datas importantes
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_atendimento = models.DateTimeField(null=True, blank=True)
    
    # Usuários responsáveis
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='requisicoes_stock_criadas',
        help_text='Usuário que criou a requisição'
    )
    aprovado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisicoes_stock_aprovadas',
        help_text='Usuário que aprovou a requisição'
    )

    def __str__(self):
        destino = self.sucursal_destino.nome if self.sucursal_destino else "Por definir"
        return f"REQ-{self.codigo} - {self.sucursal_origem.nome} -> {destino}"
    
    @property
    def valor_total(self):
        """Calcula o valor total da requisição (solicitado)"""
        return sum(item.valor_total for item in self.itens.all())
    
    @property
    def valor_atendido(self):
        """Calcula o valor total da requisição atendida"""
        return sum(item.valor_atendido for item in self.itens.all())

    class Meta:
        verbose_name = 'Requisição de Stock'
        verbose_name_plural = 'Requisições de Stock'
        ordering = ['-data_criacao']

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gerar código automático sequencial único
            import time
            from django.db import transaction
            
            with transaction.atomic():
                # Buscar o último código existente
                ultima_requisicao = RequisicaoStock.objects.filter(
                    codigo__startswith='REQ'
                ).order_by('-codigo').first()
                
                if ultima_requisicao:
                    # Extrair número do último código
                    try:
                        ultimo_numero = int(ultima_requisicao.codigo[3:])
                        proximo_numero = ultimo_numero + 1
                    except (ValueError, IndexError):
                        proximo_numero = 1
                else:
                    proximo_numero = 1
                
                # Verificar se o código já existe e incrementar se necessário
                while True:
                    codigo_tentativa = f"REQ{proximo_numero:04d}"
                    if not RequisicaoStock.objects.filter(codigo=codigo_tentativa).exists():
                        self.codigo = codigo_tentativa
                        break
                    proximo_numero += 1
                    
                    # Proteção contra loop infinito
                    if proximo_numero > 9999:
                        # Se chegou ao limite, usar timestamp
                        self.codigo = f"REQ{int(time.time())}"
                        break
                        
        super().save(*args, **kwargs)

    def promover_para_pendente(self):
        """Promove a requisição de RASCUNHO para PENDENTE"""
        if self.status == 'RASCUNHO' and self.itens.exists():
            self.status = 'PENDENTE'
            self.save()
            return True
        return False


class ItemRequisicaoStock(models.Model):
    """Itens de uma requisição de stock (SISTEMA UNIFICADO)"""
    requisicao = models.ForeignKey(
        RequisicaoStock,
        on_delete=models.CASCADE,
        related_name='itens',
        help_text='Requisição a que pertence este item'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Item solicitado (produto ou material)'
    )
    quantidade_solicitada = models.PositiveIntegerField(
        help_text='Quantidade solicitada'
    )
    quantidade_atendida = models.PositiveIntegerField(
        default=0,
        help_text='Quantidade efetivamente atendida'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre este item'
    )

    def __str__(self):
        nome = self.item.nome if self.item else 'Item não definido'
        return f"{nome} - {self.quantidade_solicitada} unidades"

    class Meta:
        verbose_name = 'Item de Requisição'
        verbose_name_plural = 'Itens de Requisição'
        unique_together = [['requisicao', 'item']]

    @property
    def quantidade_pendente(self):
        """Quantidade ainda pendente de atendimento"""
        return self.quantidade_solicitada - self.quantidade_atendida

    @property
    def totalmente_atendido(self):
        """Verifica se o item foi totalmente atendido"""
        return self.quantidade_atendida >= self.quantidade_solicitada
    
    @property
    def valor_total(self):
        """Calcula o valor total do item (solicitado)"""
        preco = self.item.preco_custo if self.item else 0
        return self.quantidade_solicitada * preco
    
    @property
    def valor_atendido(self):
        """Calcula o valor total do item atendido"""
        preco = self.item.preco_custo if self.item else 0
        return self.quantidade_atendida * preco


# =============================================================================
# MODELOS DE REQUISIÇÕES DE COMPRA EXTERNA
# =============================================================================

class RequisicaoCompraExterna(models.Model):
    """Requisições de compra para fornecedores externos"""
    STATUS_CHOICES = [
        ('RASCUNHO', 'Rascunho'),
        ('PENDENTE', 'Pendente'),
        ('APROVADA', 'Aprovada'),
        ('ENVIADA', 'Enviada ao Fornecedor'),
        ('RECEBIDA', 'Recebida'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da requisição de compra'
    )
    sucursal_solicitante = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name='requisicoes_compra_enviadas',
        help_text='Sucursal que solicita a compra'
    )
    fornecedor = models.ForeignKey(
        'Fornecedor',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text='Fornecedor selecionado para a compra'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='RASCUNHO',
        help_text='Status da requisição de compra'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a requisição de compra'
    )
    
    # Datas importantes
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    data_envio_fornecedor = models.DateTimeField(null=True, blank=True)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    
    # Usuários responsáveis
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='requisicoes_compra_criadas',
        help_text='Usuário que criou a requisição de compra'
    )
    aprovado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requisicoes_compra_aprovadas',
        help_text='Usuário que aprovou a requisição de compra'
    )

    def __str__(self):
        fornecedor_nome = self.fornecedor.nome if self.fornecedor else 'Sem fornecedor'
        return f"COMP-{self.codigo} - {self.sucursal_solicitante.nome} → {fornecedor_nome}"
    
    @property
    def valor_total(self):
        """Calcula o valor total da requisição de compra"""
        return sum(item.valor_total for item in self.itens.all())
    
    @property
    def valor_recebido(self):
        """Calcula o valor total recebido"""
        return sum(item.valor_recebido for item in self.itens.all())

    class Meta:
        verbose_name = 'Requisição de Compra Externa'
        verbose_name_plural = 'Requisições de Compra Externa'
        ordering = ['-data_criacao']

    def save(self, *args, **kwargs):
        if not self.codigo:
            # Gerar código automático sequencial único
            import time
            from django.db import transaction
            
            with transaction.atomic():
                # Buscar o último código existente
                ultima_requisicao = RequisicaoCompraExterna.objects.filter(
                    codigo__startswith='COMP'
                ).order_by('-codigo').first()
                
                if ultima_requisicao:
                    # Extrair número do último código
                    try:
                        ultimo_numero = int(ultima_requisicao.codigo[4:])
                        proximo_numero = ultimo_numero + 1
                    except (ValueError, IndexError):
                        proximo_numero = 1
                else:
                    proximo_numero = 1
                
                # Verificar se o código já existe e incrementar se necessário
                while True:
                    codigo_tentativa = f"COMP{proximo_numero:04d}"
                    if not RequisicaoCompraExterna.objects.filter(codigo=codigo_tentativa).exists():
                        self.codigo = codigo_tentativa
                        break
                    proximo_numero += 1
                    
                    # Proteção contra loop infinito
                    if proximo_numero > 9999:
                        # Se chegou ao limite, usar timestamp
                        self.codigo = f"COMP{int(time.time())}"
                        break
                        
        super().save(*args, **kwargs)

    def promover_para_pendente(self):
        """Promove a requisição de RASCUNHO para PENDENTE"""
        if self.status == 'RASCUNHO' and self.itens.exists():
            self.status = 'PENDENTE'
            self.save()
            return True
        return False


class ItemRequisicaoCompraExterna(models.Model):
    """Itens de uma requisição de compra externa"""
    requisicao = models.ForeignKey(
        RequisicaoCompraExterna,
        on_delete=models.CASCADE,
        related_name='itens',
        help_text='Requisição de compra a que pertence este item'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text='Item solicitado (produto ou material)'
    )
    quantidade_solicitada = models.PositiveIntegerField(
        help_text='Quantidade solicitada'
    )
    quantidade_recebida = models.PositiveIntegerField(
        default=0,
        help_text='Quantidade efetivamente recebida'
    )
    preco_unitario_estimado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Preço unitário estimado para compra (opcional)'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre este item'
    )

    def __str__(self):
        nome = self.item.nome if self.item else 'Item não definido'
        return f"{nome} - {self.quantidade_solicitada} unidades"

    class Meta:
        verbose_name = 'Item de Requisição de Compra Externa'
        verbose_name_plural = 'Itens de Requisição de Compra Externa'
        unique_together = [['requisicao', 'item']]

    @property
    def quantidade_pendente(self):
        """Quantidade ainda pendente de recebimento"""
        return self.quantidade_solicitada - self.quantidade_recebida

    @property
    def totalmente_recebido(self):
        """Verifica se o item foi totalmente recebido"""
        return self.quantidade_recebida >= self.quantidade_solicitada
    
    @property
    def valor_total(self):
        """Calcula o valor total do item (solicitado)"""
        if self.preco_unitario_estimado is None:
            return 0
        return self.quantidade_solicitada * self.preco_unitario_estimado
    
    @property
    def valor_recebido(self):
        """Calcula o valor total do item recebido"""
        if self.preco_unitario_estimado is None:
            return 0
        return self.quantidade_recebida * self.preco_unitario_estimado


# =============================================================================
# MODELOS DE RASTREAMENTO LOGÍSTICO
# =============================================================================

class VeiculoInterno(models.Model):
    """Veículos internos da empresa (frota própria)"""
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('INATIVO', 'Inativo'),
        ('MANUTENCAO', 'Em Manutenção'),
    ]

    CATEGORIA_CHOICES = [
        ('CAMINHAO', 'Caminhão'),
        ('VAN', 'Van'),
        ('MOTO', 'Moto'),
        ('CARRO', 'Carro'),
        ('BICICLETA', 'Bicicleta'),
        ('ONIBUS', 'Ônibus'),
    ]
    
    # Identificação
    codigo = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Código único do veículo'
    )
    nome = models.CharField(
        max_length=200,
        help_text='Nome do veículo (ex: "Van de Entregas - Matola")'
    )
    
    # Tipo de veículo
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        help_text='Categoria do veículo'
    )
    
    # Dados do veículo
    placa = models.CharField(
        max_length=10,
        unique=True,
        help_text='Placa do veículo'
    )
    marca = models.CharField(
        max_length=50,
        help_text='Marca do veículo'
    )
    modelo = models.CharField(
        max_length=100,
        help_text='Modelo do veículo'
    )
    ano_fabricacao = models.PositiveIntegerField(
        help_text='Ano de fabricação do veículo'
    )
    capacidade_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Capacidade de carga em kg'
    )
    
    # Manutenção
    quilometragem_atual = models.PositiveIntegerField(
        default=0,
        help_text='Quilometragem atual do veículo'
    )
    proxima_revisao = models.DateField(
        null=True,
        blank=True,
        help_text='Data da próxima revisão'
    )
    
    # Motorista
    motorista_responsavel = models.CharField(
        max_length=200,
        help_text='Nome do motorista responsável'
    )
    telefone_motorista = models.CharField(
        max_length=13,
        help_text='Telefone do motorista'
    )
    
    # Custos operacionais
    custo_por_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Custo por quilômetro em MT'
    )
    custo_fixo_mensal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Custo fixo mensal em MT'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ATIVO',
        help_text='Status do veículo'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o veículo está ativo'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de cadastro do veículo'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre o veículo'
    )

    class Meta:
        verbose_name = 'Veículo Interno'
        verbose_name_plural = 'Veículos Internos'
        ordering = ['nome']

    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.placa})"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático para veículo interno"""
        total_veiculos = VeiculoInterno.objects.count()
        proximo_numero = total_veiculos + 1
        return f"VIAT{proximo_numero:04d}"


class ChecklistViatura(models.Model):
    """Checklist para avaliação do estado das viaturas internas"""
    TIPO_CHOICES = [
        ('PRE_VIAGEM', 'Pré-Viagem'),
        ('POS_VIAGEM', 'Pós-Viagem'),
        ('MANUTENCAO', 'Manutenção'),
        ('INSPECAO', 'Inspeção Geral'),
        ('SEMANAL', 'Inspeção Semanal'),
        ('MENSAL', 'Inspeção Mensal'),
    ]
    
    STATUS_CHOICES = [
        ('APROVADO', 'Aprovado'),
        ('REPROVADO', 'Reprovado'),
        ('CONDICIONAL', 'Aprovado com Condições'),
    ]
    
    # Identificação
    codigo = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Código único do checklist'
    )
    veiculo = models.ForeignKey(
        VeiculoInterno,
        on_delete=models.CASCADE,
        related_name='checklists',
        help_text='Veículo avaliado'
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        help_text='Tipo de checklist'
    )
    
    # Responsáveis
    inspetor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='checklists_realizados',
        help_text='Inspetor responsável'
    )
    motorista = models.CharField(
        max_length=200,
        help_text='Motorista presente na inspeção'
    )
    
    # Data e local
    data_inspecao = models.DateTimeField(
        default=timezone.now,
        help_text='Data e hora da inspeção'
    )
    local_inspecao = models.CharField(
        max_length=200,
        help_text='Local onde foi realizada a inspeção'
    )
    quilometragem = models.PositiveIntegerField(
        help_text='Quilometragem no momento da inspeção'
    )
    
    # Itens do checklist
    # Sistema de Freios
    freios_funcionando = models.BooleanField(
        default=True,
        help_text='Freios funcionando corretamente'
    )
    fluido_freio_ok = models.BooleanField(
        default=True,
        help_text='Fluido de freio em nível adequado'
    )
    pastilhas_ok = models.BooleanField(
        default=True,
        help_text='Pastilhas de freio em bom estado'
    )
    
    # Sistema de Direção
    direcao_funcionando = models.BooleanField(
        default=True,
        help_text='Direção funcionando corretamente'
    )
    fluido_direcao_ok = models.BooleanField(
        default=True,
        help_text='Fluido de direção em nível adequado'
    )
    
    # Sistema Elétrico
    bateria_ok = models.BooleanField(
        default=True,
        help_text='Bateria em bom estado'
    )
    alternador_ok = models.BooleanField(
        default=True,
        help_text='Alternador funcionando'
    )
    farois_funcionando = models.BooleanField(
        default=True,
        help_text='Faróis funcionando'
    )
    luzes_sinalizacao = models.BooleanField(
        default=True,
        help_text='Luzes de sinalização funcionando'
    )
    
    # Pneus e Rodas
    pneus_pressao_ok = models.BooleanField(
        default=True,
        help_text='Pressão dos pneus adequada'
    )
    pneus_desgaste_ok = models.BooleanField(
        default=True,
        help_text='Desgaste dos pneus dentro do limite'
    )
    rodas_ok = models.BooleanField(
        default=True,
        help_text='Rodas em bom estado'
    )
    
    # Motor e Fluidos
    motor_funcionando = models.BooleanField(
        default=True,
        help_text='Motor funcionando corretamente'
    )
    oleo_motor_ok = models.BooleanField(
        default=True,
        help_text='Óleo do motor em nível adequado'
    )
    agua_radiador_ok = models.BooleanField(
        default=True,
        help_text='Água do radiador em nível adequado'
    )
    combustivel_ok = models.BooleanField(
        default=True,
        help_text='Combustível suficiente'
    )
    
    # Documentação
    documentos_ok = models.BooleanField(
        default=True,
        help_text='Documentação do veículo em dia'
    )
    seguro_ok = models.BooleanField(
        default=True,
        help_text='Seguro do veículo em dia'
    )
    licenciamento_ok = models.BooleanField(
        default=True,
        help_text='Licenciamento em dia'
    )
    
    # Limpeza e Aparência
    limpeza_interior = models.BooleanField(
        default=True,
        help_text='Interior limpo e organizado'
    )
    limpeza_exterior = models.BooleanField(
        default=True,
        help_text='Exterior limpo'
    )
    
    # Equipamentos de Segurança
    extintor_ok = models.BooleanField(
        default=True,
        help_text='Extintor presente e em dia'
    )
    triangulo_ok = models.BooleanField(
        default=True,
        help_text='Triângulo de sinalização presente'
    )
    macaco_ok = models.BooleanField(
        default=True,
        help_text='Macaco presente e funcionando'
    )
    chave_roda_ok = models.BooleanField(
        default=True,
        help_text='Chave de roda presente'
    )
    
    # Resultado final
    status_final = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        help_text='Status final da inspeção'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a inspeção'
    )
    recomendacoes = models.TextField(
        blank=True,
        help_text='Recomendações para manutenção'
    )
    
    # Controle
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de criação do checklist'
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Indica se o checklist está ativo'
    )

    class Meta:
        verbose_name = 'Checklist de Viatura'
        verbose_name_plural = 'Checklists de Viaturas'
        ordering = ['-data_inspecao']

    def __str__(self):
        return f"{self.codigo} - {self.veiculo.nome} ({self.get_tipo_display()})"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        
        # Calcula status final baseado nos itens
        self.status_final = self.calcular_status_final()
        
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático para checklist"""
        total_checklists = ChecklistViatura.objects.count()
        proximo_numero = total_checklists + 1
        return f"CHK{proximo_numero:04d}"
    
    def calcular_status_final(self):
        """Calcula o status final baseado nos itens do checklist"""
        itens_obrigatorios = [
            'freios_funcionando', 'fluido_freio_ok', 'direcao_funcionando',
            'bateria_ok', 'motor_funcionando', 'oleo_motor_ok',
            'pneus_pressao_ok', 'pneus_desgaste_ok', 'documentos_ok',
            'extintor_ok', 'triangulo_ok'
        ]
        
        itens_falhados = []
        for item in itens_obrigatorios:
            if not getattr(self, item, True):
                itens_falhados.append(item)
        
        if len(itens_falhados) == 0:
            return 'APROVADO'
        elif len(itens_falhados) <= 2:
            return 'CONDICIONAL'
        else:
            return 'REPROVADO'
    
    def get_pontuacao_total(self):
        """Retorna a pontuação total do checklist (0-100)"""
        todos_itens = [
            'freios_funcionando', 'fluido_freio_ok', 'pastilhas_ok',
            'direcao_funcionando', 'fluido_direcao_ok', 'bateria_ok',
            'alternador_ok', 'farois_funcionando', 'luzes_sinalizacao',
            'pneus_pressao_ok', 'pneus_desgaste_ok', 'rodas_ok',
            'motor_funcionando', 'oleo_motor_ok', 'agua_radiador_ok',
            'combustivel_ok', 'documentos_ok', 'seguro_ok',
            'licenciamento_ok', 'limpeza_interior', 'limpeza_exterior',
            'extintor_ok', 'triangulo_ok', 'macaco_ok', 'chave_roda_ok'
        ]
        
        itens_ok = sum(1 for item in todos_itens if getattr(self, item, True))
        total_itens = len(todos_itens)
        
        return round((itens_ok / total_itens) * 100, 1)


class Transportadora(models.Model):
    """Transportadoras externas e fornecedores logísticos"""
    STATUS_CHOICES = [
        ('ATIVA', 'Ativa'),
        ('INATIVA', 'Inativa'),
        ('SUSPENSA', 'Suspensa'),
        ('MANUTENCAO', 'Em Manutenção'),
    ]

    TIPO_CHOICES = [
        ('TRANSPORTADORA', 'Transportadora Externa'),
        ('ENTREGA_RAPIDA', 'Entrega Rápida'),
        ('CORREIOS', 'Correios'),
        ('MOTORISTA', 'Motorista Próprio'),
        ('TERCEIRIZADA', 'Terceirizada'),
    ]
    
    nome = models.CharField(
        max_length=200,
        help_text='Nome da transportadora'
    )
    codigo = models.CharField(
        max_length=20,
        unique=True,
        help_text='Código único da transportadora'
    )
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        default='TRANSPORTADORA',
        help_text='Tipo de transportadora'
    )
    
    # Dados da empresa
    nuit = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Número de Identificação Única do Trabalhador (NUIT)'
    )
    email = models.EmailField(
        blank=True,
        help_text='Email de contato'
    )
    telefone = models.CharField(
        max_length=13,
        blank=True,
        help_text='Número de telefone com código do país (+258)'
    )
    website = models.URLField(
        blank=True,
        help_text='Website da transportadora'
    )
    endereco = models.TextField(
        blank=True,
        help_text='Endereço completo'
    )
    cidade = models.CharField(
        max_length=100,
        blank=True,
        help_text='Cidade'
    )
    provincia = models.CharField(
        max_length=50,
        blank=True,
        help_text='Província'
    )
    
    # Informações logísticas
    prazo_entrega_padrao = models.PositiveIntegerField(
        default=1,
        help_text='Prazo de entrega padrão em dias'
    )
    custo_por_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Custo por quilograma em MT'
    )
    custo_fixo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Custo fixo por entrega em MT'
    )
    cobertura_provincias = models.JSONField(
        default=list,
        blank=True,
        help_text='Províncias cobertas pela transportadora'
    )
    
    # Associação com sucursal (para viaturas internas)
    sucursal = models.ForeignKey(
        'empresa.Sucursal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Sucursal responsável pela viatura (apenas para viaturas internas)'
    )
    
    # Status e controle
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ATIVA',
        help_text='Status da transportadora'
    )
    ativa = models.BooleanField(
        default=True,
        help_text='Indica se a transportadora está ativa'
    )
    data_cadastro = models.DateTimeField(
        auto_now_add=True,
        help_text='Data de cadastro da transportadora'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a transportadora'
    )
    
    # Campos específicos para veículos internos
    categoria_veiculo = models.CharField(
        max_length=20,
        blank=True,
        help_text='Categoria do veículo (Automóvel, Moto, Van, etc.)'
    )
    placa = models.CharField(
        max_length=10,
        blank=True,
        help_text='Placa do veículo'
    )
    marca = models.CharField(
        max_length=50,
        blank=True,
        help_text='Marca do veículo'
    )
    modelo = models.CharField(
        max_length=100,
        blank=True,
        help_text='Modelo do veículo'
    )
    ano_fabricacao = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Ano de fabricação do veículo'
    )
    capacidade_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Capacidade de carga em kg'
    )
    quilometragem_atual = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Quilometragem atual do veículo'
    )
    proxima_revisao = models.DateField(
        null=True,
        blank=True,
        help_text='Data da próxima revisão'
    )
    motorista_responsavel = models.CharField(
        max_length=200,
        blank=True,
        help_text='Nome do motorista responsável'
    )
    telefone_motorista = models.CharField(
        max_length=13,
        blank=True,
        help_text='Telefone do motorista'
    )

    class Meta:
        verbose_name = 'Transportadora'
        verbose_name_plural = 'Transportadoras'
        ordering = ['nome']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def save(self, *args, **kwargs):
        # Gera código automaticamente se não fornecido
        if not self.codigo:
            self.codigo = self.gerar_codigo_automatico()
        super().save(*args, **kwargs)
    
    def gerar_codigo_automatico(self):
        """Gera código automático para transportadora"""
        total_transportadoras = Transportadora.objects.count()
        proximo_numero = total_transportadoras + 1
        return f"TRANS{proximo_numero:04d}"
    
    def gerar_nome_automatico(self):
        """Gera nome automático para viatura baseado na sucursal, categoria e número sequencial"""
        if not self.sucursal or not self.categoria_veiculo:
            return self.nome
        
        # Mapear categorias para abreviações
        categoria_abrev = {
            'AUTOMOVEL': 'AUTO',
            'MOTOCICLETA': 'MOTO',
            'VAN': 'VAN',
            'CAMINHAO': 'CAM',
            'BICICLETA': 'BIC',
            'PICKUP': 'PIC',
            'CAMINHONETE': 'CAM',
            'ONIBUS': 'ONI',
            'AMBULANCIA': 'AMB',
        }
        
        abrev_categoria = categoria_abrev.get(self.categoria_veiculo, 'VEI')
        abrev_sucursal = self.sucursal.nome[:3].upper()
        
        # Contar quantas viaturas já existem desta categoria nesta sucursal
        count = Transportadora.objects.filter(
            tipo='VIATURA_INTERNA',
            sucursal=self.sucursal,
            categoria_veiculo=self.categoria_veiculo
        ).count()
        
        # Se estamos editando uma viatura existente, não contar ela mesma
        if self.pk:
            count -= 1
        
        numero = count + 1
        
        return f"{abrev_sucursal}-{abrev_categoria}-{numero:02d}"


class RastreamentoEntrega(models.Model):
    """Rastreamento de entregas e envios"""
    STATUS_CHOICES = [
        ('PREPARANDO', 'Preparando'),
        ('COLETADO', 'Coletado'),
        ('EM_TRANSITO', 'Em Trânsito'),
        ('EM_DISTRIBUICAO', 'Em Distribuição'),
        ('ENTREGUE', 'Entregue'),
        ('DEVOLVIDO', 'Devolvido'),
        ('PERDIDO', 'Perdido'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    codigo_rastreamento = models.CharField(
        max_length=50,
        unique=True,
        help_text='Código único de rastreamento'
    )
    
    # Transporte: transportadora OU veículo interno (apenas um deve estar preenchido)
    transportadora = models.ForeignKey(
        Transportadora,
        on_delete=models.PROTECT,
        related_name='entregas',
        null=True,
        blank=True,
        help_text='Transportadora externa responsável'
    )
    veiculo_interno = models.ForeignKey(
        VeiculoInterno,
        on_delete=models.PROTECT,
        related_name='entregas',
        null=True,
        blank=True,
        help_text='Veículo interno responsável'
    )
    
    # Referências aos documentos
    transferencia = models.ForeignKey(
        TransferenciaStock,
        on_delete=models.CASCADE,
        related_name='rastreamentos',
        null=True,
        blank=True,
        help_text='Transferência relacionada'
    )
    ordem_compra = models.ForeignKey(
        OrdemCompra,
        on_delete=models.CASCADE,
        related_name='rastreamentos',
        null=True,
        blank=True,
        help_text='Ordem de compra relacionada'
    )
    
    # Informações da entrega
    destinatario_nome = models.CharField(
        max_length=200,
        help_text='Nome do destinatário'
    )
    destinatario_telefone = models.CharField(
        max_length=13,
        blank=True,
        help_text='Telefone do destinatário'
    )
    endereco_entrega = models.TextField(
        help_text='Endereço de entrega'
    )
    cidade_entrega = models.CharField(
        max_length=100,
        help_text='Cidade de entrega'
    )
    provincia_entrega = models.CharField(
        max_length=50,
        help_text='Província de entrega'
    )
    
    # Status e datas
    status_atual = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PREPARANDO',
        db_index=True,
        help_text='Status atual da entrega'
    )
    data_coleta = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora da coleta'
    )
    data_entrega_prevista = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data prevista para entrega'
    )
    data_entrega_realizada = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora da entrega realizada'
    )
    
    # Informações do envio
    peso_total = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Peso total em kg'
    )
    valor_declarado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor declarado do envio'
    )
    custo_envio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Custo do envio'
    )
    
    # Controle
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text='Data de criação do rastreamento'
    )
    criado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='rastreamentos_criados',
        help_text='Usuário que criou o rastreamento'
    )
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a entrega'
    )

    class Meta:
        verbose_name = 'Rastreamento de Entrega'
        verbose_name_plural = 'Rastreamentos de Entrega'
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['status_atual']),
            models.Index(fields=['data_criacao']),
            models.Index(fields=['transportadora']),
            models.Index(fields=['veiculo_interno']),
        ]

    def __str__(self):
        return f"{self.codigo_rastreamento} - {self.destinatario_nome}"

    def clean(self):
        """Validação: deve ter transportadora OU veículo interno, não ambos"""
        if not self.transportadora and not self.veiculo_interno:
            raise ValidationError('Selecione transportadora OU veículo interno.')
        if self.transportadora and self.veiculo_interno:
            raise ValidationError('Selecione apenas um tipo de transporte.')

    def save(self, *args, **kwargs):
        # Gera código de rastreamento automaticamente se não fornecido
        if not self.codigo_rastreamento:
            self.codigo_rastreamento = self.gerar_codigo_rastreamento()
        super().save(*args, **kwargs)
    
    def gerar_codigo_rastreamento(self):
        """Gera código único de rastreamento"""
        import time
        import random
        
        # Formato: TRANS + timestamp + random
        timestamp = int(time.time())
        random_num = random.randint(100, 999)
        return f"TRANS{timestamp}{random_num}"
    
    @property
    def documento_origem(self):
        """Retorna o documento de origem (transferência ou ordem de compra)"""
        return self.transferencia or self.ordem_compra
    
    @property
    def tipo_documento(self):
        """Retorna o tipo do documento de origem"""
        if self.transferencia:
            return 'Transferência'
        elif self.ordem_compra:
            return 'Ordem de Compra'
        return 'N/A'
    
    @property
    def transporte_responsavel(self):
        """Retorna o transporte responsável (transportadora ou veículo)"""
        return self.transportadora or self.veiculo_interno
    
    @property
    def tipo_transporte(self):
        """Retorna o tipo do transporte"""
        if self.transportadora:
            return 'Transportadora Externa'
        elif self.veiculo_interno:
            return 'Veículo Interno'
        return 'N/A'
    
    @property
    def tempo_em_transito(self):
        """Calcula o tempo em trânsito"""
        if self.data_coleta and self.status_atual in ['EM_TRANSITO', 'EM_DISTRIBUICAO', 'ENTREGUE']:
            data_fim = self.data_entrega_realizada or timezone.now()
            return (data_fim - self.data_coleta).total_seconds() / 3600  # em horas
        return 0


class EventoRastreamento(models.Model):
    """Eventos do rastreamento de entrega"""
    TIPO_EVENTO_CHOICES = [
        ('PREPARANDO', 'Preparando'),
        ('CRIADO', 'Criado'),
        ('COLETADO', 'Coletado'),
        ('EM_TRANSITO', 'Em Trânsito'),
        ('EM_DISTRIBUICAO', 'Em Distribuição'),
        ('TENTATIVA_ENTREGA', 'Tentativa de Entrega'),
        ('ENTREGUE', 'Entregue'),
        ('DEVOLVIDO', 'Devolvido'),
        ('PERDIDO', 'Perdido'),
        ('CANCELADO', 'Cancelado'),
        ('OBSERVACAO', 'Observação'),
    ]
    
    rastreamento = models.ForeignKey(
        RastreamentoEntrega,
        on_delete=models.CASCADE,
        related_name='eventos',
        help_text='Rastreamento relacionado'
    )
    tipo_evento = models.CharField(
        max_length=20,
        choices=TIPO_EVENTO_CHOICES,
        help_text='Tipo do evento'
    )
    descricao = models.TextField(
        help_text='Descrição do evento'
    )
    localizacao = models.CharField(
        max_length=200,
        blank=True,
        help_text='Localização onde ocorreu o evento'
    )
    data_evento = models.DateTimeField(
        default=timezone.now,
        help_text='Data e hora do evento'
    )
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Usuário que registrou o evento'
    )
    dados_extras = models.JSONField(
        default=dict,
        blank=True,
        help_text='Dados adicionais do evento'
    )

    class Meta:
        verbose_name = 'Evento de Rastreamento'
        verbose_name_plural = 'Eventos de Rastreamento'
        ordering = ['-data_evento']

    def __str__(self):
        return f"{self.rastreamento.codigo_rastreamento} - {self.get_tipo_evento_display()}"

    def save(self, *args, **kwargs):
        # Atualiza o status do rastreamento baseado no evento
        if self.tipo_evento in ['COLETADO', 'EM_TRANSITO', 'EM_DISTRIBUICAO', 'ENTREGUE', 'DEVOLVIDO', 'PERDIDO', 'CANCELADO']:
            self.rastreamento.status_atual = self.tipo_evento
            
            # Atualiza datas específicas
            if self.tipo_evento == 'COLETADO' and not self.rastreamento.data_coleta:
                self.rastreamento.data_coleta = self.data_evento
            elif self.tipo_evento == 'ENTREGUE' and not self.rastreamento.data_entrega_realizada:
                self.rastreamento.data_entrega_realizada = self.data_evento
            
            self.rastreamento.save()
        
        super().save(*args, **kwargs)




class NotificacaoLogisticaUnificada(models.Model):
    def clean(self):
        # Exclusividade entre transportadora_externa e veiculo_interno
        if not self.transportadora_externa and not self.veiculo_interno:
            raise ValidationError('Selecione transportadora externa OU veículo interno.')
        if self.transportadora_externa and self.veiculo_interno:
            raise ValidationError('Selecione apenas um tipo de transporte.')

    def save(self, *args, **kwargs):
        # Atualizar data de atribuição quando transporte é escolhido
        if not self.data_atribuicao and (self.veiculo_interno_id or self.transportadora_externa_id):
            self.data_atribuicao = timezone.now()
            if self.status == 'PENDENTE':
                self.status = 'ATRIBUIDA'
        super().save(*args, **kwargs)
    """Notificações logísticas unificadas para transferências e coletas"""
    
    TIPO_OPERACAO_CHOICES = [
        ('TRANSFERENCIA', 'Transferência Interna'),
        ('COLETA', 'Coleta de Compra'),
    ]
    
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ATRIBUIDA', 'Transporte Atribuído'),
        ('COLETADA', 'Coletada'),
        ('EM_TRANSITO', 'Em Trânsito'),
        ('ENTREGUE', 'Entregue'),
        ('CONCLUIDA', 'Concluída'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    TIPO_TRANSPORTE_CHOICES = [
        ('VEICULO_INTERNO', 'Veículo Interno'),
        ('TRANSPORTADORA_EXTERNA', 'Transportadora Externa'),
    ]
    
    # Tipo de operação
    tipo_operacao = models.CharField(
        max_length=20,
        choices=TIPO_OPERACAO_CHOICES,
        help_text='Tipo de operação logística'
    )
    
    # Referências (apenas uma deve estar preenchida)
    transferencia = models.OneToOneField(
        TransferenciaStock,
        on_delete=models.CASCADE,
        related_name='notificacao_logistica_unificada',
        null=True,
        blank=True,
        help_text='Transferência relacionada'
    )
    ordem_compra = models.OneToOneField(
        OrdemCompra,
        on_delete=models.CASCADE,
        related_name='notificacao_logistica_unificada',
        null=True,
        blank=True,
        help_text='Ordem de compra relacionada'
    )
    
    # Status da notificação
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDENTE',
        help_text='Status da notificação logística'
    )
    
    # Tipo de transporte escolhido
    tipo_transporte = models.CharField(
        max_length=30,
        choices=TIPO_TRANSPORTE_CHOICES,
        null=True,
        blank=True,
        help_text='Tipo de transporte escolhido'
    )
    
    # Transporte escolhido (apenas um deve estar preenchido)
    veiculo_interno = models.ForeignKey(
        VeiculoInterno,
        on_delete=models.PROTECT,
        related_name='operacoes_internas',
        null=True,
        blank=True,
        help_text='Veículo interno escolhido'
    )
    transportadora_externa = models.ForeignKey(
        Transportadora,
        on_delete=models.PROTECT,
        related_name='operacoes_externas',
        null=True,
        blank=True,
        limit_choices_to={'tipo__in': ['TRANSPORTADORA', 'ENTREGA_RAPIDA', 'CORREIOS', 'MOTORISTA', 'TERCEIRIZADA']},
        help_text='Transportadora externa escolhida'
    )
    
    # Datas importantes
    data_notificacao = models.DateTimeField(
        auto_now_add=True,
        help_text='Data da notificação'
    )
    data_atribuicao = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data em que foi atribuída ao transporte'
    )
    data_conclusao = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data de conclusão da operação'
    )
    
    # Usuários responsáveis
    usuario_notificacao = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificacoes_logistica_unificada_criadas',
        help_text='Usuário que criou a notificação'
    )
    usuario_atribuicao = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notificacoes_logistica_unificada_atribuidas',
        help_text='Usuário que atribuiu o transporte'
    )
    
    # Observações
    observacoes = models.TextField(
        blank=True,
        help_text='Observações sobre a operação'
    )
    
    # Prioridade
    prioridade = models.CharField(
        max_length=20,
        choices=[
            ('BAIXA', 'Baixa'),
            ('NORMAL', 'Normal'),
            ('ALTA', 'Alta'),
            ('URGENTE', 'Urgente'),
        ],
        default='NORMAL',
        db_index=True,
        help_text='Prioridade da operação'
    )
    
    # Campos de Confirmação de Coleta
    coletado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operacoes_coletadas',
        help_text='Usuário que confirmou a coleta'
    )
    data_coleta = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora da coleta'
    )
    local_coleta = models.CharField(
        max_length=200,
        blank=True,
        help_text='Local onde foi realizada a coleta'
    )
    observacoes_coleta = models.TextField(
        blank=True,
        help_text='Observações sobre a coleta'
    )
    
    # Campos de Transporte
    data_inicio_transporte = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora do início do transporte'
    )
    observacoes_transporte = models.TextField(
        blank=True,
        help_text='Observações sobre o transporte'
    )
    
    # Campos de Confirmação de Entrega
    entregue_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operacoes_entregues',
        help_text='Usuário que confirmou a entrega'
    )
    recebido_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operacoes_recebidas',
        help_text='Usuário que confirmou o recebimento'
    )
    data_entrega = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Data e hora da entrega'
    )
    local_entrega = models.CharField(
        max_length=200,
        blank=True,
        help_text='Local onde foi realizada a entrega'
    )
    observacoes_entrega = models.TextField(
        blank=True,
        help_text='Observações sobre a entrega'
    )
    
    # Campos de Conclusão
    observacoes_conclusao = models.TextField(
        blank=True,
        help_text='Observações sobre a conclusão'
    )
    
    # Documentos de Transporte
    guia_coleta = models.FileField(
        upload_to='guias_coleta/',
        null=True,
        blank=True,
        help_text='Guia de coleta gerada'
    )
    guia_entrega = models.FileField(
        upload_to='guias_entrega/',
        null=True,
        blank=True,
        help_text='Guia de entrega gerada'
    )
    comprovante_recebimento = models.FileField(
        upload_to='comprovantes_recebimento/',
        null=True,
        blank=True,
        help_text='Comprovante de recebimento assinado'
    )

    class Meta:
        verbose_name = 'Notificação Logística Unificada'
        verbose_name_plural = 'Notificações Logísticas Unificadas'
        ordering = ['-data_notificacao']
        indexes = [
            models.Index(fields=['tipo_operacao']),
            models.Index(fields=['status']),
            models.Index(fields=['data_notificacao']),
            models.Index(fields=['prioridade']),
        ]

    def __str__(self):
        if self.tipo_operacao == 'TRANSFERENCIA':
            return f"Transferência {self.transferencia.codigo} - {self.get_status_display()}"
        else:
            return f"Coleta {self.ordem_compra.codigo} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Atualizar data de atribuição quando transporte é escolhido
        if not self.data_atribuicao and (self.veiculo_interno_id or self.transportadora_externa_id):
            self.data_atribuicao = timezone.now()
            self.status = 'ATRIBUIDA'
        
        # Atualizar data de conclusão quando status muda para concluída
        if self.status == 'CONCLUIDA' and not self.data_conclusao:
            self.data_conclusao = timezone.now()
        
        super().save(*args, **kwargs)
    
    def confirmar_coleta(self, usuario, local_coleta='', observacoes=''):
        """Confirmar coleta da operação"""
        self.status = 'COLETADA'
        self.coletado_por = usuario
        self.data_coleta = timezone.now()
        self.local_coleta = local_coleta
        self.observacoes_coleta = observacoes
        self.save()
    
    def confirmar_entrega(self, usuario_entrega, usuario_recebimento, local_entrega='', observacoes=''):
        """Confirmar entrega da operação"""
        self.status = 'ENTREGUE'
        self.entregue_por = usuario_entrega
        self.recebido_por = usuario_recebimento
        self.data_entrega = timezone.now()
        self.local_entrega = local_entrega
        self.observacoes_entrega = observacoes
        self.save()
    
    def concluir_operacao(self):
        """Finalizar operação após todas as confirmações"""
        if self.status == 'ENTREGUE':
            self.status = 'CONCLUIDA'
            self.data_conclusao = timezone.now()
            self.save()
    
    @property
    def pode_coletar(self):
        """Verifica se a operação pode ser coletada"""
        return self.status in ['ATRIBUIDA']
    
    @property
    def pode_entregar(self):
        """Verifica se a operação pode ser entregue"""
        return self.status in ['COLETADA', 'EM_TRANSITO']
    
    @property
    def pode_concluir(self):
        """Verifica se a operação pode ser concluída"""
        return self.status == 'ENTREGUE'

    @property
    def operacao_relacionada(self):
        """Retorna a operação relacionada"""
        if self.tipo_operacao == 'TRANSFERENCIA':
            return self.transferencia
        else:
            return self.ordem_compra

    @property
    def codigo_operacao(self):
        """Retorna o código da operação"""
        if self.tipo_operacao == 'TRANSFERENCIA':
            return self.transferencia.codigo
        else:
            return self.ordem_compra.codigo

    @property
    def origem_operacao(self):
        """Retorna a origem da operação"""
        if self.tipo_operacao == 'TRANSFERENCIA':
            return self.transferencia.sucursal_origem.nome
        else:
            return self.ordem_compra.fornecedor.nome

    @property
    def destino_operacao(self):
        """Retorna o destino da operação"""
        if self.tipo_operacao == 'TRANSFERENCIA':
            return self.transferencia.sucursal_destino.nome
        else:
            return self.ordem_compra.sucursal_destino.nome

    @property
    def valor_operacao(self):
        """Retorna o valor da operação"""
        if self.tipo_operacao == 'TRANSFERENCIA':
            return self.transferencia.valor_total
        else:
            return self.ordem_compra.valor_total

    @property
    def transporte_escolhido(self):
        """Retorna o transporte escolhido"""
        if self.veiculo_interno:
            return self.veiculo_interno
        elif self.transportadora_externa:
            return self.transportadora_externa
        return None

    @property
    def tempo_pendente(self):
        """Calcula o tempo que está pendente"""
        if self.status == 'PENDENTE':
            return timezone.now() - self.data_notificacao
        return None

    @property
    def tempo_em_andamento(self):
        """Calcula o tempo em andamento"""
        if self.status == 'EM_ANDAMENTO' and self.data_atribuicao:
            return timezone.now() - self.data_atribuicao
        return None

    def get_prioridade_color(self):
        """Retorna a cor da prioridade"""
        colors = {
            'BAIXA': 'success',
            'NORMAL': 'info',
            'ALTA': 'warning',
            'URGENTE': 'danger',
        }
        return colors.get(self.prioridade, 'info')

    def get_status_color(self):
        """Retorna a cor do status"""
        colors = {
            'PENDENTE': 'warning',
            'EM_ANDAMENTO': 'info',
            'CONCLUIDA': 'success',
            'CANCELADA': 'danger',
        }
        return colors.get(self.status, 'info')

    def get_tipo_operacao_icon(self):
        """Retorna o ícone do tipo de operação"""
        icons = {
            'TRANSFERENCIA': 'fas fa-exchange-alt',
            'COLETA': 'fas fa-shopping-cart',
        }
        return icons.get(self.tipo_operacao, 'fas fa-question')

    def get_tipo_operacao_color(self):
        """Retorna a cor do tipo de operação"""
        colors = {
            'TRANSFERENCIA': 'primary',
            'COLETA': 'success',
        }
        return colors.get(self.tipo_operacao, 'secondary')




