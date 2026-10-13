from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import InscricaoForm, JogadorForm, ResultadoForm, TorneioForm
from .models import Inscricao, Jogador, Partida, Torneio

ABAS = ['visao', 'inscritos', 'chave', 'partidas', 'classificacao']


def home(request):
    q = request.GET.get('q', '').strip()
    if not q:
        recentes = Torneio.objects.annotate(num_inscritos=Count('inscricoes'))[:6]
        return render(request, 'torneios/home.html', {'recentes': recentes})
    torneios = Torneio.objects.filter(
        Q(nome__icontains=q) | Q(local__icontains=q) | Q(descricao__icontains=q)
    ).annotate(num_inscritos=Count('inscricoes'))
    jogadores = Jogador.objects.filter(nome__icontains=q)
    return render(request, 'torneios/busca.html', {
        'q': q, 'torneios': torneios, 'jogadores': jogadores, 'total': len(torneios) + len(jogadores),
    })


# ---------- Torneios ----------

def torneio_lista(request):
    torneios = Torneio.objects.annotate(num_inscritos=Count('inscricoes'))
    status = request.GET.get('status')
    if status:
        torneios = torneios.filter(status=status)
    return render(request, 'torneios/torneio_lista.html', {
        'torneios': torneios, 'status_atual': status, 'status_choices': Torneio.Status.choices,
    })


def torneio_form(request, pk=None):
    torneio = get_object_or_404(Torneio, pk=pk) if pk else None
    form = TorneioForm(request.POST or None, request.FILES or None, instance=torneio)
    if request.method == 'POST' and form.is_valid():
        torneio = form.save()
        messages.success(request, 'Torneio salvo.')
        return redirect(torneio)
    return render(request, 'torneios/form.html', {
        'form': form, 'titulo': 'Editar torneio' if pk else 'Novo torneio', 'voltar': torneio,
    })


@require_POST
def torneio_excluir(request, pk):
    torneio = get_object_or_404(Torneio, pk=pk)
    torneio.delete()
    messages.success(request, f'Torneio "{torneio.nome}" excluído.')
    return redirect('torneio_lista')


def torneio_detalhe(request, pk):
    torneio = get_object_or_404(Torneio.objects.select_related('organizador'), pk=pk)
    aba = request.GET.get('aba', 'visao')
    if aba not in ABAS:
        aba = 'visao'

    inscricoes = list(torneio.inscricoes.select_related('jogador'))
    partidas = list(
        torneio.partidas.select_related(
            'inscricao_1__jogador', 'inscricao_2__jogador', 'vencedor__jogador', 'proxima_partida'
        ).order_by('grupo', 'jornada', 'posicao')
    )
    tem_mata_mata = any(p.rodada in Partida.MATA_MATA for p in partidas)
    grupos_concluidos = (
        torneio.formato == Torneio.Formato.GRUPOS
        and partidas and not tem_mata_mata and all(p.encerrada for p in partidas)
    )

    contexto = {
        'torneio': torneio,
        'aba': aba,
        'inscricoes': inscricoes,
        'partidas': partidas,
        'tem_chave': bool(partidas),
        'tem_mata_mata': tem_mata_mata,
        'grupos_concluidos': grupos_concluidos,
        'campeao': services.campeao(torneio),
        'encerradas': sum(p.encerrada for p in partidas),
        'inscricao_form': InscricaoForm(torneio) if torneio.aceita_inscricoes else None,
        'chave': services.chave_mata_mata(torneio) if tem_mata_mata else [],
    }
    if torneio.formato == Torneio.Formato.ROUND_ROBIN and partidas:
        contexto['tabela_geral'] = services.classificacao(inscricoes, partidas)
    if torneio.formato == Torneio.Formato.GRUPOS and partidas:
        contexto['grupos'] = [
            {
                'letra': letra,
                'tabela': tabela,
                'jogos': [p for p in partidas if p.rodada == Partida.Rodada.GRUPOS and p.grupo == letra],
            }
            for letra, tabela in services.classificacao_por_grupo(torneio)
        ]
    return render(request, 'torneios/torneio_detalhe.html', contexto)


@require_POST
def inscrever(request, pk):
    torneio = get_object_or_404(Torneio, pk=pk)
    if not torneio.aceita_inscricoes:
        messages.error(request, 'Este torneio não aceita mais inscrições.')
        return redirect(f'{torneio.get_absolute_url()}?aba=inscritos')
    form = InscricaoForm(torneio, request.POST)
    if form.is_valid():
        inscricao = form.save()
        messages.success(request, f'{inscricao.jogador.nome} inscrito(a).')
    else:
        for erros in form.errors.values():
            for erro in erros:
                messages.error(request, erro)
    return redirect(f'{torneio.get_absolute_url()}?aba=inscritos')


@require_POST
def remover_inscricao(request, pk):
    inscricao = get_object_or_404(Inscricao.objects.select_related('torneio', 'jogador'), pk=pk)
    torneio = inscricao.torneio
    if not torneio.aceita_inscricoes:
        messages.error(request, 'Não é possível remover inscritos depois de gerada a chave.')
    else:
        inscricao.delete()
        messages.success(request, f'{inscricao.jogador.nome} removido(a) do torneio.')
    return redirect(f'{torneio.get_absolute_url()}?aba=inscritos')


def _executar(request, torneio, acao, sucesso, aba='chave'):
    try:
        acao(torneio)
        messages.success(request, sucesso)
    except services.FluxoError as erro:
        messages.error(request, str(erro))
    return redirect(f'{torneio.get_absolute_url()}?aba={aba}')


@require_POST
def gerar_chave(request, pk):
    torneio = get_object_or_404(Torneio, pk=pk)
    return _executar(request, torneio, services.gerar_chave, 'Chave gerada! Bons jogos.')


@require_POST
def gerar_mata_mata(request, pk):
    torneio = get_object_or_404(Torneio, pk=pk)
    return _executar(request, torneio, services.gerar_mata_mata_dos_grupos, 'Mata-mata gerado com os classificados.')


@require_POST
def refazer_chave(request, pk):
    torneio = get_object_or_404(Torneio, pk=pk)
    return _executar(request, torneio, services.refazer_chave,
                     'Chave apagada. Ajuste os inscritos e gere novamente.', aba='inscritos')


# ---------- Partidas ----------

def partida_resultado(request, pk):
    partida = get_object_or_404(
        Partida.objects.select_related('torneio', 'inscricao_1__jogador', 'inscricao_2__jogador', 'proxima_partida'),
        pk=pk,
    )
    voltar = request.GET.get('voltar') or request.POST.get('voltar') or 'chave'
    destino = f'{partida.torneio.get_absolute_url()}?aba={voltar if voltar in ABAS else "chave"}'
    if not partida.editavel:
        messages.error(request, 'Esta partida não pode mais ser alterada (a fase seguinte já foi disputada).')
        return redirect(destino)

    form = ResultadoForm(partida, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        dados = form.cleaned_data
        services.registrar_resultado(partida, dados['status'], dados['placar'], dados['vencedor_obj'], dados['data_hora'])
        messages.success(request, 'Partida atualizada.')
        return redirect(destino)
    return render(request, 'torneios/partida_form.html', {'partida': partida, 'form': form, 'voltar': voltar, 'destino': destino})


# ---------- Jogadores ----------

def jogador_lista(request):
    q = request.GET.get('q', '').strip()
    jogadores = Jogador.objects.annotate(
        num_torneios=Count('inscricoes', distinct=True),
        num_vitorias=Count('inscricoes__vitorias', filter=~Q(inscricoes__vitorias__placar='BYE'), distinct=True),
    )
    if q:
        jogadores = jogadores.filter(nome__icontains=q)
    return render(request, 'torneios/jogador_lista.html', {'jogadores': jogadores, 'q': q})


def jogador_form(request, pk=None):
    jogador = get_object_or_404(Jogador, pk=pk) if pk else None
    form = JogadorForm(request.POST or None, request.FILES or None, instance=jogador)
    if request.method == 'POST' and form.is_valid():
        jogador = form.save()
        messages.success(request, 'Jogador salvo.')
        return redirect(jogador)
    return render(request, 'torneios/form.html', {
        'form': form, 'titulo': 'Editar jogador' if pk else 'Novo jogador', 'voltar': jogador,
    })


@require_POST
def jogador_excluir(request, pk):
    jogador = get_object_or_404(Jogador, pk=pk)
    if Partida.objects.filter(Q(inscricao_1__jogador=jogador) | Q(inscricao_2__jogador=jogador)).exists():
        messages.error(request, 'Este jogador já disputou partidas e não pode ser excluído.')
        return redirect(jogador)
    jogador.delete()
    messages.success(request, f'Jogador "{jogador.nome}" excluído.')
    return redirect('jogador_lista')


def jogador_detalhe(request, pk):
    jogador = get_object_or_404(Jogador, pk=pk)
    inscricoes = jogador.inscricoes.select_related('torneio')
    partidas = (
        Partida.objects.filter(Q(inscricao_1__jogador=jogador) | Q(inscricao_2__jogador=jogador))
        .exclude(placar='BYE')
        .select_related('torneio', 'inscricao_1__jogador', 'inscricao_2__jogador', 'vencedor')
        .order_by('-torneio__data_torneio', 'torneio', '-id')
    )
    vitorias = sum(1 for p in partidas if p.vencedor and p.vencedor.jogador_id == jogador.pk)
    derrotas = sum(1 for p in partidas if p.vencedor and p.vencedor.jogador_id != jogador.pk)
    return render(request, 'torneios/jogador_detalhe.html', {
        'jogador': jogador, 'inscricoes': inscricoes, 'partidas': partidas,
        'vitorias': vitorias, 'derrotas': derrotas,
    })
