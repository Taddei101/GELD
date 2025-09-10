# GELD

# GELD Finance Control - Sistema de Gestão Financeira

## Visão Geral do Projeto

**GELD** é um sistema web de gestão financeira desenvolvido com Flask para gerenciar carteiras de investimentos, objetivos financeiros e balanceamento de risco de clientes.

### Stack Tecnológico
- **Backend**: Python 3.x + Flask
- **Frontend**: HTML5, CSS3, JavaScript, Jinja2 Templates
- **Banco de Dados**: SQLite (SQLAlchemy ORM)
- **Bibliotecas**: Pandas, Requests, Werkzeug
- **Deploy**: PythonAnywhere (produção)

### Propósito Principal
Sistema para assessores de investimento gerenciarem:
- Cadastro e perfil de clientes
- Objetivos financeiros com metas e prazos
- Posições em fundos de investimento
- Balanceamento automático por perfil de risco
- Distribuição de capital entre objetivos
- Atualização automática de cotas via CVM

## Arquitetura do Sistema

### Estrutura de Pastas
```
/
├── run.py                    # Ponto de entrada da aplicação
├── app_config.py            # Configuração da app Flask e blueprints
├── config.py                # Configurações de ambiente (dev/prod)
├── app/
│   ├── models/
│   │   └── geld_models.py   # Modelos SQLAlchemy
│   ├── routes/              # Blueprints das rotas
│   │   ├── auth.py         # Autenticação
│   │   ├── cliente.py      # CRUD de clientes
│   │   ├── objetivo.py     # CRUD de objetivos
│   │   ├── fundos.py       # CRUD de fundos
│   │   ├── posicao.py      # Posições em fundos
│   │   ├── dashboard.py    # Dashboard principal
│   │   ├── balanco.py      # Balanceamento de aportes
│   │   └── distribuicao.py # Distribuição de capital
│   ├── services/           # Lógica de negócio
│   │   ├── global_services.py
│   │   ├── balance_service.py
│   │   ├── distribuicao_capital_service.py
│   │   ├── extract_services.py
│   │   └── objetivo_services.py
│   ├── templates/          # Templates HTML
│   │   └── base.html       # Template base
│   └── static/             # CSS, JS, imagens
```

### Padrões Arquiteturais

**Blueprint Pattern**: Cada módulo funcional é um blueprint separado
- `auth_bp`: Autenticação
- `cliente_bp`: Gestão de clientes  
- `objetivo_bp`: Objetivos financeiros
- `fundos_bp`: Fundos de investimento
- `posicao_bp`: Posições do cliente
- `dashboard_bp`: Dashboard e métricas
- `balanco_bp`: Balanceamento de aportes
- `distribuicao_bp`: Distribuição de capital

**Service Layer Pattern**: Lógica de negócio isolada em services
- `GlobalServices`: CRUD genérico + validações
- `Balance`: Algoritmos de balanceamento por risco
- `DistribuicaoCapitalService`: Alocação de capital existente
- `ExtractServices`: Integração com APIs externas (CVM, BCB)
- `ObjetivoServices`: Cálculos financeiros

## Modelos de Dados Principais

### Cliente
- Dados pessoais, contato, banco
- Status (ativo/inativo)
- Relacionamento 1:N com objetivos e posições

### Objetivo  
- Nome, valor inicial, valor atual, valor final
- Datas inicial e final (calcula duração automaticamente)
- Vinculado a um cliente

### InfoFundo
- Dados do fundo (nome, CNPJ, classe ANBIMA)
- Nível de risco (baixo/moderado/alto)
- Valor da cota atualizado via CVM
- Status do fundo

### PosicaoFundo
- Relaciona cliente + fundo + quantidade de cotas
- Data de atualização

### IndicadoresEconomicos
- IPCA mensal e anual
- Data da última atualização

## Funcionalidades Implementadas

### 1. Gestão de Clientes
- **CRUD completo**: criar, listar, editar, deletar
- **Área do cliente**: overview com montante total, número de objetivos/fundos
- **Informações pessoais**: dados de contato e perfil

### 2. Gestão de Objetivos
- **CRUD de objetivos** com metas financeiras
- **Cálculo de aportes mensais** necessários (PMT)
- Integração com IPCA para correção inflacionária
- **Duração automática** calculada entre datas

### 3. Gestão de Fundos
- **Cadastro manual** ou **por CNPJ via CVM**
- **Atualização automática de cotas** via API CVM
- **Classificação por risco** (baixo/moderado/alto)
- **Batch de CNPJs** para cadastro múltiplo

### 4. Posições em Fundos
- **Registro manual** de cotas
- **Upload de planilhas BTG** e **XP** (processamento automático)
- **Visualização consolidada** do portfolio
- **Cálculo automático de valores** (cotas × valor_cota)

### 5. Balanceamento de Aportes
- **Algoritmo de distribuição** baseado no prazo dos objetivos
- **Tabela de risco dinâmica**: mais conservador para prazos curtos
- **Simulação de aportes** antes da aplicação
- **Quebra por tipo de risco** (baixo/moderado/alto)

### 6. Distribuição de Capital
- **Alocação automática** do capital existente para objetivos
- **Priorização por prazo** (objetivos mais urgentes primeiro)
- **Respeitando perfil de risco** de cada objetivo
- **Simulação antes da aplicação** aos valores reais

### 7. Dashboard e Métricas
- **Métricas gerais**: total de clientes, capital administrado
- **Indicadores econômicos**: IPCA atualizado via BCB
- **Clientes ativos/inativos**
- **Número total de fundos** cadastrados

### 8. Integrações Externas
- **API Banco Central**: IPCA mensal e anual
- **API CVM**: informações de fundos e valor das cotas
- **Processamento de planilhas**: BTG e XP com diferentes formatos

## Decisões Técnicas

### Autenticação
- **Sistema simples** com usuário/senha fixos
- **Session-based** authentication
- **Decorator `@login_required`** para proteção de rotas

### Banco de Dados
- **SQLite** para simplicidade (fácil backup e portabilidade)
- **SQLAlchemy ORM** para abstrair SQL
- **Enums** para campos com valores fixos (Risco, Status, Banco)

### Configuração por Ambiente
- **Desenvolvimento**: caminho local do banco
- **Produção (PythonAnywhere)**: caminho absoluto
- **Variáveis de ambiente** para configurações sensíveis

### Tratamento de Erros
- **Flash messages** com categorias (success, error, warning, info)
- **Try/catch abrangente** com rollback automático
- **Logs de debug** para troubleshooting

### Upload de Arquivos
- **Werkzeug secure_filename** para segurança
- **Validação de tipo** (apenas .xlsx, .xls)
- **Limite de tamanho** (16MB)
- **Timestamp nos nomes** para evitar conflitos

## Algoritmos de Negócio

### Balanceamento por Risco
Baseado na duração do objetivo em meses:
- **≤12 meses**: 85% baixo, 13.5% moderado, 1.5% alto
- **≤24 meses**: 78.5% baixo, 17.8% moderado, 3.7% alto
- **[...gradual até...]**
- **≥132 meses**: 20% baixo, 16% moderado, 64% alto

### Cálculo de Aportes (PMT)
- **Valor presente**: valor_real atual do objetivo
- **Valor futuro**: valor_final corrigido pelo IPCA
- **Taxa**: IPCA mensal + 3.5% ao ano (taxa real)
- **Fórmula PMT** padrão de matemática financeira

### Distribuição de Capital
1. **Ordena objetivos** por prazo (mais urgentes primeiro)
2. **Determina perfil de risco** para cada objetivo
3. **Aloca fundos existentes** respeitando os percentuais de risco
4. **Prioriza objetivos** até esgotar capital disponível

## Estado Atual do Desenvolvimento

### Funcionalidades Prontas ✅
- Sistema de autenticação básico
- CRUD completo de clientes, objetivos e fundos
- Registro e visualização de posições
- Upload e processamento de planilhas BTG/XP
- Balanceamento de aportes simulado
- Distribuição de capital simulada
- Dashboard com métricas principais
- Integração com APIs CVM e BCB
- Atualização automática de cotas

### Pontos de Atenção ⚠️
- **Autenticação simples**: apenas 1 usuário hardcoded
- **Sem validação robusta**: CPF, CNPJ básicos
- **Upload via tkinter**: pode não funcionar em produção web
- **Processamento planilhas**: específico para formatos BTG/XP
- **Sem backup automático**: banco SQLite local
- **Sem logs estruturados**: apenas prints para debug

### Próximas Evoluções Sugeridas 🔄
- **Sistema de usuários** multi-tenant
- **API REST** para integração externa  
- **Relatórios PDF** automatizados
- **Gráficos interativos** (Chart.js/D3.js)
- **Notificações** para rebalanceamento
- **Importação automática** de posições
- **Backup para cloud** (AWS S3, Google Drive)
- **Testes automatizados** (pytest)
- **Logs estruturados** (logging module)

## Comandos Úteis

### Execução Local
```bash
python run.py
# Acessa http://localhost:5000
# Login: claudio / senha: 1234
```

### Dependências
```bash
pip install flask sqlalchemy pandas requests werkzeug
```

### Inicialização do Banco
```python
from app.models.geld_models import init_db
init_db()  # Cria tabelas automaticamente
```

## Convenções de Código

### Nomenclatura
- **Classes**: PascalCase (`GlobalServices`, `InfoFundo`)
- **Funções/métodos**: snake_case (`create_classe`, `listar_objetivos`)
- **Variáveis**: snake_case (`cliente_id`, `valor_final`)
- **Templates**: snake_case (`listar_clientes.html`)

### Estrutura de Rotas
- **GET**: formulários e listagens
- **POST**: criação e edição
- **Padrão**: `/entidade/<id>/acao`

### Fluxo de Dados
1. **Route** recebe request
2. **Route** cria sessão DB
3. **Route** chama **Service** 
4. **Service** executa lógica + persiste dados
5. **Route** renderiza template ou redirect
6. **Finally** fecha sessão DB

Este README serve como minha "memória" para retomar o contexto do projeto GELD em futuras sessões. O sistema está funcional mas há espaço para evoluções em robustez, segurança e funci
