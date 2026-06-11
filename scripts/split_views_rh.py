"""Divide views_rh.py monolítico em módulos por domínio."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'meuprojeto/empresa/views_rh.py'
content = path.read_text(encoding='utf-8')
lines = content.splitlines(keepends=True)
tree = ast.parse(content)

HEADER = '''"""Views RH — {title}."""
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

'''


def classify(name: str) -> str:
    if name.startswith('rh_folha') or name.startswith('rh_canhoto'):
        return 'folha'
    if name.startswith('relatorio') or name == 'rh_relatorios':
        return 'relatorios'
    if name in ('rh_main', 'empresa_info', 'api_funcionarios_search', 'api_departamentos_por_sucursal'):
        return 'core'
    if name.startswith('rh_funcionario') or name.startswith('rh_departamento') or name.startswith('rh_cargo'):
        return 'core'
    if name.startswith('rh_salario') or name in ('rh_beneficios_salariais', 'rh_descontos_salariais'):
        return 'salarios'
    if name.startswith('rh_beneficio_salarial') or name.startswith('rh_desconto_salarial'):
        return 'salarios'
    if (
        name.startswith('rh_promocao') or name.startswith('rh_promocoes')
        or name.startswith('rh_transferencia') or name == 'rh_transferencias'
        or name.startswith('treinamento') or name.startswith('inscricao')
        or name.startswith('rh_treinamento') or name == 'rh_avaliacoes'
        or name.startswith('avaliacao') or name.startswith('criterio')
    ):
        return 'desenvolvimento'
    return 'presenca'


def main():
    modules = {k: [] for k in ('core', 'presenca', 'salarios', 'desenvolvimento', 'relatorios', 'folha')}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            start = node.lineno - 1
            if node.decorator_list:
                start = node.decorator_list[0].lineno - 1
            end = node.end_lineno
            chunk = ''.join(lines[start:end])
            mod = classify(node.name)
            modules[mod].append((node.name, chunk))

    titles = {
        'core': 'núcleo (dashboard, funcionários, dept, cargo, API)',
        'presenca': 'presenças, calendário, feriados, horas extras',
        'salarios': 'salários, benefícios e descontos',
        'desenvolvimento': 'treinos, avaliações, promoções, transferências',
        'relatorios': 'relatórios RH',
        'folha': 'folha salarial',
    }

    base = ROOT / 'meuprojeto/empresa'
    all_names = []
    for mod, chunks in modules.items():
        fname = f'views_rh_{mod}.py'
        body = '\n\n'.join(c[1].rstrip() for c in chunks)
        (base / fname).write_text(HEADER.format(title=titles[mod]) + '\n' + body + '\n', encoding='utf-8')
        all_names.extend(c[0] for c in chunks)
        print(f'{fname}: {len(chunks)} funções')

    exports = [f'from .views_rh_{mod} import *  # noqa: F401, F403' for mod in modules]
    (base / 'views_rh.py').write_text(
        '"""Hub de compatibilidade — re-exporta views RH dos submódulos."""\n' + '\n'.join(exports) + '\n',
        encoding='utf-8',
    )
    print('total funções:', len(all_names))


if __name__ == '__main__':
    main()
