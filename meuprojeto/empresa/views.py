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
import asyncio
import subprocess
import shutil
from urllib.parse import urlencode
from django.urls import reverse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import logging
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import tempfile
import os
from .models_rh import Funcionario, Departamento, Cargo, Presenca, TipoPresenca, Feriado, HorasExtras, Salario, BeneficioSalarial, DescontoSalarial, Treinamento, AvaliacaoDesempenho, CriterioAvaliacao, CriterioAvaliado, FolhaSalarial, FuncionarioFolha, Promocao, DepartamentoSucursal, TransferenciaFuncionario, InscricaoTreinamento

# Configurar logger
logger = logging.getLogger(__name__)
from .models_base import Sucursal

# =============================================================================
# UTILITÁRIOS PARA PDF
# =============================================================================

def generate_pdf_report(title, data, filename):
    """Gera PDF usando ReportLab"""
    try:
        # Criar arquivo temporário
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.close()
        
        # Criar documento PDF
        doc = SimpleDocTemplate(temp_file.name, pagesize=A4)
        story = []
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            textColor=colors.darkblue
        )
        
        normal_style = styles['Normal']
        
        # Título do documento
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # Data de geração
        story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", normal_style))
        story.append(Spacer(1, 20))
        
        # Processar dados
        for section_title, section_data in data.items():
            story.append(Paragraph(section_title, heading_style))
            
            if isinstance(section_data, list) and section_data:
                # Criar tabela para dados em lista
                if isinstance(section_data[0], dict):
                    # Dados em formato de dicionário
                    headers = list(section_data[0].keys())
                    table_data = [headers]
                    
                    for row in section_data:
                        table_data.append([str(row.get(header, '')) for header in headers])
                    
                    table = Table(table_data)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)
                    ]))
                    story.append(table)
                else:
                    # Dados simples em lista
                    for item in section_data:
                        story.append(Paragraph(f"• {str(item)}", normal_style))
            else:
                # Dados simples
                story.append(Paragraph(str(section_data), normal_style))
            
            story.append(Spacer(1, 20))
        
        # Construir PDF
        doc.build(story)
        
        # Ler arquivo e criar resposta
        with open(temp_file.name, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
        
        # Limpar arquivo temporário
        os.unlink(temp_file.name)
        
        # Criar resposta HTTP
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        # Em caso de erro, retornar uma resposta de erro
        return HttpResponse(f'Erro ao gerar PDF: {str(e)}', status=500)

def generate_pdf_from_html(html_content, filename):
    """Compat: gera PDF simples via ReportLab, ignorando HTML (sem dependências nativas)."""
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.close()

        doc = SimpleDocTemplate(temp_file.name, pagesize=A4)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'PdfTitle', parent=styles['Heading1'], fontSize=16, alignment=TA_CENTER, textColor=colors.darkblue
        )
        normal_style = styles['Normal']

        story = []
        story.append(Paragraph('Exportação PDF (modo simples)', title_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(datetime.now().strftime('%d/%m/%Y %H:%M'), normal_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph('Conteúdo renderizado sem engine HTML por compatibilidade.', normal_style))

        doc.build(story)

        with open(temp_file.name, 'rb') as f:
            pdf_bytes = f.read()
        os.unlink(temp_file.name)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return HttpResponse(f'Erro ao gerar PDF: {str(e)}', status=500)

def _find_chromium_executable() -> str | None:
    # Prefer env vars
    for env_var in [
        'PUPPETEER_EXECUTABLE_PATH',
        'CHROME_PATH',
        'GOOGLE_CHROME_BIN',
        'EDGE_PATH',
    ]:
        path = os.environ.get(env_var)
        if path and os.path.exists(path):
            return path

    # Common Windows paths (Chrome, Edge)
    candidates = [
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    ]
    for exe in candidates:
        if os.path.exists(exe):
            return exe

    # Last resort: locate via PATH
    for name in ["chrome.exe", "msedge.exe", "chromium.exe"]:
        found = shutil.which(name)
        if found:
            return found
    return None

async def _chromium_render_pdf(url: str, landscape: bool = False, scale: float = 1.0) -> bytes:
    try:
        from pyppeteer import launch
    except Exception as e:
        raise RuntimeError(f'Chromium não disponível: {e}')

    executable_path = _find_chromium_executable()
    launch_kwargs = {
        'headless': True,
        'args': [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--font-render-hinting=none',
        ],
    }
    # If local Chrome/Edge found, use it to avoid downloading snapshots
    if executable_path:
        launch_kwargs['executablePath'] = executable_path

    browser = await launch(**launch_kwargs)
    try:
        page = await browser.newPage()
        await page.goto(url, {'waitUntil': 'networkidle0'})
        pdf_bytes = await page.pdf({
            'format': 'A4',
            'printBackground': True,
            'landscape': landscape,
            'scale': scale,
            'margin': {'top': '10mm', 'right': '10mm', 'bottom': '10mm', 'left': '10mm'},
        })
        await page.close()
        return pdf_bytes
    finally:
        await browser.close()

def render_pdf_from_url(request, url: str, filename: str, *, landscape: bool = False, scale: float = 1.0) -> HttpResponse:
    # Primeiro: tentar Chrome/Edge via subprocess (mais estável em Windows/threads)
    try:
        exec_path = _find_chromium_executable()
        if not exec_path:
            raise RuntimeError('Chrome/Edge não encontrado no sistema')

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.close()

        args = [
            exec_path,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            f'--print-to-pdf={temp_file.name}',
            '--print-to-pdf-no-header',
        ]
        if landscape:
            args.append('--landscape')
        # Chrome não aceita scale direto em CLI; usar default
        args.append(url)

        completed = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.decode(errors='ignore') or 'Falha ao gerar PDF com Chrome')

        with open(temp_file.name, 'rb') as f:
            pdf_bytes = f.read()
        os.unlink(temp_file.name)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        # Fallback: pyppeteer (se compatível)
        try:
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
            except Exception:
                pass
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                pdf_bytes = loop.run_until_complete(_chromium_render_pdf(url, landscape=landscape, scale=scale))
            finally:
                loop.close()
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:
            return HttpResponse(f'Erro ao gerar PDF: {str(e)}', status=500)

def render_pdf_from_html_string(request, html_content: str, filename: str, *, landscape: bool = False) -> HttpResponse:
    # Gera um ficheiro HTML temporário com <base href> para resolver recursos relativos
    import uuid
    temp_html_path = None
    temp_pdf_path = None
    
    try:
        base_href = request.build_absolute_uri('/')
        # Inserir <base> após <head>
        if '</head>' in html_content.lower() or '<head' in html_content.lower():
            # Inserção simples e tolerante a maiúsculas/minúsculas
            insert_idx = html_content.lower().find('<head')
            if insert_idx != -1:
                close_idx = html_content.lower().find('>', insert_idx)
                if close_idx != -1:
                    html_content = html_content[:close_idx+1] + f"\n<base href=\"{base_href}\">\n" + html_content[close_idx+1:]

        # Criar arquivos temporários com nomes únicos
        temp_html_path = os.path.join(tempfile.gettempdir(), f"temp_html_{uuid.uuid4().hex}.html")
        temp_pdf_path = os.path.join(tempfile.gettempdir(), f"temp_pdf_{uuid.uuid4().hex}.pdf")
        
        with open(temp_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        exec_path = _find_chromium_executable()
        if not exec_path:
            raise RuntimeError('Chrome/Edge não encontrado no sistema')

        args = [
            exec_path,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            f'--print-to-pdf={temp_pdf_path}',
            '--print-to-pdf-no-header',
        ]
        if landscape:
            args.append('--landscape')
        args.append(f'file:///{temp_html_path.replace("\\", "/")}')

        completed = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.decode(errors='ignore') or 'Falha ao gerar PDF com Chrome')

        with open(temp_pdf_path, 'rb') as f:
            pdf_bytes = f.read()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        return HttpResponse(f'Erro ao gerar PDF: {str(e)}', status=500)
    finally:
        # Limpar arquivos temporários
        for temp_path in [temp_html_path, temp_pdf_path]:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"Não foi possível remover arquivo temporário {temp_path}: {cleanup_error}")

# =============================================================================
# VIEWS PRINCIPAIS DO RH
# =============================================================================

@login_required
def rh_main(request):
    """Página principal do módulo RH"""
    context = {
        'total_funcionarios': Funcionario.objects.count(),
        'presenca_hoje': '0%',
        'treinamentos_ativos': 0,
        'avaliacoes_pendentes': 0,
    }
    return render(request, 'rh/main.html', context)

# =============================================================================
# GESTÃO DE FUNCIONÁRIOS
# =============================================================================

@login_required
def rh_funcionarios(request):
    """Lista de funcionários com filtros e paginação"""
    try:
        # Parâmetros de busca e filtro
        search_query = request.GET.get('q', '').strip()
        departamento_id = request.GET.get('departamento')
        cargo_id = request.GET.get('cargo')
        status = request.GET.get('status')

        # Query base com otimizações
        funcionarios = Funcionario.objects.select_related('departamento', 'cargo', 'sucursal')

        # Aplicar filtros
        if search_query:
            funcionarios = funcionarios.filter(
                Q(nome_completo__icontains=search_query) |
                Q(codigo_funcionario__icontains=search_query) |
                Q(nuit__icontains=search_query) |
                Q(email__icontains=search_query)
            )

        if departamento_id:
            funcionarios = funcionarios.filter(departamento_id=departamento_id)

        if cargo_id:
            funcionarios = funcionarios.filter(cargo_id=cargo_id)

        if status:
            funcionarios = funcionarios.filter(status=status)

        # Ordenação
        funcionarios = funcionarios.order_by('nome_completo')

        # Paginação
        paginator = Paginator(funcionarios, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Calcular estatísticas
        total_funcionarios = Funcionario.objects.count()
        funcionarios_ativos = Funcionario.objects.filter(status='AT').count()
        total_departamentos = Departamento.objects.count()
        total_cargos = Cargo.objects.count()

        context = {
            'page_obj': page_obj,
            'search_query': search_query,
            'departamento_id': departamento_id,
            'cargo_id': cargo_id,
            'status': status,
            'departamentos': Departamento.objects.filter(ativo=True),
            'cargos': Cargo.objects.filter(ativo=True),
            'status_choices': Funcionario.STATUS_CHOICES,
            # Estatísticas para os cards
            'total_funcionarios': total_funcionarios,
            'funcionarios_ativos': funcionarios_ativos,
            'total_departamentos': total_departamentos,
            'total_cargos': total_cargos,
        }

        return render(request, 'rh/funcionarios/main.html', context)
    except Exception as e:
        logger.error(f"Erro ao listar funcionários: {e}")
        messages.error(request, 'Erro ao carregar lista de funcionários.')
        return render(request, 'rh/funcionarios/main.html', {'page_obj': None})

@login_required
def rh_funcionario_detail(request, id):
    """Detalhes de um funcionário específico"""
    funcionario = get_object_or_404(Funcionario, id=id)
    
    # Calcular dados adicionais
    hoje = date.today()
    
    # Calcular idade
    if funcionario.data_nascimento:
        idade = hoje.year - funcionario.data_nascimento.year
        if hoje.month < funcionario.data_nascimento.month or (hoje.month == funcionario.data_nascimento.month and hoje.day < funcionario.data_nascimento.day):
            idade -= 1
    else:
        idade = None
    
    # Calcular tempo de empresa
    if funcionario.data_admissao:
        tempo_empresa = hoje - funcionario.data_admissao
        anos = tempo_empresa.days // 365
        meses = (tempo_empresa.days % 365) // 30
        dias = tempo_empresa.days % 30
        tempo_empresa_str = f"{anos} anos, {meses} meses e {dias} dias"
    else:
        tempo_empresa_str = "Não informado"
    
    # Buscar folhas recentes do funcionário
    from meuprojeto.empresa.models_rh import FolhaSalarial, FuncionarioFolha
    folhas_recentes = FolhaSalarial.objects.filter(
        funcionarios_folha__funcionario=funcionario
    ).order_by('-mes_referencia')[:5]
    
    # Calcular remunerações
    remuneracao_hora_real = funcionario.get_remuneracao_por_hora()
    remuneracao_hora_teorica = funcionario.get_remuneracao_por_hora_teorica()
    remuneracao_dia_real = funcionario.get_remuneracao_por_dia()
    
    context = {
        'funcionario': funcionario,
        'idade': idade,
        'tempo_empresa': tempo_empresa_str,
        'folhas_recentes': folhas_recentes,
        'remuneracao_hora_real': remuneracao_hora_real,
        'remuneracao_hora_teorica': remuneracao_hora_teorica,
        'remuneracao_dia_real': remuneracao_dia_real,
    }
    
    return render(request, 'rh/funcionarios/detail.html', context)

# =============================================================================
# GESTÃO DE PRESENÇAS
# =============================================================================

@login_required
def rh_presencas(request):
    """Lista de presenças com resumo mensal por funcionário"""
    # Parâmetros de filtro
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Filtrar presenças do mês
    presencas = Presenca.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'tipo_presenca')
    
    if funcionario_id:
        presencas = presencas.filter(funcionario_id=funcionario_id)
    
    # Agrupar presenças por funcionário e tipo para resumo mensal
    resumo_funcionarios = presencas.values(
        'funcionario__id',
        'funcionario__nome_completo',
        'funcionario__codigo_funcionario'
    ).annotate(
        total_presente=Count(Case(When(tipo_presenca__codigo='PR', then=1), output_field=IntegerField())),
        total_ausente=Count(Case(When(tipo_presenca__codigo='AU', then=1), output_field=IntegerField())),
        total_falta_justificada=Count(Case(When(tipo_presenca__codigo='FJ', then=1), output_field=IntegerField())),
        total_atraso=Count(Case(When(tipo_presenca__codigo='AT', then=1), output_field=IntegerField())),
        total_licenca=Count(Case(When(tipo_presenca__codigo='LI', then=1), output_field=IntegerField())),
        total_ferias=Count(Case(When(tipo_presenca__codigo='FE', then=1), output_field=IntegerField())),
        total_registros=Count('id')
    ).order_by('funcionario__nome_completo')
    
    # Calcular dias úteis do mês (excluindo feriados)
    dias_uteis = calcular_dias_uteis(ano, mes)
    
    # Calcular estatísticas adicionais
    total_presencas = presencas.count()
    total_funcionarios = Funcionario.objects.filter(status='AT').count()
    
    # Resumo por tipo de presença
    resumo_por_tipo = presencas.values('tipo_presenca__codigo', 'tipo_presenca__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Anos disponíveis (últimos 5 anos)
    anos_disponiveis = list(range(ano - 2, ano + 3))
    
    # Calcular horas extras do mês atual
    from meuprojeto.empresa.models_rh import HorasExtras
    from django.db.models import Sum
    
    horas_extras_mes = HorasExtras.objects.filter(
        data__year=ano,
        data__month=mes
    ).aggregate(
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    )
    
    total_horas_extras_mes = float(horas_extras_mes['total_horas'] or 0)
    total_valor_horas_extras_mes = float(horas_extras_mes['total_valor'] or 0)
    
    # Criar dados para resumo anual (simulado)
    page_obj = []
    for mes_num in range(1, 13):
        mes_nome = calendar.month_name[mes_num]
        
        # Calcular horas extras para cada mês
        horas_extras_mes_anual = HorasExtras.objects.filter(
            data__year=ano,
            data__month=mes_num
        ).aggregate(
            total_horas=Sum('quantidade_horas'),
            total_valor=Sum('valor_total')
        )
        
        
        # Calcular presenças por tipo para o mês
        presencas_mes = Presenca.objects.filter(
            data__year=ano,
            data__month=mes_num
        ).values('tipo_presenca__codigo').annotate(
            total=Count('id')
        )
        
        # Inicializar contadores
        total_presente = 0
        total_ausente = 0
        total_falta_justificada = 0
        total_atraso = 0
        total_licenca = 0
        total_ferias = 0
        total_registros = 0
        
        # Processar presenças
        for presenca in presencas_mes:
            codigo = presenca['tipo_presenca__codigo']
            total = presenca['total']
            total_registros += total
            
            if codigo == 'PR':
                total_presente = total
            elif codigo == 'AU':
                total_ausente = total
            elif codigo == 'FJ':
                total_falta_justificada = total
            elif codigo == 'AT':
                total_atraso = total
            elif codigo == 'LI':
                total_licenca = total
            elif codigo == 'FE':
                total_ferias = total
        
        page_obj.append({
            'mes_num': mes_num,
            'mes_nome': mes_nome,
            'total_presente': total_presente,
            'total_ausente': total_ausente,
            'total_falta_justificada': total_falta_justificada,
            'total_atraso': total_atraso,
            'total_licenca': total_licenca,
            'total_ferias': total_ferias,
            'total_horas_extras': float(horas_extras_mes_anual['total_horas'] or 0),
            'total_valor_horas_extras': float(horas_extras_mes_anual['total_valor'] or 0),
            'total_registros': total_registros,
            'dias_uteis': len(calcular_dias_uteis(ano, mes_num)),
            'primeiro_dia': date(ano, mes_num, 1),
            'ultimo_dia': date(ano, mes_num, calendar.monthrange(ano, mes_num)[1])
        })
    
    from django.utils import timezone
    
    context = {
        'presencas': presencas,
        'resumo_funcionarios': resumo_funcionarios,
        'mes': mes,
        'ano': ano,
        'dias_uteis': len(dias_uteis),
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'funcionario_id': funcionario_id,
        'total_presencas': total_presencas,
        'total_funcionarios': total_funcionarios,
        'resumo_por_tipo': resumo_por_tipo,
        'anos_disponiveis': anos_disponiveis,
        'page_obj': page_obj,
        'mes_atual': date.today().month,
        'total_horas_extras': total_horas_extras_mes,
        'total_valor_horas_extras': total_valor_horas_extras_mes,
        'timestamp': int(timezone.now().timestamp()),
    }
    
    return render(request, 'rh/presencas/main.html', context)

@login_required
def rh_calendario_presencas(request, template_name='rh/presencas/calendario.html'):
    """Calendário de presenças com marcação visual"""
    import calendar
    from datetime import datetime
    
    # Parâmetros
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Buscar presenças do mês
    presencas = Presenca.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'tipo_presenca')
    
    if funcionario_id:
        presencas = presencas.filter(funcionario_id=funcionario_id)
    
    # Criar dicionário de presenças por data
    presencas_por_data = {}
    for presenca in presencas:
        data_str = presenca.data.strftime('%Y-%m-%d')
        if data_str not in presencas_por_data:
            presencas_por_data[data_str] = []
        presencas_por_data[data_str].append(presenca)
    
    # Calcular dias úteis
    dias_uteis = calcular_dias_uteis(ano, mes)
    
    # Gerar dados dos dias do mês
    dias_detalhados = []
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    
    for dia in range(1, ultimo_dia + 1):
        data_atual = date(ano, mes, dia)
        dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
        e_fim_semana = dia_semana >= 5  # sábado=5, domingo=6
        
        dias_detalhados.append({
            'dia': dia,
            'dia_semana': dia_semana,
            'e_fim_semana': e_fim_semana,
            'data': data_atual
        })
    
    # Funcionários para exibir
    funcionarios_exibir = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    if funcionario_id:
        funcionarios_exibir = funcionarios_exibir.filter(id=funcionario_id)
    
    # Criar dicionário de presenças para JavaScript
    presencas_dict = {}
    for presenca in presencas:
        chave = f"{presenca.funcionario.id}_{presenca.data.day}"
        presencas_dict[chave] = {
            'id': presenca.id,
            'tipo': presenca.tipo_presenca.codigo,
            'tipo_nome': presenca.tipo_presenca.nome,
            'tipo_cor': presenca.tipo_presenca.cor,
            'observacoes': presenca.observacoes or ''
        }
    
    
    # Lista de meses
    meses = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    # Lista de anos (últimos 5 anos + próximos 2)
    anos = list(range(ano - 5, ano + 3))
    
    import json
    from django.core.serializers import serialize
    
    # Serializar os tipos de presença para JSON
    tipos_presenca = TipoPresenca.objects.all()
    tipos_presenca_json = json.dumps([{
        'id': tp.id,
        'nome': tp.nome,
        'codigo': tp.codigo,
        'cor': tp.cor or '#cccccc',
        'desconta_salario': tp.desconta_salario,
        'ativo': tp.ativo
    } for tp in tipos_presenca])
    
    # Buscar feriados do mês
    feriados = Feriado.objects.filter(
        data__year=ano,
        data__month=mes,
        ativo=True
    ).order_by('data')
    
    # Criar dicionário de feriados para JavaScript
    feriados_dict = {}
    for feriado in feriados:
        chave = f"feriado_{feriado.data.day}"
        feriados_dict[chave] = {
            'nome': feriado.nome,
            'tipo': feriado.tipo,
            'descricao': feriado.descricao or ''
        }
    
    context = {
        'mes': mes,
        'ano': ano,
        'mes_nome': meses[mes - 1],
        'mes_atual': date.today().month,
        'ano_atual': date.today().year,
        'presencas_por_data': presencas_por_data,
        'presencas_dict': json.dumps(presencas_dict),
        'dias_uteis': dias_uteis,
        'dias_detalhados': dias_detalhados,
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'funcionarios_exibir': funcionarios_exibir,
        'funcionario_id': funcionario_id,
        'tipos_presenca': tipos_presenca,
        'tipos_presenca_json': tipos_presenca_json,
        'feriados': feriados,
        'feriados_dict': json.dumps(feriados_dict),
        'meses': meses,
        'anos': anos,
    }
    
    return render(request, template_name, context)

@login_required
def rh_calendario_debug(request):
    """Calendário de presenças - versão debug"""
    import calendar
    from datetime import datetime, date
    
    # Parâmetros
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Buscar presenças do mês
    presencas = Presenca.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'tipo_presenca')
    
    if funcionario_id:
        presencas = presencas.filter(funcionario_id=funcionario_id)
    
    # Gerar dados dos dias do mês
    dias_detalhados = []
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    
    for dia in range(1, ultimo_dia + 1):
        data_atual = date(ano, mes, dia)
        dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
        e_fim_semana = dia_semana >= 5  # sábado=5, domingo=6
        
        dias_detalhados.append({
            'dia': dia,
            'dia_semana': dia_semana,
            'e_fim_semana': e_fim_semana,
            'data': data_atual
        })
    
    # Funcionários para exibir
    funcionarios_exibir = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    if funcionario_id:
        funcionarios_exibir = funcionarios_exibir.filter(id=funcionario_id)
    
    # Criar dicionário de presenças para JavaScript
    presencas_dict = {}
    for presenca in presencas:
        chave = f"{presenca.funcionario.id}_{presenca.data.day}"
        presencas_dict[chave] = {
            'id': presenca.id,
            'tipo': presenca.tipo_presenca.codigo,
            'tipo_nome': presenca.tipo_presenca.nome,
            'tipo_cor': presenca.tipo_presenca.cor,
            'observacoes': presenca.observacoes or ''
        }
    
    import json
    
    context = {
        'mes': mes,
        'ano': ano,
        'presencas_dict': json.dumps(presencas_dict),
        'dias_detalhados': dias_detalhados,
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'funcionarios_exibir': funcionarios_exibir,
        'funcionario_id': funcionario_id,
    }
    
    return render(request, 'rh/presencas/calendario_debug.html', context)

@login_required
def rh_salvar_presenca_calendario(request):
    """Salvar presença via AJAX no calendário"""
    if request.method == 'POST':
        try:
            import json
            import logging
            logger = logging.getLogger(__name__)
            
            # Verificar se é JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                funcionario_id = data.get('funcionario_id')
                dia = data.get('dia')
                mes = data.get('mes')
                ano = data.get('ano')
                tipo_presenca_id = data.get('tipo_presenca_id')
                observacoes = data.get('observacoes', '')
                
                # Log dos dados recebidos
                logger.info(f"Dados recebidos: funcionario_id={funcionario_id}, dia={dia}, mes={mes}, ano={ano}, tipo_presenca_id={tipo_presenca_id}, observacoes={observacoes}")
                
                # Construir data da presença
                data_presenca = date(ano, mes, dia)
            else:
                # Fallback para form data
                funcionario_id = request.POST.get('funcionario_id')
                data_presenca = request.POST.get('data')
                tipo_presenca_id = request.POST.get('tipo_presenca_id')
                observacoes = request.POST.get('observacoes', '')
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, id=tipo_presenca_id)
            
            # Verificar se já existe presença para esta data
            presenca_existente = Presenca.objects.filter(
                funcionario=funcionario,
                data=data_presenca
            ).first()
            
            if presenca_existente:
                # Atualizar presença existente
                presenca_existente.tipo_presenca = tipo_presenca
                presenca_existente.observacoes = observacoes
                presenca_existente.save()
                logger.info(f"Presença atualizada: ID={presenca_existente.id}")
                action = 'updated'
            else:
                # Criar nova presença
                presenca_existente = Presenca.objects.create(
                    funcionario=funcionario,
                    data=data_presenca,
                    tipo_presenca=tipo_presenca,
                    observacoes=observacoes
                )
                logger.info(f"Presença criada: ID={presenca_existente.id}")
                action = 'created'
            
            return JsonResponse({
                'success': True,
                'action': action,
                'presenca_id': presenca_existente.id,
                'tipo_codigo': tipo_presenca.codigo,
                'tipo_nome': tipo_presenca.nome,
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_remover_presenca_calendario(request):
    """Remover presença via AJAX do calendário"""
    if request.method == 'POST':
        try:
            import json
            
            # Verificar se é JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                presenca_id = data.get('presenca_id')
            else:
                # Fallback para form data
                presenca_id = request.POST.get('presenca_id')
            
            presenca = get_object_or_404(Presenca, id=presenca_id)
            presenca.delete()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_marcar_dias_uteis(request):
    """Marcar automaticamente todos os dias úteis como presente"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario_id')
            mes = int(request.POST.get('mes'))
            ano = int(request.POST.get('ano'))
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presente = get_object_or_404(TipoPresenca, codigo='PR')
            
            # Calcular dias úteis do mês
            dias_uteis = calcular_dias_uteis(ano, mes)
            
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for dia in dias_uteis:
                presenca_existente = Presenca.objects.filter(
                    funcionario=funcionario,
                    data=dia
                ).first()
                
                if presenca_existente:
                    presenca_existente.tipo_presenca = tipo_presente
                    presenca_existente.observacoes = "Marcação automática - Dias úteis"
                    presenca_existente.save()
                    presencas_atualizadas += 1
                else:
                    Presenca.objects.create(
                        funcionario=funcionario,
                        data=dia,
                        tipo_presenca=tipo_presente,
                        observacoes="Marcação automática - Dias úteis"
                    )
                    presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_dias': len(dias_uteis)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_marcar_finais_semana(request):
    """Marcar automaticamente finais de semana"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario_id')
            mes = int(request.POST.get('mes'))
            ano = int(request.POST.get('ano'))
            tipo_codigo = request.POST.get('tipo_codigo', 'AU')
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, codigo=tipo_codigo)
            
            # Calcular finais de semana do mês
            finais_semana = calcular_finais_semana(ano, mes)
            
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for dia in finais_semana:
                presenca_existente = Presenca.objects.filter(
                    funcionario=funcionario,
                    data=dia
                ).first()
                
                if presenca_existente:
                    presenca_existente.tipo_presenca = tipo_presenca
                    presenca_existente.observacoes = "Marcação automática - Finais de semana"
                    presenca_existente.save()
                    presencas_atualizadas += 1
                else:
                    Presenca.objects.create(
                        funcionario=funcionario,
                        data=dia,
                        tipo_presenca=tipo_presenca,
                        observacoes="Marcação automática - Finais de semana"
                    )
                    presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_dias': len(finais_semana)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_detalhes_mes(request, ano, mes):
    """Página de detalhes específicos de um mês - versão debug"""
    try:
        # Validar parâmetros
        if not (1 <= mes <= 12):
            raise ValueError("Mês inválido")
        if ano < 2000 or ano > 2100:
            raise ValueError("Ano inválido")
        
        # Buscar presenças do mês com horas extras relacionadas
        presencas = Presenca.objects.filter(
            data__year=ano,
            data__month=mes
        ).select_related('funcionario', 'tipo_presenca').prefetch_related('funcionario__horas_extras')
        
        # Calcular estatísticas básicas
        total_presencas = presencas.count()
        total_funcionarios = Funcionario.objects.filter(status='AT').count()
        dias_uteis = calcular_dias_uteis(ano, mes)
        
        # Resumo por tipo de presença (simplificado)
        resumo_tipos = []
        for presenca in presencas:
            tipo_nome = presenca.tipo_presenca.nome if presenca.tipo_presenca else 'N/A'
            tipo_codigo = presenca.tipo_presenca.codigo if presenca.tipo_presenca else 'N/A'
            
            # Procurar se já existe no resumo
            encontrado = False
            for item in resumo_tipos:
                if item['tipo_presenca__nome'] == tipo_nome:
                    item['total'] += 1
                    encontrado = True
                    break
            
            if not encontrado:
                resumo_tipos.append({
                    'tipo_presenca__nome': tipo_nome,
                    'tipo_presenca__codigo': tipo_codigo,
                    'total': 1
                })
        
        # Resumo por funcionário (simplificado)
        resumo_funcionarios = []
        funcionarios_processados = set()
        
        for presenca in presencas:
            func_id = presenca.funcionario.id
            if func_id not in funcionarios_processados:
                funcionarios_processados.add(func_id)
                
                # Contar presenças por tipo para este funcionário
                presencas_func = presencas.filter(funcionario_id=func_id)
                total_presente = presencas_func.filter(tipo_presenca__codigo='PR').count()
                total_ausente = presencas_func.filter(tipo_presenca__codigo='AU').count()
                total_falta_justificada = presencas_func.filter(tipo_presenca__codigo='FJ').count()
                total_atraso = presencas_func.filter(tipo_presenca__codigo='AT').count()
                total_licenca = presencas_func.filter(tipo_presenca__codigo='LI').count()
                total_ferias = presencas_func.filter(tipo_presenca__codigo='FE').count()
                # Calcular horas extras do modelo HorasExtras para este funcionário
                total_horas_extras = HorasExtras.objects.filter(
                    funcionario_id=func_id,
                    data__year=ano,
                    data__month=mes
                ).aggregate(
                    total=Sum('quantidade_horas')
                )['total'] or 0
                total_registros = presencas_func.count()
                
                resumo_funcionarios.append({
                    'funcionario__id': func_id,
                    'funcionario__nome_completo': presenca.funcionario.nome_completo,
                    'funcionario__codigo_funcionario': presenca.funcionario.codigo_funcionario,
                    'total_presente': total_presente,
                    'total_ausente': total_ausente,
                    'total_falta_justificada': total_falta_justificada,
                    'total_atraso': total_atraso,
                    'total_licenca': total_licenca,
                    'total_ferias': total_ferias,
                    'total_horas_extras': total_horas_extras,
                    'total_registros': total_registros,
                })
        
        # Calcular total de horas extras do mês (usando modelo HorasExtras)
        total_horas_extras = HorasExtras.objects.filter(
            data__year=ano,
            data__month=mes
        ).aggregate(
            total=Sum('quantidade_horas')
        )['total'] or 0
        
        context = {
            'ano': ano,
            'mes': mes,
            'mes_nome': calendar.month_name[mes],
            'presencas_mes': presencas,
            'resumo_por_tipo': resumo_tipos,
            'resumo_por_funcionario': resumo_funcionarios,
            'total_presencas': total_presencas,
            'total_funcionarios': total_funcionarios,
            'dias_uteis': len(dias_uteis),
            'total_horas_extras': total_horas_extras,
            'resumo_mes': {
                'total_registros': total_presencas,
                'total_horas_extras': total_horas_extras,
            },
            'primeiro_dia': date(ano, mes, 1),
            'ultimo_dia': date(ano, mes, calendar.monthrange(ano, mes)[1]),
        }
        
        return render(request, 'rh/presencas/detalhes_mes.html', context)
        
    except Exception as e:
        # Log do erro para debug
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro na view rh_detalhes_mes: {str(e)}")
        
        messages.error(request, f"Erro ao carregar detalhes: {str(e)}")
        return redirect('rh:presencas')

# =============================================================================
# GESTÃO DE FERIADOS
# =============================================================================

@login_required
def rh_feriados(request):
    """Lista de feriados com filtros"""
    # Parâmetros de filtro
    ano = request.GET.get('ano', date.today().year)
    tipo = request.GET.get('tipo', '')
    
    try:
        ano = int(ano)
    except (ValueError, TypeError):
        ano = date.today().year
    
    # Query base
    feriados = Feriado.objects.filter(data__year=ano)
    
    if tipo:
        feriados = feriados.filter(tipo=tipo)
    
    feriados = feriados.order_by('data')
    
    # Paginação
    paginator = Paginator(feriados, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Gerar opções para os filtros
    anos_choices = list(range(2020, 2030))  # Últimos 10 anos + próximos 5
    tipos_choices = Feriado.TIPO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'feriados': page_obj,  # Para compatibilidade
        'ano': ano,
        'tipo': tipo,
        'tipos_feriado': Feriado.TIPO_CHOICES,
        'tipos_choices': tipos_choices,
        'anos_choices': anos_choices,
        'tipo_filter': tipo,
        'ano_filter': ano,
    }
    
    return render(request, 'rh/feriados/main.html', context)

@login_required
def rh_feriado_add(request):
    """Adicionar novo feriado"""
    if request.method == 'POST':
        try:
            feriado = Feriado(
                nome=request.POST['nome'],
                data=request.POST['data'],
                tipo=request.POST['tipo'],
                descricao=request.POST.get('descricao', ''),
                ativo=request.POST.get('ativo') == 'on'
            )
            feriado.full_clean()
            feriado.save()
            messages.success(request, 'Feriado adicionado com sucesso!')
            return redirect('rh:feriados')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar feriado: {e}')
    
    context = {
        'tipos_feriado': Feriado.TIPO_CHOICES,
    }
    
    return render(request, 'rh/feriados/form.html', context)

@login_required
def rh_feriado_edit(request, feriado_id):
    """Editar feriado existente"""
    feriado = get_object_or_404(Feriado, id=feriado_id)
    
    if request.method == 'POST':
        try:
            feriado.nome = request.POST['nome']
            feriado.data = request.POST['data']
            feriado.tipo = request.POST['tipo']
            feriado.descricao = request.POST.get('descricao', '')
            feriado.ativo = request.POST.get('ativo') == 'on'
            feriado.full_clean()
            feriado.save()
            messages.success(request, 'Feriado atualizado com sucesso!')
            return redirect('rh:feriados')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar feriado: {e}')
    
    context = {
        'feriado': feriado,
        'tipos_feriado': Feriado.TIPO_CHOICES,
    }
    
    return render(request, 'rh/feriados/form.html', context)

@login_required
def rh_feriado_delete(request, feriado_id):
    """Excluir feriado"""
    feriado = get_object_or_404(Feriado, id=feriado_id)
    
    if request.method == 'POST':
        try:
            feriado.delete()
            messages.success(request, 'Feriado excluído com sucesso!')
            return redirect('rh:feriados')
        except Exception as e:
            messages.error(request, f'Erro ao excluir feriado: {e}')
    
    context = {
        'feriado': feriado,
    }
    
    return render(request, 'rh/feriados/delete.html', context)

# =============================================================================
# GESTÃO DE SALÁRIOS
# =============================================================================

@login_required
def rh_salarios(request):
    """Lista de salários"""
    salarios = Salario.objects.select_related('funcionario').order_by('-data_inicio')
    
    # Paginação
    paginator = Paginator(salarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    status_choices = Salario.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'status_choices': status_choices,
    }
    
    return render(request, 'rh/salarios/main.html', context)

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def calcular_dias_uteis(ano, mes):
    """Calcula os dias úteis de um mês (segunda a sexta, excluindo feriados)"""
    # Obter todos os dias do mês
    dias_mes = []
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        data = date(ano, mes, dia)
        # Verificar se é dia útil (segunda=0, sexta=4)
        if data.weekday() < 5:  # 0-4 = segunda a sexta
            dias_mes.append(data)
    
    # Remover feriados ativos
    feriados = Feriado.objects.filter(
        data__year=ano,
        data__month=mes,
        ativo=True
    ).values_list('data', flat=True)
    
    dias_uteis = [dia for dia in dias_mes if dia not in feriados]
    return dias_uteis

def calcular_finais_semana(ano, mes):
    """Calcula os finais de semana de um mês (sábado e domingo)"""
    finais_semana = []
    for dia in range(1, calendar.monthrange(ano, mes)[1] + 1):
        data = date(ano, mes, dia)
        # Verificar se é final de semana (sábado=5, domingo=6)
        if data.weekday() >= 5:  # 5-6 = sábado e domingo
            finais_semana.append(data)
    return finais_semana

# =============================================================================
# PLACEHOLDER VIEWS (para manter compatibilidade com URLs)
# =============================================================================

@login_required
def rh_departamentos(request):
    """Lista de departamentos"""
    departamentos = Departamento.objects.select_related('sucursal').all().order_by('sucursal__nome', 'nome')
    
    # Paginação
    paginator = Paginator(departamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas para os cards
    total_departamentos = Departamento.objects.count()
    departamentos_ativos = Departamento.objects.filter(ativo=True).count()
    departamentos_inativos = Departamento.objects.filter(ativo=False).count()
    total_funcionarios = Funcionario.objects.count()
    
    context = {
        'departamentos': page_obj,
        'total_departamentos': total_departamentos,
        'departamentos_ativos': departamentos_ativos,
        'departamentos_inativos': departamentos_inativos,
        'total_funcionarios': total_funcionarios,
    }
    
    return render(request, 'rh/departamentos/main.html', context)

@login_required
def rh_departamento_add(request):
    """Adicionar novo departamento"""
    if request.method == 'POST':
        try:
            # Buscar a primeira sucursal disponível
            from meuprojeto.empresa.models_base import Sucursal
            sucursal = Sucursal.objects.first()
            if not sucursal:
                messages.error(request, 'Nenhuma sucursal encontrada. Por favor, cadastre uma sucursal primeiro.')
                return redirect('rh:departamentos')
            
            departamento = Departamento(
                nome=request.POST['nome'],
                codigo='',  # Será gerado automaticamente pelo método save
                tipo=request.POST.get('tipo', 'ADM'),
                descricao=request.POST.get('descricao', ''),
                ativo=request.POST.get('ativo') == 'on',
                sucursal=sucursal
            )
            departamento.full_clean()
            departamento.save()
            messages.success(request, 'Departamento adicionado com sucesso!')
            return redirect('rh:departamentos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar departamento: {e}')
    
    # Buscar sucursal para exibir no formulário
    from meuprojeto.empresa.models_base import Sucursal
    sucursal = Sucursal.objects.first()
    
    context = {
        'tipos_departamento': Departamento.TIPO_CHOICES,
        'sucursal': sucursal,
    }
    
    return render(request, 'rh/departamentos/form.html', context)

@login_required
def rh_departamento_edit(request, id):
    """Editar departamento existente"""
    departamento = get_object_or_404(Departamento, id=id)
    
    if request.method == 'POST':
        try:
            departamento.nome = request.POST['nome']
            # Código não é editável - é gerado automaticamente
            departamento.tipo = request.POST.get('tipo', 'ADM')
            departamento.descricao = request.POST.get('descricao', '')
            departamento.ativo = request.POST.get('ativo') == 'on'
            departamento.full_clean()
            departamento.save()
            messages.success(request, 'Departamento atualizado com sucesso!')
            return redirect('rh:departamentos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar departamento: {e}')
    
    # Buscar sucursal para exibir no formulário
    from meuprojeto.empresa.models_base import Sucursal
    sucursal = Sucursal.objects.first()
    
    context = {
        'departamento': departamento,
        'tipos_departamento': Departamento.TIPO_CHOICES,
        'sucursal': sucursal,
    }
    
    return render(request, 'rh/departamentos/form.html', context)

@login_required
def rh_departamento_delete(request, id):
    """Excluir departamento com migração automática de dados vinculados"""
    departamento = get_object_or_404(Departamento, id=id)
    
    # Verificar se há funcionários vinculados
    funcionarios_vinculados = Funcionario.objects.filter(departamento=departamento)
    cargos_vinculados = Cargo.objects.filter(departamento=departamento)
    
    if request.method == 'POST':
        try:
            
            # Se há dados vinculados, verificar se foi selecionado um departamento de destino
            if funcionarios_vinculados.exists() or cargos_vinculados.exists():
                departamento_destino_id = request.POST.get('departamento_destino')
                if not departamento_destino_id:
                    messages.error(request, 'Selecione um departamento de destino para migrar os dados vinculados.')
                    return redirect('rh:departamento_delete', id=departamento.id)
                
                departamento_destino = get_object_or_404(Departamento, id=departamento_destino_id)
                # Migrar funcionários
                funcionarios_migrados = 0
                if funcionarios_vinculados.exists():
                    funcionarios_vinculados.update(departamento=departamento_destino)
                    funcionarios_migrados = funcionarios_vinculados.count()
                
                # Migrar cargos
                cargos_migrados = 0
                if cargos_vinculados.exists():
                    cargos_vinculados.update(departamento=departamento_destino)
                    cargos_migrados = cargos_vinculados.count()
                
                # Agora pode deletar o departamento
                departamento.delete()
                
                # Mensagem de sucesso com detalhes da migração
                mensagem = f'Departamento "{departamento.nome}" excluído com sucesso!'
                if funcionarios_migrados > 0:
                    mensagem += f' {funcionarios_migrados} funcionário(s) migrado(s) para "{departamento_destino.nome}".'
                if cargos_migrados > 0:
                    mensagem += f' {cargos_migrados} cargo(s) migrado(s) para "{departamento_destino.nome}".'
                
                messages.success(request, mensagem)
                return redirect('rh:departamentos')
            else:
                # Não há dados vinculados, pode deletar diretamente
                departamento.delete()
                messages.success(request, 'Departamento excluído com sucesso!')
                return redirect('rh:departamentos')
                
        except Exception as e:
            messages.error(request, f'Erro ao excluir departamento: {e}')
    
    # Buscar departamentos disponíveis para migração (excluindo o próprio)
    departamentos_disponiveis = Departamento.objects.exclude(id=departamento.id).filter(ativo=True).order_by('nome')
    
    context = {
        'departamento': departamento,
        'funcionarios_vinculados': funcionarios_vinculados,
        'cargos_vinculados': cargos_vinculados,
        'departamentos_disponiveis': departamentos_disponiveis,
    }
    
    return render(request, 'rh/departamentos/delete.html', context)

@login_required
def rh_cargos(request):
    """Lista de cargos com sistema unificado de filtros"""
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Parâmetros de filtro
    search_query = request.GET.get('q', '').strip()
    departamento_id = request.GET.get('departamento')
    ativo_param = request.GET.get('ativo')
    nivel_param = request.GET.get('nivel')
    categoria_param = request.GET.get('categoria')
    
    # Query base
    cargos = Cargo.objects.select_related('departamento')
    
    # Aplicar filtros
    if search_query:
        cargos = cargos.filter(
            Q(nome__icontains=search_query) |
            Q(codigo_cargo__icontains=search_query) |
            Q(descricao__icontains=search_query)
        )
    
    if departamento_id:
        cargos = cargos.filter(departamento_id=departamento_id)
    
    if ativo_param == 'true':
        cargos = cargos.filter(ativo=True)
    elif ativo_param == 'false':
        cargos = cargos.filter(ativo=False)
    
    if nivel_param:
        cargos = cargos.filter(nivel=nivel_param)
    
    if categoria_param:
        cargos = cargos.filter(categoria=categoria_param)
    
    # Ordenação
    cargos = cargos.order_by('nome')
    
    # Paginação
    paginator = Paginator(cargos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    total_cargos = Cargo.objects.count()
    cargos_ativos = Cargo.objects.filter(ativo=True).count()
    cargos_inativos = Cargo.objects.filter(ativo=False).count()
    funcionarios_com_cargo = Funcionario.objects.filter(cargo__isnull=False).count()
    
    # Choices para filtros
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    status_choices = [
        ('true', 'Ativo'),
        ('false', 'Inativo'),
    ]
    nivel_choices = Cargo.NIVEL_CHOICES if hasattr(Cargo, 'NIVEL_CHOICES') else []
    categoria_choices = Cargo.CATEGORIA_CHOICES if hasattr(Cargo, 'CATEGORIA_CHOICES') else []
    
    # Configurar ações dos botões (será processado no template)
    actions_config = [
        {
            'action': 'edit',
            'text': 'Editar',
            'icon': 'edit',
            'url_name': 'rh:cargo_edit',
            'class': 'secondary'
        },
        {
            'action': 'delete',
            'text': 'Eliminar',
            'icon': 'trash',
            'url_name': 'rh:cargo_delete',
            'class': 'danger',
            'onclick': 'return confirm("Tem certeza que deseja eliminar este cargo?")'
        }
    ]
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'departamento_id': departamento_id,
        'ativo': ativo_param,
        'nivel': nivel_param,
        'categoria': categoria_param,
        'total_cargos': total_cargos,
        'cargos_ativos': cargos_ativos,
        'cargos_inativos': cargos_inativos,
        'funcionarios_com_cargo': funcionarios_com_cargo,
        'departamentos': departamentos,
        'status_choices': status_choices,
        'nivel_choices': nivel_choices,
        'categoria_choices': categoria_choices,
        'actions_config': actions_config,
    }
    
    return render(request, 'rh/cargos/main.html', context)

@login_required
def rh_cargo_add(request):
    """Adicionar novo cargo"""
    if request.method == 'POST':
        try:
            cargo = Cargo(
                nome=request.POST['nome'],
                nivel=request.POST['nivel'],
                categoria=request.POST.get('categoria', 'OP'),
                departamento_id=request.POST.get('departamento'),
                descricao=request.POST.get('descricao', ''),
                ativo=request.POST.get('ativo') == 'on'
            )
            cargo.full_clean()
            cargo.save()
            messages.success(request, 'Cargo adicionado com sucesso!')
            return redirect('rh:cargos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao adicionar cargo: {e}')
    
    # Buscar departamentos disponíveis (próprios + vinculados)
    
    # Buscar sucursal atual (primeira disponível)
    sucursal_atual = Sucursal.objects.first()
    
    # Departamentos próprios da sucursal
    dept_proprios = Departamento.objects.filter(
        sucursal=sucursal_atual, 
        ativo=True
    ).select_related('sucursal')
    
    # Departamentos vinculados de outras sucursais
    dept_vinculados = Departamento.objects.filter(
        sucursais_vinculadas__sucursal=sucursal_atual,
        sucursais_vinculadas__ativo=True,
        ativo=True
    ).exclude(sucursal=sucursal_atual).select_related('sucursal')
    
    # Combinar e ordenar
    departamentos = (dept_proprios | dept_vinculados).distinct().order_by('sucursal__nome', 'nome')
    
    context = {
        'departamentos': departamentos,
        'sucursal_atual': sucursal_atual,
    }
    
    return render(request, 'rh/cargos/form.html', context)

@login_required
def rh_cargo_edit(request, id):
    """Editar cargo existente"""
    cargo = get_object_or_404(Cargo, id=id)
    
    if request.method == 'POST':
        try:
            cargo.nome = request.POST['nome']
            cargo.nivel = request.POST['nivel']
            cargo.categoria = request.POST.get('categoria', 'OP')
            # Código não é editável - é gerado automaticamente
            cargo.departamento_id = request.POST.get('departamento')
            cargo.descricao = request.POST.get('descricao', '')
            cargo.ativo = request.POST.get('ativo') == 'on'
            cargo.full_clean()
            cargo.save()
            messages.success(request, 'Cargo atualizado com sucesso!')
            return redirect('rh:cargos')
        except ValidationError as e:
            messages.error(request, f'Erro de validação: {e}')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar cargo: {e}')
    
    context = {
        'cargo': cargo,
        'departamentos': Departamento.objects.filter(ativo=True),
    }
    
    return render(request, 'rh/cargos/form.html', context)

@login_required
def rh_cargo_delete(request, id):
    """Excluir cargo com migração automática de funcionários vinculados"""
    cargo = get_object_or_404(Cargo, id=id)
    
    # Verificar se há funcionários vinculados
    funcionarios_vinculados = Funcionario.objects.filter(cargo=cargo)
    
    if request.method == 'POST':
        try:
            # Se há funcionários vinculados, verificar se foi selecionado um cargo de destino
            if funcionarios_vinculados.exists():
                cargo_destino_id = request.POST.get('cargo_destino')
                
                if not cargo_destino_id:
                    messages.error(request, 'Selecione um cargo de destino para migrar os funcionários vinculados.')
                    return redirect('rh:cargo_delete', id=cargo.id)
                
                cargo_destino = get_object_or_404(Cargo, id=cargo_destino_id)
                
                # Migrar funcionários
                funcionarios_migrados = 0
                if funcionarios_vinculados.exists():
                    funcionarios_vinculados.update(cargo=cargo_destino)
                    funcionarios_migrados = funcionarios_vinculados.count()
                
                # Agora pode deletar o cargo
                cargo.delete()
                
                # Mensagem de sucesso com detalhes da migração
                mensagem = f'Cargo "{cargo.nome}" excluído com sucesso!'
                if funcionarios_migrados > 0:
                    mensagem += f' {funcionarios_migrados} funcionário(s) migrado(s) para "{cargo_destino.nome}".'
                
                messages.success(request, mensagem)
                return redirect('rh:cargos')
            else:
                # Não há funcionários vinculados, pode deletar diretamente
                cargo.delete()
                messages.success(request, 'Cargo excluído com sucesso!')
                return redirect('rh:cargos')
                
        except Exception as e:
            messages.error(request, f'Erro ao excluir cargo: {e}')
    
    # Buscar cargos disponíveis para migração (excluindo o próprio e do mesmo departamento)
    cargos_disponiveis = Cargo.objects.exclude(id=cargo.id).filter(
        departamento=cargo.departamento, 
        ativo=True
    ).order_by('nome')
    
    context = {
        'cargo': cargo,
        'funcionarios_vinculados': funcionarios_vinculados,
        'cargos_disponiveis': cargos_disponiveis,
    }
    
    return render(request, 'rh/cargos/delete.html', context)

@login_required
def rh_funcionario_add(request):
    """Adicionar novo funcionário"""
    
    if request.method == 'POST':
        try:
            # Dados básicos
            nome_completo = request.POST.get('nome_completo')
            nuit = request.POST.get('nuit')
            data_nascimento = request.POST.get('data_nascimento')
            genero = request.POST.get('genero')
            estado_civil = request.POST.get('estado_civil')
            nacionalidade = request.POST.get('nacionalidade')
            naturalidade = request.POST.get('naturalidade')
            
            # Dados de contato
            telefone = request.POST.get('telefone')
            email = request.POST.get('email')
            endereco = request.POST.get('endereco')
            
            # Dados de localização
            provincia = request.POST.get('provincia')
            cidade = request.POST.get('cidade')
            bairro = request.POST.get('bairro')
            
            # Dados profissionais
            sucursal_id = request.POST.get('sucursal')
            departamento_id = request.POST.get('departamento')
            cargo_id = request.POST.get('cargo')
            data_admissao = request.POST.get('data_admissao')
            salario_atual = request.POST.get('salario_atual')
            
            # Dados bancários
            banco = request.POST.get('banco')
            outro_banco = request.POST.get('outro_banco')
            conta = request.POST.get('conta')
            nib = request.POST.get('nib')
            
            # Se "Outro" foi selecionado, usar o valor do campo outro_banco
            if banco == 'Outro' and outro_banco:
                banco = outro_banco
            
            # Validações básicas - apenas campos realmente obrigatórios
            if not nome_completo or not sucursal_id or not departamento_id or not cargo_id:
                messages.error(request, 'Preencha todos os campos obrigatórios.')
                # Buscar dados para os dropdowns
                sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
                departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
                cargos = Cargo.objects.filter(ativo=True).order_by('nome')
                
                # Buscar benefícios e descontos disponíveis
                from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
                beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
                descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
                
                context = {
                    'sucursais': sucursais,
                    'departamentos': departamentos,
                    'cargos': cargos,
                    'beneficios_disponiveis': beneficios_disponiveis,
                    'descontos_disponiveis': descontos_disponiveis,
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # Verificar se NUIT já existe
            if Funcionario.objects.filter(nuit=nuit).exists():
                messages.error(request, 'Este NUIT já está sendo usado por outro funcionário.')
                # Buscar dados para os dropdowns
                sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
                departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
                cargos = Cargo.objects.filter(ativo=True).order_by('nome')
                
                # Buscar benefícios e descontos disponíveis
                from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
                beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
                descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
                
                context = {
                    'sucursais': sucursais,
                    'departamentos': departamentos,
                    'cargos': cargos,
                    'beneficios_disponiveis': beneficios_disponiveis,
                    'descontos_disponiveis': descontos_disponiveis,
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # Buscar sucursal, departamento, cargo e localização
            sucursal = get_object_or_404(Sucursal, id=sucursal_id)
            departamento = get_object_or_404(Departamento, id=departamento_id)
            cargo = get_object_or_404(Cargo, id=cargo_id)
            
            # Criar funcionário
            funcionario = Funcionario.objects.create(
                nome_completo=nome_completo,
                nuit=nuit,
                data_nascimento=data_nascimento if data_nascimento else None,
                genero=genero if genero else 'M',
                estado_civil=estado_civil if estado_civil else 'S',
                nacionalidade=nacionalidade if nacionalidade else 'Moçambicana',
                naturalidade=naturalidade if naturalidade else '',
                telefone=telefone if telefone else '',
                email=email if email else '',
                endereco=endereco if endereco else '',
                provincia=provincia,
                cidade=cidade,
                bairro=bairro,
                sucursal=sucursal,
                departamento=departamento,
                cargo=cargo,
                data_admissao=data_admissao if data_admissao else date.today(),
                salario_atual=float(salario_atual) if salario_atual else 0.0,
                banco=banco if banco else '',
                conta=conta if conta else '',
                nib=nib if nib else '',
                status='AT'
            )
            
            # Processar benefícios e descontos
            beneficios_ids = request.POST.getlist('beneficios')
            descontos_ids = request.POST.getlist('descontos')
            
            # Atualizar benefícios
            funcionario.beneficios.set(beneficios_ids)
            
            # Atualizar descontos
            funcionario.descontos.set(descontos_ids)
            
            messages.success(request, f'Funcionário "{funcionario.nome_completo}" adicionado com sucesso!')
            return redirect('rh:funcionario_detail', id=funcionario.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar funcionário: {e}')
            # Buscar dados para os dropdowns
            sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
            departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
            cargos = Cargo.objects.filter(ativo=True).order_by('nome')
            
            # Buscar benefícios e descontos disponíveis
            from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
            beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
            descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
            
            context = {
                'sucursais': sucursais,
                'departamentos': departamentos,
                'cargos': cargos,
                'beneficios_disponiveis': beneficios_disponiveis,
                'descontos_disponiveis': descontos_disponiveis,
            }
            return render(request, 'rh/funcionarios/form.html', context)
    
    # Buscar dados para os dropdowns
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Buscar benefícios e descontos disponíveis
    from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
    beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
    descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'sucursais': sucursais,
        'departamentos': departamentos,
        'cargos': cargos,
        'beneficios_disponiveis': beneficios_disponiveis,
        'descontos_disponiveis': descontos_disponiveis,
    }
    
    return render(request, 'rh/funcionarios/form.html', context)

@login_required
def rh_funcionario_edit(request, id):
    """Editar funcionário existente"""
    funcionario = get_object_or_404(Funcionario, id=id)
    
    
    if request.method == 'POST':
        try:
            # PRIMEIRO: Validar dados ANTES de atualizar o funcionário
            nome_completo = request.POST.get('nome_completo')
            nuit = request.POST.get('nuit')
            provincia = request.POST.get('provincia')
            cidade = request.POST.get('cidade')
            bairro = request.POST.get('bairro')
            sucursal_id = request.POST.get('sucursal')
            departamento_id = request.POST.get('departamento')
            cargo_id = request.POST.get('cargo')
            
            # Validações básicas ANTES de modificar o funcionário
            # Validações básicas - apenas campos realmente obrigatórios
            if not nome_completo or not sucursal_id or not departamento_id or not cargo_id:
                messages.error(request, 'Preencha todos os campos obrigatórios.')
                # Renderizar o template com os dados atuais em vez de redirecionar
                context = {
                    'funcionario': funcionario,
                    'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
                    'departamentos': Departamento.objects.filter(ativo=True).order_by('nome'),
                    'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
                    'beneficios_disponiveis': BeneficioSalarial.objects.filter(ativo=True).order_by('nome'),
                    'descontos_disponiveis': DescontoSalarial.objects.filter(ativo=True).order_by('nome'),
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # Verificar se NUIT já existe (exceto para o próprio funcionário)
            if Funcionario.objects.filter(nuit=nuit).exclude(id=funcionario.id).exists():
                messages.error(request, 'Este NUIT já está sendo usado por outro funcionário.')
                # Renderizar o template com os dados atuais em vez de redirecionar
                context = {
                    'funcionario': funcionario,
                    'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
                    'departamentos': Departamento.objects.filter(ativo=True).order_by('nome'),
                    'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
                    'beneficios_disponiveis': BeneficioSalarial.objects.filter(ativo=True).order_by('nome'),
                    'descontos_disponiveis': DescontoSalarial.objects.filter(ativo=True).order_by('nome'),
                }
                return render(request, 'rh/funcionarios/form.html', context)
            
            # SEGUNDO: Agora que validamos, atualizar os dados do funcionário
            # Dados básicos
            funcionario.nome_completo = nome_completo
            funcionario.nuit = nuit
            funcionario.data_nascimento = request.POST.get('data_nascimento') if request.POST.get('data_nascimento') else None
            funcionario.genero = request.POST.get('genero')
            funcionario.estado_civil = request.POST.get('estado_civil')
            funcionario.nacionalidade = request.POST.get('nacionalidade')
            funcionario.naturalidade = request.POST.get('naturalidade')
            
            # Dados de contato
            funcionario.telefone = request.POST.get('telefone')
            funcionario.email = request.POST.get('email')
            funcionario.endereco = request.POST.get('endereco')
            
            # Dados de localização
            funcionario.provincia = provincia
            funcionario.cidade = cidade
            funcionario.bairro = bairro
            
            # Dados profissionais
            funcionario.data_admissao = request.POST.get('data_admissao') if request.POST.get('data_admissao') else funcionario.data_admissao
            funcionario.salario_atual = float(request.POST.get('salario_atual')) if request.POST.get('salario_atual') else funcionario.salario_atual
            
            # Dados bancários
            banco = request.POST.get('banco')
            outro_banco = request.POST.get('outro_banco')
            
            # Se "Outro" foi selecionado, usar o valor do campo outro_banco
            if banco == 'Outro' and outro_banco:
                funcionario.banco = outro_banco
            else:
                funcionario.banco = banco
                
            funcionario.conta = request.POST.get('conta')
            funcionario.nib = request.POST.get('nib')
            
            # Buscar sucursal, departamento, cargo
            sucursal = get_object_or_404(Sucursal, id=sucursal_id)
            departamento = get_object_or_404(Departamento, id=departamento_id)
            cargo = get_object_or_404(Cargo, id=cargo_id)
            
            # Atualizar sucursal, departamento, cargo
            funcionario.sucursal = sucursal
            funcionario.departamento = departamento
            funcionario.cargo = cargo
            
            # Processar benefícios e descontos
            beneficios_ids = request.POST.getlist('beneficios')
            descontos_ids = request.POST.getlist('descontos')
            
            # Atualizar benefícios
            funcionario.beneficios.set(beneficios_ids)
            
            # Atualizar descontos
            funcionario.descontos.set(descontos_ids)
            
            # Salvar alterações
            funcionario.save()
            
            messages.success(request, f'Funcionário "{funcionario.nome_completo}" atualizado com sucesso!')
            return redirect('rh:funcionario_detail', id=funcionario.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar funcionário: {e}')
    
    # Buscar dados para os dropdowns
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Buscar benefícios e descontos disponíveis
    from meuprojeto.empresa.models_rh import BeneficioSalarial, DescontoSalarial
    beneficios_disponiveis = BeneficioSalarial.objects.filter(ativo=True).order_by('nome')
    descontos_disponiveis = DescontoSalarial.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'funcionario': funcionario,
        'sucursais': sucursais,
        'departamentos': departamentos,
        'cargos': cargos,
        'beneficios_disponiveis': beneficios_disponiveis,
        'descontos_disponiveis': descontos_disponiveis,
    }
    
    return render(request, 'rh/funcionarios/form.html', context)

@login_required
def rh_funcionario_delete(request, id):
    """Deletar funcionário"""
    funcionario = get_object_or_404(Funcionario, id=id)
    
    if request.method == 'POST':
        try:
            nome_funcionario = funcionario.nome_completo
            funcionario.delete()
            messages.success(request, f'Funcionário "{nome_funcionario}" excluído com sucesso!')
            return redirect('rh:funcionarios')
        except Exception as e:
            messages.error(request, f'Erro ao excluir funcionário: {e}')
    
    context = {
        'funcionario': funcionario,
    }
    
    return render(request, 'rh/funcionarios/delete.html', context)

@login_required
def rh_presenca_add(request):
    """Adicionar nova presença"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            tipo_presenca_id = request.POST.get('tipo_presenca')
            observacoes = request.POST.get('observacoes', '')
            
            # Validar dados
            if not all([funcionario_id, data, tipo_presenca_id]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:presenca_add')
            
            # Obter objetos
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, id=tipo_presenca_id)
            
            
            # Verificar se já existe presença para esta data
            presenca_existente = Presenca.objects.filter(
                funcionario=funcionario,
                data=data
            ).first()
            
            if presenca_existente:
                messages.warning(request, f'Já existe uma presença registrada para {funcionario.nome_completo} em {data}.')
                return redirect('rh:presenca_edit', id=presenca_existente.id)
            
            # Criar presença
            presenca = Presenca.objects.create(
                funcionario=funcionario,
                data=data,
                tipo_presenca=tipo_presenca,
                observacoes=observacoes
            )
            
            messages.success(request, f'Presença registrada com sucesso para {funcionario.nome_completo} em {data}.')
            return redirect('rh:presencas')
            
        except Exception as e:
            messages.error(request, f'Erro ao registrar presença: {str(e)}')
            return redirect('rh:presenca_add')
    
    # GET - Mostrar formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    tipos_presenca = TipoPresenca.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'funcionarios': funcionarios,
        'tipos_presenca': tipos_presenca,
    }
    
    return render(request, 'rh/presencas/form.html', context)

@login_required
def rh_presenca_detail(request, id):
    """Ver detalhes de uma presença específica"""
    try:
        presenca = Presenca.objects.select_related('funcionario', 'tipo_presenca').get(id=id)
    except Presenca.DoesNotExist:
        messages.error(request, 'Presença não encontrada.')
        return redirect('rh:presencas')
    
    context = {
        'presenca': presenca,
    }
    
    return render(request, 'rh/presencas/detail.html', context)

@login_required
def rh_presenca_edit(request, id):
    """Editar presença existente"""
    presenca = get_object_or_404(Presenca, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            tipo_presenca_id = request.POST.get('tipo_presenca')
            observacoes = request.POST.get('observacoes', '')
            
            # Validar dados
            if not all([funcionario_id, data, tipo_presenca_id]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:presenca_edit', id=id)
            
            # Obter objetos
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_presenca = get_object_or_404(TipoPresenca, id=tipo_presenca_id)
            
            
            # Verificar se já existe outra presença para esta data (exceto a atual)
            presenca_existente = Presenca.objects.filter(
                funcionario=funcionario,
                data=data
            ).exclude(id=id).first()
            
            if presenca_existente:
                messages.warning(request, f'Já existe uma presença registrada para {funcionario.nome_completo} em {data}.')
                return redirect('rh:presenca_edit', id=id)
            
            # Atualizar presença
            presenca.funcionario = funcionario
            presenca.data = data
            presenca.tipo_presenca = tipo_presenca
            presenca.observacoes = observacoes
            presenca.save()
            
            messages.success(request, f'Presença atualizada com sucesso para {funcionario.nome_completo} em {data}.')
            return redirect('rh:presencas')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar presença: {str(e)}')
            return redirect('rh:presenca_edit', id=id)
    
    # GET - Mostrar formulário preenchido
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    tipos_presenca = TipoPresenca.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'presenca': presenca,
        'funcionarios': funcionarios,
        'tipos_presenca': tipos_presenca,
    }
    
    return render(request, 'rh/presencas/form.html', context)

@login_required
def rh_presenca_delete(request, id):
    """Excluir presença"""
    presenca = get_object_or_404(Presenca, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_nome = presenca.funcionario.nome_completo
            data = presenca.data
            presenca.delete()
            
            messages.success(request, f'Presença de {funcionario_nome} em {data} excluída com sucesso.')
            return redirect('rh:presencas')
            
        except Exception as e:
            messages.error(request, f'Erro ao excluir presença: {str(e)}')
            return redirect('rh:presencas')
    
    context = {
        'presenca': presenca,
    }
    
    return render(request, 'rh/presencas/delete.html', context)

@login_required
def rh_horas_extras(request):
    """Gestão completa de horas extras dos funcionários usando modelo HorasExtras"""
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fim = request.POST.get('hora_fim')
            observacoes = request.POST.get('observacoes', '')
            
            # Novos campos separados
            horas_diurnas = Decimal(request.POST.get('horas_diurnas', 0) or 0)
            horas_noturnas = Decimal(request.POST.get('horas_noturnas', 0) or 0)
            horas_extraordinarias = Decimal(request.POST.get('horas_extraordinarias', 0) or 0)
            
            # Validar dados obrigatórios (incluindo funcionário)
            if not all([funcionario_id, data, hora_inicio, hora_fim]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:horas_extras')
            
            # Verificar se pelo menos um tipo de horas foi preenchido
            if horas_diurnas == 0 and horas_noturnas == 0 and horas_extraordinarias == 0:
                messages.error(request, 'Pelo menos um tipo de horas extras deve ser preenchido.')
                return redirect('rh:horas_extras')
            
            # Obter funcionário específico
            try:
                funcionario = Funcionario.objects.get(id=funcionario_id, status='AT')
            except Funcionario.DoesNotExist:
                messages.error(request, 'Funcionário não encontrado ou inativo.')
                return redirect('rh:horas_extras')
            
            # Calcular valor base dinamicamente baseado no funcionário
            remuneracao_teorica = funcionario.get_remuneracao_por_hora_teorica()
            if remuneracao_teorica and remuneracao_teorica.get('remuneracao_por_hora_teorica'):
                valor_base = remuneracao_teorica['remuneracao_por_hora_teorica']
            else:
                # Fallback: usar salário atual dividido por 160 horas mensais
                salario_atual = funcionario.get_salario_atual()
                valor_base = float(salario_atual) / 160 if salario_atual else 0
            
            registros_criados = []
            
            # Criar registros para o funcionário específico
            # Criar registro para horas diurnas se houver
            if horas_diurnas > 0:
                valor_por_hora_diurno = valor_base * Decimal('0.5')  # 50%
                valor_total_diurno = horas_diurnas * valor_por_hora_diurno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='DI',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_diurnas,
                    valor_por_hora=valor_por_hora_diurno,
                    valor_total=valor_total_diurno,
                    observacoes=f"{observacoes} (Diurno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"{funcionario.nome_completo} - Diurno: {horas_diurnas}h - {valor_total_diurno:.2f} MT")
            
            # Criar registro para horas noturnas se houver
            if horas_noturnas > 0:
                valor_por_hora_noturno = valor_base * Decimal('1.0')  # 100%
                valor_total_noturno = horas_noturnas * valor_por_hora_noturno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='NO',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_noturnas,
                    valor_por_hora=valor_por_hora_noturno,
                    valor_total=valor_total_noturno,
                    observacoes=f"{observacoes} (Noturno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"{funcionario.nome_completo} - Noturno: {horas_noturnas}h - {valor_total_noturno:.2f} MT")
            
            # Criar registro para horas extraordinárias se houver
            if horas_extraordinarias > 0:
                valor_por_hora_extraordinario = valor_base * Decimal('1.0')  # 100%
                valor_total_extraordinario = horas_extraordinarias * valor_por_hora_extraordinario
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='EX',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_extraordinarias,
                    valor_por_hora=valor_por_hora_extraordinario,
                    valor_total=valor_total_extraordinario,
                    observacoes=f"{observacoes} (Extraordinário)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"{funcionario.nome_completo} - Extraordinário: {horas_extraordinarias}h - {valor_total_extraordinario:.2f} MT")
            
            # Calcular total geral
            total_horas = horas_diurnas + horas_noturnas + horas_extraordinarias
            total_valor = (horas_diurnas * valor_base * Decimal('0.5') + 
                          horas_noturnas * valor_base * Decimal('1.0') + 
                          horas_extraordinarias * valor_base * Decimal('1.0'))
            
            mensagem = f'Horas extras registradas para {funcionario.nome_completo} em {data}:\n'
            mensagem += '\n'.join(registros_criados)
            mensagem += f'\n\nTotal: {total_horas}h - {total_valor:.2f} MT'
            
            messages.success(request, mensagem)
            return redirect('rh:horas_extras')
            
        except Exception as e:
            messages.error(request, f'Erro ao registrar horas extras: {str(e)}')
            return redirect('rh:horas_extras')
    
    # GET - Mostrar formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    
    # Obter horas extras recentes
    horas_extras_recentes = HorasExtras.objects.select_related(
        'funcionario', 'aprovado_por', 'criado_por'
    ).order_by('-data', '-data_criacao')[:10]
    
    context = {
        'funcionarios': funcionarios,
        'horas_extras_recentes': horas_extras_recentes,
        'tipos_choices': HorasExtras.TIPO_CHOICES,
    }
    
    return render(request, 'rh/presencas/horas_extras_form.html', context)

@login_required
def rh_horas_extras_lista(request):
    """Lista todas as horas extras registradas com opções de edição e exclusão"""
    # Parâmetros de filtro
    mes = request.GET.get('mes', date.today().month)
    ano = request.GET.get('ano', date.today().year)
    funcionario_id = request.GET.get('funcionario')
    tipo = request.GET.get('tipo')
    
    try:
        mes = int(mes)
        ano = int(ano)
    except (ValueError, TypeError):
        mes = date.today().month
        ano = date.today().year
    
    # Filtrar horas extras
    horas_extras = HorasExtras.objects.filter(
        data__year=ano,
        data__month=mes
    ).select_related('funcionario', 'criado_por', 'aprovado_por').order_by('-data', '-id')
    
    if funcionario_id:
        horas_extras = horas_extras.filter(funcionario_id=funcionario_id)
    
    if tipo:
        horas_extras = horas_extras.filter(tipo=tipo)
    
    # Calcular totais
    total_horas = horas_extras.aggregate(
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    )
    
    # Anos disponíveis
    anos_disponiveis = list(range(ano - 2, ano + 3))
    
    # Funcionários para filtro
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    
    # Tipos de horas extras
    tipos_horas_extras = [
        ('DI', 'Diurno'),
        ('NO', 'Noturno'),
        ('EX', 'Extraordinário'),
    ]
    
    context = {
        'horas_extras': horas_extras,
        'mes': mes,
        'ano': ano,
        'funcionario_id': funcionario_id,
        'tipo': tipo,
        'total_horas': float(total_horas['total_horas'] or 0),
        'total_valor': float(total_horas['total_valor'] or 0),
        'anos_disponiveis': anos_disponiveis,
        'funcionarios': funcionarios,
        'tipos_horas_extras': tipos_horas_extras,
    }
    
    return render(request, 'rh/presencas/horas_extras_lista.html', context)

@login_required
def rh_horas_extras_editar(request, id):
    """Editar horas extras existentes"""
    horas_extras = get_object_or_404(HorasExtras, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_id = request.POST.get('funcionario')
            data = request.POST.get('data')
            hora_inicio = request.POST.get('hora_inicio')
            hora_fim = request.POST.get('hora_fim')
            observacoes = request.POST.get('observacoes', '')
            
            # Novos campos separados
            horas_diurnas = Decimal(request.POST.get('horas_diurnas', 0) or 0)
            horas_noturnas = Decimal(request.POST.get('horas_noturnas', 0) or 0)
            horas_extraordinarias = Decimal(request.POST.get('horas_extraordinarias', 0) or 0)
            
            # Validar dados obrigatórios
            if not all([funcionario_id, data, hora_inicio, hora_fim]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:horas_extras_editar', id=id)
            
            # Verificar se pelo menos um tipo de horas foi preenchido
            if horas_diurnas == 0 and horas_noturnas == 0 and horas_extraordinarias == 0:
                messages.error(request, 'Pelo menos um tipo de horas extras deve ser preenchido.')
                return redirect('rh:horas_extras_editar', id=id)
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Calcular valor base do funcionário (assumindo 726 MT para CONS001)
            valor_base = 726  # Este valor deve ser obtido dinamicamente
            
            # Deletar registros existentes para esta data e funcionário
            HorasExtras.objects.filter(
                funcionario=funcionario,
                data=data
            ).delete()
            
            registros_criados = []
            
            # Criar registro para horas diurnas se houver
            if horas_diurnas > 0:
                valor_por_hora_diurno = valor_base * Decimal('0.5')  # 50%
                valor_total_diurno = horas_diurnas * valor_por_hora_diurno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='DI',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_diurnas,
                    valor_por_hora=valor_por_hora_diurno,
                    valor_total=valor_total_diurno,
                    observacoes=f"{observacoes} (Diurno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"Diurno: {horas_diurnas}h - {valor_total_diurno:.2f} MT")
            
            # Criar registro para horas noturnas se houver
            if horas_noturnas > 0:
                valor_por_hora_noturno = valor_base * Decimal('1.0')  # 100%
                valor_total_noturno = horas_noturnas * valor_por_hora_noturno
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='NO',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_noturnas,
                    valor_por_hora=valor_por_hora_noturno,
                    valor_total=valor_total_noturno,
                    observacoes=f"{observacoes} (Noturno)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"Noturno: {horas_noturnas}h - {valor_total_noturno:.2f} MT")
            
            # Criar registro para horas extraordinárias se houver
            if horas_extraordinarias > 0:
                valor_por_hora_extraordinario = valor_base * Decimal('1.0')  # 100%
                valor_total_extraordinario = horas_extraordinarias * valor_por_hora_extraordinario
                
                HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data,
                    tipo='EX',
                    hora_inicio=hora_inicio,
                    hora_fim=hora_fim,
                    quantidade_horas=horas_extraordinarias,
                    valor_por_hora=valor_por_hora_extraordinario,
                    valor_total=valor_total_extraordinario,
                    observacoes=f"{observacoes} (Extraordinário)".strip(),
                    criado_por=request.user
                )
                registros_criados.append(f"Extraordinário: {horas_extraordinarias}h - {valor_total_extraordinario:.2f} MT")
            
            # Calcular total geral
            total_horas = horas_diurnas + horas_noturnas + horas_extraordinarias
            total_valor = (horas_diurnas * valor_base * Decimal('0.5') + 
                          horas_noturnas * valor_base * Decimal('1.0') + 
                          horas_extraordinarias * valor_base * Decimal('1.0'))
            
            mensagem = f'Horas extras atualizadas para {funcionario.nome_completo} em {data}:\n'
            mensagem += '\n'.join(registros_criados)
            mensagem += f'\n\nTotal: {total_horas}h - {total_valor:.2f} MT'
            
            messages.success(request, mensagem)
            return redirect('rh:horas_extras')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar horas extras: {str(e)}')
    
    # GET - Mostrar formulário de edição
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    
    context = {
        'horas_extras': horas_extras,
        'funcionarios': funcionarios,
        'tipos_choices': HorasExtras.TIPO_CHOICES,
    }
    
    return render(request, 'rh/presencas/horas_extras_editar.html', context)

@login_required
def rh_horas_extras_excluir(request, id):
    """Excluir horas extras"""
    horas_extras = get_object_or_404(HorasExtras, id=id)
    
    if request.method == 'POST':
        try:
            funcionario_nome = horas_extras.funcionario.nome_completo
            data = horas_extras.data
            horas_extras.delete()
            messages.success(request, f'Horas extras de {funcionario_nome} em {data} foram excluídas com sucesso!')
            return redirect('rh:horas_extras_lista')
        except Exception as e:
            messages.error(request, f'Erro ao excluir horas extras: {str(e)}')
    
    context = {
        'horas_extras': horas_extras,
    }
    
    return render(request, 'rh/presencas/horas_extras_excluir.html', context)

@login_required
def rh_detectar_tipo_horas_extras(request):
    """Endpoint AJAX para detectar automaticamente o tipo de horas extras"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime
            
            data = json.loads(request.body)
            funcionario_id = data.get('funcionario_id')
            data_str = data.get('data')
            hora_inicio = data.get('hora_inicio')
            hora_fim = data.get('hora_fim')
            
            if not all([funcionario_id, data_str, hora_inicio, hora_fim]):
                return JsonResponse({'success': False, 'error': 'Dados incompletos'})
            
            # Converter data string para objeto date
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Detectar tipo automaticamente
            tipo, justificativa, sugestao_misto = HorasExtras.determinar_tipo_automatico(
                funcionario, data_obj, hora_inicio, hora_fim
            )
            
            return JsonResponse({
                'success': True,
                'tipo': tipo,
                'justificativa': justificativa,
                'sugestao_misto': sugestao_misto
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_calcular_horas_extras_mistas(request):
    """Endpoint AJAX para calcular horas extras mistas com percentuais separados"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime
            
            data = json.loads(request.body)
            funcionario_id = data.get('funcionario_id')
            data_str = data.get('data')
            hora_inicio = data.get('hora_inicio')
            hora_fim = data.get('hora_fim')
            
            if not all([funcionario_id, data_str, hora_inicio, hora_fim]):
                return JsonResponse({'success': False, 'error': 'Dados incompletos'})
            
            # Converter data string para objeto date
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Calcular horas extras mistas
            calculo_misto = HorasExtras.calcular_horas_extras_mistas(
                funcionario, data_obj, hora_inicio, hora_fim
            )
            
            if not calculo_misto:
                return JsonResponse({
                    'success': False,
                    'error': 'Não foi possível calcular as horas extras mistas'
                })
            
            # Converter Decimal para float para serialização JSON
            calculo_misto_serializado = {
                'diurno': None,
                'noturno': None,
                'total': {
                    'horas_totais': float(calculo_misto['total']['horas_totais']),
                    'valor_total': float(calculo_misto['total']['valor_total'])
                }
            }
            
            if calculo_misto['diurno']:
                calculo_misto_serializado['diurno'] = {
                    'horas': float(calculo_misto['diurno']['horas']),
                    'valor_por_hora': float(calculo_misto['diurno']['valor_por_hora']),
                    'valor_total': float(calculo_misto['diurno']['valor_total']),
                    'percentual': float(calculo_misto['diurno']['percentual']),
                    'tipo': calculo_misto['diurno']['tipo'],
                    'tipo_display': calculo_misto['diurno']['tipo_display']
                }
            
            if calculo_misto['noturno']:
                calculo_misto_serializado['noturno'] = {
                    'horas': float(calculo_misto['noturno']['horas']),
                    'valor_por_hora': float(calculo_misto['noturno']['valor_por_hora']),
                    'valor_total': float(calculo_misto['noturno']['valor_total']),
                    'percentual': float(calculo_misto['noturno']['percentual']),
                    'tipo': calculo_misto['noturno']['tipo'],
                    'tipo_display': calculo_misto['noturno']['tipo_display']
                }
            
            return JsonResponse({
                'success': True,
                'calculo_misto': calculo_misto_serializado
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_criar_horas_extras_mistas(request):
    """Endpoint AJAX para criar registros duplos de horas extras mistas"""
    if request.method == 'POST':
        try:
            import json
            from datetime import datetime
            from decimal import Decimal
            
            data = json.loads(request.body)
            funcionario_id = data.get('funcionario_id')
            data_str = data.get('data')
            hora_inicio = data.get('hora_inicio')
            hora_fim = data.get('hora_fim')
            observacoes = data.get('observacoes', '')
            
            if not all([funcionario_id, data_str, hora_inicio, hora_fim]):
                return JsonResponse({'success': False, 'error': 'Dados incompletos'})
            
            # Converter data string para objeto date
            data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Calcular horas extras mistas
            calculo_misto = HorasExtras.calcular_horas_extras_mistas(
                funcionario, data_obj, hora_inicio, hora_fim
            )
            
            if not calculo_misto:
                return JsonResponse({
                    'success': False,
                    'error': 'Não foi possível calcular as horas extras mistas'
                })
            
            # Criar registros separados
            registros_criados = []
            
            # Registrar período diurno se existir
            if calculo_misto['diurno']:
                diurno = calculo_misto['diurno']
                horas_extras_diurno = HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data_obj,
                    tipo='DI',
                    hora_inicio=hora_inicio,
                    hora_fim='20:00',  # Fim do período diurno
                    quantidade_horas=Decimal(str(diurno['horas'])),
                    valor_por_hora=Decimal(str(diurno['valor_por_hora'])),
                    valor_total=Decimal(str(diurno['valor_total'])),
                    observacoes=f"{observacoes} - Período Diurno".strip(' -'),
                    criado_por=request.user
                )
                registros_criados.append({
                    'id': horas_extras_diurno.id,
                    'tipo': 'DI',
                    'horas': float(diurno['horas']),
                    'valor_total': float(diurno['valor_total'])
                })
            
            # Registrar período noturno se existir
            if calculo_misto['noturno']:
                noturno = calculo_misto['noturno']
                horas_extras_noturno = HorasExtras.objects.create(
                    funcionario=funcionario,
                    data=data_obj,
                    tipo='NO',
                    hora_inicio='20:00',  # Início do período noturno
                    hora_fim=hora_fim,
                    quantidade_horas=Decimal(str(noturno['horas'])),
                    valor_por_hora=Decimal(str(noturno['valor_por_hora'])),
                    valor_total=Decimal(str(noturno['valor_total'])),
                    observacoes=f"{observacoes} - Período Noturno".strip(' -'),
                    criado_por=request.user
                )
                registros_criados.append({
                    'id': horas_extras_noturno.id,
                    'tipo': 'NO',
                    'horas': float(noturno['horas']),
                    'valor_total': float(noturno['valor_total'])
                })
            
            return JsonResponse({
                'success': True,
                'registros_criados': registros_criados,
                'total_valor': float(calculo_misto['total']['valor_total']),
                'total_horas': float(calculo_misto['total']['horas_totais'])
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_funcionario_dados_remuneracao(request, id):
    """Endpoint AJAX para obter dados de remuneração do funcionário"""
    if request.method == 'GET':
        try:
            funcionario = get_object_or_404(Funcionario, id=id)
            
            # Obter remuneração por hora real
            remuneracao_real = funcionario.get_remuneracao_por_hora()
            remuneracao_real_valor = remuneracao_real['remuneracao_por_hora'] if remuneracao_real else None
            
            # Obter remuneração por hora teórica
            remuneracao_teorica = funcionario.get_remuneracao_por_hora_teorica()
            remuneracao_teorica_valor = remuneracao_teorica['remuneracao_por_hora_teorica'] if remuneracao_teorica else None
            
            # Obter salário atual
            salario_atual = funcionario.get_salario_atual()
            
            # Obter tipo de horas extras se fornecido
            tipo_horas_extras = request.GET.get('tipo', 'DI')
            
            # Criar instância temporária para calcular valor
            from meuprojeto.empresa.models_rh import HorasExtras
            horas_extras_temp = HorasExtras(
                funcionario=funcionario,
                tipo=tipo_horas_extras
            )
            
            # Calcular valor por hora das horas extras
            calculo_horas_extras = horas_extras_temp.calcular_valor_por_hora_automatico()
            
            return JsonResponse({
                'success': True,
                'salario_atual': float(salario_atual) if salario_atual else None,
                'remuneracao_real': remuneracao_real_valor,
                'remuneracao_teorica': remuneracao_teorica_valor,
                'funcionario_nome': funcionario.nome_completo,
                'calculo_horas_extras': calculo_horas_extras
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_tipos_presenca(request):
    """Lista de tipos de presença"""
    tipos = TipoPresenca.objects.filter(ativo=True).order_by('nome')
    
    # Filtros
    search_query = request.GET.get('search', '')
    if search_query:
        tipos = tipos.filter(nome__icontains=search_query)
    
    # Paginação
    paginator = Paginator(tipos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'tipos': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'rh/presencas/tipos/main.html', context)

@login_required
def rh_tipo_presenca_add(request):
    """Adicionar tipo de presença"""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        cor = request.POST.get('cor', '#28a745')
        ativo = request.POST.get('ativo') == 'on'
        
        if not nome:
            messages.error(request, 'Nome é obrigatório.')
        else:
            try:
                TipoPresenca.objects.create(
                    nome=nome,
                    descricao=descricao,
                    cor=cor,
                    ativo=ativo
                )
                messages.success(request, 'Tipo de presença criado com sucesso!')
                return redirect('rh:tipos_presenca')
            except Exception as e:
                messages.error(request, f'Erro ao criar tipo de presença: {str(e)}')
    
    context = {
        'cores_disponiveis': [
            ('#28a745', 'Verde'),
            ('#dc3545', 'Vermelho'),
            ('#ffc107', 'Amarelo'),
            ('#17a2b8', 'Azul'),
            ('#6f42c1', 'Roxo'),
            ('#fd7e14', 'Laranja'),
            ('#20c997', 'Verde claro'),
            ('#6c757d', 'Cinza'),
        ]
    }
    
    return render(request, 'rh/presencas/tipos/form.html', context)

@login_required
def rh_tipo_presenca_edit(request, id):
    """Editar tipo de presença"""
    try:
        tipo = TipoPresenca.objects.get(id=id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            descricao = request.POST.get('descricao', '')
            cor = request.POST.get('cor', '#28a745')
            ativo = request.POST.get('ativo') == 'on'
            
            if not nome:
                messages.error(request, 'Nome é obrigatório.')
            else:
                try:
                    tipo.nome = nome
                    tipo.descricao = descricao
                    tipo.cor = cor
                    tipo.ativo = ativo
                    tipo.save()
                    
                    messages.success(request, 'Tipo de presença atualizado com sucesso!')
                    return redirect('rh:tipos_presenca')
                except Exception as e:
                    messages.error(request, f'Erro ao atualizar tipo de presença: {str(e)}')
        
        context = {
            'tipo': tipo,
            'cores_disponiveis': [
                ('#28a745', 'Verde'),
                ('#dc3545', 'Vermelho'),
                ('#ffc107', 'Amarelo'),
                ('#17a2b8', 'Azul'),
                ('#6f42c1', 'Roxo'),
                ('#fd7e14', 'Laranja'),
                ('#20c997', 'Verde claro'),
                ('#6c757d', 'Cinza'),
            ]
        }
        
        return render(request, 'rh/presencas/tipos/form.html', context)
        
    except TipoPresenca.DoesNotExist:
        messages.error(request, 'Tipo de presença não encontrado.')
        return redirect('rh:tipos_presenca')

@login_required
def rh_tipo_presenca_delete(request, id):
    """Deletar tipo de presença"""
    try:
        tipo = TipoPresenca.objects.get(id=id)
        
        if request.method == 'POST':
            try:
                # Verificar se há presenças usando este tipo
                presencas_count = Presenca.objects.filter(tipo=tipo).count()
                if presencas_count > 0:
                    messages.error(request, f'Não é possível deletar este tipo de presença pois existem {presencas_count} presenças associadas.')
                    return redirect('rh:tipos_presenca')
                
                tipo.delete()
                messages.success(request, 'Tipo de presença deletado com sucesso!')
                return redirect('rh:tipos_presenca')
            except Exception as e:
                messages.error(request, f'Erro ao deletar tipo de presença: {str(e)}')
        
        context = {'tipo': tipo}
        return render(request, 'rh/presencas/tipos/delete.html', context)
        
    except TipoPresenca.DoesNotExist:
        messages.error(request, 'Tipo de presença não encontrado.')
        return redirect('rh:tipos_presenca')

@login_required
def rh_marcar_feriados_automaticos(request):
    """Marcar automaticamente os feriados no calendário de presenças"""
    if request.method == 'POST':
        try:
            import json
            
            # Verificar se é JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                funcionario_id = data.get('funcionario_id')
                mes = int(data.get('mes'))
                ano = int(data.get('ano'))
            else:
                # Fallback para form data
                funcionario_id = request.POST.get('funcionario_id')
                mes = int(request.POST.get('mes'))
                ano = int(request.POST.get('ano'))
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_feriado = get_object_or_404(TipoPresenca, codigo='FD')  # FD = Feriado
            
            # Obter todos os feriados ativos para o mês/ano especificado
            from django.db.models.functions import ExtractMonth, ExtractYear
            
            feriados = Feriado.objects.filter(
                ativo=True,
                data__year=ano,
                data__month=mes
            )
            
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for feriado in feriados:
                presenca_existente = Presenca.objects.filter(
                    funcionario=funcionario,
                    data=feriado.data
                ).first()
                
                if presenca_existente:
                    presenca_existente.tipo_presenca = tipo_feriado
                    presenca_existente.observacoes = f"Feriado: {feriado.nome}"
                    presenca_existente.save()
                    presencas_atualizadas += 1
                else:
                    Presenca.objects.create(
                        funcionario=funcionario,
                        data=feriado.data,
                        tipo_presenca=tipo_feriado,
                        observacoes=f"Feriado: {feriado.nome}",
                        horas_extras=0
                    )
                    presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_feriados': len(feriados),
                'message': f'Foram processados {len(feriados)} feriados: {presencas_criadas} criados, {presencas_atualizadas} atualizados.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Erro interno do servidor'
            })
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def rh_salario_add(request):
    """Adicionar novo salário"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            funcionario_id = request.POST.get('funcionario')
            valor_base = request.POST.get('valor_base')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            status = request.POST.get('status')
            observacoes = request.POST.get('observacoes', '')
            
            # Validações básicas
            if not funcionario_id or not valor_base or not data_inicio or not status:
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
                return redirect('rh:salario_add')
            
            # Converter valor base
            try:
                valor_base = Decimal(valor_base)
                if valor_base <= 0:
                    raise ValueError("Valor deve ser positivo")
            except (InvalidOperation, ValueError):
                messages.error(request, 'Valor base deve ser um número válido maior que zero.')
                return redirect('rh:salario_add')
            
            # Obter funcionário
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            
            # Converter datas
            try:
                data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date() if data_fim else None
                
                # Validar datas
                if data_fim and data_fim <= data_inicio:
                    messages.error(request, 'Data de fim deve ser posterior à data de início.')
                    return redirect('rh:salario_add')
                    
            except ValueError:
                messages.error(request, 'Formato de data inválido.')
                return redirect('rh:salario_add')
            
            # Criar salário
            salario = Salario.objects.create(
                funcionario=funcionario,
                valor_base=valor_base,
                data_inicio=data_inicio,
                data_fim=data_fim,
                status=status,
                observacoes=observacoes
            )
            
            messages.success(request, f'Salário de {funcionario.nome_completo} adicionado com sucesso!')
            return redirect('rh:salarios')
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar salário: {str(e)}')
            return redirect('rh:salario_add')
    
    # GET - Mostrar formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    status_choices = Salario.STATUS_CHOICES
    
    context = {
        'funcionarios': funcionarios,
        'status_choices': status_choices,
    }
    
    return render(request, 'rh/salarios/form.html', context)

@login_required
def rh_salario_edit(request, salario_id):
    """Editar salário"""
    try:
        salario = Salario.objects.get(id=salario_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            valor_base = request.POST.get('valor_base')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            status = request.POST.get('status')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([funcionario_id, valor_base, data_inicio, data_fim, status]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            else:
                try:
                    salario.funcionario_id = funcionario_id
                    salario.valor_base = Decimal(valor_base)
                    salario.data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    salario.data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    salario.status = status
                    salario.observacoes = observacoes
                    salario.save()
                    
                    messages.success(request, 'Salário atualizado com sucesso!')
                    return redirect('rh:salarios')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        
        context = {
            'salario': salario,
            'funcionarios': funcionarios,
            'STATUS_CHOICES': Salario.STATUS_CHOICES,
        }
        
        return render(request, 'rh/salarios/form.html', context)
        
    except Salario.DoesNotExist:
        messages.error(request, 'Salário não encontrado.')
        return redirect('rh:salarios')

@login_required
def rh_salario_delete(request, salario_id):
    """Deletar salário"""
    try:
        salario = Salario.objects.get(id=salario_id)
        
        if request.method == 'POST':
            try:
                salario.delete()
                messages.success(request, 'Salário deletado com sucesso!')
                return redirect('rh:salarios')
            except Exception as e:
                messages.error(request, f'Erro ao deletar salário: {str(e)}')
        
        context = {'salario': salario}
        return render(request, 'rh/salarios/delete.html', context)
        
    except Salario.DoesNotExist:
        messages.error(request, 'Salário não encontrado.')
        return redirect('rh:salarios')

@login_required
def rh_beneficios_salariais(request):
    """Lista de benefícios salariais"""
    beneficios = BeneficioSalarial.objects.filter(ativo=True).order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(beneficios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Dados para filtros
    tipo_choices = BeneficioSalarial.TIPO_CHOICES
    
    context = {
        'page_obj': page_obj,
        'tipo_choices': tipo_choices,
    }
    
    return render(request, 'rh/salarios/beneficios/main.html', context)

@login_required
def rh_beneficio_salarial_add(request):
    """Adicionar novo benefício salarial"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            valor_minimo_isencao = request.POST.get('valor_minimo_isencao', '0')
            valor_maximo_isencao = request.POST.get('valor_maximo_isencao', '0')
            aplicar_automaticamente = request.POST.get('aplicar_automaticamente') == 'on'
            is_nao_monetario = request.POST.get('is_nao_monetario') == 'on'
            fornecedor = request.POST.get('fornecedor', '')
            observacoes = request.POST.get('observacoes', '')
            descricao = request.POST.get('descricao', '')
            ativo = request.POST.get('ativo') == 'on'
            
            # Validações básicas
            if not nome or not tipo:
                messages.error(request, 'Nome e tipo são obrigatórios.')
                return redirect('rh:beneficio_salarial_add')
            
            # Para benefícios monetários, validar base de cálculo, tipo_valor e valor
            if not is_nao_monetario:
                if not base_calculo:
                    messages.error(request, 'Base de cálculo é obrigatória para benefícios monetários.')
                    return redirect('rh:beneficio_salarial_add')
                if not tipo_valor or not valor:
                    messages.error(request, 'Tipo de valor e valor são obrigatórios para benefícios monetários.')
                    return redirect('rh:beneficio_salarial_add')
            
            # Converter valores
            try:
                # Para benefícios não monetários, valor é sempre zero
                if is_nao_monetario:
                    valor = Decimal('0')
                    tipo_valor = 'NAO_MONETARIO'  # Definir tipo_valor correto para não monetários
                    base_calculo = 'SALARIO_BASE'  # Base padrão para não monetários (não usada no cálculo)
                else:
                    if not valor or valor.strip() == '':
                        raise ValueError("Valor é obrigatório para benefícios monetários")
                    valor = Decimal(valor)
                    if valor < 0:
                        raise ValueError("Valor deve ser positivo")
                
                valor_minimo_isencao = Decimal(valor_minimo_isencao) if valor_minimo_isencao else Decimal('0')
                valor_maximo_isencao = Decimal(valor_maximo_isencao) if valor_maximo_isencao else Decimal('0')
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Erro nos valores: {str(e)}')
                return redirect('rh:beneficio_salarial_add')
            
            # Criar benefício
            beneficio = BeneficioSalarial(
                nome=nome,
                tipo=tipo,
                tipo_valor=tipo_valor,
                valor=valor,
                base_calculo=base_calculo,
                base_calculo_personalizada=base_calculo_personalizada,
                fornecedor=fornecedor,
                observacoes=observacoes,
                ativo=ativo
            )
            beneficio.save()  # Salvar para gerar código automaticamente
            
            messages.success(request, f'Benefício "{nome}" adicionado com sucesso!')
            return redirect('rh:beneficios_salariais')
            
        except Exception as e:
            messages.error(request, f'Erro ao adicionar benefício: {str(e)}')
            return redirect('rh:beneficio_salarial_add')
    
    # GET - Mostrar formulário
    context = {
        'tipo_choices': BeneficioSalarial.TIPO_CHOICES,
        'tipo_valor_choices': BeneficioSalarial.TIPO_VALOR_CHOICES,
        'base_calculo_choices': BeneficioSalarial.BASE_CALCULO_CHOICES,
    }
    
    return render(request, 'rh/salarios/beneficios/form.html', context)

@login_required
def rh_beneficio_salarial_edit(request, beneficio_id):
    """Editar benefício salarial"""
    try:
        beneficio = BeneficioSalarial.objects.get(id=beneficio_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            is_nao_monetario = request.POST.get('is_nao_monetario') == 'on'
            # Campos de fornecedor/contato (para benefícios não monetários)
            fornecedor = request.POST.get('fornecedor', '')
            localizacao = request.POST.get('localizacao', '')
            horario_funcionamento = request.POST.get('horario_funcionamento', '')
            limite_uso = request.POST.get('limite_uso', '')
            documento_necessario = request.POST.get('documento_necessario', '')
            contato_responsavel = request.POST.get('contato_responsavel', '')
            telefone_contato = request.POST.get('telefone_contato', '')
            email_contato = request.POST.get('email_contato', '')
            observacoes = request.POST.get('observacoes', '')
            ativo = request.POST.get('ativo') == 'on'
            
            # Validações básicas
            if not nome or not tipo:
                messages.error(request, 'Nome e tipo são obrigatórios.')
            elif not is_nao_monetario and not base_calculo:
                messages.error(request, 'Base de cálculo é obrigatória para benefícios monetários.')
            elif not is_nao_monetario and (not tipo_valor or not valor):
                messages.error(request, 'Tipo de valor e valor são obrigatórios para benefícios monetários.')
            else:
                try:
                    # Converter valor com validação para benefícios não monetários
                    if is_nao_monetario:
                        valor_decimal = Decimal('0')  # Benefícios não monetários sempre têm valor zero
                        tipo_valor = 'NAO_MONETARIO'  # Definir tipo_valor correto para não monetários
                        base_calculo = 'SALARIO_BASE'  # Base padrão para não monetários (não usada no cálculo)
                    else:
                        if not valor or valor.strip() == '':
                            raise ValueError("Valor é obrigatório para benefícios monetários")
                        valor_decimal = Decimal(valor)
                        if valor_decimal < 0:
                            raise ValueError("Valor deve ser positivo")
                    
                    beneficio.nome = nome
                    beneficio.tipo = tipo
                    beneficio.tipo_valor = tipo_valor
                    beneficio.valor = valor_decimal
                    beneficio.base_calculo = base_calculo
                    beneficio.base_calculo_personalizada = base_calculo_personalizada
                    # Campos de fornecedor/contato (existem apenas em BeneficioSalarial)
                    beneficio.fornecedor = fornecedor
                    beneficio.localizacao = localizacao
                    beneficio.horario_funcionamento = horario_funcionamento
                    beneficio.limite_uso = limite_uso
                    beneficio.documento_necessario = documento_necessario
                    beneficio.contato_responsavel = contato_responsavel
                    beneficio.telefone_contato = telefone_contato
                    beneficio.email_contato = email_contato
                    beneficio.observacoes = observacoes
                    beneficio.ativo = ativo
                    beneficio.save()
                    
                    messages.success(request, 'Benefício salarial atualizado com sucesso!')
                    return redirect('rh:beneficios_salariais')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {
            'beneficio': beneficio,
            'tipo_choices': BeneficioSalarial.TIPO_CHOICES,
            'tipo_valor_choices': BeneficioSalarial.TIPO_VALOR_CHOICES,
            'base_calculo_choices': BeneficioSalarial.BASE_CALCULO_CHOICES,
        }
        
        return render(request, 'rh/salarios/beneficios/form.html', context)
        
    except BeneficioSalarial.DoesNotExist:
        messages.error(request, 'Benefício salarial não encontrado.')
        return redirect('rh:beneficios_salariais')

@login_required
def rh_beneficio_salarial_delete(request, beneficio_id):
    """Deletar benefício salarial"""
    try:
        beneficio = BeneficioSalarial.objects.get(id=beneficio_id)
        
        if request.method == 'POST':
            try:
                beneficio.delete()
                messages.success(request, 'Benefício salarial deletado com sucesso!')
                return redirect('rh:beneficios_salariais')
            except Exception as e:
                messages.error(request, f'Erro ao deletar benefício salarial: {str(e)}')
        
        context = {'beneficio': beneficio}
        return render(request, 'rh/salarios/beneficios/delete.html', context)
        
    except BeneficioSalarial.DoesNotExist:
        messages.error(request, 'Benefício salarial não encontrado.')
        return redirect('rh:beneficios_salariais')

@login_required
def rh_descontos_salariais(request):
    """Lista de descontos salariais"""
    descontos = DescontoSalarial.objects.filter(ativo=True).order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(descontos, 20)
    page_number = request.GET.get('page')
    descontos = paginator.get_page(page_number)
    
    context = {
        'page_obj': descontos,
    }
    
    return render(request, 'rh/salarios/descontos/main.html', context)

@login_required
def rh_desconto_salarial_add(request):
    """Adicionar novo desconto salarial"""
    if request.method == 'POST':
        try:
            # Obter dados do formulário
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor_raw = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            vmin_raw = request.POST.get('valor_minimo_isencao', '0')
            vmax_raw = request.POST.get('valor_maximo_isencao', '0')
            aplicar_automaticamente = request.POST.get('aplicar_automaticamente') == 'on'
            descricao = request.POST.get('descricao', '')
            observacoes = request.POST.get('observacoes', '')
            ativo = request.POST.get('ativo') == 'on'

            # Validações básicas
            if not all([nome, tipo, tipo_valor, valor_raw, base_calculo]):
                messages.error(request, 'Nome, tipo, tipo de valor, valor e base de cálculo são obrigatórios.')
                return redirect('rh:desconto_salarial_add')

            # Normalizar separadores decimais (vírgula -> ponto)
            def norm(v):
                return (v or '').replace(',', '.')

            try:
                valor = Decimal(norm(valor_raw))
                vmin = Decimal(norm(vmin_raw)) if vmin_raw else Decimal('0')
                vmax = Decimal(norm(vmax_raw)) if vmax_raw else Decimal('0')
                if valor < 0 or vmin < 0 or vmax < 0:
                    raise ValueError('Valores não podem ser negativos')
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Valores devem ser números válidos. {str(e)}')
                return redirect('rh:desconto_salarial_add')

            # Criar desconto
            DescontoSalarial.objects.create(
                nome=nome,
                tipo=tipo,
                tipo_valor=tipo_valor,
                valor=valor,
                base_calculo=base_calculo,
                base_calculo_personalizada=base_calculo_personalizada,
                valor_minimo_isencao=vmin,
                valor_maximo_isencao=vmax,
                aplicar_automaticamente=aplicar_automaticamente,
                descricao=descricao,
                observacoes=observacoes,
                ativo=ativo
            )

            messages.success(request, f'Desconto "{nome}" adicionado com sucesso!')
            return redirect('rh:descontos_salariais')

        except Exception as e:
            messages.error(request, f'Erro ao adicionar desconto: {str(e)}')
            return redirect('rh:desconto_salarial_add')
    
    # GET - Mostrar formulário
    context = {
        'tipo_choices': DescontoSalarial.TIPO_CHOICES,
        'tipo_valor_choices': DescontoSalarial.TIPO_VALOR_CHOICES,
        'base_calculo_choices': DescontoSalarial.BASE_CALCULO_CHOICES,
    }
    
    return render(request, 'rh/salarios/descontos/form.html', context)

@login_required
def rh_desconto_salarial_edit(request, desconto_id):
    """Editar desconto salarial"""
    try:
        desconto = DescontoSalarial.objects.get(id=desconto_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            tipo = request.POST.get('tipo')
            tipo_valor = request.POST.get('tipo_valor')
            valor = request.POST.get('valor')
            base_calculo = request.POST.get('base_calculo')
            base_calculo_personalizada = request.POST.get('base_calculo_personalizada', '')
            valor_minimo_isencao = request.POST.get('valor_minimo_isencao', '0')
            valor_maximo_isencao = request.POST.get('valor_maximo_isencao', '0')
            aplicar_automaticamente = request.POST.get('aplicar_automaticamente') == 'on'
            observacoes = request.POST.get('observacoes', '')
            ativo = request.POST.get('ativo') == 'on'

            # Validações básicas
            if not all([nome, tipo, tipo_valor, valor, base_calculo]):
                messages.error(request, 'Nome, tipo, tipo de valor, valor e base de cálculo são obrigatórios.')
            else:
                try:
                    # Conversões seguras para Decimal
                    valor_decimal = Decimal(valor)
                    if valor_decimal < 0:
                        raise ValueError('Valor deve ser positivo')
                    vmin = Decimal(valor_minimo_isencao) if valor_minimo_isencao else Decimal('0')
                    vmax = Decimal(valor_maximo_isencao) if valor_maximo_isencao else Decimal('0')

                    # Atualizar campos existentes no modelo
                    desconto.nome = nome
                    desconto.tipo = tipo
                    desconto.tipo_valor = tipo_valor
                    desconto.valor = valor_decimal
                    desconto.base_calculo = base_calculo
                    desconto.base_calculo_personalizada = base_calculo_personalizada
                    desconto.valor_minimo_isencao = vmin
                    desconto.valor_maximo_isencao = vmax
                    desconto.aplicar_automaticamente = aplicar_automaticamente
                    desconto.observacoes = observacoes
                    desconto.ativo = ativo
                    desconto.save()

                    messages.success(request, 'Desconto salarial atualizado com sucesso!')
                    return redirect('rh:descontos_salariais')
                except (InvalidOperation, ValueError) as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {
            'desconto': desconto,
            'tipo_choices': DescontoSalarial.TIPO_CHOICES,
            'tipo_valor_choices': DescontoSalarial.TIPO_VALOR_CHOICES,
            'base_calculo_choices': DescontoSalarial.BASE_CALCULO_CHOICES,
        }
        
        return render(request, 'rh/salarios/descontos/form.html', context)
        
    except DescontoSalarial.DoesNotExist:
        messages.error(request, 'Desconto salarial não encontrado.')
        return redirect('rh:descontos_salariais')

@login_required
def rh_desconto_salarial_delete(request, desconto_id):
    """Deletar desconto salarial"""
    try:
        desconto = DescontoSalarial.objects.get(id=desconto_id)
        
        if request.method == 'POST':
            try:
                desconto.delete()
                messages.success(request, 'Desconto salarial deletado com sucesso!')
                return redirect('rh:descontos_salariais')
            except Exception as e:
                messages.error(request, f'Erro ao deletar desconto salarial: {str(e)}')
        
        context = {'desconto': desconto}
        return render(request, 'rh/salarios/descontos/delete.html', context)
        
    except DescontoSalarial.DoesNotExist:
        messages.error(request, 'Desconto salarial não encontrado.')
        return redirect('rh:descontos_salariais')

@login_required
def rh_treinamentos(request):
    """Lista de treinamentos"""
    from datetime import date, timedelta
    from django.db.models import Q
    
    # Filtros
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    tipo_filter = request.GET.get('tipo', '')
    prioridade_filter = request.GET.get('prioridade', '')
    
    # Query base
    treinamentos = Treinamento.objects.all()
    
    # Aplicar filtros
    if search_query:
        treinamentos = treinamentos.filter(
            Q(nome__icontains=search_query) |
            Q(instrutor__icontains=search_query) |
            Q(instituicao__icontains=search_query)
        )
    
    if status_filter:
        treinamentos = treinamentos.filter(status=status_filter)
    
    if tipo_filter:
        treinamentos = treinamentos.filter(tipo=tipo_filter)
    
    if prioridade_filter:
        treinamentos = treinamentos.filter(prioridade=prioridade_filter)
    
    # Ordenação
    treinamentos = treinamentos.order_by('-data_inicio')
    
    # Paginação
    paginator = Paginator(treinamentos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    total_treinamentos = Treinamento.objects.count()
    treinamentos_ativos = Treinamento.objects.filter(status='EM_ANDAMENTO').count()
    treinamentos_planejados = Treinamento.objects.filter(status='PLANEJADO').count()
    treinamentos_concluidos = Treinamento.objects.filter(status='CONCLUIDO').count()
    
    # Próximos 7 dias
    data_limite = date.today() + timedelta(days=7)
    proximos_7_dias = Treinamento.objects.filter(
        data_inicio__lte=data_limite,
        data_inicio__gte=date.today()
    ).count()
    
    # Total de inscrições - otimizado para evitar N+1 queries
    total_inscricoes = InscricaoTreinamento.objects.count()
    
    # Choices para os filtros
    status_choices = Treinamento.STATUS_CHOICES
    tipo_choices = Treinamento.TIPO_CHOICES
    prioridade_choices = Treinamento.PRIORIDADE_CHOICES
    
    context = {
        'treinamentos': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
        'prioridade_filter': prioridade_filter,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
        'prioridade_choices': prioridade_choices,
        'stats': {
            'total_treinamentos': total_treinamentos,
            'treinamentos_ativos': treinamentos_ativos,
            'treinamentos_planejados': treinamentos_planejados,
            'treinamentos_concluidos': treinamentos_concluidos,
            'proximos_7_dias': proximos_7_dias,
            'total_inscricoes': total_inscricoes,
        }
    }
    
    return render(request, 'rh/treinamentos/main.html', context)

@login_required
def treinamento_add(request):
    """Adicionar treinamento"""
    from datetime import datetime
    from decimal import Decimal
    
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        tipo = request.POST.get('tipo')
        status = request.POST.get('status')
        prioridade = request.POST.get('prioridade')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        capacidade_maxima = request.POST.get('capacidade_maxima')
        instrutor = request.POST.get('instrutor', '')
        instituicao = request.POST.get('instituicao', '')
        local = request.POST.get('local', '')
        observacoes = request.POST.get('observacoes', '')
        
        if not all([nome, tipo, status, prioridade, data_inicio, data_fim, capacidade_maxima]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                data_limite_inscricao = request.POST.get('data_limite_inscricao')
                if data_limite_inscricao:
                    data_limite_inscricao = datetime.strptime(data_limite_inscricao, '%Y-%m-%d').date()
                
                Treinamento.objects.create(
                    nome=nome,
                    descricao=descricao,
                    tipo=tipo,
                    status=status,
                    prioridade=prioridade,
                    data_inicio=datetime.strptime(data_inicio, '%Y-%m-%d').date(),
                    data_fim=datetime.strptime(data_fim, '%Y-%m-%d').date(),
                    capacidade_maxima=int(capacidade_maxima),
                    instrutor=instrutor,
                    instituicao=instituicao,
                    local=local,
                    custo_por_participante=Decimal(request.POST.get('custo_por_participante', '0')),
                    custo_total=Decimal(request.POST.get('custo_total', '0')),
                    carga_horaria=int(request.POST.get('carga_horaria', '0')),
                    data_limite_inscricao=data_limite_inscricao,
                    objetivos=request.POST.get('objetivos', ''),
                    requisitos=request.POST.get('requisitos', ''),
                    conteudo_programatico=request.POST.get('conteudo_programatico', ''),
                    emite_certificado='emite_certificado' in request.POST,
                    ativo='ativo' in request.POST,
                    observacoes=observacoes
                )
                messages.success(request, 'Treinamento criado com sucesso!')
                return redirect('rh:treinamentos')
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    context = {
        'status_choices': Treinamento.STATUS_CHOICES,
        'tipo_choices': Treinamento.TIPO_CHOICES,
        'prioridade_choices': Treinamento.PRIORIDADE_CHOICES,
    }
    
    return render(request, 'rh/treinamentos/form.html', context)

@login_required
def treinamento_edit(request, treinamento_id):
    """Editar treinamento"""
    from datetime import datetime
    from decimal import Decimal
    
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            descricao = request.POST.get('descricao', '')
            tipo = request.POST.get('tipo')
            status = request.POST.get('status')
            prioridade = request.POST.get('prioridade')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            capacidade_maxima = request.POST.get('capacidade_maxima')
            instrutor = request.POST.get('instrutor', '')
            instituicao = request.POST.get('instituicao', '')
            local = request.POST.get('local', '')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([nome, tipo, status, prioridade, data_inicio, data_fim, capacidade_maxima]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            else:
                try:
                    treinamento.nome = nome
                    treinamento.descricao = descricao
                    treinamento.tipo = tipo
                    treinamento.status = status
                    treinamento.prioridade = prioridade
                    treinamento.data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    treinamento.data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    treinamento.capacidade_maxima = int(capacidade_maxima)
                    treinamento.instrutor = instrutor
                    treinamento.instituicao = instituicao
                    treinamento.local = local
                    treinamento.custo_por_participante = Decimal(request.POST.get('custo_por_participante', '0'))
                    treinamento.custo_total = Decimal(request.POST.get('custo_total', '0'))
                    treinamento.carga_horaria = int(request.POST.get('carga_horaria', '0'))
                    treinamento.data_limite_inscricao = request.POST.get('data_limite_inscricao') or None
                    if treinamento.data_limite_inscricao:
                        treinamento.data_limite_inscricao = datetime.strptime(treinamento.data_limite_inscricao, '%Y-%m-%d').date()
                    treinamento.objetivos = request.POST.get('objetivos', '')
                    treinamento.requisitos = request.POST.get('requisitos', '')
                    treinamento.conteudo_programatico = request.POST.get('conteudo_programatico', '')
                    treinamento.emite_certificado = 'emite_certificado' in request.POST
                    treinamento.ativo = 'ativo' in request.POST
                    treinamento.observacoes = observacoes
                    treinamento.save()
                    
                    messages.success(request, 'Treinamento atualizado com sucesso!')
                    return redirect('rh:treinamentos')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {
            'treinamento': treinamento,
            'status_choices': Treinamento.STATUS_CHOICES,
            'tipo_choices': Treinamento.TIPO_CHOICES,
            'prioridade_choices': Treinamento.PRIORIDADE_CHOICES,
        }
        
        return render(request, 'rh/treinamentos/form.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_detail(request, treinamento_id):
    """Detalhes do treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        # Buscar inscrições (se existir o modelo)
        inscricoes = []
        try:
            from meuprojeto.empresa.models_rh import InscricaoTreinamento
            inscricoes = InscricaoTreinamento.objects.filter(treinamento=treinamento)
        except:
            pass
        
        context = {
            'treinamento': treinamento,
            'inscricoes': inscricoes,
        }
        
        return render(request, 'rh/treinamentos/detail.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_delete(request, treinamento_id):
    """Deletar treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        if request.method == 'POST':
            try:
                treinamento.delete()
                messages.success(request, 'Treinamento deletado com sucesso!')
                return redirect('rh:treinamentos')
            except Exception as e:
                messages.error(request, f'Erro ao deletar treinamento: {str(e)}')
        
        context = {'treinamento': treinamento}
        return render(request, 'rh/treinamentos/delete.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_inscrever(request, treinamento_id):
    """Inscrever funcionário em treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            observacoes = request.POST.get('observacoes', '')
            
            if not funcionario_id:
                messages.error(request, 'Funcionário é obrigatório.')
            else:
                try:
                    # Verificar se já existe inscrição
                    from meuprojeto.empresa.models_rh import InscricaoTreinamento
                    if InscricaoTreinamento.objects.filter(treinamento=treinamento, funcionario_id=funcionario_id).exists():
                        messages.error(request, 'Funcionário já está inscrito neste treinamento.')
                    else:
                        InscricaoTreinamento.objects.create(
                            treinamento=treinamento,
                            funcionario_id=funcionario_id,
                            observacoes=observacoes,
                            status='PENDENTE'
                        )
                        messages.success(request, 'Inscrição realizada com sucesso!')
                        return redirect('rh:treinamento_inscricoes', treinamento_id=treinamento_id)
                except Exception as e:
                    messages.error(request, f'Erro ao inscrever: {str(e)}')
        
        # Filtros
        search_query = request.GET.get('search', '')
        departamento_filter = request.GET.get('departamento', '')
        
        funcionarios = Funcionario.objects.filter(status='AT')
        
        # Aplicar filtros
        if search_query:
            funcionarios = funcionarios.filter(
                Q(nome_completo__icontains=search_query) |
                Q(cargo__nome__icontains=search_query)
            )
        
        if departamento_filter:
            funcionarios = funcionarios.filter(cargo__departamento_id=departamento_filter)
        
        # Excluir funcionários já inscritos
        try:
            from meuprojeto.empresa.models_rh import InscricaoTreinamento
            funcionarios_inscritos = InscricaoTreinamento.objects.filter(
                treinamento=treinamento
            ).values_list('funcionario_id', flat=True)
            funcionarios = funcionarios.exclude(id__in=funcionarios_inscritos)
        except:
            pass
        
        funcionarios = funcionarios.order_by('nome_completo')
        
        # Obter departamentos para o dropdown
        from meuprojeto.empresa.models import Departamento
        departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
        
        context = {
            'treinamento': treinamento,
            'funcionarios': funcionarios,
            'search_query': search_query,
            'departamento_filter': departamento_filter,
            'departamentos': departamentos,
        }
        return render(request, 'rh/treinamentos/inscrever.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def treinamento_inscricoes(request, treinamento_id):
    """Lista de inscrições do treinamento"""
    try:
        treinamento = Treinamento.objects.get(id=treinamento_id)
        
        # Buscar inscrições (se existir o modelo)
        inscricoes = []
        status_choices = []
        try:
            from meuprojeto.empresa.models_rh import InscricaoTreinamento
            inscricoes = InscricaoTreinamento.objects.filter(treinamento=treinamento).order_by('-data_inscricao')
            status_choices = InscricaoTreinamento.STATUS_CHOICES
        except:
            pass
        
        # Filtros
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        
        # Aplicar filtros
        if search_query:
            inscricoes = inscricoes.filter(
                Q(funcionario__nome_completo__icontains=search_query) |
                Q(funcionario__cargo__nome__icontains=search_query)
            )
        
        if status_filter:
            inscricoes = inscricoes.filter(status=status_filter)
        
        # Calcular estatísticas
        total_inscricoes = inscricoes.count()
        confirmadas = inscricoes.filter(status='CONFIRMADA').count()
        pendentes = inscricoes.filter(status='PENDENTE').count()
        canceladas = inscricoes.filter(status='CANCELADA').count()
        concluidas = inscricoes.filter(status='CONCLUIDA').count()
        
        context = {
            'treinamento': treinamento,
            'inscricoes': inscricoes,
            'search_query': search_query,
            'status_filter': status_filter,
            'status_choices': status_choices,
            'total_inscricoes': total_inscricoes,
            'confirmadas': confirmadas,
            'pendentes': pendentes,
            'canceladas': canceladas,
            'concluidas': concluidas,
        }
        return render(request, 'rh/treinamentos/inscricoes.html', context)
        
    except Treinamento.DoesNotExist:
        messages.error(request, 'Treinamento não encontrado.')
        return redirect('rh:treinamentos')

@login_required
def inscricao_alterar_status(request, inscricao_id):
    """Alterar status da inscrição"""
    try:
        from meuprojeto.empresa.models_rh import InscricaoTreinamento
        inscricao = InscricaoTreinamento.objects.get(id=inscricao_id)
        
        if request.method == 'POST':
            status = request.POST.get('status')
            observacoes = request.POST.get('observacoes', '')
            
            if status:
                inscricao.status = status
                if observacoes:
                    inscricao.observacoes = observacoes
                inscricao.save()
                messages.success(request, 'Status da inscrição atualizado com sucesso!')
                return redirect('rh:treinamento_inscricoes', treinamento_id=inscricao.treinamento.id)
        
        context = {
            'inscricao': inscricao,
            'STATUS_CHOICES': [
                ('INSCRITO', 'Inscrito'),
                ('CONFIRMADO', 'Confirmado'),
                ('CANCELADO', 'Cancelado'),
                ('CONCLUIDO', 'Concluído'),
            ]
        }
        return render(request, 'rh/treinamentos/alterar_status.html', context)
        
    except Exception as e:
        messages.error(request, 'Inscrição não encontrada.')
        return redirect('rh:treinamentos')

@login_required
def inscricao_avaliar(request, inscricao_id):
    """Avaliar inscrição de treinamento"""
    try:
        from meuprojeto.empresa.models_rh import InscricaoTreinamento
        inscricao = InscricaoTreinamento.objects.get(id=inscricao_id)
        
        if request.method == 'POST':
            nota = request.POST.get('nota')
            observacoes = request.POST.get('observacoes', '')
            
            if nota:
                inscricao.nota = float(nota)
                inscricao.observacoes = observacoes
                inscricao.save()
                messages.success(request, 'Inscrição avaliada com sucesso!')
                return redirect('rh:treinamento_inscricoes', treinamento_id=inscricao.treinamento.id)
        
        context = {'inscricao': inscricao}
        return render(request, 'rh/treinamentos/avaliar.html', context)
        
    except Exception as e:
        messages.error(request, 'Inscrição não encontrada.')
        return redirect('rh:treinamentos')

@login_required
def inscricao_deletar(request, inscricao_id):
    """Deletar inscrição de treinamento"""
    try:
        from meuprojeto.empresa.models_rh import InscricaoTreinamento
        inscricao = InscricaoTreinamento.objects.get(id=inscricao_id)
        
        if request.method == 'POST':
            inscricao.delete()
            messages.success(request, 'Inscrição deletada com sucesso!')
            return redirect('rh:treinamento_inscricoes', treinamento_id=inscricao.treinamento.id)
        
        context = {'inscricao': inscricao}
        return render(request, 'rh/treinamentos/deletar_inscricao.html', context)
        
    except Exception as e:
        messages.error(request, 'Inscrição não encontrada.')
        return redirect('rh:treinamentos')

@login_required
def rh_avaliacoes(request):
    """Lista de avaliações de desempenho"""
    avaliacoes = AvaliacaoDesempenho.objects.all().order_by('-data_avaliacao')
    
    # Filtros
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    tipo_filter = request.GET.get('tipo', '')
    ano_filter = request.GET.get('ano', '')
    departamento_filter = request.GET.get('departamento', '')
    cargo_filter = request.GET.get('cargo', '')
    
    # Aplicar filtros
    if search_query:
        avaliacoes = avaliacoes.filter(
            Q(funcionario__nome_completo__icontains=search_query) |
            Q(avaliador__nome_completo__icontains=search_query)
        )
    
    if status_filter:
        avaliacoes = avaliacoes.filter(status=status_filter)
    
    if tipo_filter:
        avaliacoes = avaliacoes.filter(tipo=tipo_filter)
    
    if ano_filter:
        avaliacoes = avaliacoes.filter(data_avaliacao__year=ano_filter)
    
    if departamento_filter:
        avaliacoes = avaliacoes.filter(funcionario__departamento_id=departamento_filter)
    
    if cargo_filter:
        avaliacoes = avaliacoes.filter(funcionario__cargo_id=cargo_filter)
    
    # Obter anos disponíveis para o dropdown (de todas as avaliações, não apenas as filtradas)
    todos_anos = AvaliacaoDesempenho.objects.exclude(data_avaliacao__isnull=True).values_list('data_avaliacao__year', flat=True).distinct()
    anos = sorted([ano for ano in todos_anos if ano is not None], reverse=True)
    
    # Obter departamentos e cargos para os dropdowns
    from meuprojeto.empresa.models import Departamento, Cargo
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    # Calcular estatísticas (usando todas as avaliações, não apenas as filtradas)
    todas_avaliacoes = AvaliacaoDesempenho.objects.all()
    
    stats = {
        'total_avaliacoes': todas_avaliacoes.count(),
        'planejadas': todas_avaliacoes.filter(status='PLANEJADA').count(),
        'em_andamento': todas_avaliacoes.filter(status='EM_ANDAMENTO').count(),
        'concluidas': todas_avaliacoes.filter(status='CONCLUIDA').count(),
        'canceladas': todas_avaliacoes.filter(status='CANCELADA').count(),
    }
    
    # Calcular nota média das avaliações concluídas
    from django.db import models
    avaliacoes_com_nota = todas_avaliacoes.filter(status='CONCLUIDA').exclude(nota_geral__isnull=True)
    if avaliacoes_com_nota.exists():
        stats['nota_media'] = avaliacoes_com_nota.aggregate(avg_nota=models.Avg('nota_geral'))['avg_nota']
    else:
        stats['nota_media'] = 0
    
    # Calcular percentagens
    total = stats['total_avaliacoes']
    if total > 0:
        stats['percent_planejadas'] = round((stats['planejadas'] / total) * 100, 1)
        stats['percent_em_andamento'] = round((stats['em_andamento'] / total) * 100, 1)
        stats['percent_concluidas'] = round((stats['concluidas'] / total) * 100, 1)
        stats['percent_canceladas'] = round((stats['canceladas'] / total) * 100, 1)
    else:
        stats['percent_planejadas'] = 0
        stats['percent_em_andamento'] = 0
        stats['percent_concluidas'] = 0
        stats['percent_canceladas'] = 0
    
    # Paginação
    paginator = Paginator(avaliacoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'avaliacoes': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
        'ano_filter': ano_filter,
        'departamento_filter': departamento_filter,
        'cargo_filter': cargo_filter,
        'status_choices': AvaliacaoDesempenho.STATUS_CHOICES,
        'tipo_choices': AvaliacaoDesempenho.TIPO_CHOICES,
        'anos': anos,
        'departamentos': departamentos,
        'cargos': cargos,
        'stats': stats,
    }
    
    return render(request, 'rh/avaliacoes/main.html', context)

@login_required
def avaliacao_add_batch(request):
    """Adicionar avaliações em lote por departamento ou cargo"""
    if request.method == 'POST':
        departamento_id = request.POST.get('departamento')
        cargo_id = request.POST.get('cargo')
        avaliador_id = request.POST.get('avaliador')
        tipo = request.POST.get('tipo')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        
        if not all([avaliador_id, tipo, data_inicio, data_fim]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                # Obter funcionários baseado nos filtros
                funcionarios = Funcionario.objects.filter(status='AT')
                
                if departamento_id:
                    funcionarios = funcionarios.filter(departamento_id=departamento_id)
                
                if cargo_id:
                    funcionarios = funcionarios.filter(cargo_id=cargo_id)
                
                if not funcionarios.exists():
                    messages.warning(request, 'Nenhum funcionário encontrado com os critérios selecionados.')
                    return redirect('rh:avaliacao_add_batch')
                
                # Criar avaliações para cada funcionário
                avaliacoes_criadas = 0
                for funcionario in funcionarios:
                    # Verificar se já existe avaliação para este funcionário no período
                    avaliacao_existente = AvaliacaoDesempenho.objects.filter(
                        funcionario=funcionario,
                        data_inicio__lte=datetime.strptime(data_fim, '%Y-%m-%d').date(),
                        data_fim__gte=datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    ).exists()
                    
                    if not avaliacao_existente:
                        AvaliacaoDesempenho.objects.create(
                            funcionario=funcionario,
                            avaliador_id=avaliador_id,
                            tipo=tipo,
                            status='PLANEJADA',
                            data_inicio=datetime.strptime(data_inicio, '%Y-%m-%d').date(),
                            data_fim=datetime.strptime(data_fim, '%Y-%m-%d').date()
                        )
                        avaliacoes_criadas += 1
                
                if avaliacoes_criadas > 0:
                    messages.success(request, f'{avaliacoes_criadas} avaliações criadas com sucesso!')
                else:
                    messages.warning(request, 'Nenhuma avaliação foi criada. Verifique se já existem avaliações para o período selecionado.')
                
                return redirect('rh:avaliacoes')
                
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao criar avaliações: {str(e)}')
    
    # Buscar dados para o formulário
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.filter(ativo=True).order_by('nome')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    
    context = {
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'cargos': cargos,
        'STATUS_CHOICES': AvaliacaoDesempenho.STATUS_CHOICES,
        'TIPO_CHOICES': AvaliacaoDesempenho.TIPO_CHOICES,
    }
    
    return render(request, 'rh/avaliacoes/add_batch.html', context)

@login_required
def avaliacao_add(request):
    """Adicionar avaliação de desempenho"""
    if request.method == 'POST':
        funcionario_id = request.POST.get('funcionario')
        avaliador_id = request.POST.get('avaliador')
        tipo = request.POST.get('tipo')
        status = request.POST.get('status')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        nota_geral = request.POST.get('nota_geral')
        classificacao = request.POST.get('classificacao')
        metas_estabelecidas = request.POST.get('metas_estabelecidas')
        metas_alcancadas = request.POST.get('metas_alcancadas')
        pontos_fortes = request.POST.get('pontos_fortes')
        pontos_melhoria = request.POST.get('pontos_melhoria')
        observacoes_avaliador = request.POST.get('observacoes_avaliador')
        observacoes_funcionario = request.POST.get('observacoes_funcionario')
        plano_desenvolvimento = request.POST.get('plano_desenvolvimento')
        
        if not all([funcionario_id, avaliador_id, tipo, status, data_inicio, data_fim]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
        else:
            try:
                avaliacao = AvaliacaoDesempenho.objects.create(
                    funcionario_id=funcionario_id,
                    avaliador_id=avaliador_id,
                    tipo=tipo,
                    status=status,
                    data_inicio=datetime.strptime(data_inicio, '%Y-%m-%d').date(),
                    data_fim=datetime.strptime(data_fim, '%Y-%m-%d').date(),
                    nota_geral=float(nota_geral) if nota_geral else None,
                    classificacao=classificacao,
                    metas_estabelecidas=metas_estabelecidas,
                    metas_alcancadas=metas_alcancadas,
                    pontos_fortes=pontos_fortes,
                    pontos_melhoria=pontos_melhoria,
                    observacoes_avaliador=observacoes_avaliador,
                    observacoes_funcionario=observacoes_funcionario,
                    plano_desenvolvimento=plano_desenvolvimento
                )
                
                # Actualizar status automaticamente
                avaliacao.actualizar_status_automatico()
                
                # Processar critérios de avaliação
                criterios = CriterioAvaliacao.objects.filter(ativo=True)
                for criterio in criterios:
                    nota_key = f'nota_{criterio.id}'
                    obs_key = f'obs_{criterio.id}'
                    
                    if nota_key in request.POST and request.POST[nota_key]:
                        nota = float(request.POST[nota_key])
                        observacoes = request.POST.get(obs_key, '')
                        
                        CriterioAvaliado.objects.create(
                            avaliacao=avaliacao,
                            criterio=criterio,
                            nota=nota,
                            observacoes=observacoes
                        )
                        
                        # Actualizar status após adicionar critério
                        avaliacao.actualizar_status_automatico()
                
                # Recalcular nota geral e classificação após processar critérios
                avaliacao.nota_geral = avaliacao.calcular_nota_geral()
                avaliacao.classificacao = avaliacao.definir_classificacao()
                avaliacao.save()
                
                messages.success(request, 'Avaliação criada com sucesso!')
                return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao.id)
                
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    criterios = CriterioAvaliacao.objects.filter(ativo=True)
    
    context = {
        'funcionarios': funcionarios,
        'criterios': criterios,
        'STATUS_CHOICES': AvaliacaoDesempenho.STATUS_CHOICES,
        'TIPO_CHOICES': AvaliacaoDesempenho.TIPO_CHOICES,
        'CLASSIFICACAO_CHOICES': AvaliacaoDesempenho.CLASSIFICACAO_CHOICES,
    }
    
    return render(request, 'rh/avaliacoes/form.html', context)

@login_required
def avaliacao_iniciar(request, avaliacao_id):
    """Iniciar uma avaliação (mudar status para EM_ANDAMENTO)"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if avaliacao.status == 'PLANEJADA':
            avaliacao.status = 'EM_ANDAMENTO'
            from django.utils import timezone
            avaliacao.data_avaliacao = timezone.now().date()
            avaliacao.save()
            messages.success(request, 'Avaliação iniciada com sucesso!')
        else:
            messages.warning(request, 'Esta avaliação não pode ser iniciada no estado actual.')
            
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
    
    return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao_id)

@login_required
def avaliacao_concluir(request, avaliacao_id):
    """Concluir uma avaliação (mudar status para CONCLUIDA)"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if avaliacao.marcar_como_concluida():
            messages.success(request, 'Avaliação concluída com sucesso!')
        else:
            messages.warning(request, 'Esta avaliação não pode ser concluída. Verifique se tem nota geral e critérios avaliados.')
            
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
    
    return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao_id)

@login_required
def avaliacao_edit(request, avaliacao_id):
    """Editar uma avaliação de desempenho"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if request.method == 'POST':
            # Processar dados do formulário
            funcionario_id = request.POST.get('funcionario')
            avaliador_id = request.POST.get('avaliador')
            tipo = request.POST.get('tipo')
            status = request.POST.get('status')
            data_inicio = request.POST.get('data_inicio')
            data_fim = request.POST.get('data_fim')
            nota_geral = request.POST.get('nota_geral')
            classificacao = request.POST.get('classificacao')
            metas_estabelecidas = request.POST.get('metas_estabelecidas')
            metas_alcancadas = request.POST.get('metas_alcancadas')
            pontos_fortes = request.POST.get('pontos_fortes')
            pontos_melhoria = request.POST.get('pontos_melhoria')
            observacoes_avaliador = request.POST.get('observacoes_avaliador')
            observacoes_funcionario = request.POST.get('observacoes_funcionario')
            plano_desenvolvimento = request.POST.get('plano_desenvolvimento')
            
            # Validações básicas
            if not all([funcionario_id, avaliador_id, tipo, status, data_inicio, data_fim]):
                messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            else:
                try:
                    # Atualizar avaliação
                    avaliacao.funcionario_id = funcionario_id
                    avaliacao.avaliador_id = avaliador_id
                    avaliacao.tipo = tipo
                    avaliacao.status = status
                    avaliacao.data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    avaliacao.data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    
                    if nota_geral:
                        avaliacao.nota_geral = float(nota_geral)
                    if classificacao:
                        avaliacao.classificacao = classificacao
                    if metas_estabelecidas:
                        avaliacao.metas_estabelecidas = metas_estabelecidas
                    if metas_alcancadas:
                        avaliacao.metas_alcancadas = metas_alcancadas
                    if pontos_fortes:
                        avaliacao.pontos_fortes = pontos_fortes
                    if pontos_melhoria:
                        avaliacao.pontos_melhoria = pontos_melhoria
                    if observacoes_avaliador:
                        avaliacao.observacoes_avaliador = observacoes_avaliador
                    if observacoes_funcionario:
                        avaliacao.observacoes_funcionario = observacoes_funcionario
                    if plano_desenvolvimento:
                        avaliacao.plano_desenvolvimento = plano_desenvolvimento
                    
                    avaliacao.save()
                    
                    # Actualizar status automaticamente
                    avaliacao.actualizar_status_automatico()
                    
                    # Processar critérios de avaliação
                    criterios = CriterioAvaliacao.objects.filter(ativo=True)
                    for criterio in criterios:
                        nota_key = f'nota_{criterio.id}'
                        obs_key = f'obs_{criterio.id}'
                        
                        if nota_key in request.POST and request.POST[nota_key]:
                            nota = float(request.POST[nota_key])
                            observacoes = request.POST.get(obs_key, '')
                            
                            # Atualizar ou criar avaliação do critério
                            criterio_avaliado, created = CriterioAvaliado.objects.get_or_create(
                                avaliacao=avaliacao,
                                criterio=criterio,
                                defaults={
                                    'nota': nota,
                                    'observacoes': observacoes
                                }
                            )
                            
                            if not created:
                                criterio_avaliado.nota = nota
                                criterio_avaliado.observacoes = observacoes
                                criterio_avaliado.save()
                            
                            # Actualizar status após modificar critério
                            avaliacao.actualizar_status_automatico()
                    
                    # Recalcular nota geral e classificação após processar critérios
                    avaliacao.nota_geral = avaliacao.calcular_nota_geral()
                    avaliacao.classificacao = avaliacao.definir_classificacao()
                    avaliacao.save()
                    
                    messages.success(request, 'Avaliação atualizada com sucesso!')
                    return redirect('rh:avaliacao_detail', avaliacao_id=avaliacao.id)
                    
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        # Buscar dados para o formulário
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        criterios = CriterioAvaliacao.objects.filter(ativo=True)
        avaliacoes_criterios = CriterioAvaliado.objects.filter(avaliacao=avaliacao)
        
        # Criar dicionário de notas para facilitar o acesso no template
        notas_criterios = {}
        for ac in avaliacoes_criterios:
            notas_criterios[ac.criterio.id] = {
                'nota': ac.nota,
                'observacoes': ac.observacoes
            }
        
        context = {
            'avaliacao': avaliacao,
            'funcionarios': funcionarios,
            'criterios': criterios,
            'notas_criterios': notas_criterios,
            'STATUS_CHOICES': AvaliacaoDesempenho.STATUS_CHOICES,
            'TIPO_CHOICES': AvaliacaoDesempenho.TIPO_CHOICES,
            'CLASSIFICACAO_CHOICES': AvaliacaoDesempenho.CLASSIFICACAO_CHOICES,
        }
        
        return render(request, 'rh/avaliacoes/form.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_detail(request, avaliacao_id):
    """Detalhes de uma avaliação específica"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        # Buscar critérios de avaliação
        criterios = CriterioAvaliacao.objects.filter(ativo=True)
        
        # Buscar avaliações dos critérios para esta avaliação
        avaliacoes_criterios = CriterioAvaliado.objects.filter(avaliacao=avaliacao)
        
        context = {
            'avaliacao': avaliacao,
            'criterios': criterios,
            'avaliacoes_criterios': avaliacoes_criterios,
        }
        
        return render(request, 'rh/avaliacoes/detail.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_delete(request, avaliacao_id):
    """Deletar avaliação de desempenho"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        if request.method == 'POST':
            try:
                avaliacao.delete()
                messages.success(request, 'Avaliação deletada com sucesso!')
                return redirect('rh:avaliacoes')
            except Exception as e:
                messages.error(request, f'Erro ao deletar avaliação: {str(e)}')
        
        context = {'avaliacao': avaliacao}
        return render(request, 'rh/avaliacoes/delete.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_print(request, avaliacao_id):
    """Gerar PDF da avaliação de desempenho"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        # Por enquanto, redirecionar para a versão HTML
        # Em uma implementação completa, aqui seria gerado o PDF
        return redirect('rh:avaliacao_print_html', avaliacao_id=avaliacao_id)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def avaliacao_print_html(request, avaliacao_id):
    """Visualização da avaliação para impressão"""
    try:
        avaliacao = AvaliacaoDesempenho.objects.get(id=avaliacao_id)
        
        # Buscar critérios de avaliação
        criterios = CriterioAvaliacao.objects.filter(ativo=True)
        
        # Buscar avaliações dos critérios para esta avaliação
        avaliacoes_criterios = CriterioAvaliado.objects.filter(avaliacao=avaliacao)
        
        context = {
            'avaliacao': avaliacao,
            'criterios': criterios,
            'avaliacoes_criterios': avaliacoes_criterios,
        }
        
        return render(request, 'rh/avaliacoes/print.html', context)
        
    except AvaliacaoDesempenho.DoesNotExist:
        messages.error(request, 'Avaliação não encontrada.')
        return redirect('rh:avaliacoes')

@login_required
def criterios(request):
    """Lista de critérios de avaliação"""
    criterios = CriterioAvaliacao.objects.filter(ativo=True).order_by('nome')
    
    # Filtros
    search_query = request.GET.get('search', '')
    if search_query:
        criterios = criterios.filter(nome__icontains=search_query)
    
    # Paginação
    paginator = Paginator(criterios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'criterios': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'rh/avaliacoes/criterios/main.html', context)

@login_required
def criterio_add(request):
    """Adicionar critério de avaliação"""
    if request.method == 'POST':
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        peso = request.POST.get('peso')
        ativo = request.POST.get('ativo') == 'on'
        
        if not all([nome, peso]):
            messages.error(request, 'Nome e peso são obrigatórios.')
        else:
            try:
                CriterioAvaliacao.objects.create(
                    nome=nome,
                    descricao=descricao,
                    peso=int(peso),
                    ativo=ativo
                )
                messages.success(request, 'Critério de avaliação criado com sucesso!')
                return redirect('rh:criterios')
            except ValueError as e:
                messages.error(request, f'Erro nos dados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    return render(request, 'rh/avaliacoes/criterios/form.html')

@login_required
def criterio_edit(request, criterio_id):
    """Editar critério de avaliação"""
    try:
        criterio = CriterioAvaliacao.objects.get(id=criterio_id)
        
        if request.method == 'POST':
            nome = request.POST.get('nome')
            descricao = request.POST.get('descricao', '')
            peso = request.POST.get('peso')
            ativo = request.POST.get('ativo') == 'on'
            
            if not all([nome, peso]):
                messages.error(request, 'Nome e peso são obrigatórios.')
            else:
                try:
                    criterio.nome = nome
                    criterio.descricao = descricao
                    criterio.peso = int(peso)
                    criterio.ativo = ativo
                    criterio.save()
                    
                    messages.success(request, 'Critério de avaliação atualizado com sucesso!')
                    return redirect('rh:criterios')
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        context = {'criterio': criterio}
        return render(request, 'rh/avaliacoes/criterios/form.html', context)
        
    except CriterioAvaliacao.DoesNotExist:
        messages.error(request, 'Critério de avaliação não encontrado.')
        return redirect('rh:criterios')

@login_required
def criterio_delete(request, criterio_id):
    """Deletar critério de avaliação"""
    try:
        criterio = CriterioAvaliacao.objects.get(id=criterio_id)
        
        if request.method == 'POST':
            try:
                # Verificar se há avaliações usando este critério
                avaliacoes_count = CriterioAvaliado.objects.filter(criterio=criterio).count()
                if avaliacoes_count > 0:
                    messages.error(request, f'Não é possível deletar este critério pois existem {avaliacoes_count} avaliações associadas.')
                    return redirect('rh:criterios')
                
                criterio.delete()
                messages.success(request, 'Critério de avaliação deletado com sucesso!')
                return redirect('rh:criterios')
            except Exception as e:
                messages.error(request, f'Erro ao deletar critério: {str(e)}')
        
        context = {'criterio': criterio}
        return render(request, 'rh/avaliacoes/criterios/delete.html', context)
        
    except CriterioAvaliacao.DoesNotExist:
        messages.error(request, 'Critério de avaliação não encontrado.')
        return redirect('rh:criterios')

@login_required
def rh_relatorios(request):
    """Página de relatórios do RH"""
    context = {
        'total_funcionarios': Funcionario.objects.count(),
        'total_departamentos': Departamento.objects.count(),
        'total_cargos': Cargo.objects.count(),
        'presencas_hoje': Presenca.objects.filter(data=date.today()).count(),
    }
    
    return render(request, 'rh/relatorios/main.html', context)

@login_required
def relatorio_funcionarios_documento(request):
    """Relatório de Funcionários - Documento Completo"""
    from django.db.models import Count, Q
    from django.utils import timezone
    
    # Filtros opcionais
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_admissao_inicio = request.GET.get('data_admissao_inicio')
    data_admissao_fim = request.GET.get('data_admissao_fim')
    
    # Query base
    funcionarios_query = Funcionario.objects.select_related('cargo', 'departamento', 'sucursal').order_by('nome_completo')
    
    # Aplicar filtros
    if departamento_id:
        funcionarios_query = funcionarios_query.filter(departamento_id=departamento_id)
    
    if status_filter:
        funcionarios_query = funcionarios_query.filter(status=status_filter)
    
    if data_admissao_inicio:
        try:
            from datetime import datetime
            data_inicio = datetime.strptime(data_admissao_inicio, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__gte=data_inicio)
        except ValueError:
            pass
    
    if data_admissao_fim:
        try:
            from datetime import datetime
            data_fim = datetime.strptime(data_admissao_fim, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    funcionarios = funcionarios_query
    total_funcionarios = funcionarios.count()
    funcionarios_ativos = funcionarios.filter(status='AT').count()
    funcionarios_inativos = funcionarios.filter(status='IN').count()
    
    # Estatísticas por departamento (corrigido)
    funcionarios_por_departamento = funcionarios.values(
        'departamento__nome'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Calcular percentuais
    for dept in funcionarios_por_departamento:
        if total_funcionarios > 0:
            dept['percentual'] = (dept['total'] / total_funcionarios) * 100
        else:
            dept['percentual'] = 0
    
    # Estatísticas por cargo
    funcionarios_por_cargo = funcionarios.values(
        'cargo__nome'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por sucursal
    funcionarios_por_sucursal = funcionarios.values(
        'sucursal__nome'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Outras estatísticas
    total_departamentos = Departamento.objects.count()
    total_cargos = Cargo.objects.count()
    total_sucursais = Sucursal.objects.filter(ativa=True).count()
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'funcionarios': funcionarios,
        'total_funcionarios': total_funcionarios,
        'funcionarios_ativos': funcionarios_ativos,
        'funcionarios_inativos': funcionarios_inativos,
        'total_departamentos': total_departamentos,
        'total_cargos': total_cargos,
        'total_sucursais': total_sucursais,
        'funcionarios_por_departamento': funcionarios_por_departamento,
        'funcionarios_por_cargo': funcionarios_por_cargo,
        'funcionarios_por_sucursal': funcionarios_por_sucursal,
        'departamentos': departamentos,
        'filtros': {
            'departamento': departamento_id,
            'status': status_filter,
            'data_admissao_inicio': data_admissao_inicio,
            'data_admissao_fim': data_admissao_fim,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/funcionarios_documento.html', context)

@login_required
def relatorio_presencas_documento(request):
    """Relatório de Presenças - Documento Completo"""
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Período padrão: últimos 30 dias
    data_fim = timezone.now().date()
    data_inicio = data_fim - timedelta(days=30)
    
    # Filtros opcionais
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    
    # Permitir filtros via GET
    if request.GET.get('data_inicio'):
        try:
            data_inicio = datetime.strptime(request.GET.get('data_inicio'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if request.GET.get('data_fim'):
        try:
            data_fim = datetime.strptime(request.GET.get('data_fim'), '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Query base
    presencas_query = Presenca.objects.filter(
        data__range=[data_inicio, data_fim]
    ).select_related('funcionario', 'tipo_presenca', 'funcionario__cargo', 'funcionario__departamento')
    
    # Aplicar filtros
    if funcionario_id:
        presencas_query = presencas_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        presencas_query = presencas_query.filter(funcionario__departamento_id=departamento_id)
    
    # Dados básicos
    presencas = presencas_query
    total_presencas = presencas.count()
    
    # Obter tipos de presença existentes
    tipos_presenca = TipoPresenca.objects.all()
    
    # Estatísticas por tipo (corrigido)
    presencas_por_tipo = []
    for tipo in tipos_presenca:
        count = presencas.filter(tipo_presenca=tipo).count()
        if count > 0:
            presencas_por_tipo.append({
                'tipo_presenca__nome': tipo.nome,
                'total': count,
                'percentual': (count / total_presencas) * 100 if total_presencas > 0 else 0
            })
    
    # Contar presentes e ausentes (usando nomes em vez de códigos)
    presencas_presente = presencas.filter(tipo_presenca__nome__icontains='presente').count()
    presencas_ausente = presencas.filter(tipo_presenca__nome__icontains='ausente').count()
    
    # Calcular taxa de presença
    if total_presencas > 0:
        percentual_presenca = (presencas_presente / total_presencas) * 100
    else:
        percentual_presenca = 0
    
    # Presenças por funcionário (corrigido)
    presencas_por_funcionario = presencas.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        presentes=Count('id', filter=Q(tipo_presenca__nome__icontains='presente')),
        ausentes=Count('id', filter=Q(tipo_presenca__nome__icontains='ausente')),
        total=Count('id')
    ).order_by('-presentes')
    
    # Calcular taxa de presença por funcionário
    for func in presencas_por_funcionario:
        if func['total'] > 0:
            func['taxa_presenca'] = (func['presentes'] / func['total']) * 100
        else:
            func['taxa_presenca'] = 0
    
    # Presenças por departamento
    presencas_por_departamento = presencas.values(
        'funcionario__departamento__nome'
    ).annotate(
        total=Count('id'),
        presentes=Count('id', filter=Q(tipo_presenca__nome__icontains='presente')),
        ausentes=Count('id', filter=Q(tipo_presenca__nome__icontains='ausente'))
    ).order_by('-total')
    
    # Calcular taxa por departamento
    for dept in presencas_por_departamento:
        if dept['total'] > 0:
            dept['taxa_presenca'] = (dept['presentes'] / dept['total']) * 100
        else:
            dept['taxa_presenca'] = 0
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'presencas': presencas,
        'total_presencas': total_presencas,
        'presencas_presente': presencas_presente,
        'presencas_ausente': presencas_ausente,
        'percentual_presenca': percentual_presenca,
        'presencas_por_tipo': presencas_por_tipo,
        'presencas_por_funcionario': presencas_por_funcionario,
        'presencas_por_departamento': presencas_por_departamento,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
        },
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/presencas_documento.html', context)

@login_required
def relatorio_salarios_documento(request):
    """Relatório de Salários - Documento Completo"""
    from django.db.models import Count, Q, Sum, Avg
    from django.utils import timezone
    
    # Filtros opcionais
    departamento_id = request.GET.get('departamento')
    mes_referencia = request.GET.get('mes_referencia')
    
    # Query base - usar FolhaSalarial em vez de Salario
    folhas_query = FolhaSalarial.objects.all().order_by('-mes_referencia')
    
    # Aplicar filtros
    if mes_referencia:
        try:
            from datetime import datetime
            mes_ref = datetime.strptime(mes_referencia, '%Y-%m').date()
            folhas_query = folhas_query.filter(mes_referencia=mes_ref)
        except ValueError:
            pass
    
    # Dados básicos
    folhas = folhas_query
    total_folhas = folhas.count()
    folhas_calculadas = folhas.filter(status='CALCULADA').count()
    folhas_fechadas = folhas.filter(status='FECHADA').count()
    
    # Estatísticas gerais
    valor_total_bruto = folhas.aggregate(total=Sum('total_bruto'))['total'] or 0
    valor_total_liquido = folhas.aggregate(total=Sum('total_liquido'))['total'] or 0
    valor_total_descontos = folhas.aggregate(total=Sum('total_descontos'))['total'] or 0
    
    # Estatísticas por departamento (usando FuncionarioFolha)
    funcionarios_folha = FuncionarioFolha.objects.select_related(
        'funcionario', 'funcionario__departamento', 'folha'
    )
    
    if departamento_id:
        funcionarios_folha = funcionarios_folha.filter(funcionario__departamento_id=departamento_id)
    
    salarios_por_departamento = funcionarios_folha.values(
        'funcionario__departamento__nome'
    ).annotate(
        total_funcionarios=Count('id'),
        salario_total=Sum('salario_liquido'),
        salario_medio=Avg('salario_liquido')
    ).order_by('-salario_total')
    
    # Calcular percentuais
    for dept in salarios_por_departamento:
        if valor_total_liquido > 0:
            dept['percentual'] = ((dept['salario_total'] or 0) / valor_total_liquido) * 100
        else:
            dept['percentual'] = 0
    
    # Estatísticas por cargo
    salarios_por_cargo = funcionarios_folha.values(
        'funcionario__cargo__nome'
    ).annotate(
        total_funcionarios=Count('id'),
        salario_total=Sum('salario_liquido'),
        salario_medio=Avg('salario_liquido')
    ).order_by('-salario_total')
    
    # Funcionários com maiores salários
    funcionarios_maiores_salarios = funcionarios_folha.order_by('-salario_liquido')[:10]
    
    # Funcionários com menores salários
    funcionarios_menores_salarios = funcionarios_folha.order_by('salario_liquido')[:10]
    
    # Estatísticas de benefícios e descontos
    total_beneficios = funcionarios_folha.aggregate(total=Sum('total_beneficios'))['total'] or 0
    total_descontos = funcionarios_folha.aggregate(total=Sum('total_descontos'))['total'] or 0
    
    # Outras estatísticas
    total_departamentos = Departamento.objects.count()
    total_cargos = Cargo.objects.count()
    total_funcionarios_folha = funcionarios_folha.count()
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'folhas': folhas,
        'total_folhas': total_folhas,
        'folhas_calculadas': folhas_calculadas,
        'folhas_fechadas': folhas_fechadas,
        'total_departamentos': total_departamentos,
        'total_cargos': total_cargos,
        'total_funcionarios_folha': total_funcionarios_folha,
        'salarios_por_departamento': salarios_por_departamento,
        'salarios_por_cargo': salarios_por_cargo,
        'funcionarios_maiores_salarios': funcionarios_maiores_salarios,
        'funcionarios_menores_salarios': funcionarios_menores_salarios,
        'valor_total_bruto': valor_total_bruto,
        'valor_total_liquido': valor_total_liquido,
        'valor_total_descontos': valor_total_descontos,
        'total_beneficios': total_beneficios,
        'total_descontos': total_descontos,
        'departamentos': departamentos,
        'filtros': {
            'departamento': departamento_id,
            'mes_referencia': mes_referencia,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/salarios_documento.html', context)

@login_required
def relatorio_treinamentos_documento(request):
    """Relatório de Treinamentos - Documento Completo"""
    from django.db.models import Count, Q, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Filtros opcionais
    tipo_filter = request.GET.get('tipo')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    treinamentos_query = Treinamento.objects.all().order_by('-data_inicio')
    
    # Aplicar filtros
    # Nota: Treinamento não tem campo departamento, removendo filtro
    
    if tipo_filter:
        treinamentos_query = treinamentos_query.filter(tipo=tipo_filter)
    
    if status_filter:
        treinamentos_query = treinamentos_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    treinamentos = treinamentos_query
    total_treinamentos = treinamentos.count()
    treinamentos_ativos = treinamentos.filter(status='EM_ANDAMENTO').count()
    treinamentos_concluidos = treinamentos.filter(status='CONCLUIDO').count()
    treinamentos_cancelados = treinamentos.filter(status='CANCELADO').count()
    
    # Estatísticas por tipo (em vez de departamento)
    treinamentos_por_tipo = treinamentos.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Calcular percentuais
    for tipo in treinamentos_por_tipo:
        if total_treinamentos > 0:
            tipo['percentual'] = (tipo['total'] / total_treinamentos) * 100
        else:
            tipo['percentual'] = 0
    
    # Inscrições por treinamento
    inscricoes_por_treinamento = treinamentos.annotate(
        total_inscricoes=Count('inscricoes'),
        inscricoes_concluidas=Count('inscricoes', filter=Q(inscricoes__status='CONCLUIDO')),
        inscricoes_ativas=Count('inscricoes', filter=Q(inscricoes__status='ATIVO'))
    ).order_by('-total_inscricoes')
    
    # Calcular taxa de conclusão por treinamento
    for treinamento in inscricoes_por_treinamento:
        if treinamento.total_inscricoes > 0:
            treinamento.taxa_conclusao = (treinamento.inscricoes_concluidas / treinamento.total_inscricoes) * 100
        else:
            treinamento.taxa_conclusao = 0
    
    # Funcionários mais treinados
    funcionarios_mais_treinados = InscricaoTreinamento.objects.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_treinamentos=Count('id'),
        treinamentos_concluidos=Count('id', filter=Q(status='CONCLUIDO'))
    ).order_by('-total_treinamentos')[:10]
    
    # Calcular taxa de conclusão por funcionário
    for func in funcionarios_mais_treinados:
        if func['total_treinamentos'] > 0:
            func['taxa_conclusao'] = (func['treinamentos_concluidos'] / func['total_treinamentos']) * 100
        else:
            func['taxa_conclusao'] = 0
    
    # Estatísticas gerais
    total_inscricoes = InscricaoTreinamento.objects.count()
    inscricoes_concluidas = InscricaoTreinamento.objects.filter(status='CONCLUIDO').count()
    inscricoes_ativas = InscricaoTreinamento.objects.filter(status='ATIVO').count()
    
    # Calcular taxa geral de conclusão
    if total_inscricoes > 0:
        taxa_conclusao_geral = (inscricoes_concluidas / total_inscricoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'treinamentos': treinamentos,
        'total_treinamentos': total_treinamentos,
        'treinamentos_ativos': treinamentos_ativos,
        'treinamentos_concluidos': treinamentos_concluidos,
        'treinamentos_cancelados': treinamentos_cancelados,
        'treinamentos_por_tipo': treinamentos_por_tipo,
        'inscricoes_por_treinamento': inscricoes_por_treinamento,
        'funcionarios_mais_treinados': funcionarios_mais_treinados,
        'total_inscricoes': total_inscricoes,
        'inscricoes_concluidas': inscricoes_concluidas,
        'inscricoes_ativas': inscricoes_ativas,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'filtros': {
            'tipo': tipo_filter,
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/treinamentos_documento.html', context)

@login_required
def relatorio_avaliacoes_documento(request):
    """Relatório de Avaliações de Desempenho - Documento Completo"""
    from django.db.models import Count, Q, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Filtros opcionais
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    avaliacoes_query = AvaliacaoDesempenho.objects.select_related('funcionario', 'funcionario__departamento').order_by('-data_inicio')
    
    # Aplicar filtros
    if departamento_id:
        avaliacoes_query = avaliacoes_query.filter(funcionario__departamento_id=departamento_id)
    
    if status_filter:
        avaliacoes_query = avaliacoes_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    avaliacoes = avaliacoes_query
    total_avaliacoes = avaliacoes.count()
    avaliacoes_pendentes = avaliacoes.filter(status='PENDENTE').count()
    avaliacoes_concluidas = avaliacoes.filter(status='CONCLUIDO').count()
    avaliacoes_canceladas = avaliacoes.filter(status='CANCELADO').count()
    
    # Estatísticas por departamento
    avaliacoes_por_departamento = avaliacoes.values(
        'funcionario__departamento__nome'
    ).annotate(
        total=Count('id'),
        concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        pendentes=Count('id', filter=Q(status='PENDENTE'))
    ).order_by('-total')
    
    # Calcular percentuais e notas médias
    for dept in avaliacoes_por_departamento:
        if dept['total'] > 0:
            dept['percentual'] = (dept['total'] / total_avaliacoes) * 100
            dept['taxa_conclusao'] = (dept['concluidas'] / dept['total']) * 100
        else:
            dept['percentual'] = 0
            dept['taxa_conclusao'] = 0
    
    # Avaliações por funcionário
    avaliacoes_por_funcionario = avaliacoes.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_avaliacoes=Count('id'),
        avaliacoes_concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        nota_media=Avg('nota_geral')
    ).order_by('-nota_media')
    
    # Calcular taxa de conclusão por funcionário
    for func in avaliacoes_por_funcionario:
        if func['total_avaliacoes'] > 0:
            func['taxa_conclusao'] = (func['avaliacoes_concluidas'] / func['total_avaliacoes']) * 100
        else:
            func['taxa_conclusao'] = 0
    
    # Funcionários com melhores notas
    melhores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral')[:10]
    
    # Funcionários com piores notas
    piores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral')[:10]
    
    # Estatísticas de critérios
    criterios_stats = CriterioAvaliado.objects.values(
        'criterio__nome'
    ).annotate(
        total_avaliacoes=Count('id'),
        nota_media=Avg('nota')
    ).order_by('-nota_media')
    
    # Estatísticas gerais
    nota_media_geral = avaliacoes.filter(status='CONCLUIDO').aggregate(media=Avg('nota_geral'))['media'] or 0
    nota_maior = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral').first()
    nota_menor = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral').first()
    
    # Calcular taxa geral de conclusão
    if total_avaliacoes > 0:
        taxa_conclusao_geral = (avaliacoes_concluidas / total_avaliacoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'avaliacoes': avaliacoes,
        'total_avaliacoes': total_avaliacoes,
        'avaliacoes_pendentes': avaliacoes_pendentes,
        'avaliacoes_concluidas': avaliacoes_concluidas,
        'avaliacoes_canceladas': avaliacoes_canceladas,
        'avaliacoes_por_departamento': avaliacoes_por_departamento,
        'avaliacoes_por_funcionario': avaliacoes_por_funcionario,
        'melhores_funcionarios': melhores_funcionarios,
        'piores_funcionarios': piores_funcionarios,
        'criterios_stats': criterios_stats,
        'nota_media_geral': nota_media_geral,
        'nota_maior': nota_maior,
        'nota_menor': nota_menor,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'filtros': {
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/avaliacoes_documento.html', context)

@login_required
def relatorio_feriados_documento(request):
    """Gera relatório completo de feriados"""
    # Filtros
    ano = request.GET.get('ano')
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')
    
    # Query base
    feriados = Feriado.objects.all().order_by('data')
    
    # Aplicar filtros
    if ano:
        feriados = feriados.filter(data__year=ano)
    if tipo:
        feriados = feriados.filter(tipo=tipo)
    if status:
        feriados = feriados.filter(ativo=status == 'ativo')
    
    # Estatísticas gerais
    total_feriados = feriados.count()
    feriados_ativos = feriados.filter(ativo=True).count()
    feriados_inativos = feriados.filter(ativo=False).count()
    
    # Estatísticas por tipo
    feriados_por_tipo = feriados.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por ano
    feriados_por_ano = feriados.values('data__year').annotate(
        total=Count('id')
    ).order_by('data__year')
    
    # Feriados próximos (próximos 30 dias)
    from datetime import date, timedelta
    hoje = date.today()
    proximos_30_dias = hoje + timedelta(days=30)
    feriados_proximos = feriados.filter(
        data__gte=hoje,
        data__lte=proximos_30_dias,
        ativo=True
    ).order_by('data')
    
    # Feriados por mês (ano atual)
    ano_atual = date.today().year
    feriados_por_mes = feriados.filter(
        data__year=ano_atual,
        ativo=True
    ).extra(
        select={'mes': 'EXTRACT(month FROM data)'}
    ).values('mes').annotate(
        total=Count('id')
    ).order_by('mes')
    
    # Contexto
    context = {
        'feriados': feriados,
        'total_feriados': total_feriados,
        'feriados_ativos': feriados_ativos,
        'feriados_inativos': feriados_inativos,
        'feriados_por_tipo': feriados_por_tipo,
        'feriados_por_ano': feriados_por_ano,
        'feriados_proximos': feriados_proximos,
        'feriados_por_mes': feriados_por_mes,
        'filtros': {
            'ano': ano,
            'tipo': tipo,
            'status': status,
        },
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/feriados_documento.html', context)

@login_required
def relatorio_feriados_pdf(request):
    """Gera PDF do relatório de feriados"""
    from django.template.loader import render_to_string
    
    # Reutilizar a mesma lógica do documento
    from django.template.response import TemplateResponse
    
    # Criar uma resposta temporária para obter o contexto
    temp_response = relatorio_feriados_documento(request)
    if hasattr(temp_response, 'context_data'):
        context = temp_response.context_data
    else:
        # Se não tem context_data, criar o contexto manualmente
        ano = request.GET.get('ano')
        tipo = request.GET.get('tipo')
        status = request.GET.get('status')
        
        # Query base
        feriados = Feriado.objects.all().order_by('data')
        
        # Aplicar filtros
        if ano:
            feriados = feriados.filter(data__year=ano)
        if tipo:
            feriados = feriados.filter(tipo=tipo)
        if status:
            feriados = feriados.filter(ativo=status == 'ativo')
        
        # Estatísticas gerais
        total_feriados = feriados.count()
        feriados_ativos = feriados.filter(ativo=True).count()
        feriados_inativos = feriados.filter(ativo=False).count()
        
        # Estatísticas por tipo
        feriados_por_tipo = feriados.values('tipo').annotate(
            total=Count('id')
        ).order_by('-total')
        
        # Estatísticas por ano
        feriados_por_ano = feriados.values('data__year').annotate(
            total=Count('id')
        ).order_by('data__year')
        
        # Feriados próximos (próximos 30 dias)
        from datetime import date, timedelta
        hoje = date.today()
        proximos_30_dias = hoje + timedelta(days=30)
        feriados_proximos = feriados.filter(
            data__gte=hoje,
            data__lte=proximos_30_dias,
            ativo=True
        ).order_by('data')
        
        # Feriados por mês (ano atual)
        ano_atual = date.today().year
        feriados_por_mes = feriados.filter(
            data__year=ano_atual,
            ativo=True
        ).extra(
            select={'mes': 'EXTRACT(month FROM data)'}
        ).values('mes').annotate(
            total=Count('id')
        ).order_by('mes')
        
        # Contexto
        context = {
            'feriados': feriados,
            'total_feriados': total_feriados,
            'feriados_ativos': feriados_ativos,
            'feriados_inativos': feriados_inativos,
            'feriados_por_tipo': feriados_por_tipo,
            'feriados_por_ano': feriados_por_ano,
            'feriados_proximos': feriados_proximos,
            'feriados_por_mes': feriados_por_mes,
            'filtros': {
                'ano': ano,
                'tipo': tipo,
                'status': status,
            },
            'data_relatorio': timezone.now(),
        }
    
    html_string = render_to_string('rh/relatorios/feriados_documento.html', context, request=request)
    filename = f"relatorio_feriados_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_horas_extras_documento(request):
    """Relatório de Horas Extras - Documento Completo"""
    from django.db.models import Count, Q, Sum, Avg
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    # Filtros opcionais
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    tipo_filter = request.GET.get('tipo')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Período padrão: últimos 30 dias
    data_fim = timezone.now().date()
    data_inicio = data_fim - timedelta(days=30)
    
    # Permitir filtros via GET
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Query base
    horas_extras_query = HorasExtras.objects.filter(
        data__range=[data_inicio, data_fim]
    ).select_related('funcionario', 'funcionario__departamento', 'criado_por')
    
    # Aplicar filtros
    if funcionario_id:
        horas_extras_query = horas_extras_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        horas_extras_query = horas_extras_query.filter(funcionario__departamento_id=departamento_id)
    
    if tipo_filter:
        horas_extras_query = horas_extras_query.filter(tipo=tipo_filter)
    
    # Dados básicos
    horas_extras = horas_extras_query
    total_registros = horas_extras.count()
    
    # Estatísticas por tipo
    horas_por_tipo = horas_extras.values('tipo').annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        valor_total=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Calcular percentuais
    total_horas_geral = sum([item['total_horas'] or 0 for item in horas_por_tipo])
    total_valor_geral = sum([item['valor_total'] or 0 for item in horas_por_tipo])
    
    for tipo in horas_por_tipo:
        if total_horas_geral > 0:
            tipo['percentual_horas'] = ((tipo['total_horas'] or 0) / total_horas_geral) * 100
        else:
            tipo['percentual_horas'] = 0
        
        if total_valor_geral > 0:
            tipo['percentual_valor'] = ((tipo['valor_total'] or 0) / total_valor_geral) * 100
        else:
            tipo['percentual_valor'] = 0
    
    # Estatísticas por funcionário
    horas_por_funcionario = horas_extras.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        valor_total=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Estatísticas por departamento
    horas_por_departamento = horas_extras.values(
        'funcionario__departamento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        valor_total=Sum('valor_total'),
        funcionarios_distintos=Count('funcionario', distinct=True)
    ).order_by('-total_horas')
    
    # Calcular médias por departamento
    for dept in horas_por_departamento:
        if dept['funcionarios_distintos'] > 0:
            dept['media_horas_por_funcionario'] = (dept['total_horas'] or 0) / dept['funcionarios_distintos']
            dept['media_valor_por_funcionario'] = (dept['valor_total'] or 0) / dept['funcionarios_distintos']
        else:
            dept['media_horas_por_funcionario'] = 0
            dept['media_valor_por_funcionario'] = 0
    
    # Funcionários com mais horas extras
    funcionarios_mais_horas = horas_por_funcionario[:10]
    
    # Estatísticas gerais
    total_horas_extras = horas_extras.aggregate(total=Sum('quantidade_horas'))['total'] or 0
    total_valor_horas_extras = horas_extras.aggregate(total=Sum('valor_total'))['total'] or 0
    media_horas_por_registro = horas_extras.aggregate(media=Avg('quantidade_horas'))['media'] or 0
    media_valor_por_registro = horas_extras.aggregate(media=Avg('valor_total'))['media'] or 0
    
    # Funcionários únicos que fizeram horas extras
    funcionarios_unicos = horas_extras.values('funcionario').distinct().count()
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'horas_extras': horas_extras,
        'total_registros': total_registros,
        'horas_por_tipo': horas_por_tipo,
        'horas_por_funcionario': horas_por_funcionario,
        'horas_por_departamento': horas_por_departamento,
        'funcionarios_mais_horas': funcionarios_mais_horas,
        'total_horas_extras': total_horas_extras,
        'total_valor_horas_extras': total_valor_horas_extras,
        'media_horas_por_registro': media_horas_por_registro,
        'media_valor_por_registro': media_valor_por_registro,
        'funcionarios_unicos': funcionarios_unicos,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
            'tipo': tipo_filter,
        },
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'data_relatorio': timezone.now(),
    }
    
    return render(request, 'rh/relatorios/horas_extras_documento.html', context)

# =============================================================================
# VIEWS DE EXPORTAÇÃO PDF
# =============================================================================

@login_required
def relatorio_funcionarios_pdf(request):
    """Exportar Relatório de Funcionários para PDF"""
    
    # Reutilizar a lógica da view de documento
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_admissao_inicio = request.GET.get('data_admissao_inicio')
    data_admissao_fim = request.GET.get('data_admissao_fim')
    
    # Query base
    funcionarios_query = Funcionario.objects.select_related('departamento', 'sucursal', 'cargo').order_by('nome_completo')
    
    # Aplicar filtros
    if departamento_id:
        funcionarios_query = funcionarios_query.filter(departamento_id=departamento_id)
    
    if status_filter:
        funcionarios_query = funcionarios_query.filter(status=status_filter)
    
    if data_admissao_inicio:
        try:
            data_inicio = datetime.strptime(data_admissao_inicio, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__gte=data_inicio)
        except ValueError:
            pass
    
    if data_admissao_fim:
        try:
            data_fim = datetime.strptime(data_admissao_fim, '%Y-%m-%d').date()
            funcionarios_query = funcionarios_query.filter(data_admissao__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    funcionarios = funcionarios_query
    total_funcionarios = funcionarios.count()
    funcionarios_ativos = funcionarios.filter(status='AT').count()
    funcionarios_inativos = funcionarios.filter(status='IN').count()
    
    # Estatísticas por departamento
    funcionarios_por_departamento = funcionarios.values('departamento__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por cargo
    funcionarios_por_cargo = funcionarios.values('cargo__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Estatísticas por sucursal
    funcionarios_por_sucursal = funcionarios.values('sucursal__nome').annotate(
        total=Count('id')
    ).order_by('-total')
    
    total_sucursais = funcionarios.values('sucursal').distinct().count()
    
    # Renderizar HTML original com os filtros para PDF idêntico
    # Renderizar o mesmo template que a página de documento
    context = {
        'funcionarios': funcionarios,
        'total_funcionarios': total_funcionarios,
        'funcionarios_ativos': funcionarios_ativos,
        'funcionarios_inativos': funcionarios_inativos,
        'funcionarios_por_departamento': funcionarios_por_departamento,
        'funcionarios_por_cargo': funcionarios_por_cargo,
        'funcionarios_por_sucursal': funcionarios_por_sucursal,
        'total_sucursais': total_sucursais,
        'departamentos': Departamento.objects.all().order_by('nome'),
        'filtros': {
            'departamento': departamento_id,
            'status': status_filter,
            'data_admissao_inicio': data_admissao_inicio,
            'data_admissao_fim': data_admissao_fim,
        },
        'data_relatorio': timezone.now(),
    }
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/funcionarios_documento.html', context, request=request)
    filename = f'relatorio_funcionarios_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_presencas_pdf(request):
    """Exportar Relatório de Presenças para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    presencas_query = Presenca.objects.select_related('funcionario', 'funcionario__departamento', 'tipo_presenca').order_by('-data')
    
    # Aplicar filtros
    if funcionario_id:
        presencas_query = presencas_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        presencas_query = presencas_query.filter(funcionario__departamento_id=departamento_id)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            presencas_query = presencas_query.filter(data__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            presencas_query = presencas_query.filter(data__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    presencas = presencas_query
    total_presencas = presencas.count()
    presencas_presentes = presencas.filter(tipo_presenca__nome__icontains='presente').count()
    presencas_ausentes = presencas.filter(tipo_presenca__nome__icontains='ausente').count()
    
    # Estatísticas por departamento
    presencas_por_departamento = presencas.values('funcionario__departamento__nome').annotate(
        total=Count('id'),
        presentes=Count('id', filter=Q(tipo_presenca__nome__icontains='presente')),
        ausentes=Count('id', filter=Q(tipo_presenca__nome__icontains='ausente'))
    ).order_by('-total')
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'presencas': presencas,
        'total_presencas': total_presencas,
        'presencas_presentes': presencas_presentes,
        'presencas_ausentes': presencas_ausentes,
        'presencas_por_departamento': presencas_por_departamento,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    # Renderização HTML idêntica
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/presencas_documento.html', context, request=request)
    filename = f'relatorio_presencas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_salarios_pdf(request):
    """Exportar Relatório de Salários para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    departamento_id = request.GET.get('departamento')
    mes_referencia_filter = request.GET.get('mes_referencia')
    
    # Query base
    folhas_query = FolhaSalarial.objects.select_related().order_by('-mes_referencia')
    
    # Aplicar filtros
    if departamento_id:
        folhas_query = folhas_query.filter(funcionarios__funcionario__departamento_id=departamento_id).distinct()
    
    if mes_referencia_filter:
        try:
            mes_referencia = datetime.strptime(mes_referencia_filter, '%Y-%m').date()
            folhas_query = folhas_query.filter(mes_referencia=mes_referencia)
        except ValueError:
            pass
    
    # Dados básicos
    folhas = folhas_query
    total_folhas = folhas.count()
    folhas_calculadas = folhas.filter(status='CALCULADA').count()
    folhas_fechadas = folhas.filter(status='FECHADA').count()
    
    # Estatísticas gerais
    from meuprojeto.empresa.models_rh import BeneficioFolha
    total_funcionarios_folha = FuncionarioFolha.objects.count()
    valor_total_bruto = folhas.aggregate(total=Sum('total_bruto'))['total'] or 0
    valor_total_liquido = folhas.aggregate(total=Sum('total_liquido'))['total'] or 0
    valor_total_descontos = folhas.aggregate(total=Sum('total_descontos'))['total'] or 0
    total_beneficios = BeneficioFolha.objects.aggregate(total=Sum('valor'))['total'] or 0
    
    # Salários por departamento
    salarios_por_departamento = FuncionarioFolha.objects.values(
        'funcionario__departamento__nome'
    ).annotate(
        total_funcionarios=Count('id'),
        salario_total=Sum('salario_liquido'),
        salario_medio=Sum('salario_liquido') / Count('id')
    ).order_by('-salario_total')
    
    # Funcionários com maiores e menores salários
    funcionarios_maiores_salarios = FuncionarioFolha.objects.select_related('funcionario').order_by('-salario_liquido')[:5]
    funcionarios_menores_salarios = FuncionarioFolha.objects.select_related('funcionario').order_by('salario_liquido')[:5]
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'folhas': folhas,
        'total_folhas': total_folhas,
        'folhas_calculadas': folhas_calculadas,
        'folhas_fechadas': folhas_fechadas,
        'total_funcionarios_folha': total_funcionarios_folha,
        'valor_total_bruto': valor_total_bruto,
        'valor_total_liquido': valor_total_liquido,
        'valor_total_descontos': valor_total_descontos,
        'total_beneficios': total_beneficios,
        'salarios_por_departamento': salarios_por_departamento,
        'funcionarios_maiores_salarios': funcionarios_maiores_salarios,
        'funcionarios_menores_salarios': funcionarios_menores_salarios,
        'departamentos': departamentos,
        'filtros': {
            'departamento': departamento_id,
            'mes_referencia': mes_referencia_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    # Preparar dados e gerar PDF
    pdf_data = {
        'Estatísticas Gerais': [
            f'Total Folhas: {total_folhas}',
            f'Calculadas: {folhas_calculadas}',
            f'Fechadas: {folhas_fechadas}',
            f'Funcionários em Folhas: {total_funcionarios_folha}',
            f'Total Bruto: {valor_total_bruto}',
            f'Total Líquido: {valor_total_liquido}',
            f'Total Descontos: {valor_total_descontos}',
            f'Total Benefícios: {total_beneficios}',
        ],
        'Salários por Departamento': [
            {
                'Departamento': d['funcionario__departamento__nome'] or '-',
                'Funcionários': d['total_funcionarios'],
                'Total': d['salario_total'],
            } for d in salarios_por_departamento
        ],
    }
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/salarios_documento.html', context, request=request)
    filename = f'relatorio_salarios_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_treinamentos_pdf(request):
    """Exportar Relatório de Treinamentos para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    tipo_filter = request.GET.get('tipo')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    treinamentos_query = Treinamento.objects.select_related().order_by('-data_inicio')
    
    # Aplicar filtros
    if tipo_filter:
        treinamentos_query = treinamentos_query.filter(tipo=tipo_filter)
    
    if status_filter:
        treinamentos_query = treinamentos_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            treinamentos_query = treinamentos_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    treinamentos = treinamentos_query
    total_treinamentos = treinamentos.count()
    treinamentos_ativos = treinamentos.filter(status='EM_ANDAMENTO').count()
    treinamentos_concluidos = treinamentos.filter(status='CONCLUIDO').count()
    treinamentos_cancelados = treinamentos.filter(status='CANCELADO').count()
    
    # Estatísticas por tipo
    treinamentos_por_tipo = treinamentos.values('tipo').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Inscrições por treinamento
    inscricoes_por_treinamento = treinamentos.annotate(
        total_inscricoes=Count('inscricoes'),
        inscricoes_concluidas=Count('inscricoes', filter=Q(inscricoes__status='CONCLUIDO'))
    ).order_by('-total_inscricoes')[:10]
    
    # Funcionários mais treinados
    funcionarios_mais_treinados = InscricaoTreinamento.objects.values(
        'funcionario__nome_completo'
    ).annotate(
        total_inscricoes=Count('id'),
        treinamentos_concluidos=Count('id', filter=Q(status='CONCLUIDO'))
    ).order_by('-total_inscricoes')[:10]
    
    # Estatísticas de inscrições
    total_inscricoes = InscricaoTreinamento.objects.count()
    inscricoes_concluidas = InscricaoTreinamento.objects.filter(status='CONCLUIDO').count()
    inscricoes_ativas = InscricaoTreinamento.objects.filter(status='ATIVO').count()
    
    # Calcular taxa de conclusão geral
    if total_inscricoes > 0:
        taxa_conclusao_geral = (inscricoes_concluidas / total_inscricoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    context = {
        'treinamentos': treinamentos,
        'total_treinamentos': total_treinamentos,
        'treinamentos_ativos': treinamentos_ativos,
        'treinamentos_concluidos': treinamentos_concluidos,
        'treinamentos_cancelados': treinamentos_cancelados,
        'treinamentos_por_tipo': treinamentos_por_tipo,
        'inscricoes_por_treinamento': inscricoes_por_treinamento,
        'funcionarios_mais_treinados': funcionarios_mais_treinados,
        'total_inscricoes': total_inscricoes,
        'inscricoes_concluidas': inscricoes_concluidas,
        'inscricoes_ativas': inscricoes_ativas,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'filtros': {
            'tipo': tipo_filter,
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/treinamentos_documento.html', context, request=request)
    filename = f'relatorio_treinamentos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_avaliacoes_pdf(request):
    """Exportar Relatório de Avaliações para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    departamento_id = request.GET.get('departamento')
    status_filter = request.GET.get('status')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    avaliacoes_query = AvaliacaoDesempenho.objects.select_related('funcionario', 'funcionario__departamento').order_by('-data_inicio')
    
    # Aplicar filtros
    if departamento_id:
        avaliacoes_query = avaliacoes_query.filter(funcionario__departamento_id=departamento_id)
    
    if status_filter:
        avaliacoes_query = avaliacoes_query.filter(status=status_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_inicio__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            avaliacoes_query = avaliacoes_query.filter(data_fim__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    avaliacoes = avaliacoes_query
    total_avaliacoes = avaliacoes.count()
    avaliacoes_pendentes = avaliacoes.filter(status='PENDENTE').count()
    avaliacoes_concluidas = avaliacoes.filter(status='CONCLUIDO').count()
    avaliacoes_canceladas = avaliacoes.filter(status='CANCELADO').count()
    
    # Estatísticas por departamento
    avaliacoes_por_departamento = avaliacoes.values('funcionario__departamento__nome').annotate(
        total=Count('id'),
        concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        pendentes=Count('id', filter=Q(status='PENDENTE'))
    ).order_by('-total')
    
    # Avaliações por funcionário
    avaliacoes_por_funcionario = avaliacoes.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_avaliacoes=Count('id'),
        avaliacoes_concluidas=Count('id', filter=Q(status='CONCLUIDO')),
        nota_media=Avg('nota_geral')
    ).order_by('-nota_media')
    
    # Calcular taxa de conclusão por funcionário
    for func in avaliacoes_por_funcionario:
        if func['total_avaliacoes'] > 0:
            func['taxa_conclusao'] = (func['avaliacoes_concluidas'] / func['total_avaliacoes']) * 100
        else:
            func['taxa_conclusao'] = 0
    
    # Funcionários com melhores notas
    melhores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral')[:10]
    
    # Funcionários com piores notas
    piores_funcionarios = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral')[:10]
    
    # Estatísticas de critérios
    criterios_stats = CriterioAvaliado.objects.values('criterio__nome').annotate(
        total_avaliacoes=Count('id'),
        nota_media=Avg('nota')
    ).order_by('-nota_media')
    
    # Estatísticas gerais
    nota_media_geral = avaliacoes.filter(status='CONCLUIDO').aggregate(media=Avg('nota_geral'))['media'] or 0
    nota_maior = avaliacoes.filter(status='CONCLUIDO').order_by('-nota_geral').first()
    nota_menor = avaliacoes.filter(status='CONCLUIDO').order_by('nota_geral').first()
    
    # Calcular taxa geral de conclusão
    if total_avaliacoes > 0:
        taxa_conclusao_geral = (avaliacoes_concluidas / total_avaliacoes) * 100
    else:
        taxa_conclusao_geral = 0
    
    # Dados para filtros
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'avaliacoes': avaliacoes,
        'total_avaliacoes': total_avaliacoes,
        'avaliacoes_pendentes': avaliacoes_pendentes,
        'avaliacoes_concluidas': avaliacoes_concluidas,
        'avaliacoes_canceladas': avaliacoes_canceladas,
        'avaliacoes_por_departamento': avaliacoes_por_departamento,
        'avaliacoes_por_funcionario': avaliacoes_por_funcionario,
        'melhores_funcionarios': melhores_funcionarios,
        'piores_funcionarios': piores_funcionarios,
        'criterios_stats': criterios_stats,
        'nota_media_geral': nota_media_geral,
        'nota_maior': nota_maior,
        'nota_menor': nota_menor,
        'taxa_conclusao_geral': taxa_conclusao_geral,
        'departamentos': departamentos,
        'filtros': {
            'status': status_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_relatorio': timezone.now(),
    }
    
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/avaliacoes_documento.html', context, request=request)
    filename = f'relatorio_avaliacoes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_horas_extras_pdf(request):
    """Exportar Relatório de Horas Extras para PDF"""
    from django.template.loader import render_to_string
    
    # Reutilizar a lógica da view de documento
    funcionario_id = request.GET.get('funcionario')
    departamento_id = request.GET.get('departamento')
    tipo_filter = request.GET.get('tipo')
    data_inicio_filter = request.GET.get('data_inicio')
    data_fim_filter = request.GET.get('data_fim')
    
    # Query base
    horas_extras_query = HorasExtras.objects.select_related('funcionario', 'funcionario__departamento').order_by('-data')
    
    # Aplicar filtros
    if funcionario_id:
        horas_extras_query = horas_extras_query.filter(funcionario_id=funcionario_id)
    
    if departamento_id:
        horas_extras_query = horas_extras_query.filter(funcionario__departamento_id=departamento_id)
    
    if tipo_filter:
        horas_extras_query = horas_extras_query.filter(tipo=tipo_filter)
    
    if data_inicio_filter:
        try:
            data_inicio = datetime.strptime(data_inicio_filter, '%Y-%m-%d').date()
            horas_extras_query = horas_extras_query.filter(data__gte=data_inicio)
        except ValueError:
            pass
    
    if data_fim_filter:
        try:
            data_fim = datetime.strptime(data_fim_filter, '%Y-%m-%d').date()
            horas_extras_query = horas_extras_query.filter(data__lte=data_fim)
        except ValueError:
            pass
    
    # Dados básicos
    horas_extras = horas_extras_query
    total_registros = horas_extras.count()
    total_horas_extras = horas_extras.aggregate(total=Sum('quantidade_horas'))['total'] or 0
    total_valor_horas_extras = horas_extras.aggregate(total=Sum('valor_total'))['total'] or 0
    
    # Estatísticas por tipo
    horas_por_tipo = horas_extras.values('tipo').annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Estatísticas por funcionário
    horas_por_funcionario = horas_extras.values(
        'funcionario__nome_completo',
        'funcionario__departamento__nome'
    ).annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    ).order_by('-total_horas')[:10]
    
    # Estatísticas por departamento
    horas_por_departamento = horas_extras.values('funcionario__departamento__nome').annotate(
        total_registros=Count('id'),
        total_horas=Sum('quantidade_horas'),
        total_valor=Sum('valor_total')
    ).order_by('-total_horas')
    
    # Funcionários com mais horas extras
    funcionarios_mais_horas = horas_extras.values('funcionario__nome_completo').annotate(
        total_horas=Sum('quantidade_horas')
    ).order_by('-total_horas')[:10]
    
    # Estatísticas gerais
    media_horas_por_registro = total_horas_extras / total_registros if total_registros > 0 else 0
    media_valor_por_registro = total_valor_horas_extras / total_registros if total_registros > 0 else 0
    funcionarios_unicos = horas_extras.values('funcionario').distinct().count()
    
    # Dados para filtros
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    departamentos = Departamento.objects.all().order_by('nome')
    
    context = {
        'horas_extras': horas_extras,
        'total_registros': total_registros,
        'total_horas_extras': total_horas_extras,
        'total_valor_horas_extras': total_valor_horas_extras,
        'horas_por_tipo': horas_por_tipo,
        'horas_por_funcionario': horas_por_funcionario,
        'horas_por_departamento': horas_por_departamento,
        'funcionarios_mais_horas': funcionarios_mais_horas,
        'media_horas_por_registro': media_horas_por_registro,
        'media_valor_por_registro': media_valor_por_registro,
        'funcionarios_unicos': funcionarios_unicos,
        'funcionarios': funcionarios,
        'departamentos': departamentos,
        'filtros': {
            'funcionario': funcionario_id,
            'departamento': departamento_id,
            'tipo': tipo_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
        },
        'data_inicio': data_inicio_filter,
        'data_fim': data_fim_filter,
        'data_relatorio': timezone.now(),
    }
    
    from django.template.loader import render_to_string
    html_string = render_to_string('rh/relatorios/horas_extras_documento.html', context, request=request)
    filename = f'relatorio_horas_extras_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return render_pdf_from_html_string(request, html_string, filename)

@login_required
def relatorio_pdf(request):
    """Gerar relatório PDF"""
    if request.method == 'POST':
        tipo_relatorio = request.POST.get('tipo_relatorio')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        sucursal_id = request.POST.get('sucursal')
        
        if not all([tipo_relatorio, data_inicio, data_fim]):
            messages.error(request, 'Tipo de relatório, data início e data fim são obrigatórios.')
        else:
            try:
                # Por enquanto, redirecionar para página de relatórios
                # Em uma implementação completa, aqui seria gerado o PDF
                messages.success(request, 'Relatório será gerado em breve!')
                return redirect('rh:relatorios')
            except Exception as e:
                messages.error(request, f'Erro ao gerar relatório: {str(e)}')
    
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    context = {
        'sucursais': sucursais,
        'tipos_relatorio': [
            ('funcionarios', 'Relatório de Funcionários'),
            ('presencas', 'Relatório de Presenças'),
            ('salarios', 'Relatório de Salários'),
            ('treinamentos', 'Relatório de Treinamentos'),
            ('avaliacoes', 'Relatório de Avaliações'),
        ]
    }
    return render(request, 'rh/relatorios/gerar.html', context)

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
    
    context = {}
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
            mes = request.POST.get('mes')
            ano = request.POST.get('ano')
            sucursal_id = request.POST.get('sucursal')
            observacoes = request.POST.get('observacoes', '')
            
            if not all([mes, ano, sucursal_id]):
                messages.error(request, 'Mês, ano e sucursal são obrigatórios.')
            else:
                try:
                    folha.mes = int(mes)
                    folha.ano = int(ano)
                    folha.sucursal_id = sucursal_id
                    folha.observacoes = observacoes
                    folha.save()
                    
                    messages.success(request, 'Folha salarial atualizada com sucesso!')
                    return redirect('rh:folha_detail', folha_id=folha.id)
                except ValueError as e:
                    messages.error(request, f'Erro nos dados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
        context = {
            'folha': folha,
            'sucursais': sucursais,
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
            from meuprojeto.empresa.models_rh import FuncionarioFolha
            
            # Adicionar todos os funcionários ativos à folha se ainda não estiverem
            funcionarios_ativos = Funcionario.objects.filter(status='AT')
            funcionarios_adicionados = 0
            
            for funcionario in funcionarios_ativos:
                # Verificar se o funcionário já está na folha
                if not FuncionarioFolha.objects.filter(folha=folha, funcionario=funcionario).exists():
                    # Criar registro do funcionário na folha
                    funcionario_folha = FuncionarioFolha.objects.create(
                        folha=folha,
                        funcionario=funcionario,
                        salario_base=funcionario.get_salario_atual(),
                        dias_trabalhados=22,  # Padrão de 22 dias úteis
                        horas_trabalhadas=176,  # 22 dias * 8 horas
                        observacoes='Adicionado automaticamente no cálculo da folha'
                    )
                    funcionarios_adicionados += 1
            
            # Calcular totais da folha
            folha.calcular_totais()
            
            # Marcar como calculada
            folha.status = 'CALCULADA'
            folha.save()
            
            if funcionarios_adicionados > 0:
                messages.success(request, f'Folha salarial calculada com sucesso! {funcionarios_adicionados} funcionário(s) adicionado(s).')
            else:
                messages.success(request, 'Folha salarial recalculada com sucesso!')
            
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
    """Validar fechamento da folha salarial"""
    try:
        folha = FolhaSalarial.objects.get(id=folha_id)
        
        if request.method == 'POST':
            # Lógica de validação
            folha.status = 'VALIDADA'
            folha.save()
            messages.success(request, 'Folha salarial validada com sucesso!')
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {'folha': folha}
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
            folha.status = 'FECHADA'
            folha.save()
            messages.success(request, 'Folha salarial fechada com sucesso!')
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {'folha': folha}
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
            folha.status = 'ABERTA'
            folha.save()
            messages.success(request, 'Folha salarial reaberta com sucesso!')
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
            folha.status = 'PAGA'
            folha.save()
            messages.success(request, 'Folha salarial marcada como paga!')
            return redirect('rh:folha_detail', folha_id=folha.id)
        
        context = {'folha': folha}
        return render(request, 'rh/folha_salarial/marcar_paga.html', context)
        
    except FolhaSalarial.DoesNotExist:
        messages.error(request, 'Folha salarial não encontrada.')
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

@login_required
def rh_promocoes(request):
    """Lista de promoções"""
    promocoes = Promocao.objects.all().order_by('-data_solicitacao')
    
    # Filtros
    status_filter = request.GET.get('status', '')
    if status_filter:
        promocoes = promocoes.filter(status=status_filter)
    
    tipo_filter = request.GET.get('tipo', '')
    if tipo_filter:
        promocoes = promocoes.filter(tipo=tipo_filter)
    
    funcionario_filter = request.GET.get('funcionario', '')
    if funcionario_filter:
        promocoes = promocoes.filter(funcionario__nome_completo__icontains=funcionario_filter)
    
    # Paginação
    paginator = Paginator(promocoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    total_promocoes = promocoes.count()
    promocoes_pendentes = promocoes.filter(status='PENDENTE').count()
    promocoes_aprovadas = promocoes.filter(status='APROVADO').count()
    promocoes_implementadas = promocoes.filter(status='IMPLEMENTADO').count()
    promocoes_rejeitadas = promocoes.filter(status='REJEITADO').count()
    
    # Choices para os filtros
    status_choices = Promocao.STATUS_CHOICES
    tipo_choices = Promocao.TIPO_CHOICES
    
    context = {
        'promocoes': page_obj,
        'status_filter': status_filter,
        'tipo_filter': tipo_filter,
        'funcionario_filter': funcionario_filter,
        'status_choices': status_choices,
        'tipo_choices': tipo_choices,
        'stats': {
            'total': total_promocoes,
            'pendentes': promocoes_pendentes,
            'aprovadas': promocoes_aprovadas,
            'implementadas': promocoes_implementadas,
            'rejeitadas': promocoes_rejeitadas,
        }
    }
    
    return render(request, 'rh/promocoes/main.html', context)

@login_required
def rh_promocao_add(request):
    """Adicionar promoção"""
    if request.method == 'POST':
        from datetime import date
        funcionario_id = request.POST.get('funcionario')
        tipo = request.POST.get('tipo')
        cargo_novo_id = request.POST.get('cargo_novo')
        salario_novo = request.POST.get('salario_novo')
        motivo = request.POST.get('motivo', '')
        justificativa = request.POST.get('justificativa', '')
        observacoes = request.POST.get('observacoes', '')

        # Validações mínimas: funcionário, tipo e salário novo
        if not funcionario_id or not tipo or not salario_novo:
            messages.error(request, 'Selecione o funcionário, o tipo e informe o salário novo.')
        else:
            try:
                funcionario = get_object_or_404(Funcionario, id=funcionario_id)
                salario_anterior_val = Decimal(funcionario.get_salario_atual())
                cargo_anterior_obj = funcionario.cargo

                # Se for promoção de cargo, cargo_novo é opcional (pode manter o mesmo)
                cargo_novo_val = cargo_novo_id if cargo_novo_id else None

                promocao = Promocao.objects.create(
                    funcionario=funcionario,
                    tipo=tipo,
                    status='PENDENTE',
                    cargo_anterior=cargo_anterior_obj,
                    cargo_novo_id=cargo_novo_val,
                    data_solicitacao=date.today(),
                    salario_anterior=salario_anterior_val,
                    salario_novo=Decimal(salario_novo),
                    motivo=motivo,
                    justificativa=justificativa,
                    observacoes=observacoes,
                )
                messages.success(request, 'Promoção/Aumento criado com sucesso!')
                return redirect('rh:promocao_detail', promocao_id=promocao.id)
            except (InvalidOperation, ValueError) as e:
                messages.error(request, f'Erro nos valores informados: {str(e)}')
            except Exception as e:
                messages.error(request, f'Erro ao salvar: {str(e)}')
    
    funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
    cargos = Cargo.objects.filter(ativo=True).order_by('nome')
    tipo_choices = Promocao.TIPO_CHOICES
    
    context = {
        'funcionarios': funcionarios,
        'cargos': cargos,
        'tipo_choices': tipo_choices,
    }
    return render(request, 'rh/promocoes/form.html', context)

@login_required
def rh_promocao_detail(request, promocao_id):
    """Detalhes da promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/detail.html', context)
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_edit(request, promocao_id):
    """Editar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            funcionario_id = request.POST.get('funcionario')
            tipo = request.POST.get('tipo')
            cargo_novo_id = request.POST.get('cargo_novo')
            salario_novo = request.POST.get('salario_novo')
            motivo = request.POST.get('motivo', '')
            justificativa = request.POST.get('justificativa', '')
            observacoes = request.POST.get('observacoes', '')

            if not funcionario_id or not tipo or not salario_novo:
                messages.error(request, 'Selecione o funcionário, o tipo e informe o salário novo.')
            else:
                try:
                    funcionario = get_object_or_404(Funcionario, id=funcionario_id)
                    promocao.funcionario = funcionario
                    promocao.tipo = tipo
                    promocao.cargo_anterior = funcionario.cargo
                    promocao.cargo_novo_id = cargo_novo_id if cargo_novo_id else None
                    # Mantemos data_solicitacao original
                    promocao.salario_anterior = Decimal(funcionario.get_salario_atual())
                    promocao.salario_novo = Decimal(salario_novo)
                    promocao.motivo = motivo
                    promocao.justificativa = justificativa
                    promocao.observacoes = observacoes
                    promocao.save()

                    messages.success(request, 'Promoção/Aumento atualizado com sucesso!')
                    return redirect('rh:promocao_detail', promocao_id=promocao.id)
                except (InvalidOperation, ValueError) as e:
                    messages.error(request, f'Erro nos valores informados: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Erro ao salvar: {str(e)}')
        
        funcionarios = Funcionario.objects.filter(status='AT').order_by('nome_completo')
        cargos = Cargo.objects.filter(ativo=True).order_by('nome')
        tipo_choices = Promocao.TIPO_CHOICES
        
        context = {
            'promocao': promocao,
            'funcionarios': funcionarios,
            'cargos': cargos,
            'tipo_choices': tipo_choices,
        }
        return render(request, 'rh/promocoes/form.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_delete(request, promocao_id):
    """Deletar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            promocao.delete()
            messages.success(request, 'Promoção deletada com sucesso!')
            return redirect('rh:promocoes')
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/delete.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_aprovar(request, promocao_id):
    """Aprovar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            observacoes = request.POST.get('observacoes', '')
            promocao.status = 'APROVADO'
            if observacoes:
                promocao.observacoes = observacoes
            promocao.save()
            messages.success(request, 'Promoção aprovada com sucesso!')
            return redirect('rh:promocao_detail', promocao_id=promocao.id)
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/aprovar.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_rejeitar(request, promocao_id):
    """Rejeitar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            motivo_rejeicao = request.POST.get('motivo_rejeicao', '')
            if not motivo_rejeicao:
                messages.error(request, 'Motivo da rejeição é obrigatório.')
            else:
                promocao.status = 'REJEITADO'
                promocao.observacoes = motivo_rejeicao
                promocao.save()
                messages.success(request, 'Promoção rejeitada com sucesso!')
                return redirect('rh:promocao_detail', promocao_id=promocao.id)
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/rejeitar.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_promocao_implementar(request, promocao_id):
    """Implementar promoção"""
    try:
        promocao = Promocao.objects.get(id=promocao_id)
        
        if request.method == 'POST':
            data_implementacao = request.POST.get('data_implementacao')
            if not data_implementacao:
                messages.error(request, 'Data de implementação é obrigatória.')
            else:
                try:
                    # Atualizar dados do funcionário de forma segura
                    implement_date = datetime.strptime(data_implementacao, '%Y-%m-%d').date()

                    funcionario = promocao.funcionario
                    # Atualizar salário
                    if promocao.salario_novo is not None:
                        funcionario.salario_atual = promocao.salario_novo
                    # Atualizar cargo somente se foi definido um novo cargo
                    if promocao.cargo_novo is not None:
                        funcionario.cargo = promocao.cargo_novo
                    funcionario.save()

                    # Atualizar status e datas da promoção
                    promocao.status = 'IMPLEMENTADO'
                    promocao.data_implementacao = implement_date
                    promocao.data_efetivacao = implement_date
                    promocao.save()

                    messages.success(request, 'Promoção/Aumento implementado com sucesso!')
                    return redirect('rh:promocao_detail', promocao_id=promocao.id)
                except ValueError as e:
                    messages.error(request, f'Erro na data: {str(e)}')
        
        context = {'promocao': promocao}
        return render(request, 'rh/promocoes/implementar.html', context)
        
    except Promocao.DoesNotExist:
        messages.error(request, 'Promoção não encontrada.')
        return redirect('rh:promocoes')

@login_required
def rh_departamento_vinculacao(request, id):
    """Gerenciar vinculação de departamento a outras sucursais"""
    departamento = get_object_or_404(Departamento, id=id)
    
    if request.method == 'POST':
        sucursal_id = request.POST.get('sucursal')
        acao = request.POST.get('acao')
        
        try:
            sucursal = Sucursal.objects.get(id=sucursal_id)
            
            if acao == 'vincular':
                DepartamentoSucursal.objects.get_or_create(
                    departamento=departamento,
                    sucursal=sucursal,
                    defaults={'ativo': True}
                )
                messages.success(request, f'Departamento vinculado à {sucursal.nome}')
            elif acao == 'desvincular':
                DepartamentoSucursal.objects.filter(
                    departamento=departamento,
                    sucursal=sucursal
                ).delete()
                messages.success(request, f'Departamento desvinculado de {sucursal.nome}')
            
            return redirect('rh:departamento_vinculacao', id=departamento.id)
            
        except Sucursal.DoesNotExist:
            messages.error(request, 'Sucursal não encontrada')
        except Exception as e:
            messages.error(request, f'Erro: {e}')
    
    # Buscar sucursais disponíveis e vinculações
    sucursais_disponiveis = Sucursal.objects.exclude(id=departamento.sucursal.id).order_by('nome')
    vinculacoes = DepartamentoSucursal.objects.filter(departamento=departamento).select_related('sucursal')
    
    context = {
        'departamento': departamento,
        'sucursais_disponiveis': sucursais_disponiveis,
        'vinculacoes': vinculacoes,
    }
    
    return render(request, 'rh/departamentos/vinculacao.html', context)

@login_required
def rh_promocoes_relatorio(request):
    """Relatório de promoções"""
    promocoes = Promocao.objects.all().order_by('-data_solicitacao')
    
    # Filtros
    status_filter = request.GET.get('status', '')
    if status_filter:
        promocoes = promocoes.filter(status=status_filter)
    
    data_inicio = request.GET.get('data_inicio')
    if data_inicio:
        try:
            promocoes = promocoes.filter(data_solicitacao__gte=datetime.strptime(data_inicio, '%Y-%m-%d').date())
        except ValueError:
            pass
    
    data_fim = request.GET.get('data_fim')
    if data_fim:
        try:
            promocoes = promocoes.filter(data_solicitacao__lte=datetime.strptime(data_fim, '%Y-%m-%d').date())
        except ValueError:
            pass
    
    # Paginação
    paginator = Paginator(promocoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    total_promocoes = promocoes.count()
    promocoes_aprovadas = promocoes.filter(status='APROVADO').count()
    promocoes_pendentes = promocoes.filter(status='PENDENTE').count()
    promocoes_implementadas = promocoes.filter(status='IMPLEMENTADO').count()
    
    context = {
        'promocoes': page_obj,
        'status_filter': status_filter,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'total_promocoes': total_promocoes,
        'promocoes_aprovadas': promocoes_aprovadas,
        'promocoes_pendentes': promocoes_pendentes,
        'promocoes_implementadas': promocoes_implementadas,
        'STATUS_CHOICES': [
            ('PENDENTE', 'Pendente'),
            ('APROVADO', 'Aprovado'),
            ('REJEITADO', 'Rejeitado'),
            ('IMPLEMENTADO', 'Implementado'),
        ]
    }
    
    return render(request, 'rh/promocoes/relatorio.html', context)

@login_required
def api_funcionarios_search(request):
    return JsonResponse([], safe=False)

# Função de informações da empresa
@login_required
def empresa_info(request):
    from .models_base import DadosEmpresa, Sucursal
    
    # Buscar dados da empresa (assumindo que há apenas uma empresa sede)
    dados_empresa = DadosEmpresa.objects.filter(is_sede=True).first()
    
    # Buscar sucursais da empresa
    sucursais = []
    if dados_empresa:
        sucursais = Sucursal.objects.filter(empresa_sede=dados_empresa, ativa=True).order_by('nome')
    
    context = {
        'dados_empresa': dados_empresa,
        'sucursais': sucursais,
    }
    
    return render(request, 'empresa/info.html', context)


@login_required
def rh_marcar_finais_semana_automaticos(request):
    """Marcar automaticamente os finais de semana no calendário de presenças"""
    if request.method == 'POST':
        try:
            import json
            import calendar
            from datetime import date
            
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                funcionario_id = data.get('funcionario_id')
                mes = int(data.get('mes') or date.today().month)
                ano = int(data.get('ano') or date.today().year)
            else:
                funcionario_id = request.POST.get('funcionario_id')
                mes = int(request.POST.get('mes') or date.today().month)
                ano = int(request.POST.get('ano') or date.today().year)
            
            funcionario = get_object_or_404(Funcionario, id=funcionario_id)
            tipo_folga = get_object_or_404(TipoPresenca, codigo='FG')
            
            # Obter configuração de dias de trabalho da sucursal
            sucursal = funcionario.sucursal
            dias_trabalho = sucursal.get_dias_trabalho_weekdays()
            
            # Obter todos os dias do mês
            dias_no_mes = calendar.monthrange(ano, mes)[1]
            presencas_criadas = 0
            presencas_atualizadas = 0
            
            for dia in range(1, dias_no_mes + 1):
                data_atual = date(ano, mes, dia)
                dia_semana = data_atual.weekday()  # 0=segunda, 6=domingo
                
                # Verificar se NÃO é dia de trabalho (folga)
                if dia_semana not in dias_trabalho:
                    presenca_existente = Presenca.objects.filter(
                        funcionario=funcionario,
                        data=data_atual
                    ).first()
                    
                    if presenca_existente:
                        # Só atualizar se não for um tipo mais específico (como Horas Extras)
                        if presenca_existente.tipo_presenca.codigo == 'FG':
                            nome_dia = data_atual.strftime('%A')
                            presenca_existente.observacoes = f"Folga - {nome_dia}"
                            presenca_existente.save()
                            presencas_atualizadas += 1
                    else:
                        nome_dia = data_atual.strftime('%A')
                        Presenca.objects.create(
                            funcionario=funcionario,
                            data=data_atual,
                            tipo_presenca=tipo_folga,
                            observacoes=f"Folga - {nome_dia}"
                        )
                        presencas_criadas += 1
            
            return JsonResponse({
                'success': True,
                'criadas': presencas_criadas,
                'atualizadas': presencas_atualizadas,
                'total_dias_folga': presencas_criadas + presencas_atualizadas,
                'dias_trabalho_sucursal': dias_trabalho,
                'message': f'Foram processados {presencas_criadas + presencas_atualizadas} dias de folga baseados no horário da sucursal: {presencas_criadas} criados, {presencas_atualizadas} atualizados.'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)

@login_required
def rh_horarios_expediente(request, sucursal_id=None):
    """Gerenciar horários de expediente da sucursal"""
    
    # Obter sucursal
    if sucursal_id:
        sucursal = get_object_or_404(Sucursal, id=sucursal_id)
    else:
        # Usar primeira sucursal ativa do usuário
        sucursal = Sucursal.objects.filter(ativa=True).first()
        if not sucursal:
            messages.error(request, 'Nenhuma sucursal ativa encontrada.')
            return redirect('rh:index')
    
    # Dias da semana
    DIAS_SEMANA = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]
    
    # Processar formulário
    if request.method == 'POST':
        try:
            # Atualizar configurações básicas da sucursal
            hora_inicio = request.POST.get('hora_inicio_padrao')
            hora_fim = request.POST.get('hora_fim_padrao')
            duracao_almoco = request.POST.get('duracao_almoco_padrao')
            horas_trabalho = request.POST.get('horas_trabalho_dia')
            
            if hora_inicio:
                from datetime import time
                try:
                    sucursal.hora_inicio_expediente = time.fromisoformat(hora_inicio)
                except ValueError:
                    messages.error(request, f'Formato de hora de início inválido: {hora_inicio}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            if hora_fim:
                from datetime import time
                try:
                    sucursal.hora_fim_expediente = time.fromisoformat(hora_fim)
                except ValueError:
                    messages.error(request, f'Formato de hora de fim inválido: {hora_fim}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            if duracao_almoco:
                from datetime import timedelta
                try:
                    # Converter formato HH:MM:SS para timedelta
                    if ':' in duracao_almoco:
                        parts = duracao_almoco.split(':')
                        if len(parts) == 3:
                            hours, minutes, seconds = map(int, parts)
                            sucursal.duracao_almoco = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        else:
                            raise ValueError("Formato inválido")
                    else:
                        raise ValueError("Formato inválido")
                except ValueError:
                    messages.error(request, f'Formato de duração do almoço inválido: {duracao_almoco}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            if horas_trabalho:
                from datetime import timedelta
                try:
                    # Converter formato HH:MM:SS para timedelta
                    if ':' in horas_trabalho:
                        parts = horas_trabalho.split(':')
                        if len(parts) == 3:
                            hours, minutes, seconds = map(int, parts)
                            sucursal.horas_trabalho_dia = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                        else:
                            raise ValueError("Formato inválido")
                    else:
                        raise ValueError("Formato inválido")
                except ValueError:
                    messages.error(request, f'Formato de horas de trabalho inválido: {horas_trabalho}')
                    return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
            # Calcular dias de trabalho baseado nos checkboxes
            dias_trabalho = []
            for dia_semana, nome_dia in DIAS_SEMANA:
                if request.POST.get(f'ativo_{dia_semana}') == 'on':
                    dias_trabalho.append(dia_semana)
            
            sucursal.dias_trabalho_semana = len(dias_trabalho)
            sucursal.save()
            
            messages.success(request, 'Horários de expediente atualizados com sucesso!')
            return redirect('rh:horarios_expediente', sucursal_id=sucursal.id)
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar horários: {str(e)}')
    
    # Obter todas as sucursais para o seletor
    sucursais = Sucursal.objects.filter(ativa=True).order_by('nome')
    
    # Determinar quais dias estão ativos baseado no dias_trabalho_semana
    dias_ativos = []
    if sucursal.dias_trabalho_semana == 5:
        dias_ativos = [0, 1, 2, 3, 4]  # Segunda a sexta
    elif sucursal.dias_trabalho_semana == 6:
        dias_ativos = [0, 1, 2, 3, 4, 5]  # Segunda a sábado
    elif sucursal.dias_trabalho_semana == 7:
        dias_ativos = [0, 1, 2, 3, 4, 5, 6]  # Todos os dias
    else:
        dias_ativos = [0, 1, 2, 3, 4]  # Padrão: segunda a sexta
    
    context = {
        'sucursal': sucursal,
        'sucursais': sucursais,
        'dias_semana': DIAS_SEMANA,
        'dias_ativos': dias_ativos,
    }
    
    return render(request, 'rh/horarios_expediente.html', context)

# =============================================================================
# TRANSFERÊNCIAS DE FUNCIONÁRIOS
# =============================================================================

@login_required
def rh_transferencias(request):
    """Lista de transferências de funcionários"""
    transferencias = TransferenciaFuncionario.objects.select_related(
        'funcionario', 'sucursal_origem', 'sucursal_destino', 
        'departamento_origem', 'departamento_destino'
    ).all().order_by('-data_solicitacao')
    
    # Filtros
    status = request.GET.get('status', '')
    funcionario_id = request.GET.get('funcionario', '')
    sucursal_id = request.GET.get('sucursal', '')
    
    if status:
        transferencias = transferencias.filter(status=status)
    
    if funcionario_id:
        transferencias = transferencias.filter(funcionario_id=funcionario_id)
    
    if sucursal_id:
        transferencias = transferencias.filter(
            Q(sucursal_origem_id=sucursal_id) | Q(sucursal_destino_id=sucursal_id)
        )
    
    paginator = Paginator(transferencias, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status': status,
        'funcionario_id': funcionario_id,
        'sucursal_id': sucursal_id,
        'funcionarios': Funcionario.objects.filter(status='AT').order_by('nome_completo'),
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'status_choices': TransferenciaFuncionario.STATUS_CHOICES,
    }
    return render(request, 'rh/transferencias/main.html', context)

@login_required
def rh_transferencia_add(request):
    """Adicionar nova transferência"""
    if request.method == 'POST':
        funcionario_id = request.POST.get('funcionario')
        sucursal_destino_id = request.POST.get('sucursal_destino')
        departamento_destino_id = request.POST.get('departamento_destino')
        cargo_novo_id = request.POST.get('cargo_novo', '')
        data_efetiva = request.POST.get('data_efetiva')
        motivo = request.POST.get('motivo')
        observacoes = request.POST.get('observacoes', '')
        
        if not all([funcionario_id, sucursal_destino_id, departamento_destino_id, data_efetiva, motivo]):
            messages.error(request, 'Todos os campos obrigatórios devem ser preenchidos.')
            return redirect('rh:transferencia_add')
        
        try:
            funcionario = Funcionario.objects.get(id=funcionario_id)
            # Verificar se já existe transferência pendente para este funcionário
            transferencia_pendente = TransferenciaFuncionario.objects.filter(
                funcionario=funcionario,
                status__in=['PENDENTE', 'APROVADO']
            ).exists()
            
            if transferencia_pendente:
                messages.error(request, 'Este funcionário já possui uma transferência pendente ou aprovada.')
                return redirect('rh:transferencia_add')
            transferencia = TransferenciaFuncionario.objects.create(
                funcionario=funcionario,
                sucursal_origem=funcionario.sucursal,
                departamento_origem=funcionario.departamento,
                sucursal_destino_id=sucursal_destino_id,
                departamento_destino_id=departamento_destino_id,
                cargo_novo_id=cargo_novo_id if cargo_novo_id else None,
                data_solicitacao=timezone.now().date(),
                data_efetiva=data_efetiva,
                motivo=motivo,
                observacoes=observacoes,
                criado_por=request.user
            )
            messages.success(request, 'Transferência solicitada com sucesso.')
            return redirect('rh:transferencias')
        except Exception as e:
            messages.error(request, f'Erro ao criar transferência: {str(e)}')
    
    context = {
        'funcionarios': Funcionario.objects.filter(status='AT').select_related('sucursal', 'departamento', 'cargo').order_by('nome_completo'),
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'rh/transferencias/form.html', context)

@login_required
def rh_transferencia_detail(request, transferencia_id):
    """Detalhes da transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    context = {
        'transferencia': transferencia,
    }
    return render(request, 'rh/transferencias/detail.html', context)

@login_required
def rh_transferencia_edit(request, transferencia_id):
    """Editar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    # Só permite editar se estiver pendente
    if transferencia.status != 'PENDENTE':
        messages.error(request, 'Apenas transferências pendentes podem ser editadas.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        transferencia.sucursal_destino_id = request.POST.get('sucursal_destino')
        transferencia.departamento_destino_id = request.POST.get('departamento_destino')
        transferencia.cargo_novo_id = request.POST.get('cargo_novo') or None
        transferencia.data_efetiva = request.POST.get('data_efetiva')
        transferencia.motivo = request.POST.get('motivo')
        transferencia.observacoes = request.POST.get('observacoes', '')
        
        try:
            transferencia.save()
            messages.success(request, 'Transferência atualizada com sucesso.')
            return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
        except Exception as e:
            messages.error(request, f'Erro ao atualizar transferência: {str(e)}')
    
    context = {
        'transferencia': transferencia,
        'sucursais': Sucursal.objects.filter(ativa=True).order_by('nome'),
        'cargos': Cargo.objects.filter(ativo=True).order_by('nome'),
    }
    return render(request, 'rh/transferencias/form.html', context)

@login_required
def rh_transferencia_delete(request, transferencia_id):
    """Excluir transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    # Só permite excluir se estiver pendente
    if transferencia.status != 'PENDENTE':
        messages.error(request, 'Apenas transferências pendentes podem ser excluídas.')
        return redirect('rh:transferencias')
    
    if request.method == 'POST':
        try:
            transferencia.delete()
            messages.success(request, 'Transferência excluída com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao excluir transferência: {str(e)}')
        return redirect('rh:transferencias')
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/delete.html', context)

@login_required
def rh_transferencia_aprovar(request, transferencia_id):
    """Aprovar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if not transferencia.pode_aprovar:
        messages.error(request, 'Esta transferência não pode ser aprovada.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        try:
            transferencia.status = 'APROVADO'
            transferencia.data_aprovacao = timezone.now().date()
            transferencia.aprovado_por = request.user
            transferencia.save()
            messages.success(request, 'Transferência aprovada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao aprovar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/approve.html', context)

@login_required
def rh_transferencia_rejeitar(request, transferencia_id):
    """Rejeitar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if not transferencia.pode_aprovar:
        messages.error(request, 'Esta transferência não pode ser rejeitada.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        motivo_rejeicao = request.POST.get('motivo_rejeicao', '')
        if not motivo_rejeicao:
            messages.error(request, 'Motivo da rejeição é obrigatório.')
            return redirect('rh:transferencia_rejeitar', transferencia_id=transferencia_id)
        
        try:
            transferencia.status = 'REJEITADO'
            transferencia.motivo_rejeicao = motivo_rejeicao
            transferencia.rejeitado_por = request.user
            transferencia.save()
            messages.success(request, 'Transferência rejeitada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao rejeitar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/reject.html', context)

@login_required
def rh_transferencia_implementar(request, transferencia_id):
    """Implementar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if not transferencia.pode_implementar:
        messages.error(request, 'Esta transferência não pode ser implementada.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        try:
            # Atualizar dados do funcionário
            funcionario = transferencia.funcionario
            funcionario.sucursal = transferencia.sucursal_destino
            funcionario.departamento = transferencia.departamento_destino
            
            if transferencia.cargo_novo:
                funcionario.cargo = transferencia.cargo_novo
            
            funcionario.save()
            
            # Atualizar status da transferência
            transferencia.status = 'IMPLEMENTADO'
            transferencia.data_implementacao = timezone.now().date()
            transferencia.save()
            
            messages.success(request, 'Transferência implementada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao implementar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/implement.html', context)

@login_required
def rh_transferencia_efetivar(request, transferencia_id):
    """Efetivar transferência"""
    transferencia = get_object_or_404(TransferenciaFuncionario, id=transferencia_id)
    
    if transferencia.status != 'IMPLEMENTADO':
        messages.error(request, 'Apenas transferências implementadas podem ser efetivadas.')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    if request.method == 'POST':
        try:
            transferencia.status = 'EFETIVADO'
            transferencia.data_efetivacao = timezone.now().date()
            transferencia.save()
            messages.success(request, 'Transferência efetivada com sucesso.')
        except Exception as e:
            messages.error(request, f'Erro ao efetivar transferência: {str(e)}')
        return redirect('rh:transferencia_detail', transferencia_id=transferencia_id)
    
    context = {'transferencia': transferencia}
    return render(request, 'rh/transferencias/efetivar.html', context)

@login_required
def rh_transferencias_relatorio(request):
    """Relatório de transferências"""
    transferencias = TransferenciaFuncionario.objects.select_related(
        'funcionario', 'sucursal_origem', 'sucursal_destino'
    ).all().order_by('-data_solicitacao')
    
    # Filtros
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    status = request.GET.get('status')
    
    if data_inicio:
        transferencias = transferencias.filter(data_solicitacao__gte=data_inicio)
    
    if data_fim:
        transferencias = transferencias.filter(data_solicitacao__lte=data_fim)
    
    if status:
        transferencias = transferencias.filter(status=status)
    
    context = {
        'transferencias': transferencias,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'status': status,
        'status_choices': TransferenciaFuncionario.STATUS_CHOICES,
    }
    return render(request, 'rh/transferencias/relatorio.html', context)

@login_required
def api_departamentos_por_sucursal(request, sucursal_id):
    """API para buscar departamentos por sucursal"""
    try:
        sucursal = Sucursal.objects.get(id=sucursal_id)
        
        # Buscar departamentos da sucursal e departamentos vinculados
        departamentos_da_sucursal = Departamento.objects.filter(sucursal=sucursal).order_by('nome')
        departamentos_vinculados = Departamento.objects.filter(
            sucursais_vinculadas__sucursal=sucursal,
            sucursais_vinculadas__ativo=True
        ).order_by('nome')
        
        # Combinar e remover duplicatas
        todos_departamentos = list(departamentos_da_sucursal) + list(departamentos_vinculados)
        departamentos_unicos = list({dept.id: dept for dept in todos_departamentos}.values())
        
        results = []
        for departamento in departamentos_unicos:
            results.append({
                'id': departamento.id,
                'nome': departamento.nome,
                'codigo': departamento.codigo,
            })
        return JsonResponse({'results': results})
    except Sucursal.DoesNotExist:
        return JsonResponse({'results': []})
    except Exception as e:
        return JsonResponse({'results': [], 'error': str(e)})
