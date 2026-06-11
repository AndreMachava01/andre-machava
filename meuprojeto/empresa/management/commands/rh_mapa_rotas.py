"""Imprime mapa de rotas do módulo RH (urls_rh)."""
from django.core.management.base import BaseCommand
from django.urls import get_resolver


class Command(BaseCommand):
    help = 'Lista rotas do namespace rh: (path, name, view)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--formato',
            choices=('tabela', 'csv', 'markdown'),
            default='tabela',
            help='Formato de saída',
        )

    def handle(self, *args, **options):
        formato = options['formato']
        linhas = []

        def walk(patterns, prefix=''):
            for p in patterns:
                if hasattr(p, 'url_patterns'):
                    walk(p.url_patterns, prefix + str(p.pattern))
                else:
                    name = p.name or ''
                    if not name.startswith('rh:'):
                        if name:
                            name = f'rh:{name}'
                    callback = p.callback
                    view = ''
                    if callback:
                        view = getattr(callback, '__module__', '') + '.' + getattr(callback, '__name__', '')
                    linhas.append((prefix + str(p.pattern), name, view))

        resolver = get_resolver()
        for p in resolver.url_patterns:
            if hasattr(p, 'namespace') and p.namespace == 'rh':
                walk(p.url_patterns, '/rh/')
                break
            if hasattr(p, 'url_patterns'):
                for sub in p.url_patterns:
                    if getattr(sub, 'namespace', None) == 'rh':
                        walk(sub.url_patterns, '/rh/')
                        break

        linhas.sort(key=lambda x: x[0])

        if formato == 'csv':
            self.stdout.write('path,name,view')
            for path, name, view in linhas:
                self.stdout.write(f'"{path}","{name}","{view}"')
            return

        if formato == 'markdown':
            self.stdout.write('| Rota | Nome | View |')
            self.stdout.write('|------|------|------|')
            for path, name, view in linhas:
                self.stdout.write(f'| `{path}` | `{name}` | `{view}` |')
            return

        self.stdout.write(self.style.SUCCESS(f'Rotas RH: {len(linhas)}'))
        for path, name, view in linhas:
            self.stdout.write(f'{path:55} {name:40} {view}')
