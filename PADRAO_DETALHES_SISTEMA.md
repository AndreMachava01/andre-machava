# PADRÃO DE REFERÊNCIA - TELAS DE DETALHES

## 🎨 Design System para Páginas de Detalhes

### Estrutura Padrão
```html
{% extends "base_list.html" %}
{% load static %}

{% block title %}Detalhes do [Entidade]{% endblock %}

{% block extra_style %}
<style>
    /* Container principal modernizado */
    .content-section {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
        margin-top: 24px;
    }
    
    /* Cards modernizados */
    .card {
        background: #ffffff;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        border: 1px solid #e5e7eb;
        overflow: hidden;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.12);
    }
    
    .card-header {
        background: #f8f9fa;
        color: #495057;
        padding: 20px 24px;
        border-bottom: 1px solid #e9ecef;
        position: relative;
    }
    
    .card-header h5 {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        color: #495057;
    }
    
    .card-header i {
        font-size: 18px;
        color: #6c757d;
    }
    
    .card-body {
        padding: 24px;
    }
    
    /* Linhas de informação modernizadas */
    .info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #f3f4f6;
        transition: all 0.2s ease;
    }
    
    .info-row:last-child {
        border-bottom: none;
    }
    
    .info-row:hover {
        background: #f8fafc;
        margin: 0 -24px;
        padding: 12px 24px;
        border-radius: 8px;
    }
    
    .info-label {
        font-weight: 600;
        color: #374151;
        font-size: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .info-value {
        color: #6b7280;
        font-size: 14px;
        text-align: right;
        font-weight: 500;
    }
    
    /* Badges modernizados */
    .badge {
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .bg-success { background: #28a745 !important; color: white; }
    .bg-warning { background: #ffc107 !important; color: #212529; }
    .bg-secondary { background: #6c757d !important; color: white; }
    .bg-info { background: #17a2b8 !important; color: white; }
    .bg-danger { background: #dc3545 !important; color: white; }
    
    /* Cards de largura completa */
    .card-full-width {
        grid-column: 1 / -1;
    }
    
    /* Responsividade */
    @media (max-width: 768px) {
        .content-section {
            grid-template-columns: 1fr;
            gap: 16px;
        }
        
        .card-body {
            padding: 16px;
        }
        
        .info-row {
            flex-direction: column;
            align-items: flex-start;
            gap: 4px;
        }
        
        .info-value {
            text-align: left;
        }
    }
    
    /* Animações de entrada */
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .card {
        animation: slideInUp 0.6s ease-out;
    }
    
    .card:nth-child(1) { animation-delay: 0.1s; }
    .card:nth-child(2) { animation-delay: 0.2s; }
    .card:nth-child(3) { animation-delay: 0.3s; }
    .card:nth-child(4) { animation-delay: 0.4s; }
    .card:nth-child(5) { animation-delay: 0.5s; }
</style>
{% endblock %}

{% block content %}
<div class="container">
    <!-- Breadcrumb -->
    <nav aria-label="breadcrumb" class="breadcrumb-modern">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{% url "dashboard" %}">Dashboard</a></li>
            <li class="breadcrumb-item"><a href="{% url "[modulo]:[lista]" %}">[Entidade]</a></li>
            <li class="breadcrumb-item active">{{ [objeto].[nome] }}</li>
        </ol>
    </nav>

    <!-- Page Header -->
    <div class="page-header">
        <div class="page-header-content">
            <div>
                <h1 class="page-title">
                    <i class="fas fa-[icone]"></i>
                    {{ [objeto].[nome] }}
                </h1>
                <p class="page-subtitle">Detalhes completos do [entidade]</p>
            </div>
            <div class="header-actions">
                <a href="{% url '[modulo]:[lista]' %}" class="btn btn-secondary btn-responsive">
                    <i class="fas fa-arrow-left"></i>
                    Voltar
                </a>
                <a href="{% url '[modulo]:[editar]' [objeto].id %}" class="btn btn-primary btn-responsive">
                    <i class="fas fa-edit"></i>
                    Editar
                </a>
            </div>
        </div>
    </div>

    <!-- Content Section -->
    <div class="content-section">
        <!-- Seção 1: Informações Básicas -->
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">
                    <i class="fas fa-info-circle"></i>Informações Básicas
                </h5>
            </div>
            <div class="card-body">
                <div class="info-row">
                    <span class="info-label">
                        <i class="fas fa-hashtag"></i>Código:
                    </span>
                    <span class="info-value">{{ [objeto].[codigo] }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">
                        <i class="fas fa-calendar"></i>Data de Criação:
                    </span>
                    <span class="info-value">{{ [objeto].[data_criacao]|date:"d/m/Y" }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">
                        <i class="fas fa-toggle-on"></i>Status:
                    </span>
                    <span class="badge {% if [objeto].[status] == 'ATIVO' %}bg-success{% else %}bg-secondary{% endif %}">
                        {{ [objeto].[status] }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Seção 2: Informações Específicas -->
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">
                    <i class="fas fa-cog"></i>Informações Específicas
                </h5>
            </div>
            <div class="card-body">
                <!-- Adicionar campos específicos da entidade -->
            </div>
        </div>

        <!-- Seção 3: Dados Relacionados (se aplicável) -->
        <div class="card card-full-width">
            <div class="card-header">
                <h5 class="mb-0">
                    <i class="fas fa-list"></i>Dados Relacionados
                </h5>
            </div>
            <div class="card-body">
                <!-- Tabela ou lista de dados relacionados -->
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## 📋 Checklist para Implementação

### ✅ Estrutura Obrigatória
- [ ] Extends `base_list.html`
- [ ] Breadcrumb com navegação
- [ ] Header com título e ações
- [ ] Grid de 2 colunas para cards
- [ ] Cards com hover effects
- [ ] Responsividade mobile

### ✅ Elementos Visuais
- [ ] Ícones contextuais para cada campo
- [ ] Badges coloridos para status
- [ ] Cores sólidas (sem gradientes)
- [ ] Animações de entrada
- [ ] Hover effects nas linhas

### ✅ Funcionalidades
- [ ] Botões Voltar e Editar funcionais
- [ ] Cálculos automáticos (se aplicável)
- [ ] Valores monetários destacados
- [ ] Datas formatadas
- [ ] Campos com valores padrão

## 🎯 Entidades para Padronizar

1. **Produtos** (`stock/produtos/detail.html`)
2. **Inventários** (`stock/inventario/detail.html`)
3. **Requisições** (`stock/requisicoes/detail.html`)
4. **Transferências** (`stock/transferencias/detail.html`)
5. **Departamentos** (`rh/departamentos/detail.html`)
6. **Cargos** (`rh/cargos/detail.html`)
7. **Clientes** (`empresa/clientes/detail.html`)
8. **Fornecedores** (`empresa/fornecedores/detail.html`)

## 🚀 Próximos Passos

Quer que eu implemente este padrão em alguma página específica primeiro? Posso começar com:
- Produtos
- Inventários
- Departamentos
- Ou qualquer outra que você preferir!

O padrão está pronto para ser replicado em todo o sistema! 🎨✨
