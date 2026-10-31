# AGENTS.md: Relatórios Diários de Gateways

Gera, por gateway e dia (D-1), um JSON por conta em USD a partir de três fontes (painel Web, API e lake canônico), compara API e lake com o Web e mostra tudo num painel HTML. Gateways: **BuyGoods** e **PagAmerican**.

## Comece por

- `README.md`: visão rápida e medições de aderência.
- `docs/guia.md`: guia operacional completo (configuração, corte do dia, fórmulas, reexecução, painel, manutenção).
- `PRODUCT.md`: usuários, uso e regras do produto. `DESIGN.md`: sistema visual do projeto.

## Comandos

Tudo pela raiz, via `make` (Python roda com `uvx --with ... -- python`; nunca `pip install` no projeto).

| Comando                                                     | Faz                                                      |
| ----------------------------------------------------------- | -------------------------------------------------------- |
| `make buygoods` / `buygoods-api` / `buygoods-lake`          | JSON BuyGoods de D (Web também salva a planilha)         |
| `make pagamerican` / `pagamerican-api` / `pagamerican-lake` | JSON PagAmerican de D                                    |
| `make diff GATEWAY=buygoods\|pagamerican`                   | Compara API/Lake com Web (`diff_ai`, `diff_dashboard`)   |
| `make painel`                                               | Gera `mockups/painel.data.js` para `mockups/painel.html` |
| `make test` / `make lint`                                   | Testes `unittest` / ruff + prettier                      |

`DATE=AAAA-MM-DD` escolhe o dia; sem ele, o padrão é o último dia completo **no relógio do gateway** (BuyGoods GMT-4, PagAmerican UTC). `DEBUG=1`, `OUTPUT_ROOT=`, `HEADED=1` (só `pagamerican`) e `BUYGOODS_DATE=` / `PAGAMERICAN_DATE=` (só `painel`) estão no guia.

## Regras

- **Segredos:** `.env` e `credentials/` nunca são abertos em resposta, impressos, documentados com valor ou versionados. Use só os nomes das variáveis.
- **Dados:** `exports/` e as planilhas trazem dados de clientes e ficam fora do Git, assim como `mockups/painel.data.js`. Não cole valores por conta fora do projeto sem pedido.
- **AWS:** lake só com o profile somente leitura `canonico-validador-user`, região `us-east-1`, workgroup `primary`, database `gex_db_prod_silver`. Sem DDL/DML, sem trocar de profile.
- **Saídas não são sobrescritas:** um JSON ou planilha existente faz o comando terminar sem recalcular. Para refazer um dia, siga "Reexecução" no guia (copiar antes, retirar só o arquivo do dia).
- **Web é a base** de toda comparação; tolerância US$ 0,01. Diferenças conhecidas (virada do dia da PagAmerican no lake, commission voids aproximados no lake BuyGoods, refunds sem a taxa de US$ 1 na API) não são defeitos.
- **Contrato:** `schemas/daily_report.schema.json` vale para as seis combinações gateway × fonte; a fórmula do painel mora em `src/common/report.py`. Mudou o contrato? Ajuste schema, transformações, `diff_fontes.py`, `dados_painel.py`, o painel, testes e guia juntos.
- **Painel e visuais:** seguem o design system GEX (skill `gex-design-system`) e o `DESIGN.md`. O layout do painel saiu da skill `impeccable`; o contrato de direção fica em `.impeccable/surfaces/`.
- **Testes:** escreva o teste antes da mudança não trivial; `make test` e `make lint` antes de declarar pronto. Testes de seletor Playwright usam o Chrome local e não exportam nada.
- **Commits:** Conventional Commits (commitlint barra o resto), um tema por commit; os hooks rodam ruff e prettier nos arquivos do commit. Push só quando pedido.

## Mapa

- `src/scripts/extracao_diaria_<gateway>_<fonte>.py`: extrações. `src/scripts/diff_fontes.py`: diff. `src/scripts/dados_painel.py`: dados do painel.
- `src/common/report.py`: fórmula, schema, escrita atômica, data padrão. `src/common/athena.py`: cliente Athena.
- `src/transformations/`: leitura das planilhas Web. `schemas/`: contratos JSON. `tests/`: regressões.
- `mockups/painel.html`: painel. `docs/`: guia, SVGs animados e a hero (`docs/hero/`, HyperFrames).
