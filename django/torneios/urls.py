from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),

    path('torneios/', views.torneio_lista, name='torneio_lista'),
    path('torneios/novo/', views.torneio_form, name='torneio_novo'),
    path('torneios/<int:pk>/', views.torneio_detalhe, name='torneio_detalhe'),
    path('torneios/<int:pk>/editar/', views.torneio_form, name='torneio_editar'),
    path('torneios/<int:pk>/excluir/', views.torneio_excluir, name='torneio_excluir'),
    path('torneios/<int:pk>/inscrever/', views.inscrever, name='inscrever'),
    path('torneios/<int:pk>/gerar-chave/', views.gerar_chave, name='gerar_chave'),
    path('torneios/<int:pk>/gerar-mata-mata/', views.gerar_mata_mata, name='gerar_mata_mata'),
    path('torneios/<int:pk>/refazer-chave/', views.refazer_chave, name='refazer_chave'),

    path('inscricoes/<int:pk>/remover/', views.remover_inscricao, name='remover_inscricao'),
    path('partidas/<int:pk>/', views.partida_resultado, name='partida_resultado'),

    path('jogadores/', views.jogador_lista, name='jogador_lista'),
    path('jogadores/novo/', views.jogador_form, name='jogador_novo'),
    path('jogadores/<int:pk>/', views.jogador_detalhe, name='jogador_detalhe'),
    path('jogadores/<int:pk>/editar/', views.jogador_form, name='jogador_editar'),
    path('jogadores/<int:pk>/excluir/', views.jogador_excluir, name='jogador_excluir'),
]
