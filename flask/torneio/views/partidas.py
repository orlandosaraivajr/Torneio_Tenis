from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import services
from ..extensions import db
from ..forms import ResultadoForm
from ..models import Partida
from .torneios import ABAS

bp = Blueprint('partidas', __name__)


@bp.route('/partidas/<int:partida_id>/', methods=['GET', 'POST'])
def resultado(partida_id):
    partida = db.session.get(Partida, partida_id) or abort(404)
    voltar = request.values.get('voltar') or 'chave'
    if voltar not in ABAS:
        voltar = 'chave'
    destino = url_for('torneios.detalhe', torneio_id=partida.torneio_id, aba=voltar)
    if not partida.editavel:
        flash('Esta partida não pode mais ser alterada (a fase seguinte já foi disputada).', 'error')
        return redirect(destino)

    form = ResultadoForm(partida)
    if form.validate_on_submit():
        services.registrar_resultado(partida, form.status.data, form.placar.data, form.vencedor_obj, form.data_hora.data)
        flash('Partida atualizada.', 'success')
        return redirect(destino)
    return render_template('partida_form.html', partida=partida, form=form, voltar=voltar, destino=destino)
