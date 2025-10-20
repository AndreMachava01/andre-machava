import os
import logging
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO

logger = logging.getLogger(__name__)

class EmailService:
    """Serviço para envio de emails com SendGrid"""
    
    def __init__(self):
        self.sendgrid_api_key = getattr(settings, 'SENDGRID_API_KEY', None)
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@conception.co.mz')
        self.from_name = getattr(settings, 'EMAIL_FROM_NAME', 'Conception')
        
        if self.sendgrid_api_key:
            self.sg = SendGridAPIClient(api_key=self.sendgrid_api_key)
        else:
            self.sg = None
            logger.warning("SENDGRID_API_KEY não configurado. Emails serão simulados.")
    
    def gerar_pdf_ordem_compra(self, ordem_compra):
        """Gera PDF da ordem de compra usando ReportLab"""
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # Estilos personalizados
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1,  # Center
                textColor=colors.darkblue
            )
            
            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.darkblue
            )
            
            # Conteúdo do PDF
            story = []
            
            # Título
            story.append(Paragraph("ORDEM DE COMPRA", title_style))
            story.append(Spacer(1, 20))
            
            # Informações da ordem
            info_data = [
                ['Código:', ordem_compra.codigo],
                ['Número da Cotação:', ordem_compra.numero_cotacao or 'N/A'],
                ['Fornecedor:', ordem_compra.fornecedor.nome if ordem_compra.fornecedor else 'N/A'],
                ['Data:', ordem_compra.data_criacao.strftime('%d/%m/%Y')],
                ['Status:', ordem_compra.get_status_display()],
            ]
            
            info_table = Table(info_data, colWidths=[2*inch, 3*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(info_table)
            story.append(Spacer(1, 20))
            
            # Itens da ordem
            story.append(Paragraph("ITENS DA ORDEM", header_style))
            
            # Cabeçalho da tabela de itens
            items_data = [['Item', 'Quantidade', 'Preço Unitário', 'Total']]
            
            total_geral = 0
            for item in ordem_compra.itens.all():
                total_item = item.quantidade_solicitada * item.preco_unitario
                total_geral += total_item
                
                items_data.append([
                    f"{item.produto.nome} ({item.produto.codigo})" if item.produto else 'N/A',
                    str(item.quantidade_solicitada),
                    f"{item.preco_unitario:.2f} MT",
                    f"{total_item:.2f} MT"
                ])
            
            # Adicionar linha de total
            items_data.append(['', '', 'TOTAL GERAL:', f"{total_geral:.2f} MT"])
            
            items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(items_table)
            story.append(Spacer(1, 20))
            
            # Observações
            if ordem_compra.observacoes:
                story.append(Paragraph("OBSERVAÇÕES", header_style))
                story.append(Paragraph(ordem_compra.observacoes, styles['Normal']))
            
            # Gerar PDF
            doc.build(story)
            buffer.seek(0)
            
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Erro ao gerar PDF da ordem {ordem_compra.codigo}: {e}")
            return None
    
    def enviar_ordem_compra(self, ordem_compra, email_destinatario, assunto=None, mensagem_personalizada=None):
        """Envia ordem de compra por email"""
        try:
            # Gerar PDF
            pdf_content = self.gerar_pdf_ordem_compra(ordem_compra)
            if not pdf_content:
                return False, "Erro ao gerar PDF"
            
            # Preparar assunto
            if not assunto:
                assunto = f"Ordem de Compra {ordem_compra.codigo} - {ordem_compra.fornecedor.nome}"
            
            # Preparar mensagem
            if not mensagem_personalizada:
                mensagem_personalizada = f"""
                Prezado(a) {ordem_compra.fornecedor.nome},
                
                Segue em anexo a Ordem de Compra {ordem_compra.codigo} para sua análise e processamento.
                
                Detalhes da Ordem:
                - Código: {ordem_compra.codigo}
                - Número da Cotação: {ordem_compra.numero_cotacao}
                - Data: {ordem_compra.data_criacao.strftime('%d/%m/%Y')}
                - Total: {ordem_compra.valor_total} MT
                
                Por favor, confirme o recebimento e envie a cotação conforme solicitado.
                
                Atenciosamente,
                Equipe Conception
                """
            
            # Criar email
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=email_destinatario,
                subject=assunto,
                plain_text_content=mensagem_personalizada
            )
            
            # Adicionar anexo PDF
            if pdf_content:
                encoded_pdf = FileContent(pdf_content)
                pdf_attachment = Attachment(
                    file_content=encoded_pdf,
                    file_name=f"Ordem_Compra_{ordem_compra.codigo}.pdf",
                    file_type=FileType('application/pdf'),
                    disposition=Disposition('attachment')
                )
                message.attachment = pdf_attachment
            
            # Enviar email
            if self.sg:
                response = self.sg.send(message)
                logger.info(f"Email enviado para {email_destinatario}: {response.status_code}")
                return True, f"Email enviado com sucesso. Status: {response.status_code}"
            else:
                # Modo simulação
                logger.info(f"SIMULAÇÃO: Email seria enviado para {email_destinatario}")
                return True, "Email simulado (SendGrid não configurado)"
                
        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False, str(e)
    
    def enviar_email_simples(self, destinatario, assunto, mensagem, anexos=None):
        """Envia email simples com anexos opcionais"""
        try:
            message = Mail(
                from_email=(self.from_email, self.from_name),
                to_emails=destinatario,
                subject=assunto,
                plain_text_content=mensagem
            )
            
            # Adicionar anexos se fornecidos
            if anexos:
                for anexo in anexos:
                    attachment = Attachment(
                        file_content=anexo['content'],
                        file_name=anexo['filename'],
                        file_type=anexo.get('type', FileType('application/octet-stream')),
                        disposition=Disposition('attachment')
                    )
                    message.attachment = attachment
            
            if self.sg:
                response = self.sg.send(message)
                return True, f"Email enviado. Status: {response.status_code}"
            else:
                logger.info(f"SIMULAÇÃO: Email seria enviado para {destinatario}")
                return True, "Email simulado"
                
        except Exception as e:
            logger.error(f"Erro ao enviar email simples: {e}")
            return False, str(e)
