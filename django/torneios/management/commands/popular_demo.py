import datetime
import random

from django.core.management.base import BaseCommand

from torneios import services
from torneios.models import Inscricao, Jogador, Partida, Torneio

NOMES = [
    'Gustavo Kuerten', 'Fernando Meligeni', 'Thomaz Bellucci', 'João Fonseca', 'Bia Haddad Maia',
    'Marcelo Melo', 'Bruno Soares', 'Thiago Monteiro', 'Luisa Stefani', 'Rafael Matos',
    'Felipe Meligeni', 'Thiago Wild', 'Laura Pigossi', 'Carolina Alves', 'Orlando Silva', 'Ana Souza',
]


class Command(BaseCommand):
    help = 'Cria torneios de exemplo (eliminatória em andamento e grupos + mata-mata).'

    def handle(self, *args, **options):
        random.seed(42)
        jogadores = [Jogador.objects.get_or_create(nome=nome)[0] for nome in NOMES]

        elim = self._torneio('Open de Primavera', Torneio.Formato.ELIMINATORIA, jogadores[:13])
        services.gerar_chave(elim)
        self._jogar(elim, ['R16'])
        self._jogar(elim, ['QF'], limite=2)

        grupos = self._torneio('Copa dos Clubes', Torneio.Formato.GRUPOS, jogadores[:8])
        services.gerar_chave(grupos)
        self._jogar(grupos, ['GR'])
        services.gerar_mata_mata_dos_grupos(grupos)

        rr = self._torneio('Desafio Round-robin', Torneio.Formato.ROUND_ROBIN, jogadores[8:13])
        services.gerar_chave(rr)
        self._jogar(rr, ['RR'], limite=6)

        self.stdout.write(self.style.SUCCESS('Dados de demonstração criados.'))

    def _torneio(self, nome, formato, jogadores):
        torneio = Torneio.objects.create(
            nome=nome, formato=formato, status=Torneio.Status.INSCRICOES,
            data_torneio=datetime.date.today() + datetime.timedelta(days=random.randint(1, 60)),
            local='Clube de Tênis Central', premiacao='Troféu + R$ 1.000 ao campeão',
            descricao=f'Torneio de demonstração no formato {Torneio.Formato(formato).label.lower()}.',
            regulamento='Partidas em melhor de 3 sets com super tiebreak no terceiro.',
        )
        for i, jogador in enumerate(jogadores):
            Inscricao.objects.create(torneio=torneio, jogador=jogador, cabeca_de_chave=i + 1 if i < 4 else None)
        return torneio

    def _jogar(self, torneio, rodadas, limite=None):
        pendentes = torneio.partidas.filter(rodada__in=rodadas, status=Partida.Status.AGENDADA).order_by('posicao')
        for partida in list(pendentes)[:limite]:
            partida.refresh_from_db()
            placar = random.choice(['6-4 6-3', '7-6(4) 6-2', '4-6 6-3 10-7', '3-6 4-6', '6-7(5) 6-4 8-10', '2-6 6-7(3)'])
            vencedor = services.vencedor_pelo_placar(partida, placar)
            services.registrar_resultado(partida, Partida.Status.FINALIZADA, placar, vencedor, None)
