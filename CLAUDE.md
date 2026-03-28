# GELD — Contexto do Projeto

Sistema de gestão de carteiras de investimentos para assessores brasileiros.
Desenvolvido por Ulisses. Deploy em PythonAnywhere (`taddei.pythonanywhere.com`).

## Stack
- **Backend:** Flask 3.1 + SQLAlchemy 2.0 (SQLite)
- **Frontend:** Jinja2 + HTML/CSS/JS vanilla (sem framework)
- **Externos:** API CVM (cotas de fundos), API BCB (IPCA)
- **Deploy:** PythonAnywhere

## Estrutura
```
run.py                        # entry point — init_db() + app.run()
balancear_objetivo.py         # utilitário standalone para cálculos de balanceamento
app/
  app_config.py               # factory Flask, registra blueprints, rota raiz /
  config.py                   # caminhos e DB (env-aware: PythonAnywhere vs local)
  models/
    geld_models.py            # todos os modelos SQLAlchemy + init_db()
    matriz_data.py            # dados hardcoded das matrizes de risco
  routes/                     # 8 blueprints (controladores finos)
    auth.py                   # login/logout (credenciais hardcoded)
    dashboard.py              # visão geral + atualização de indicadores
    cliente.py                # CRUD de clientes
    objetivo.py               # CRUD de objetivos + troca de prioridade
    fundos.py                 # CRUD de fundos + importação CVM
    posicao.py                # CRUD de posições + uploads BTG/XP
    posicao_advisor.py        # upload de planilha Advisor
    balanco.py                # wizard de rebalanceamento (4 rotas)
  services/                   # lógica de negócio (sem imports Flask)
  templates/                  # Jinja2, organizado por blueprint
  static/                     # CSS, ícones, imagens
```

## Modelos
| Modelo | Descrição |
|--------|-----------|
| `Cliente` | Dados pessoais + banco (BTG/XP/NU) + `ultimo_balanceamento_json` |
| `Objetivo` | Meta financeira com prazo, valor alvo e prioridade |
| `DistribuicaoObjetivo` | Alocação alvo por classe de risco (9 classes) por objetivo |
| `InfoFundo` | Cadastro de fundos: `risco`, `subtipo_risco` (di/rfx), `is_previdencia`, cotação |
| `PosicaoFundo` | Cotas do cliente em cada fundo + `banco_custodia` + saldos |
| `MatrizRisco` | Tabela horizonte (meses) → alocação ideal por tipo de objetivo |
| `IndicadoresEconomicos` | IPCA anual e mensal, atualizado via BCB |

## 9 Classes de Risco
`baixo_di`, `baixo_rfx`, `moderado`, `alto`, `ouro`, `dolar`, `cripto`, `internacional`, `fii`

Constante `TODAS_CLASSES` em `balance_service.py` agrupa todas as 9. A separação entre `baixo_di` e `baixo_rfx` é feita pelo campo `subtipo_risco` em `InfoFundo`.

## Serviços principais
- `global_services.py` — CRUD genérico, validação/formatação de CNPJ, upload de arquivo, decorator `login_required`
- `posicao_service.py` — totais por classe de risco para um cliente (`calcular_totais_por_classe`, `calcular_montante_total`)
- `balance_service.py` — rebalanceamento em cascata entre objetivos (capital órfão, VP ideal, fatias)
- `objetivo_services.py` — cálculo PMT com IPCA + 3,5% a.a.
- `extract_btg_service.py` — importação planilha BTG (5 abas, deduplica por CNPJ)
- `extract_advisor_service.py` — importação planilha Advisor (matching por nome do fundo)
- `extract_services.py` — download e parsing CVM (ZIP diário) + BCB API
- `cota_update_service.py` — atualização em lote de cotas (não faz commit — o caller faz)
- `fundo_registration_service.py` — cadastro automático via CNPJ da CVM

## Fluxo de rebalanceamento (`balanco.py`)
1. `GET /balanco/iniciar/<cliente_id>` — exibe posições por classe, VP ideal por objetivo
2. `POST /balanco/editar_fatias/<cliente_id>` — salva percentuais de distribuição por objetivo
3. `POST /balanco/executar/<cliente_id>` — executa rebalanceamento cascata + aporte opcional
4. `GET /balanco/resultado/<cliente_id>` — exibe resultado final

## Matrizes de risco (`matriz_data.py`)
Duas matrizes hardcoded: `MATRIZ_GERAL` (apenas classes tradicionais) e `MATRIZ_PREVIDENCIA` (64% tradicional + 36% hedge fixo: ouro 4.5%, dólar 4.5%, cripto 2%, internacional 10%, fii 15%). Linhas keyed por duração: 12, 24, 36, 48, 60, 72, 84, 96, 120, 180, 360 meses.

## Convenções
- Rotas usam `try/finally` para garantir fechamento de sessão
- CNPJs "dummy" (fundos sem CNPJ real): prefixos `DUMMY-`, `99.xxx`, `98.xxx`, `97.xxx`
- Banco de dados deletado e recriado manualmente quando o modelo muda (sem Alembic)
- Sistema single-user — sem tabela de usuários, credenciais hardcoded em `auth.py` (`claudio`/`1234`)
- Fundos de previdência (`is_previdencia=True`) ficam em pool separado no rebalanceamento
- `cota_update_service.py` nunca faz commit — responsabilidade do caller

## Pendências conhecidas
- URL hardcoded `http://127.0.0.1:5000/upload` em `import_fundos.html` — quebrado em produção
- `print()` usado para logging — migrar para módulo `logging` futuramente
- Sem testes automatizados
