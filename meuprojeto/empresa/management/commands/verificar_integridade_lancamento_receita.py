# Comando: python manage.py verificar_integridade_lancamento_receita --data=2026-02-17 --valor=54009.95 --descricao="Parcela 1"
# Ou por ID do lançamento (71.01): --lancamento-id=123
# Verifica: partida dupla (22+71.01), PendenteContaReceber CONFIRMADO, ParcelaPagamentoOrcamento e valor coerente com a ordem.

from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Verifica a integridade de um lançamento de receita (Prestação de Serviços): partida dupla, pendente e parcela.'

    def add_arguments(self, parser):
        parser.add_argument('--lancamento-id', type=int, help='ID do LancamentoFinanceiro (conta 71.01)')
        parser.add_argument('--data', type=str, help='Data do movimento (YYYY-MM-DD)')
        parser.add_argument('--valor', type=str, help='Valor em MT (ex: 54009.95)')
        parser.add_argument('--descricao', type=str, default='', help='Substring da descrição (ex: "Parcela 1" ou "OS-2026-000003")')

    def handle(self, *args, **options):
        from meuprojeto.empresa.models_financas import LancamentoFinanceiro, PendenteContaReceber
        from meuprojeto.empresa.models_stock import ParcelaPagamentoOrcamento, OrdemServico

        lanc_id = options.get('lancamento_id')
        data_str = options.get('data')
        valor_str = options.get('valor')
        descricao_sub = (options.get('descricao') or '').strip()

        if lanc_id:
            rec = LancamentoFinanceiro.objects.filter(
                id=lanc_id, conta__codigo='71.01', valor__gt=0
            ).select_related('conta').first()
            if not rec:
                self.stdout.write(self.style.ERROR(f'Lançamento id={lanc_id} não encontrado ou não é receita 71.01 positiva.'))
                return
        else:
            if not data_str or not valor_str:
                self.stdout.write(self.style.ERROR('Indique --lancamento-id=ID ou --data=YYYY-MM-DD e --valor=XXX.XX'))
                return
            from datetime import datetime
            try:
                data = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Data inválida: {data_str}. Use YYYY-MM-DD.'))
                return
            try:
                valor = Decimal(valor_str)
            except Exception:
                self.stdout.write(self.style.ERROR(f'Valor inválido: {valor_str}'))
                return
            q = LancamentoFinanceiro.objects.filter(
                data=data, conta__codigo='71.01', valor=valor, origem_tipo='VENDAS'
            ).select_related('conta')
            if descricao_sub:
                q = q.filter(descricao__icontains=descricao_sub)
            rec = q.order_by('-id').first()
            if not rec:
                self.stdout.write(self.style.ERROR(
                    f'Nenhum lançamento 71.01 encontrado com data={data}, valor={valor}' +
                    (f', descrição contendo "{descricao_sub}"' if descricao_sub else '')
                ))
                return

        data_mov = rec.data
        valor_mov = rec.valor
        doc_ref = rec.documento_ref or ''
        origem_id = rec.origem_id

        self.stdout.write(f'Lançamento receita: id={rec.id}, data={data_mov}, conta=71.01, valor={valor_mov}, descrição="{rec.descricao}"')
        erros = []

        # 1) Partida dupla: deve existir lançamento em 22 (Clientes) com mesmo data, documento_ref, origem_tipo, origem_id e valor
        l22 = LancamentoFinanceiro.objects.filter(
            data=data_mov,
            conta__codigo='22',
            valor=valor_mov,
            documento_ref=doc_ref,
            origem_tipo=rec.origem_tipo,
            origem_id=rec.origem_id,
        ).select_related('conta').first()
        if not l22:
            erros.append('Partida dupla: não existe lançamento em 22 (Clientes) com mesma data, valor, documento_ref e origem.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Partida dupla OK: lançamento 22 (Clientes) id={l22.id}, valor={l22.valor}'))

        # 2) PendenteContaReceber CONFIRMADO com lancamento = l22 (ou seja, pendente que originou este par)
        pendente = None
        if l22:
            pendente = PendenteContaReceber.objects.filter(lancamento_id=l22.id).first()
            if not pendente:
                erros.append('Não existe PendenteContaReceber com lancamento apontando para o lançamento 22 (confirmação de conta a receber).')
            elif pendente.estado != 'CONFIRMADO':
                erros.append(f'PendenteContaReceber id={pendente.id} está em estado "{pendente.estado}", esperado CONFIRMADO.')
            elif abs(pendente.valor - valor_mov) > Decimal('0.01'):
                erros.append(f'Valor do pendente ({pendente.valor}) difere do lançamento ({valor_mov}).')
            else:
                self.stdout.write(self.style.SUCCESS(f'Pendente OK: id={pendente.id}, estado=CONFIRMADO, valor={pendente.valor}'))

        # 3) Se origem é parcela (VENDAS_PARCELA no pendente), existe ParcelaPagamentoOrcamento e OrdemServico coerente
        if pendente and pendente.origem_tipo == 'VENDAS_PARCELA' and pendente.origem_id:
            parcela = ParcelaPagamentoOrcamento.objects.filter(
                id=pendente.origem_id
            ).select_related('ordem_servico').first()
            if not parcela:
                erros.append(f'ParcelaPagamentoOrcamento id={pendente.origem_id} não encontrada.')
            else:
                ordem = parcela.ordem_servico
                self.stdout.write(f'Parcela: id={parcela.id}, numero_ordem={parcela.numero_ordem}, tipo={parcela.tipo}, percentagem={parcela.percentagem}%')
                self.stdout.write(f'Ordem: id={ordem.id}, codigo={ordem.codigo}')
                # Valor esperado: valor_total_ordem (com IVA) * percentagem / 100
                try:
                    from meuprojeto.empresa.parcelas_vendas_utils import _valor_total_com_iva_ordem
                    valor_total_iva = _valor_total_com_iva_ordem(ordem)
                    valor_esperado = valor_total_iva * Decimal(parcela.percentagem) / Decimal('100')
                    if abs(valor_esperado - valor_mov) > Decimal('0.02'):
                        erros.append(
                            f'Valor da parcela incoerente: esperado {valor_esperado:.2f} '
                            f'(total com IVA {valor_total_iva:.2f} × {parcela.percentagem}%), lançado {valor_mov}.'
                        )
                    else:
                        self.stdout.write(self.style.SUCCESS(
                            f'Valor parcela OK: total com IVA={valor_total_iva:.2f}, {parcela.percentagem}% = {valor_esperado:.2f}'
                        ))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Não foi possível recalcular valor da parcela: {e}'))

        # 4) origem_id do lançamento deve ser o id da ordem (para "Ver ordem de serviço")
        if origem_id and pendente and pendente.origem_tipo == 'VENDAS_PARCELA' and pendente.origem_id:
            parcela = ParcelaPagamentoOrcamento.objects.filter(id=pendente.origem_id).select_related('ordem_servico').first()
            if parcela and parcela.ordem_servico_id != origem_id:
                erros.append(f'origem_id do lançamento ({origem_id}) não coincide com a ordem da parcela ({parcela.ordem_servico_id}).')
            elif parcela and parcela.ordem_servico_id == origem_id:
                self.stdout.write(self.style.SUCCESS(f'Link para ordem: origem_id={origem_id} (ordem {parcela.ordem_servico.codigo})'))

        if erros:
            self.stdout.write(self.style.ERROR('Problemas encontrados:'))
            for e in erros:
                self.stdout.write(self.style.ERROR(f'  - {e}'))
        else:
            self.stdout.write(self.style.SUCCESS('Integridade verificada: partida dupla, pendente e parcela/ordem coerentes.'))
