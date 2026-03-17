# app/models/matriz_data.py
"""
Dados das matrizes de risco por tipo de objetivo e duração.

GERAL: classes tradicionais (baixo/moderado/alto), hedge zerado.
PREVIDÊNCIA: 64% nas classes tradicionais + 36% hedge fixo
    (ouro 4.5%, dólar 4.5%, cripto 2%, internacional 10%, FII 15%)
"""

MATRIZ_GERAL = [
    {
        'duracao_meses': 12,
        'perc_baixo': 85.0,
        'perc_moderado': 13.5,
        'perc_alto': 1.5,
        'perc_di_dentro_baixo': 100.0,
        'perc_rfx_dentro_baixo': 0.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 24,
        'perc_baixo': 78.5,
        'perc_moderado': 17.85,
        'perc_alto': 3.66,
        'perc_di_dentro_baixo': 15.0,
        'perc_rfx_dentro_baixo': 85.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 36,
        'perc_baixo': 72.0,
        'perc_moderado': 21.28,
        'perc_alto': 6.72,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 48,
        'perc_baixo': 65.5,
        'perc_moderado': 23.81,
        'perc_alto': 10.7,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 60,
        'perc_baixo': 59.0,
        'perc_moderado': 25.42,
        'perc_alto': 15.58,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 72,
        'perc_baixo': 52.5,
        'perc_moderado': 26.13,
        'perc_alto': 21.38,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 84,
        'perc_baixo': 46.0,
        'perc_moderado': 25.92,
        'perc_alto': 28.08,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 96,
        'perc_baixo': 39.5,
        'perc_moderado': 24.81,
        'perc_alto': 35.70,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 108,
        'perc_baixo': 33.0,
        'perc_moderado': 22.78,
        'perc_alto': 44.22,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 120,
        'perc_baixo': 26.5,
        'perc_moderado': 19.85,
        'perc_alto': 53.66,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
    {
        'duracao_meses': 132,
        'perc_baixo': 20.0,
        'perc_moderado': 16.0,
        'perc_alto': 64.0,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0,
        'perc_ouro': 0.0,
        'perc_dolar': 0.0,
        'perc_cripto': 0.0,
        'perc_internacional': 0.0,
        'perc_fii': 0.0
    },
]

# PREVIDÊNCIA: classes tradicionais ×0.64 + hedge fixo (36%)
# Hedge: ouro 4.5%, dólar 4.5%, cripto 2%, internacional 10%, FII 15%
# Split di/rfx dentro de baixo permanece inalterado (é relativo)
MATRIZ_PREVIDENCIA = [
    {
        'duracao_meses': 12,
        'perc_baixo': 57.60,       # 90.0 × 0.64
        'perc_moderado': 5.44,     # 8.5 × 0.64
        'perc_alto': 0.96,         # 1.5 × 0.64
        'perc_di_dentro_baixo': 100.0,
        'perc_rfx_dentro_baixo': 0.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 24,
        'perc_baixo': 54.40,       # 85.0 × 0.64
        'perc_moderado': 8.32,     # 13.0 × 0.64
        'perc_alto': 1.28,         # 2.0 × 0.64
        'perc_di_dentro_baixo': 20.0,
        'perc_rfx_dentro_baixo': 80.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 36,
        'perc_baixo': 51.20,       # 80.0 × 0.64
        'perc_moderado': 10.24,    # 16.0 × 0.64
        'perc_alto': 2.56,         # 4.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 48,
        'perc_baixo': 48.00,       # 75.0 × 0.64
        'perc_moderado': 12.16,    # 19.0 × 0.64
        'perc_alto': 3.84,         # 6.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 60,
        'perc_baixo': 44.80,       # 70.0 × 0.64
        'perc_moderado': 14.08,    # 22.0 × 0.64
        'perc_alto': 5.12,         # 8.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 72,
        'perc_baixo': 41.60,       # 65.0 × 0.64
        'perc_moderado': 15.36,    # 24.0 × 0.64
        'perc_alto': 7.04,         # 11.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 84,
        'perc_baixo': 38.40,       # 60.0 × 0.64
        'perc_moderado': 16.00,    # 25.0 × 0.64
        'perc_alto': 9.60,         # 15.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 96,
        'perc_baixo': 35.20,       # 55.0 × 0.64
        'perc_moderado': 16.64,    # 26.0 × 0.64
        'perc_alto': 12.16,        # 19.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 108,
        'perc_baixo': 32.00,       # 50.0 × 0.64
        'perc_moderado': 16.64,    # 26.0 × 0.64
        'perc_alto': 15.36,        # 24.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 120,
        'perc_baixo': 28.80,       # 45.0 × 0.64
        'perc_moderado': 16.00,    # 25.0 × 0.64
        'perc_alto': 19.20,        # 30.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
    {
        'duracao_meses': 132,
        'perc_baixo': 25.60,       # 40.0 × 0.64
        'perc_moderado': 15.36,    # 24.0 × 0.64
        'perc_alto': 23.04,        # 36.0 × 0.64
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0,
        'perc_ouro': 4.5,
        'perc_dolar': 4.5,
        'perc_cripto': 2.0,
        'perc_internacional': 10.0,
        'perc_fii': 15.0
    },
]

def validar_matriz(dados_matriz, nome_matriz):
    """
    Valida se os percentuais de uma matriz estão corretos.
    Soma das 9 classes (baixo + moderado + alto + 5 hedge) deve ser ~100%.
    """
    erros = []
    
    for linha in dados_matriz:
        duracao = linha['duracao_meses']
        baixo = linha['perc_baixo']
        moderado = linha['perc_moderado']
        alto = linha['perc_alto']
        ouro = linha['perc_ouro']
        dolar = linha['perc_dolar']
        cripto = linha['perc_cripto']
        internacional = linha['perc_internacional']
        fii = linha['perc_fii']
        di = linha['perc_di_dentro_baixo']
        rfx = linha['perc_rfx_dentro_baixo']
        
        # Validar se TODAS as classes somam ~100%
        total_geral = baixo + moderado + alto + ouro + dolar + cripto + internacional + fii
        if abs(total_geral - 100.0) > 0.1:
            erros.append(f"{nome_matriz} - {duracao}m: Total geral {total_geral:.2f}% (deve ser 100%)")
        
        # Validar se subdivisão baixo soma ~100%
        total_baixo = di + rfx
        if abs(total_baixo - 100.0) > 0.1:
            erros.append(f"{nome_matriz} - {duracao}m: Subdivisão baixo {total_baixo:.2f}% (deve ser 100%)")
    
    return erros

def validar_todas_matrizes():
    """
    Valida todas as matrizes definidas
    """
    todos_erros = []
    todos_erros.extend(validar_matriz(MATRIZ_GERAL, "GERAL"))
    todos_erros.extend(validar_matriz(MATRIZ_PREVIDENCIA, "PREVIDÊNCIA"))
    
    if todos_erros:
        print("❌ Erros encontrados nas matrizes:")
        for erro in todos_erros:
            print(f"  - {erro}")
        return False
    else:
        print("✅ Todas as matrizes são válidas")
        return True

# Para debug - executar validação se chamado diretamente
if __name__ == "__main__":
    print("🔍 Validando matrizes de risco...")
    validar_todas_matrizes()