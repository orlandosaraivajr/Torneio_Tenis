from django.contrib import admin

from .models import Inscricao, Jogador, Partida, Torneio


class InscricaoInline(admin.TabularInline):
    model = Inscricao
    extra = 0
    autocomplete_fields = ['jogador']


@admin.register(Torneio)
class TorneioAdmin(admin.ModelAdmin):
    list_display = ['nome', 'data_torneio', 'local', 'formato', 'status', 'organizador']
    list_filter = ['status', 'formato']
    search_fields = ['nome', 'local']
    inlines = [InscricaoInline]


@admin.register(Jogador)
class JogadorAdmin(admin.ModelAdmin):
    list_display = ['nome']
    search_fields = ['nome']


@admin.register(Partida)
class PartidaAdmin(admin.ModelAdmin):
    list_display = ['torneio', 'rodada', 'grupo', 'posicao', 'inscricao_1', 'inscricao_2', 'placar', 'status']
    list_filter = ['torneio', 'rodada', 'status']
