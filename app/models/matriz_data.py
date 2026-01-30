# app/models/matriz_data.py
"""
Dados das matrizes de risco por tipo de objetivo e duração
"""

MATRIZ_GERAL = [
    {
        'duracao_meses': 12,
        'perc_baixo': 85.0,
        'perc_moderado': 13.5,
        'perc_alto': 1.5,
        'perc_di_dentro_baixo': 100.0,
        'perc_rfx_dentro_baixo': 0.0
    },
    {
        'duracao_meses': 24,
        'perc_baixo': 78.5,
        'perc_moderado': 17.85,
        'perc_alto': 3.66,
        'perc_di_dentro_baixo': 15.0,
        'perc_rfx_dentro_baixo': 85.0
    },
    {
        'duracao_meses': 36,
        'perc_baixo': 72.0,
        'perc_moderado': 21.28,
        'perc_alto': 6.72,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 48,
        'perc_baixo': 65.5,
        'perc_moderado': 23.81,
        'perc_alto': 10.7,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 60,
        'perc_baixo': 59.0,
        'perc_moderado': 25.42,
        'perc_alto': 15.58,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 72,
        'perc_baixo': 52.5,
        'perc_moderado': 26.13,
        'perc_alto': 21.38,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 84,
        'perc_baixo': 46.0,
        'perc_moderado': 25.92,
        'perc_alto': 28.08,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 96,
        'perc_baixo': 39.5,
        'perc_moderado': 24.81,
        'perc_alto': 35.70,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 108,
        'perc_baixo': 33.0,
        'perc_moderado': 22.78,
        'perc_alto': 44.22,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 120,
        'perc_baixo': 26.5,
        'perc_moderado': 19.85,
        'perc_alto': 53.66,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
    {
        'duracao_meses': 132,
        'perc_baixo': 20.0,
        'perc_moderado': 16.0,
        'perc_alto': 64.0,
        'perc_di_dentro_baixo': 5.0,
        'perc_rfx_dentro_baixo': 95.0
    },
]

MATRIZ_PREVIDENCIA = [
    {
        'duracao_meses': 12,
        'perc_baixo': 90.0,
        'perc_moderado': 8.5,
        'perc_alto': 1.5,
        'perc_di_dentro_baixo': 100.0,
        'perc_rfx_dentro_baixo': 0.0
    },
    {
        'duracao_meses': 24,
        'perc_baixo': 85.0,
        'perc_moderado': 13.0,
        'perc_alto': 2.0,
        'perc_di_dentro_baixo': 20.0,
        'perc_rfx_dentro_baixo': 80.0
    },
    {
        'duracao_meses': 36,
        'perc_baixo': 80.0,
        'perc_moderado': 16.0,
        'perc_alto': 4.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 48,
        'perc_baixo': 75.0,
        'perc_moderado': 19.0,
        'perc_alto': 6.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 60,
        'perc_baixo': 70.0,
        'perc_moderado': 22.0,
        'perc_alto': 8.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 72,
        'perc_baixo': 65.0,
        'perc_moderado': 24.0,
        'perc_alto': 11.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 84,
        'perc_baixo': 60.0,
        'perc_moderado': 25.0,
        'perc_alto': 15.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 96,
        'perc_baixo': 55.0,
        'perc_moderado': 26.0,
        'perc_alto': 19.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 108,
        'perc_baixo': 50.0,
        'perc_moderado': 26.0,
        'perc_alto': 24.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 120,
        'perc_baixo': 45.0,
        'perc_moderado': 25.0,
        'perc_alto': 30.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
    {
        'duracao_meses': 132,
        'perc_baixo': 40.0,
        'perc_moderado': 24.0,
        'perc_alto': 36.0,
        'perc_di_dentro_baixo': 10.0,
        'perc_rfx_dentro_baixo': 90.0
    },
]

def validar_matriz(dados_matriz, nome_matriz):
    """
    Valida se os percentuais de uma matriz estão corretos
    """
    erros = []
    
    for linha in dados_matriz:
        duracao = linha['duracao_meses']
        baixo = linha['perc_baixo']
        moderado = linha['perc_moderado']
        alto = linha['perc_alto']
        di = linha['perc_di_dentro_baixo']
        rfx = linha['perc_rfx_dentro_baixo']
        
        # Validar se principais somam ~100%
        total_principal = baixo + moderado + alto
        if abs(total_principal - 100.0) > 0.1:
            erros.append(f"{nome_matriz} - {duracao}m: Total principal {total_principal:.2f}% (deve ser 100%)")
        
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