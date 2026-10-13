"""Regras do fluxo do campeonato: geração de chaves, avanço de vencedores e classificação."""
import random
import string

from django.db import transaction

from .models import Inscricao, Partida, Torneio, parse_placar

RODADAS_POR_TAMANHO = {
    2: ['F'],
    4: ['SF', 'F'],
    8: ['QF', 'SF', 'F'],
    16: ['R16', 'QF', 'SF', 'F'],
    32: ['R32', 'R16', 'QF', 'SF', 'F'],
}
MAX_JOGADORES_CHAVE = 32
JOGADORES_POR_GRUPO = 4


class FluxoError(Exception):
    """Erro de regra de negócio exibido ao usuário."""


def ordem_cabecas_de_chave(tamanho):
    """Posição das sementes na chave para que as melhores só se cruzem no fim.

    Para 8: [1, 8, 4, 5, 2, 7, 3, 6] -> jogos 1x8, 4x5, 2x7, 3x6.
    """
    ordem = [1, 2]
    while len(ordem) < tamanho:
        n = len(ordem) * 2
        ordem = [x for semente in ordem for x in (semente, n + 1 - semente)]
    return ordem


def ordenar_por_semente(inscricoes):
    """Cabeças de chave primeiro (em ordem); os demais são sorteados."""
    com_semente = sorted((i for i in inscricoes if i.cabeca_de_chave), key=lambda i: i.cabeca_de_chave)
    sem_semente = [i for i in inscricoes if not i.cabeca_de_chave]
    random.shuffle(sem_semente)
    return com_semente + sem_semente


def pares_todos_contra_todos(jogadores):
    """Método do círculo: devolve [(jornada, a, b), ...] sem repetir confrontos."""
    lista = list(jogadores)
    if len(lista) % 2:
        lista.append(None)
    n = len(lista)
    jogos = []
    for jornada in range(1, n):
        for i in range(n // 2):
            a, b = lista[i], lista[n - 1 - i]
            if a is not None and b is not None:
                jogos.append((jornada, a, b))
        lista = [lista[0], lista[-1], *lista[1:-1]]
    return jogos


def avancar_vencedor(partida):
    """Coloca o vencedor (ou limpa a vaga) na próxima partida e fecha o torneio se for o caso."""
    proxima = partida.proxima_partida
    if proxima:
        if partida.posicao % 2 == 0:
            proxima.inscricao_1 = partida.vencedor
        else:
            proxima.inscricao_2 = partida.vencedor
        proxima.save(update_fields=['inscricao_1', 'inscricao_2'])
    atualizar_status_torneio(partida.torneio)


def atualizar_status_torneio(torneio):
    partidas = torneio.partidas.all()
    if not partidas:
        return
    if torneio.formato == Torneio.Formato.GRUPOS and not partidas.filter(rodada=Partida.Rodada.F).exists():
        concluido = False  # ainda falta gerar o mata-mata
    else:
        concluido = all(p.encerrada for p in partidas)
    novo = Torneio.Status.FINALIZADO if concluido else Torneio.Status.EM_ANDAMENTO
    if torneio.status != novo and torneio.status != Torneio.Status.CANCELADO:
        torneio.status = novo
        torneio.save(update_fields=['status'])


def _criar_mata_mata(torneio, classificados):
    """Cria a chave eliminatória completa, já ligando cada partida à seguinte."""
    n = len(classificados)
    if n < 2:
        raise FluxoError('São necessários pelo menos 2 jogadores para montar a chave.')
    if n > MAX_JOGADORES_CHAVE:
        raise FluxoError(f'A chave suporta no máximo {MAX_JOGADORES_CHAVE} jogadores.')
    tamanho = 2
    while tamanho < n:
        tamanho *= 2
    rodadas = RODADAS_POR_TAMANHO[tamanho]

    # Cria da final para trás, para que cada partida já conheça a próxima.
    seguintes = []
    for i, rodada in enumerate(reversed(rodadas)):
        seguintes = [
            Partida.objects.create(
                torneio=torneio,
                rodada=rodada,
                posicao=pos,
                proxima_partida=seguintes[pos // 2] if seguintes else None,
            )
            for pos in range(2 ** i)
        ]

    vagas = [classificados[s - 1] if s <= n else None for s in ordem_cabecas_de_chave(tamanho)]
    for pos, partida in enumerate(seguintes):
        partida.inscricao_1, partida.inscricao_2 = vagas[2 * pos], vagas[2 * pos + 1]
        if partida.inscricao_1 is None or partida.inscricao_2 is None:
            # BYE: o jogador presente avança direto.
            partida.vencedor = partida.inscricao_1 or partida.inscricao_2
            partida.status = Partida.Status.FINALIZADA
            partida.placar = 'BYE'
        partida.save()
        if partida.vencedor:
            avancar_vencedor(partida)


def _criar_todos_contra_todos(torneio, inscricoes, rodada, grupo=''):
    for posicao, (jornada, a, b) in enumerate(pares_todos_contra_todos(inscricoes)):
        Partida.objects.create(
            torneio=torneio,
            rodada=rodada,
            grupo=grupo,
            jornada=jornada,
            posicao=posicao,
            inscricao_1=a,
            inscricao_2=b,
        )


@transaction.atomic
def gerar_chave(torneio):
    if torneio.partidas.exists():
        raise FluxoError('A chave deste torneio já foi gerada.')
    if torneio.status in (Torneio.Status.CANCELADO, Torneio.Status.FINALIZADO):
        raise FluxoError('Não é possível gerar a chave de um torneio cancelado ou finalizado.')

    inscricoes = ordenar_por_semente(list(torneio.inscricoes.select_related('jogador')))
    n = len(inscricoes)

    if torneio.formato == Torneio.Formato.ELIMINATORIA:
        _criar_mata_mata(torneio, inscricoes)

    elif torneio.formato == Torneio.Formato.ROUND_ROBIN:
        if n < 2:
            raise FluxoError('São necessários pelo menos 2 jogadores.')
        _criar_todos_contra_todos(torneio, inscricoes, Partida.Rodada.TODOS)

    else:  # grupos + mata-mata
        if n < 3:
            raise FluxoError('São necessários pelo menos 3 jogadores para a fase de grupos.')
        num_grupos = max(1, n // JOGADORES_POR_GRUPO)
        if num_grupos * 2 > MAX_JOGADORES_CHAVE:
            raise FluxoError('Jogadores demais para o formato de grupos.')
        letras = string.ascii_uppercase[:num_grupos]
        grupos = {letra: [] for letra in letras}
        # Distribuição em "serpentina" para equilibrar os cabeças de chave.
        for i, inscricao in enumerate(inscricoes):
            volta, resto = divmod(i, num_grupos)
            letra = letras[resto if volta % 2 == 0 else num_grupos - 1 - resto]
            inscricao.grupo = letra
            grupos[letra].append(inscricao)
        Inscricao.objects.bulk_update(inscricoes, ['grupo'])
        for letra, membros in grupos.items():
            _criar_todos_contra_todos(torneio, membros, Partida.Rodada.GRUPOS, grupo=letra)

    torneio.status = Torneio.Status.EM_ANDAMENTO
    torneio.save(update_fields=['status'])
    atualizar_status_torneio(torneio)


@transaction.atomic
def gerar_mata_mata_dos_grupos(torneio):
    partidas_grupo = torneio.partidas.filter(rodada=Partida.Rodada.GRUPOS)
    if not partidas_grupo.exists():
        raise FluxoError('Este torneio não tem fase de grupos.')
    if torneio.partidas.filter(rodada__in=Partida.MATA_MATA).exists():
        raise FluxoError('O mata-mata já foi gerado.')
    if any(not p.encerrada for p in partidas_grupo):
        raise FluxoError('Finalize todas as partidas da fase de grupos antes de gerar o mata-mata.')

    primeiros, segundos = [], []
    for _, tabela in classificacao_por_grupo(torneio):
        primeiros.append(tabela[0]['inscricao'])
        if len(tabela) > 1:
            segundos.append(tabela[1]['inscricao'])
    _criar_mata_mata(torneio, primeiros + segundos)
    atualizar_status_torneio(torneio)


@transaction.atomic
def refazer_chave(torneio):
    torneio.partidas.all().delete()
    torneio.inscricoes.update(grupo='')
    torneio.status = Torneio.Status.INSCRICOES
    torneio.save(update_fields=['status'])


@transaction.atomic
def registrar_resultado(partida, status, placar, vencedor, data_hora):
    partida.status = status
    partida.placar = placar
    partida.data_hora = data_hora
    partida.vencedor = vencedor if status in Partida.ENCERRADOS else None
    partida.save()
    avancar_vencedor(partida)


def vencedor_pelo_placar(partida, placar):
    """Devolve a inscrição que venceu mais sets, ou None se empatado/vazio."""
    sets_1 = sets_2 = 0
    for g1, g2, _ in parse_placar(placar):
        if g1 > g2:
            sets_1 += 1
        elif g2 > g1:
            sets_2 += 1
    if sets_1 > sets_2:
        return partida.inscricao_1
    if sets_2 > sets_1:
        return partida.inscricao_2
    return None


def classificacao(inscricoes, partidas):
    """Tabela de pontos: vitórias, depois saldo de sets, depois saldo de games."""
    tabela = {
        i.pk: {'inscricao': i, 'jogos': 0, 'vitorias': 0, 'derrotas': 0,
               'sets_pro': 0, 'sets_contra': 0, 'games_pro': 0, 'games_contra': 0}
        for i in inscricoes
    }
    for p in partidas:
        if not p.encerrada or p.inscricao_1_id not in tabela or p.inscricao_2_id not in tabela:
            continue
        a, b = tabela[p.inscricao_1_id], tabela[p.inscricao_2_id]
        a['jogos'] += 1
        b['jogos'] += 1
        if p.vencedor_id == p.inscricao_1_id:
            a['vitorias'] += 1
            b['derrotas'] += 1
        elif p.vencedor_id == p.inscricao_2_id:
            b['vitorias'] += 1
            a['derrotas'] += 1
        for g1, g2, _ in p.sets:
            a['games_pro'] += g1
            a['games_contra'] += g2
            b['games_pro'] += g2
            b['games_contra'] += g1
            if g1 > g2:
                a['sets_pro'] += 1
                b['sets_contra'] += 1
            elif g2 > g1:
                b['sets_pro'] += 1
                a['sets_contra'] += 1
    linhas = list(tabela.values())
    for linha in linhas:
        linha['saldo_sets'] = linha['sets_pro'] - linha['sets_contra']
        linha['saldo_games'] = linha['games_pro'] - linha['games_contra']
    linhas.sort(key=lambda l: (-l['vitorias'], -l['saldo_sets'], -l['saldo_games'], l['inscricao'].jogador.nome))
    return linhas


def classificacao_por_grupo(torneio):
    inscricoes = list(torneio.inscricoes.select_related('jogador'))
    partidas = list(torneio.partidas.filter(rodada=Partida.Rodada.GRUPOS))
    letras = sorted({i.grupo for i in inscricoes if i.grupo})
    return [
        (letra, classificacao([i for i in inscricoes if i.grupo == letra],
                              [p for p in partidas if p.grupo == letra]))
        for letra in letras
    ]


def chave_mata_mata(torneio):
    """Rodadas do mata-mata em ordem, com as partidas agrupadas em pares para desenhar a chave."""
    partidas = list(
        torneio.partidas.filter(rodada__in=Partida.MATA_MATA)
        .select_related('inscricao_1__jogador', 'inscricao_2__jogador', 'proxima_partida')
        .order_by('posicao')
    )
    rodadas = []
    for codigo in Partida.MATA_MATA:
        jogos = [p for p in partidas if p.rodada == codigo]
        if jogos:
            pares = [jogos[i:i + 2] for i in range(0, len(jogos), 2)]
            rodadas.append({'nome': Partida.Rodada(codigo).label, 'pares': pares})
    return rodadas


def campeao(torneio):
    if torneio.formato == Torneio.Formato.ROUND_ROBIN:
        partidas = list(torneio.partidas.all())
        if partidas and all(p.encerrada for p in partidas):
            return classificacao(torneio.inscricoes.select_related('jogador'), partidas)[0]['inscricao']
        return None
    final = torneio.partidas.filter(rodada=Partida.Rodada.F).select_related('vencedor__jogador').first()
    return final.vencedor if final else None
