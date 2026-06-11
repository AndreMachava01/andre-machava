from django.urls import include, path

app_name = 'rh'

urlpatterns = [
    path('', include('meuprojeto.empresa.urls_rh_core')),
    path('', include('meuprojeto.empresa.urls_rh_presenca')),
    path('', include('meuprojeto.empresa.urls_rh_salarios')),
    path('', include('meuprojeto.empresa.urls_rh_desenvolvimento')),
    path('', include('meuprojeto.empresa.urls_rh_relatorios')),
    path('', include('meuprojeto.empresa.urls_rh_folha')),
    path('', include('meuprojeto.empresa.urls_rh_submodulos')),
]
