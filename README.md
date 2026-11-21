# Ocorrências

Sistema web para registrar e acompanhar ocorrências de devolução na operação logística. Cada pessoa vê as notas das equipes em que participa. Só edita o que lançou; o status a equipe atualiza junto.

Pensado para uso interno da empresa e, mais adiante, para integrar com o ERP pela busca da nota fiscal pelo número.

## O que o sistema faz

- Lançamento e edição de ocorrência (cliente, peso, valor, placa, tipo de devolução, setor, motivo, descrição)
- Busca da nota pelo número (cadastro local hoje; banco da empresa quando configurado)
- Importação opcional do XML da NF-e ou CT-e para preencher a nota e os produtos
- Devolução total ou parcial, com os produtos da nota
- Anexos (fotos e PDF)
- Status configuráveis, com cor, e status que encerra a ocorrência
- Complemento sem alterar o lançamento original (reabre se estiver encerrada)
- Painel filtrado pela última movimentação; relatórios pela data de origem
- Relatórios: lista, por setor, por placa e por motivo (peso e valor dos produtos devolvidos)
- Impressão da tabela e da ficha individual sem sair do relatório
- Auditoria para quem gerencia a equipe
- API REST com autenticação por token e documentação Swagger

## Stack

- Python 3.12+
- Django 6.1
- Django REST Framework
- drf-spectacular (OpenAPI / Swagger)
- python-dotenv (lê o arquivo `.env`)
- SQLite no desenvolvimento (`db.sqlite3`)

## Como rodar localmente

No Windows (PowerShell), na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Cole o resultado em DJANGO_SECRET_KEY no arquivo .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Cole o resultado em DJANGO_SECRET_KEY no arquivo .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

## Segredos (`.env`)

Nenhuma chave secreta fica no código. O Django carrega `DJANGO_SECRET_KEY` e o restante das variáveis do arquivo **`.env`** na raiz. Sem essa chave, o sistema não sobe.

| Arquivo | Vai para o Git? | Conteúdo |
| --- | --- | --- |
| `.env` | Não (está no `.gitignore`) | Chaves desta máquina |
| `.env.example` | Sim | Modelo vazio, para quem clonar o repositório |

Depois de copiar o example, gere uma chave e cole em `DJANGO_SECRET_KEY`. Se a chave tiver `#`, `@` ou espaços, coloque entre aspas simples. Cada instalação (seu PC, servidor, outro desenvolvedor) deve ter a **própria** chave — não reutilize a de desenvolvimento em produção.

Abra:

| Endereço | Uso |
| --- | --- |
| http://127.0.0.1:8000/ | Painel |
| http://127.0.0.1:8000/admin/ | Administração |
| http://127.0.0.1:8000/api/docs/ | Swagger da API |

## Primeiro uso

No admin, nesta ordem:

1. Crie **equipes** e vincule usuários (ou marque **acesso total** no usuário).
2. Confira **status** (um deles deve ser o inicial; o que encerra tira a nota do painel de abertas).
3. Confira **motivos** e **setores responsáveis** (ambos são cadastráveis).
4. Entre no painel com um usuário que participe de uma equipe e lance a primeira ocorrência.

Regras de acesso:

- Sem equipe e sem acesso total, a pessoa não lança nem vê ocorrências.
- **Acesso total** vê todas as equipes.
- Quem lançou edita os dados da ocorrência. Quem está na equipe pode mudar o status e complementar.
- Só quem tem permissão de exclusão (acesso total) apaga o registro; a auditoria guarda o que havia.

## API

Autenticação: `POST /api/auth/token/` com usuário e senha. Envie o token no cabeçalho `Authorization: Token <chave>`.

Principais rotas:

- `GET /api/notas/{numero}/` — busca a nota (origem configurável)
- `POST /api/notas/xml/` — importa XML (opcional)
- `GET /api/notas/{numero}/abertas/` — ocorrências em aberto daquela NF
- `GET/POST /api/ocorrencias/`
- `GET/PUT/DELETE /api/ocorrencias/{id}/`
- `POST /api/ocorrencias/{id}/status/`
- `GET /api/status/`, `/api/motivos/`, `/api/setores/`, `/api/equipes/`
- `GET /api/schema/` e `GET /api/docs/`

O token também pode ser gerado ou visto no admin, no cadastro do usuário.

## Origem das notas

A busca no lançamento pede **só o número da NF**. A origem é definida por `NOTAS_ORIGEM`:

| Valor | Comportamento |
| --- | --- |
| `local` | Cadastro deste sistema (digitado ou XML). Padrão. |
| `externa` | Só o banco da empresa |
| `auto` | Tenta o banco da empresa; se não achar, usa o cadastro local |

Para ligar o banco da empresa, preencha `NOTAS_DB_*`, `NOTAS_SQL` e, se quiser os itens, `NOTAS_ITENS_SQL`. A consulta da nota deve devolver as colunas `numero`, `cliente`, `peso`, `valor` e `placa`. A dos itens: `codigo`, `descricao`, `quantidade`, `unidade`, `peso`, `valor`. Veja o modelo em `.env.example`.

O XML da NF-e/CT-e é um atalho enquanto não há integração. Ele grava a nota no cadastro local.

## Relatórios

As datas do **painel** usam a última movimentação (status, complemento, reabertura). As datas dos **relatórios** usam a data de lançamento original.

Peso e valor nos relatórios são dos **produtos devolvidos**. Na devolução total entra a nota inteira; na parcial, o que voltou (com rateio quando o XML não traz peso por linha).

## Variáveis de ambiente

| Variável | Função |
| --- | --- |
| `DJANGO_DEBUG` | `true` no desenvolvimento |
| `DJANGO_SECRET_KEY` | Chave do Django; obrigatória, só no `.env` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por vírgula |
| `DJANGO_CORS_ORIGINS` | Origens CORS da API, se houver front separado |
| `NOTAS_ORIGEM` | `local`, `externa` ou `auto` |
| `NOTAS_DB_*` / `NOTAS_SQL` / `NOTAS_ITENS_SQL` | Banco e SQL da nota na empresa |

## Produção

- `DJANGO_DEBUG=false` e uma `DJANGO_SECRET_KEY` forte, só no `.env` do servidor.
- Troque o SQLite por PostgreSQL (ou o banco que a empresa usar) em `DATABASES`.
- Sirva `static/` e `media/` pelo servidor web; `media/` não vai para o Git.
- Não commite `.env`, `.venv` nem `db.sqlite3`.

## Estrutura

```
config/          # settings, URLs do projeto, WSGI/ASGI
painel/          # app: modelos, telas, API, XML, regras de negócio
manage.py
requirements.txt
.env.example     # modelo; copie para .env e preencha a SECRET_KEY
.env             # local, fora do Git
```

O código de negócio fica em `painel/services.py`. A leitura de XML está em `painel/nfe.py`. A origem da nota está em `painel/origens.py`.
