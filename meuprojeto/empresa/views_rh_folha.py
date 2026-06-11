"""Views RH — folha salarial."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, IntegerField, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.utils import timezone
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import calendar
import logging
import os
import tempfile
from urllib.parse import urlencode
from django.urls import reverse

from .models_rh import (
    Funcionario, Departamento, Cargo, Presenca, TipoPresenca, Feriado, HorasExtras,
    Salario, BeneficioSalarial, DescontoSalarial, Treinamento, AvaliacaoDesempenho,
    CriterioAvaliacao, CriterioAvaliado, FolhaSalarial, FuncionarioFolha, Promocao,
    DepartamentoSucursal, TransferenciaFuncionario, InscricaoTreinamento,
)
from .models_base import Sucursal
from .views import (
    generate_pdf_report,
    generate_pdf_from_html,
    render_pdf_from_url,
    render_pdf_from_html_string,
)

logger = logging.getLogger(__name__)


@login_required
def rh_folha_salarial(request):
    """Lista de folhas salariais"""
    # Filtros
    mes_filter = request.GET.get('mes')
    status_filter = request.GET.get('status')
    search_filter = request.GET.get('search')
    
    folhas = FolhaSalarial.objects.all().order_by('-mes_referencia')
    
    # Aplicar filtros
    if mes_filter:
        folhas = folhas.filter(mes_referencia__year=mes_filter[:4], mes_referencia__month=mes_filter[5:7])
    if status_filter:
        folhas = folhas.filter(status=status_filter)
    if search_filter:
        folhas = folhas.filter(
            Q(mes_referencia__icontains=search_filter) |
            Q(observacoes__icontains=search_filter)
        )
    
    # Estatísticas
    total_folhas = folhas.count()
    folhas_abertas = folhas.filter(status='ABERTA').count()
    folhas_fechadas = folhas.filter(status='FECHADA').count()
    folhas_pagas = folhas.filter(status='PAGA').count()
    
    # Paginação
    paginator = Paginator(folhas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,  # Corrigido: template espera page_obj, não folhas
        'total_folhas': total_folhas,
        'folhas_abertas': folhas_abertas,
        'folhas_fechadas': folhas_fechadas,
        'folhas_pagas': folhas_pagas,
        'status_choices': FolhaSalarial.STATUS_CHOICES,
        'filtros': {
            'mes': mes_filter,
            'status': status_filter,
            'search': search_filter,
        }
    }
    
    return render(request, 'rh/folha_salarial/main.html', context)

@login_required
def rh_folha_add(request):
    """Adicionar folha salarial"""
    if request.method == 'POST':
        mes = request.POST.get('mes')
        ano = request.POST.get('ano')
        observacoes = request.POST.get('observacoes', '')
        
        if not all([mes, ano]):
            messages.error(request, 'Mês e ano são obrigatórios.')
        else:
            try:
                from datetime import date
                # Criar data de referência (primeiro dia do mês)
                mes_referencia = date(int(ano), int(mes), 1)
                
                # Verificar se já existe folha para este mês/ano
                if FolhaSalarial.objects.filter(mes_referencia=mes_referencia).exists():
                    messages.error(request, f'Já existe uma folha salarial para {mes}/{ano}.')
                else:
                    FolhaSalarial.objects.create(
                        mes_referencia=mes_referencia,
                        observacoes=observacoes,
                        status='ABERTA'
                    )
                    messages.success(request, f'Folha salarial para {mes}/{ano} criada com sucesso!')
                    return redirect('rh:folha_salarial')
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    context = {
        'mes_selected': int(request.POST.get('mes')) if request.POST.get('mes') else None,
        'ano_selected': request.POST.get('ano'),
    }
    return render(request, 'rh/folha_salarial/form.html', context)

@login_required
def rh_folha_detail(request, folha_id):
    """Detalhes da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        # Buscar funcionários da folha através da relação FuncionarioFolha
        funcionarios_folha = folha.funcionarios_folha.all().select_related('funcionario', 'funcionario__sucursal', 'funcionario__departamento', 'funcionario__cargo')
        
        # Buscar todos os funcionários ativos para adicionar à folha
        funcionarios_disponiveis = Funcionario.objects.filter(
            status='AT'
        ).exclude(
            id__in=funcionarios_folha.values_list('funcionario_id', flat=True)
        ).order_by('nome_completo')
        
        # Calcular totais
        total_funcionarios = funcionarios_folha.count()
        total_bruto = sum(f.salario_bruto for f in funcionarios_folha)
        total_descontos = sum(f.total_descontos for f in funcionarios_folha)
        total_liquido = sum(f.salario_liquido for f in funcionarios_folha)
        
        context = {
            'folha': folha,
            'funcionarios': funcionarios_folha,  # Corrigido: template espera 'funcionarios'
            'funcionarios_folha': funcionarios_folha,
            'funcionarios_disponiveis': funcionarios_disponiveis,
            'total_funcionarios': total_funcionarios,
            'total_bruto': total_bruto,
            'total_descontos': total_descontos,
            'total_liquido': total_liquido,
        }
        return render(request, 'rh/folha_salarial/detail.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_edit(request, folha_id):
    """Editar folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            from datetime import date
            mes = request.POST.get('mes')
            ano = request.POST.get('ano')
            observacoes = request.POST.get('observacoes', '')

            if not all([mes, ano]):
                messages.error(request, 'Mês e ano são obrigatórios.')
            else:
                try:
                    nova_referencia = date(int(ano), int(mes), 1)
                    if nova_referencia != folha.mes_referencia:
                        if folha.status != 'ABERTA':
                            messages.warning(request, 'O mês não foi alterado porque a folha não está aberta.')
                        elif FolhaSalarial.objects.filter(mes_referencia=nova_referencia).exclude(pk=folha.pk).exists():
                            messages.error(request, f'Já existe uma folha salarial para {mes}/{ano}.')
                        else:
                            folha.mes_referencia = nova_referencia
                    folha.observacoes = observacoes
                    folha.save()
                    messages.success(request, 'Folha salarial atualizada com sucesso!')
                    return redirect('rh:folha_detail', folha_id=folha.id)
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')

        context = {
            'folha': folha,
            'mes_selected': folha.mes_referencia.month,
            'ano_selected': folha.mes_referencia.year,
        }
        return render(request, 'rh/folha_salarial/form.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_delete(request, folha_id):
    """Deletar folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            folha.delete()
            messages.success(request, 'Folha salarial deletada com sucesso!')
            return redirect('rh:folha_salarial')
        
        context = {'folha': folha}
        return render(request, 'rh/folha_salarial/delete.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_calcular(request, folha_id):
    """Calcular folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            from django.core.exceptions import ValidationError as DjangoValidationError
            from .services.rh_folha_service import calcular_folha
            try:
                resultado = calcular_folha(folha)
                if resultado['funcionarios_adicionados'] > 0:
                    messages.success(
                        request,
                        f'Folha calculada: {resultado["funcionarios_adicionados"]} funcionário(s) adicionado(s).',
                    )
                else:
                    messages.success(request, 'Folha salarial recalculada com sucesso!')
            except DjangoValidationError as exc:
                messages.error(request, str(exc))
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {'folha': folha}
        return render(request, 'rh/folha_salarial/calcular.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_preview(request, folha_id):
    """Pré-visualização da folha salarial para impressão"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        # Buscar funcionários da folha
        funcionarios_folha = folha.funcionarios_folha.all().select_related('funcionario', 'funcionario__sucursal', 'funcionario__departamento', 'funcionario__cargo')
        
        # Calcular totais
        total_funcionarios = funcionarios_folha.count()
        total_bruto = sum(func.salario_bruto for func in funcionarios_folha)
        total_descontos = sum(func.total_descontos + func.desconto_faltas for func in funcionarios_folha)
        total_liquido = sum(func.salario_liquido for func in funcionarios_folha)
        
        context = {
            'folha': folha,
            'funcionarios': funcionarios_folha,
            'total_funcionarios': total_funcionarios,
            'total_bruto': total_bruto,
            'total_descontos': total_descontos,
            'total_liquido': total_liquido,
        }
        
        return render(request, 'rh/folha_salarial/preview.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')
    except Exception as e:
        messages.error(request, f'Erro ao gerar pré-visualização: {str(e)}')
        return redirect('rh:folha_detail', folha_id=folha_id)

@login_required
def rh_folha_pdf(request, folha_id):
    """Gerar PDF da folha salarial usando template HTML"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        # Buscar funcionários da folha
        funcionarios_folha = folha.funcionarios_folha.all().select_related('funcionario', 'funcionario__sucursal', 'funcionario__departamento', 'funcionario__cargo')
        
        # Calcular totais
        total_funcionarios = funcionarios_folha.count()
        total_bruto = sum(func.salario_bruto for func in funcionarios_folha)
        total_descontos = sum(func.total_descontos + func.desconto_faltas for func in funcionarios_folha)
        total_liquido = sum(func.salario_liquido for func in funcionarios_folha)
        
        context = {
            'folha': folha,
            'funcionarios': funcionarios_folha,
            'total_funcionarios': total_funcionarios,
            'total_bruto': total_bruto,
            'total_descontos': total_descontos,
            'total_liquido': total_liquido,
        }
        
        # Renderizar template HTML
        from django.template.loader import render_to_string
        html_string = render_to_string('rh/folha_salarial/pdf_template.html', context)
        
        # Gerar PDF com ReportLab (sem dependências nativas)
        return rh_folha_pdf_reportlab(request, folha_id)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')
    except Exception as e:
        messages.error(request, f'Erro ao gerar PDF: {str(e)}')
        return redirect('rh:folha_detail', folha_id=folha_id)

def rh_folha_pdf_reportlab(request, folha_id):
    """Fallback: Gerar PDF da folha salarial usando ReportLab"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from django.http import HttpResponse
        from io import BytesIO
        import locale
        
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        # Buscar funcionários da folha
        funcionarios_folha = folha.funcionarios_folha.all().select_related('funcionario', 'funcionario__sucursal', 'funcionario__departamento', 'funcionario__cargo')
        
        # Calcular totais
        total_funcionarios = funcionarios_folha.count()
        total_bruto = sum(func.salario_bruto for func in funcionarios_folha)
        total_descontos = sum(func.total_descontos + func.desconto_faltas for func in funcionarios_folha)
        total_liquido = sum(func.salario_liquido for func in funcionarios_folha)
        
        # Criar buffer para o PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        normal_style = styles['Normal']
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("FOLHA SALARIAL", title_style))
        story.append(Paragraph(f"Mês de Referência: {folha.mes_referencia.strftime('%B de %Y')}", subtitle_style))
        story.append(Paragraph(f"Status: {folha.get_status_display()}", subtitle_style))
        story.append(Spacer(1, 20))
        
        # Informações da empresa
        story.append(Paragraph("CONCEPTION - EMPRESA DE CONSTRUÇÃO E SERVIÇOS", subtitle_style))
        story.append(Spacer(1, 20))
        
        # Resumo financeiro
        resumo_data = [
            ['Total de Funcionários', f"{total_funcionarios}"],
            ['Total Bruto', f"{total_bruto:.2f} MT"],
            ['Total Descontos', f"{total_descontos:.2f} MT"],
            ['Total Líquido', f"{total_liquido:.2f} MT"]
        ]
        
        resumo_table = Table(resumo_data, colWidths=[8*cm, 4*cm])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(resumo_table)
        story.append(Spacer(1, 30))
        
        # Tabela de funcionários
        if funcionarios_folha:
            story.append(Paragraph("DETALHAMENTO POR FUNCIONÁRIO", subtitle_style))
            story.append(Spacer(1, 20))
            
            # Cabeçalho da tabela
            header_data = [
                'Funcionário', 'Departamento', 'Salário Base', 'Benefícios', 
                'Descontos', 'Faltas', 'Bruto', 'Líquido', 'Dias', 'Horas'
            ]
            
            # Dados dos funcionários
            funcionarios_data = [header_data]
            
            for func_folha in funcionarios_folha:
                funcionarios_data.append([
                    func_folha.funcionario.nome_completo,
                    func_folha.funcionario.departamento.nome if func_folha.funcionario.departamento else 'N/A',
                    f"{func_folha.salario_base:.2f}",
                    f"{func_folha.total_beneficios:.2f}",
                    f"{func_folha.total_descontos:.2f}",
                    f"{func_folha.desconto_faltas:.2f}",
                    f"{func_folha.salario_bruto:.2f}",
                    f"{func_folha.salario_liquido:.2f}",
                    str(func_folha.dias_trabalhados),
                    f"{func_folha.horas_trabalhadas:.1f}"
                ])
            
            # Criar tabela
            funcionarios_table = Table(funcionarios_data, colWidths=[3*cm, 2*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1.5*cm, 1*cm, 1*cm])
            funcionarios_table.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Linhas alternadas
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.beige, colors.white]),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(funcionarios_table)
        
        # Rodapé
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"Relatório gerado em: {timezone.now().strftime('%d/%m/%Y às %H:%M')}", normal_style))
        
        # Construir PDF
        doc.build(story)
        
        # Preparar resposta
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="folha_salarial_{folha.mes_referencia.strftime("%Y_%m")}.pdf"'
        
        return response
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')
    except Exception as e:
        messages.error(request, f'Erro ao gerar PDF: {str(e)}')
        return redirect('rh:folha_detail', folha_id=folha_id)

@login_required
def rh_folha_validar_fechamento(request, folha_id):
    """Validar e fechar a folha salarial (usa rh_folha_service.fechar_folha)."""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)

        if request.method == 'POST':
            from django.core.exceptions import ValidationError as DjangoValidationError
            from .services.rh_folha_service import fechar_folha
            try:
                fechar_folha(folha, user=request.user)
                messages.success(request, 'Folha validada e fechada com sucesso.')
            except DjangoValidationError as exc:
                messages.error(request, str(exc))
            return redirect('rh:folha_detail', folha_id=folha.id)

        context = {
            'folha': folha,
            'validacao': folha.validar_antes_fechar(),
        }
        return render(request, 'rh/folha_salarial/validar.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_fechar(request, folha_id):
    """Fechar folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            from django.core.exceptions import ValidationError as DjangoValidationError
            from .services.rh_folha_service import fechar_folha
            try:
                observacoes = request.POST.get('observacoes', '')
                fechar_folha(folha, user=request.user, observacoes=observacoes)
                messages.success(request, 'Folha fechada e pendente enviado a Finanças.')
            except DjangoValidationError as exc:
                messages.error(request, str(exc))
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {
            'folha': folha,
            'validacao': folha.validar_antes_fechar(),
        }
        return render(request, 'rh/folha_salarial/fechar.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_reabrir(request, folha_id):
    """Reabrir folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            from django.core.exceptions import ValidationError as DjangoValidationError
            from .services.rh_folha_service import reabrir_folha
            try:
                motivo = request.POST.get('motivo', '')
                reabrir_folha(folha, user=request.user, motivo=motivo)
                messages.success(request, 'Folha reaberta; pendente em Finanças cancelado.')
            except DjangoValidationError as exc:
                messages.error(request, str(exc))
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {'folha': folha}
        return render(request, 'rh/folha_salarial/reabrir.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_marcar_paga(request, folha_id):
    """Marcar folha salarial como paga"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            from django.core.exceptions import ValidationError as DjangoValidationError
            from .services.rh_folha_service import marcar_folha_paga
            try:
                observacoes = request.POST.get('observacoes', '')
                marcar_folha_paga(folha, observacoes=observacoes)
                messages.success(request, 'Folha salarial marcada como paga!')
            except DjangoValidationError as exc:
                messages.error(request, str(exc))
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {'folha': folha}
        return render(request, 'rh/folha_salarial/marcar_paga.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_funcionario_detail(request, folha_id, funcionario_id):
    """Detalhe do funcionário no contexto de uma folha salarial."""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        funcionario = Funcionario.objects.get(id=funcionario_id)
        from .services.rh_folha_service import montar_contexto_funcionario_folha_detail

        context = montar_contexto_funcionario_folha_detail(folha, funcionario)
        if context is None:
            messages.error(request, 'Funcionário não encontrado nesta folha salarial.')
            return redirect('rh:folha_detail', folha_id=folha_id)
        return render(request, 'rh/folha_salarial/funcionario_detail.html', context)
    except (FolhaSalarial.DoesNotExist, Funcionario.DoesNotExist):
        messages.error(request, 'Folha salarial ou funcionário não encontrado.')
        return redirect('rh:folha_salarial')


@login_required
def rh_canhoto_salario(request, folha_id, funcionario_id):
    """Gerar canhoto de salário"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        funcionario = Funcionario.objects.get(id=funcionario_id)
        
        # Por enquanto, redirecionar para visualização
        # Em uma implementação completa, aqui seria gerado o canhoto
        return redirect('rh:canhoto_visualizar', folha_id=folha_id, funcionario_id=funcionario_id)
        
    except (FolhaSalarial.DoesNotExist, Funcionario.DoesNotExist):
        messages.error(request, 'Folha salarial ou funcionário não encontrado.')
        return redirect('rh:folha_salarial')

@login_required
def rh_canhoto_visualizar(request, folha_id, funcionario_id):
    """Visualizar canhoto de salário"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        funcionario = Funcionario.objects.get(id=funcionario_id)
        
        # Buscar os dados da folha salarial do funcionário
        funcionario_folha = folha.funcionarios_folha.filter(funcionario=funcionario).first()
        
        if not funcionario_folha:
            messages.error(request, 'Funcionário não encontrado nesta folha salarial.')
            return redirect('rh:folha_salarial')
        
        # Recalcular salário para garantir que os descontos automáticos sejam aplicados
        funcionario_folha.calcular_salario()
        
        # Buscar dados da empresa
        from .models_base import DadosEmpresa
        empresa = DadosEmpresa.objects.filter(is_sede=True).first()
        
        context = {
            'folha': folha,
            'funcionario': funcionario,
            'funcionario_folha': funcionario_folha,
            'empresa': empresa,
        }
        return render(request, 'rh/folha_salarial/canhoto.html', context)

    except (FolhaSalarial.DoesNotExist, Funcionario.DoesNotExist):
        messages.error(request, 'Folha salarial ou funcionário não encontrado.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_beneficios(request, folha_id):
    """Lista de benefícios da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        # Buscar benefícios da folha (se existir o modelo)
        beneficios = []
        try:
            from meuprojeto.empresa.models_rh import BeneficioFolha
            beneficios = BeneficioFolha.objects.filter(folha=folha)
        except:
            pass
        
        context = {
            'folha': folha,
            'beneficios': beneficios,
        }
        return render(request, 'rh/folha_salarial/beneficios.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_beneficio_auto_add(request, folha_id):
    """Adicionar benefícios automaticamente baseados na configuração do funcionário"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            
            if not funcionario_id:
                messages.error(request, 'Funcionário é obrigatório.')
                return redirect('rh:folha_beneficios', folha_id=folha_id)
            
            try:
                funcionario = Funcionario.objects.get(id=funcionario_id)
                
                # Buscar funcionário na folha
                from meuprojeto.empresa.models_rh import FuncionarioFolha, BeneficioFolha
                funcionario_folha = FuncionarioFolha.objects.get(folha=folha, funcionario=funcionario)
                
                # Adicionar benefícios configurados para o funcionário
                beneficios_adicionados = 0
                for beneficio in funcionario.beneficios.filter(ativo=True):
                    # Verificar se já existe na folha
                    if not BeneficioFolha.objects.filter(funcionario_folha=funcionario_folha, beneficio=beneficio).exists():
                        # Calcular valor baseado no tipo
                        if beneficio.tipo_valor == 'FIXO':
                            valor = beneficio.valor
                        elif beneficio.tipo_valor == 'PERCENTUAL':
                            # Calcular percentual sobre a base de cálculo
                            if beneficio.base_calculo == 'SALARIO_BASE':
                                valor = funcionario_folha.salario_base * (beneficio.valor / 100)
                            else:
                                valor = beneficio.valor  # Fallback
                        else:  # NAO_MONETARIO
                            valor = 0
                        
                        BeneficioFolha.objects.create(
                            funcionario_folha=funcionario_folha,
                            beneficio=beneficio,
                            valor=valor,
                            observacoes=f'Aplicado automaticamente baseado na configuração do funcionário'
                        )
                        beneficios_adicionados += 1
                
                if beneficios_adicionados > 0:
                    messages.success(request, f'{beneficios_adicionados} benefício(s) adicionado(s) automaticamente!')
                else:
                    messages.info(request, 'Nenhum benefício novo foi adicionado. O funcionário já possui todos os benefícios configurados.')
                
                return redirect('rh:folha_beneficios', folha_id=folha_id)
                
            except Funcionario.DoesNotExist:
                messages.error(request, 'Funcionário não encontrado.')
            except FuncionarioFolha.DoesNotExist:
                messages.error(request, 'Funcionário não está na folha salarial.')
            except Exception as e:
                messages.error(request, f'Erro ao adicionar benefícios: {str(e)}')
        
        # Buscar funcionários da folha
        from meuprojeto.empresa.models_rh import FuncionarioFolha
        funcionarios_folha = FuncionarioFolha.objects.filter(folha=folha).select_related('funcionario')
        
        context = {
            'folha': folha,
            'funcionarios_folha': funcionarios_folha,
        }
        return render(request, 'rh/folha_salarial/beneficio_auto_form.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_beneficio_add(request, folha_id):
    """Adicionar benefício à folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            beneficio_id = request.POST.get('beneficio')
            valor = request.POST.get('valor')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([funcionario_id, beneficio_id, valor]):
                messages.error(request, 'Funcionário, benefício e valor são obrigatórios.')
            else:
                try:
                    from meuprojeto.empresa.models_rh import BeneficioFolha
                    BeneficioFolha.objects.create(
                        folha=folha,
                        funcionario_id=funcionario_id,
                        beneficio_id=beneficio_id,
                        valor=Decimal(valor),
                        observacoes=observacoes
                    )
                    messages.success(request, 'Benefício adicionado com sucesso!')
                    return redirect('rh:folha_beneficios', folha_id=folha_id)
                except Exception as e:
                    messages.error(request, f'Erro ao adicionar benefício: {str(e)}')
        
        funcionarios = Funcionario.objects.filter(sucursal=folha.sucursal, status='AT')
        beneficios = BeneficioSalarial.objects.filter(ativo=True)
        
        context = {
            'folha': folha,
            'funcionarios': funcionarios,
            'beneficios': beneficios,
        }
        return render(request, 'rh/folha_salarial/beneficio_form.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_beneficio_edit(request, folha_id, beneficio_folha_id):
    """Editar benefício da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        from meuprojeto.empresa.models_rh import BeneficioFolha
        beneficio = BeneficioFolha.objects.get(id=beneficio_folha_id, folha=folha)
        
        if request.method == 'POST':
            valor = request.POST.get('valor')
            observacoes = request.POST.get('observacoes', '')
            
            if valor:
                try:
                    beneficio.valor = Decimal(valor)
                    beneficio.observacoes = observacoes
                    beneficio.save()
                    messages.success(request, 'Benefício atualizado com sucesso!')
                    return redirect('rh:folha_beneficios', folha_id=folha_id)
                except Exception as e:
                    messages.error(request, f'Erro ao atualizar benefício: {str(e)}')
        
        context = {
            'folha': folha,
            'beneficio': beneficio,
        }
        return render(request, 'rh/folha_salarial/beneficio_form.html', context)
        
    except (FolhaSalarial.DoesNotExist, BeneficioFolha.DoesNotExist):
        messages.error(request, 'Folha salarial ou benefício não encontrado.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_beneficio_delete(request, folha_id, beneficio_folha_id):
    """Deletar benefício da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        from meuprojeto.empresa.models_rh import BeneficioFolha
        beneficio = BeneficioFolha.objects.get(id=beneficio_folha_id, folha=folha)
        
        if request.method == 'POST':
            beneficio.delete()
            messages.success(request, 'Benefício deletado com sucesso!')
            return redirect('rh:folha_beneficios', folha_id=folha_id)
        
        context = {
            'folha': folha,
            'beneficio': beneficio,
        }
        return render(request, 'rh/folha_salarial/beneficio_delete.html', context)
        
    except (FolhaSalarial.DoesNotExist, BeneficioFolha.DoesNotExist):
        messages.error(request, 'Folha salarial ou benefício não encontrado.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_descontos(request, folha_id):
    """Lista de descontos da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        # Buscar descontos da folha (se existir o modelo)
        descontos = []
        try:
            from meuprojeto.empresa.models_rh import DescontoFolha
            descontos = DescontoFolha.objects.filter(folha=folha)
        except:
            pass
        
        context = {
            'folha': folha,
            'descontos': descontos,
        }
        return render(request, 'rh/folha_salarial/descontos.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_desconto_auto_add(request, folha_id):
    """Adicionar descontos automaticamente baseados na configuração do funcionário"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            
            if not funcionario_id:
                messages.error(request, 'Funcionário é obrigatório.')
                return redirect('rh:folha_descontos', folha_id=folha_id)
            
            try:
                funcionario = Funcionario.objects.get(id=funcionario_id)
                
                # Buscar funcionário na folha
                from meuprojeto.empresa.models_rh import FuncionarioFolha, DescontoFolha
                funcionario_folha = FuncionarioFolha.objects.get(folha=folha, funcionario=funcionario)
                
                # Adicionar descontos configurados para o funcionário
                descontos_adicionados = 0
                for desconto in funcionario.descontos.filter(ativo=True):
                    # Verificar se já existe na folha
                    if not DescontoFolha.objects.filter(funcionario_folha=funcionario_folha, desconto=desconto).exists():
                        # Calcular valor baseado no tipo
                        if desconto.tipo_valor == 'FIXO':
                            valor = desconto.valor
                        elif desconto.tipo_valor == 'PERCENTUAL':
                            # Calcular percentual sobre a base de cálculo
                            if desconto.base_calculo == 'SALARIO_BASE':
                                valor = funcionario_folha.salario_base * (desconto.valor / 100)
                            else:
                                valor = desconto.valor  # Fallback
                        else:  # NAO_MONETARIO
                            valor = 0
                        
                        DescontoFolha.objects.create(
                            funcionario_folha=funcionario_folha,
                            desconto=desconto,
                            valor=valor,
                            observacoes=f'Aplicado automaticamente baseado na configuração do funcionário'
                        )
                        descontos_adicionados += 1
                
                if descontos_adicionados > 0:
                    messages.success(request, f'{descontos_adicionados} desconto(s) adicionado(s) automaticamente!')
                else:
                    messages.info(request, 'Nenhum desconto novo foi adicionado. O funcionário já possui todos os descontos configurados.')
                
                return redirect('rh:folha_descontos', folha_id=folha_id)
                
            except Funcionario.DoesNotExist:
                messages.error(request, 'Funcionário não encontrado.')
            except FuncionarioFolha.DoesNotExist:
                messages.error(request, 'Funcionário não está na folha salarial.')
            except Exception as e:
                messages.error(request, f'Erro ao adicionar descontos: {str(e)}')
        
        # Buscar funcionários da folha
        from meuprojeto.empresa.models_rh import FuncionarioFolha
        funcionarios_folha = FuncionarioFolha.objects.filter(folha=folha).select_related('funcionario')
        
        context = {
            'folha': folha,
            'funcionarios_folha': funcionarios_folha,
        }
        return render(request, 'rh/folha_salarial/desconto_auto_form.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_desconto_add(request, folha_id):
    """Adicionar desconto à folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            desconto_id = request.POST.get('desconto')
            valor = request.POST.get('valor')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([funcionario_id, desconto_id, valor]):
                messages.error(request, 'Funcionário, desconto e valor são obrigatórios.')
            else:
                try:
                    from meuprojeto.empresa.models_rh import DescontoFolha
                    DescontoFolha.objects.create(
                        folha=folha,
                        funcionario_id=funcionario_id,
                        desconto_id=desconto_id,
                        valor=Decimal(valor),
                        observacoes=observacoes
                    )
                    messages.success(request, 'Desconto adicionado com sucesso!')
                    return redirect('rh:folha_descontos', folha_id=folha_id)
                except Exception as e:
                    messages.error(request, f'Erro ao adicionar desconto: {str(e)}')
        
        funcionarios = Funcionario.objects.filter(sucursal=folha.sucursal, status='AT')
        descontos = DescontoSalarial.objects.filter(ativo=True)
        
        context = {
            'folha': folha,
            'funcionarios': funcionarios,
            'descontos': descontos,
        }
        return render(request, 'rh/folha_salarial/desconto_form.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_desconto_edit(request, folha_id, desconto_folha_id):
    """Editar desconto da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        from meuprojeto.empresa.models_rh import DescontoFolha
        desconto = DescontoFolha.objects.get(id=desconto_folha_id, folha=folha)
        
        if request.method == 'POST':
            valor = request.POST.get('valor')
            observacoes = request.POST.get('observacoes', '')
            
            if valor:
                try:
                    desconto.valor = Decimal(valor)
                    desconto.observacoes = observacoes
                    desconto.save()
                    messages.success(request, 'Desconto atualizado com sucesso!')
                    return redirect('rh:folha_descontos', folha_id=folha_id)
                except Exception as e:
                    messages.error(request, f'Erro ao atualizar desconto: {str(e)}')
        
        context = {
            'folha': folha,
            'desconto': desconto,
        }
        return render(request, 'rh/folha_salarial/desconto_form.html', context)
        
    except (FolhaSalarial.DoesNotExist, DescontoFolha.DoesNotExist):
        messages.error(request, 'Folha salarial ou desconto não encontrado.')
        return redirect('rh:folha_salarial')

@login_required
def rh_folha_desconto_delete(request, folha_id, desconto_folha_id):
    """Deletar desconto da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        from meuprojeto.empresa.models_rh import DescontoFolha
        desconto = DescontoFolha.objects.get(id=desconto_folha_id, folha=folha)
        
        if request.method == 'POST':
            desconto.delete()
            messages.success(request, 'Desconto deletado com sucesso!')
            return redirect('rh:folha_descontos', folha_id=folha_id)
        
        context = {
            'folha': folha,
            'desconto': desconto,
        }
        return render(request, 'rh/folha_salarial/desconto_delete.html', context)
        
    except (FolhaSalarial.DoesNotExist, DescontoFolha.DoesNotExist):
        messages.error(request, 'Folha salarial ou desconto não encontrado.')
        return redirect('rh:folha_salarial')
