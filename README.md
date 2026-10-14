# Torneio de Tênis

MVP web para cadastro e gestão de torneios de tênis, implementado duas vezes com as mesmas funcionalidades:

| Pasta | Stack | Interface |
|---|---|---|
| [`django/`](django/) | Django 6.1 + SQLite | Inspirada no Google (Material Design) |
| [`flask/`](flask/) | Flask 3.1 + SQLAlchemy 2.1 + SQLite | Inspirada em sites de placar esportivo |

## Funcionalidades (comuns às duas versões)

- Cadastro de **torneios** (nome, descrição, data, local, formato, status, premiação, regulamento em texto ou arquivo, organizador).
- Cadastro de **jogadores** (nome e foto opcional).
- **Inscrições** de jogadores em torneios, com cabeça de chave opcional.
- Três formatos de disputa:
  - **Eliminatória simples** (2 a 32 jogadores, com BYE automático para os cabeças de chave);
  - **Round-robin** (todos contra todos, organizado em rodadas);
  - **Grupos + mata-mata** (grupos de ~4 jogadores; os 2 primeiros de cada grupo avançam).
- Registro de resultados (placar no formato `6-4 3-6 7-6(5)`, W.O., abandono), com cálculo do vencedor pelo placar e **avanço automático** para a próxima partida.
- Visualização da **chave**, das partidas e da **classificação** (critérios: vitórias, saldo de sets, saldo de games).
- Busca de torneios, clubes e jogadores.
- Painel administrativo em `/admin`.
- Sem login/senha nas telas principais (MVP).

---

## Como rodar a versão Django

Pré-requisito: Python 3.12 ou superior (exigência do Django 6.1).

```powershell
cd django
python -m venv .venv
.\.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate            # cria o banco db.sqlite3
python manage.py popular_demo       # opcional: cria 3 torneios de exemplo
python manage.py runserver
```

Acesse **http://127.0.0.1:8000**.

O painel `/admin` do Django exige um usuário administrador:

```powershell
python manage.py createsuperuser
```

### Testes (Django)

```powershell
python manage.py test torneios
```

Cobertura (requer `pip install coverage`):

```powershell
python -m coverage run --source=torneios manage.py test torneios
python -m coverage report -m --omit="torneios/tests/*,torneios/migrations/*"
```

---

## Como rodar a versão Flask

Pré-requisito: Python 3.11 ou superior (exigência do SQLAlchemy 2.1).

```powershell
cd flask
python -m venv .venv
.\.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
flask --app app db upgrade          # cria o banco em instance/torneio.db
flask --app app popular-demo        # opcional: cria 3 torneios de exemplo
flask --app app run
```

Acesse **http://127.0.0.1:5000**. Opções úteis: `--debug` (recarrega ao editar o código) e `--port 8000`.

Cadastro de organizadores (selecionáveis no formulário de torneio):

```powershell
flask --app app criar-organizador "Nome do organizador"
```

O painel `/admin` (Flask-Admin) está aberto, sem autenticação.

### Testes (Flask)

```powershell
pytest
pytest --cov=torneio --cov-report=term-missing
```

### Problemas comuns no Windows

- **"a execução de scripts foi desabilitada neste sistema"** ao ativar o ambiente virtual: execute `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, ou chame o Python do ambiente diretamente (ex.: `.\.venv\Scripts\python -m flask --app app run`).
- **"No module named ..."**: o terminal está usando um Python diferente daquele em que o `requirements.txt` foi instalado.

---

## Estrutura do código

| Responsabilidade | Django | Flask |
|---|---|---|
| Modelos | `torneios/models.py` | `torneio/models.py` |
| Regras do campeonato | `torneios/services.py` | `torneio/services.py` |
| Formulários | `torneios/forms.py` | `torneio/forms.py` |
| Rotas / views | `torneios/urls.py` + `torneios/views.py` | `torneio/views/*.py` (Blueprints) |
| Admin | `torneios/admin.py` | `torneio/admin.py` |
| Comandos de terminal | `torneios/management/commands/` | `torneio/cli.py` |
| Migrations | `torneios/migrations/` | `migrations/` (Alembic) |
| Testes | `torneios/tests/{models,forms,views,services}/` | `tests/{models,forms,views,services}/` |

---

## Comparativo

### Números deste projeto

Linhas não vazias, incluindo comentários. Medido nesta versão do repositório.

| Métrica | Django | Flask |
|---|---|---|
| Código Python da aplicação (sem testes e migrations) | 942 | 1.092 |
| Código Python de testes | 1.407 | 1.466 |
| Templates HTML | 581 (15 arquivos) | 633 (10 arquivos) |
| CSS | 259 | 238 |
| Quantidade de testes | 285 | 313 |
| Cobertura de testes do código da aplicação | 100% | 100% |
| Dependências diretas de execução no `requirements.txt` | 2 (Django, Pillow) | 6 (Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-WTF, Flask-Admin, Pillow) |
| Arquivos de migration | 2 | 1 |

### Como cada recurso foi obtido

| Recurso | Django | Flask |
|---|---|---|
| Rotas e views | Incluído no framework | Incluído no framework (Blueprints) |
| Templates | Django Template Language (incluído) | Jinja2 (incluído) |
| ORM | Django ORM (incluído) | SQLAlchemy, via extensão Flask-SQLAlchemy |
| Migrations | Incluído (`makemigrations` / `migrate`) | Alembic, via extensão Flask-Migrate |
| Formulários e validação | Django Forms (incluído) | WTForms, via extensão Flask-WTF |
| Proteção CSRF | Middleware incluído | Flask-WTF (`CSRFProtect`) |
| Painel administrativo | Django Admin (incluído, exige login) | Extensão Flask-Admin (sem autenticação nesta implementação) |
| Modelo de usuário (organizador) | `User` do `django.contrib.auth` (incluído) | Tabela `Usuario` criada no projeto |
| Lista de opções em campos (choices) | `TextChoices` (incluído) | Classe `Choices` escrita no projeto |
| Upload de arquivos | `FileField` / `ImageField` gravam no `MEDIA_ROOT` | Gravação manual com `secure_filename` em `instance/uploads` |
| Integridade referencial no SQLite | Ativada pelo framework | Exigiu ativar `PRAGMA foreign_keys=ON` manualmente |
| Comandos de terminal | `management/commands` | `app.cli` (Click) |
| Contexto do template nos testes | `response.context` (incluído) | Fixture com o sinal `template_rendered` escrita no projeto |
| Executor de testes | `unittest` via `manage.py test` (incluído) | pytest (dependência adicional) |

### Django — prós e contras

**Prós**

- ORM, migrations, formulários, autenticação, admin, proteção CSRF e internacionalização vêm no próprio framework, com uma única dependência a manter.
- O Django Admin gera telas de CRUD a partir dos models, com controle de acesso por usuário.
- Estrutura de projeto padronizada (`startproject` / `startapp`), igual entre projetos Django.
- O test client expõe o contexto e os templates usados (`response.context`, `assertTemplateUsed`).
- Versões LTS (as versões `x.2`) com suporte estendido de segurança.

**Contras**

- O pacote instalado contém todos os componentes do framework, inclusive os que o projeto não usa.
- O ORM e os formulários são específicos do Django e não são usados fora dele.
- A estrutura padronizada define onde ficam models, views, templates e configurações.
- O Django Admin exige autenticação; nesta implementação, é preciso criar um superusuário para acessá-lo.

### Flask — prós e contras

**Prós**

- O núcleo cobre roteamento, requisição/resposta e templates; os demais componentes são escolhidos e adicionados individualmente.
- O SQLAlchemy é uma biblioteca independente do Flask e pode ser usado em outros contextos (scripts, outros frameworks).
- A organização das pastas e módulos é definida pelo desenvolvedor (neste projeto: app factory e Blueprints).
- O pytest permite fixtures e testes parametrizados (`@pytest.mark.parametrize`).

**Contras**

- Recursos como admin, migrations, formulários e modelo de usuário dependem de extensões ou de código próprio. Neste projeto, isso representou 4 extensões adicionais e código para choices, uploads e integridade referencial no SQLite.
- Cada extensão tem versionamento e compatibilidade próprios. Ocorrências neste projeto:
  - Flask-Admin 2.2 marcou como obsoleta a forma de registrar views com `db.session` (passou a esperar `db`);
  - Flask-Admin precisou de `form_base_class = FlaskForm` para usar o mesmo CSRF do restante da aplicação;
  - no SQLAlchemy 2, um objeto associado por relacionamento não é adicionado automaticamente à sessão (exigiu `db.session.add` explícito).
- A estrutura varia entre projetos Flask, pois não há um layout padrão obrigatório.
- O Flask-Admin, nesta implementação, não possui autenticação.
