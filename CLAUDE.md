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
run.py                        # entry point, chama init_db()
app/
  app_config.py               # factory Flask, registra blueprints
  config.py                   # caminhos e DB (env-aware)
  models/
    geld_models.py            # todos os modelos SQLAlchemy + init_db()
    matriz_data.py            # dados hardcoded das matrizes de risco
  routes/                     # 8 blueprints (controladores finos)
  services/                   # lógica de negócio (sem imports Flask)
  templates/                  # Jinja2, organizado por blueprint
  static/                     # CSS, ícones, imagens
```

## Modelos
| Modelo | Descrição |
|--------|-----------|
| `Cliente` | Dados pessoais + banco (BTG/XP/NU) |
| `Objetivo` | Meta financeira com prazo e valor alvo |
| `DistribuicaoObjetivo` | Alocação alvo por classe de risco (9 classes) |
| `InfoFundo` | Cadastro de fundos + cotação CVM |
| `PosicaoFundo` | Cotas do cliente em cada fundo |
| `MatrizRisco` | Tabela horizonte (meses) → alocação ideal |
| `IndicadoresEconomicos` | IPCA atualizado via BCB |

## Serviços principais
- `balance_service.py` — rebalanceamento em cascata entre objetivos
- `objetivo_services.py` — cálculo PMT com IPCA + 3,5% a.a.
- `extract_btg_service.py` — importação planilha BTG (5 abas)
- `extract_advisor_service.py` — importação planilha Advisor (por nome)
- `extract_services.py` — download e parsing CVM (ZIP diário)
- `cota_update_service.py` — atualização em lote de cotas (não faz commit — o caller faz)
- `fundo_registration_service.py` — cadastro automático via CNPJ da CVM

## Convenções
- Rotas usam `try/finally` para garantir fechamento de sessão
- CNPJs "dummy" (fundos sem CNPJ real): prefixos `DUMMY-`, `99.xxx`, `98.xxx`, `97.xxx`
- Banco de dados deletado e recriado manualmente quando o modelo muda (sem Alembic)
- Sistema single-user — sem tabela de usuários, credenciais em `auth.py`

## Pendências conhecidas
- `TipoOperacaoEnum` (resgate/aporte) existe em `geld_models.py` mas não tem feature implementada — pode ser removido
- URL hardcoded `http://127.0.0.1:5000/upload` em `import_fundos.html` — quebrado em produção
- `print()` usado para logging — migrar para módulo `logging` futuramente
- Sem testes automatizados
