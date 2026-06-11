from django.http import HttpResponse
import asyncio
import subprocess
import shutil
import tempfile
import os
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

logger = logging.getLogger(__name__)

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


# Re-export views RH (modulo views_rh) para compatibilidade
from .views_rh import *  # noqa: F401, F403

from .services.rh_empreitada_service import (  # noqa: E402
    get_or_create_contrato_empreitada as _get_or_create_contrato_empreitada,
    processar_empreitada_concluida as _processar_empreitada_concluida,
)
from .services.rh_service import (  # noqa: E402
    marcar_presencas_automaticas,
    remover_presencas_automaticas,
)
