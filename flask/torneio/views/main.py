from itertools import groupby

from flask import Blueprint, current_app, render_template, request, send_from_directory
from sqlalchemy import or_

from ..models import Jogador, Partida, Rodada, StatusPartida, StatusTorneio, Torneio

bp = Blueprint('main', __name__)

ORDEM_RODADA = {Rodada.TODOS: 0, Rodada.GRUPOS: 0, Rodada.R32: 1, Rodada.R16: 2, Rodada.QF: 3, Rodada.SF: 4, Rodada.F: 5}
FILTROS = {
    'todos': ('Todos', None),
    'ao-vivo': ('Ao vivo', [StatusPartida.EM_ANDAMENTO]),
    'agendados': ('Agendados', [StatusPartida.AGENDADA]),
    'encerrados': ('Encerrados', list(StatusPartida.ENCERRADOS)),
}


@bp.route('/')
def home():
    q = request.args.get('q', '').strip()
    if q:
        return busca(q)

    filtro = request.args.get('filtro', 'todos')
    if filtro not in FILTROS:
        filtro = 'todos'
    consulta = (
        Partida.query.join(Torneio)
        .filter(Torneio.status != StatusTorneio.CANCELADO, Partida.placar != 'BYE',
                Partida.inscricao_1_id.is_not(None), Partida.inscricao_2_id.is_not(None))
    )
    status = FILTROS[filtro][1]
    if status:
        consulta = consulta.filter(Partida.status.in_(status))
    partidas = sorted(consulta.all(), key=lambda p: (
        -p.torneio.data_torneio.toordinal(), p.torneio_id, ORDEM_RODADA[p.rodada], p.grupo, p.jornada or 0, p.posicao,
    ))
    blocos = [(torneio, list(jogos)) for torneio, jogos in groupby(partidas, key=lambda p: p.torneio)]
    ao_vivo = Partida.query.filter_by(status=StatusPartida.EM_ANDAMENTO).count()
    return render_template('home.html', blocos=blocos, filtro=filtro, filtros=FILTROS, ao_vivo=ao_vivo)


def busca(q):
    termo = f'%{q}%'
    torneios = Torneio.query.filter(
        or_(Torneio.nome.ilike(termo), Torneio.local.ilike(termo), Torneio.descricao.ilike(termo))
    ).order_by(Torneio.data_torneio.desc()).all()
    jogadores = Jogador.query.filter(Jogador.nome.ilike(termo)).order_by(Jogador.nome).all()
    return render_template('busca.html', q=q, torneios=torneios, jogadores=jogadores,
                           total=len(torneios) + len(jogadores))


@bp.route('/uploads/<path:caminho>')
def upload(caminho):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], caminho)
