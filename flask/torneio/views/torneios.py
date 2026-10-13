from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import services
from ..extensions import db
from ..forms import InscricaoForm, TorneioForm
from ..models import Formato, Inscricao, Partida, Rodada, StatusTorneio, Torneio
from ..uploads import salvar_upload

bp = Blueprint('torneios', __name__)

ABAS = ['resumo', 'inscritos', 'chave', 'partidas', 'classificacao']


def _obter(torneio_id):
    torneio = db.session.get(Torneio, torneio_id)
    if torneio is None:
        abort(404)
    return torneio


def _url_aba(torneio, aba):
    return url_for('torneios.detalhe', torneio_id=torneio.id, aba=aba)


@bp.route('/torneios/')
def lista():
    consulta = Torneio.query.order_by(Torneio.data_torneio.desc(), Torneio.nome)
    status = request.args.get('status')
    if status:
        consulta = consulta.filter_by(status=status)
    return render_template('torneios/lista.html', torneios=consulta.all(), status_atual=status,
                           status_choices=StatusTorneio.choices())


@bp.route('/torneios/novo', methods=['GET', 'POST'])
@bp.route('/torneios/<int:torneio_id>/editar', methods=['GET', 'POST'])
def formulario(torneio_id=None):
    torneio = _obter(torneio_id) if torneio_id else None
    form = TorneioForm(torneio=torneio)
    if form.validate_on_submit():
        if torneio is None:
            torneio = Torneio()
            db.session.add(torneio)
        form.preencher(torneio)
        arquivo = salvar_upload(form.regulamento_arquivo.data, 'regulamentos')
        if arquivo:
            torneio.regulamento_arquivo = arquivo
        db.session.commit()
        flash('Torneio salvo.', 'success')
        return redirect(torneio.url)
    return render_template('form.html', form=form, titulo='Editar torneio' if torneio else 'Novo torneio',
                           voltar=torneio.url if torneio else url_for('torneios.lista'))


@bp.post('/torneios/<int:torneio_id>/excluir')
def excluir(torneio_id):
    torneio = _obter(torneio_id)
    db.session.delete(torneio)
    db.session.commit()
    flash(f'Torneio "{torneio.nome}" excluído.', 'success')
    return redirect(url_for('torneios.lista'))


@bp.route('/torneios/<int:torneio_id>/')
def detalhe(torneio_id):
    torneio = _obter(torneio_id)
    aba = request.args.get('aba', 'resumo')
    if aba not in ABAS:
        aba = 'resumo'

    inscricoes = torneio.inscritos
    partidas = Partida.query.filter_by(torneio_id=torneio.id).order_by(
        Partida.grupo, Partida.jornada, Partida.posicao).all()
    tem_mata_mata = any(p.rodada in Rodada.MATA_MATA for p in partidas)
    grupos_concluidos = (
        torneio.formato == Formato.GRUPOS and bool(partidas) and not tem_mata_mata and all(p.encerrada for p in partidas)
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
        'inscricao_form': InscricaoForm(torneio, formdata=None) if torneio.aceita_inscricoes else None,
        'chave': services.chave_mata_mata(torneio) if tem_mata_mata else [],
        'tabela_geral': None,
        'grupos': [],
    }
    if torneio.formato == Formato.ROUND_ROBIN and partidas:
        contexto['tabela_geral'] = services.classificacao(inscricoes, partidas)
    if torneio.formato == Formato.GRUPOS and partidas:
        contexto['grupos'] = [
            {
                'letra': letra,
                'tabela': tabela,
                'jogos': [p for p in partidas if p.rodada == Rodada.GRUPOS and p.grupo == letra],
            }
            for letra, tabela in services.classificacao_por_grupo(torneio)
        ]
    return render_template('torneios/detalhe.html', **contexto)


@bp.post('/torneios/<int:torneio_id>/inscrever')
def inscrever(torneio_id):
    torneio = _obter(torneio_id)
    if not torneio.aceita_inscricoes:
        flash('Este torneio não aceita mais inscrições.', 'error')
        return redirect(_url_aba(torneio, 'inscritos'))
    form = InscricaoForm(torneio)
    if form.validate():
        inscricao = form.criar_inscricao()
        db.session.commit()
        flash(f'{inscricao.jogador.nome} inscrito(a).', 'success')
    else:
        for erros in form.errors.values():  # inclui os erros gerais (chave None)
            for erro in erros:
                flash(erro, 'error')
    return redirect(_url_aba(torneio, 'inscritos'))


@bp.post('/inscricoes/<int:inscricao_id>/remover')
def remover_inscricao(inscricao_id):
    inscricao = db.session.get(Inscricao, inscricao_id) or abort(404)
    torneio = inscricao.torneio
    if not torneio.aceita_inscricoes:
        flash('Não é possível remover inscritos depois de gerada a chave.', 'error')
    else:
        nome = inscricao.jogador.nome
        db.session.delete(inscricao)
        db.session.commit()
        flash(f'{nome} removido(a) do torneio.', 'success')
    return redirect(_url_aba(torneio, 'inscritos'))


def _executar(torneio, acao, sucesso, aba='chave'):
    try:
        acao(torneio)
        flash(sucesso, 'success')
    except services.FluxoError as erro:
        flash(str(erro), 'error')
    return redirect(_url_aba(torneio, aba))


@bp.post('/torneios/<int:torneio_id>/gerar-chave')
def gerar_chave(torneio_id):
    return _executar(_obter(torneio_id), services.gerar_chave, 'Chave gerada! Bons jogos.')


@bp.post('/torneios/<int:torneio_id>/gerar-mata-mata')
def gerar_mata_mata(torneio_id):
    return _executar(_obter(torneio_id), services.gerar_mata_mata_dos_grupos, 'Mata-mata gerado com os classificados.')


@bp.post('/torneios/<int:torneio_id>/refazer-chave')
def refazer_chave(torneio_id):
    return _executar(_obter(torneio_id), services.refazer_chave,
                     'Chave apagada. Ajuste os inscritos e gere novamente.', aba='inscritos')
