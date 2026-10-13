from itertools import groupby

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from ..extensions import db
from ..forms import JogadorForm
from ..models import Jogador, Partida
from ..uploads import salvar_upload

bp = Blueprint('jogadores', __name__)


def _obter(jogador_id):
    return db.session.get(Jogador, jogador_id) or abort(404)


def _partidas_do_jogador(jogador):
    ids = [i.id for i in jogador.inscricoes]
    if not ids:
        return []
    return Partida.query.filter(
        or_(Partida.inscricao_1_id.in_(ids), Partida.inscricao_2_id.in_(ids)), Partida.placar != 'BYE'
    ).all()


@bp.route('/jogadores/')
def lista():
    q = request.args.get('q', '').strip()
    consulta = Jogador.query.order_by(Jogador.nome)
    if q:
        consulta = consulta.filter(Jogador.nome.ilike(f'%{q}%'))
    linhas = []
    for jogador in consulta.all():
        ids = {i.id for i in jogador.inscricoes}
        vitorias = Partida.query.filter(Partida.vencedor_id.in_(ids), Partida.placar != 'BYE').count() if ids else 0
        linhas.append({'jogador': jogador, 'torneios': len(ids), 'vitorias': vitorias})
    return render_template('jogadores/lista.html', linhas=linhas, q=q)


@bp.route('/jogadores/novo', methods=['GET', 'POST'])
@bp.route('/jogadores/<int:jogador_id>/editar', methods=['GET', 'POST'])
def formulario(jogador_id=None):
    jogador = _obter(jogador_id) if jogador_id else None
    form = JogadorForm(obj=jogador)
    if form.validate_on_submit():
        if jogador is None:
            jogador = Jogador()
            db.session.add(jogador)
        jogador.nome = form.nome.data
        foto = salvar_upload(form.foto.data, 'jogadores')
        if foto:
            jogador.foto = foto
        db.session.commit()
        flash('Jogador salvo.', 'success')
        return redirect(jogador.url)
    return render_template('form.html', form=form, titulo='Editar jogador' if jogador else 'Novo jogador',
                           voltar=jogador.url if jogador else url_for('jogadores.lista'))


@bp.post('/jogadores/<int:jogador_id>/excluir')
def excluir(jogador_id):
    jogador = _obter(jogador_id)
    ids = [i.id for i in jogador.inscricoes]
    if ids and Partida.query.filter(or_(Partida.inscricao_1_id.in_(ids), Partida.inscricao_2_id.in_(ids))).first():
        flash('Este jogador já disputou partidas e não pode ser excluído.', 'error')
        return redirect(jogador.url)
    db.session.delete(jogador)
    db.session.commit()
    flash(f'Jogador "{jogador.nome}" excluído.', 'success')
    return redirect(url_for('jogadores.lista'))


@bp.route('/jogadores/<int:jogador_id>/')
def detalhe(jogador_id):
    jogador = _obter(jogador_id)
    inscricoes = sorted(jogador.inscricoes, key=lambda i: i.torneio.data_torneio, reverse=True)
    partidas = sorted(_partidas_do_jogador(jogador),
                      key=lambda p: (-p.torneio.data_torneio.toordinal(), p.torneio_id, -p.id))
    vitorias = sum(1 for p in partidas if p.vencedor and p.vencedor.jogador_id == jogador.id)
    derrotas = sum(1 for p in partidas if p.vencedor and p.vencedor.jogador_id != jogador.id)
    blocos = [(torneio, list(jogos)) for torneio, jogos in groupby(partidas, key=lambda p: p.torneio)]
    return render_template('jogadores/detalhe.html', jogador=jogador, inscricoes=inscricoes, partidas=partidas,
                           blocos=blocos, vitorias=vitorias, derrotas=derrotas)
