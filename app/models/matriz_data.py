# app/models/matriz_data.py
"""
Dados das matrizes de risco por tipo de objetivo e duração
"""

MATRIZ_GERAL = [
    # (duracao_meses, perc_baixo, perc_moderado, perc_alto, perc_di_dentro_baixo, perc_rfx_dentro_baixo)
    (12, 85.0, 13.5, 1.5, 100.0, 0.0),
    (24, 78.5, 17.85, 3.66, 15.0, 85.0),
    (36, 72.0, 21.28, 6.72, 5.0, 95.0),
    (48, 65.5, 23.81, 10.7, 5.0, 95.0),
    (60, 59.0, 25.42, 15.58, 5.0, 95.0),
    (72, 52.5, 26.13, 21.38, 5.0, 95.0),
    (84, 46.0, 25.92, 28.08, 5.0, 95.0),
    (96, 39.5, 24.81, 35.70, 5.0, 95.0),
    (108, 33.0, 22.78, 44.22, 5.0, 95.0),
    (120, 26.5, 19.85, 53.66, 5.0, 95.0),
    (132, 20.0, 16.0, 64.0, 5.0, 95.0),
]

# MATRIZ PREVIDÊNCIA 
MATRIZ_PREVIDENCIA = [
    # (duracao_meses, perc_baixo, perc_moderado, perc_alto, perc_di_dentro_baixo, perc_rfx_dentro_baixo)
        
    (12, 90.0, 8.5, 1.5, 100.0, 0.0),
    (24, 85.0, 13.0, 2.0, 20.0, 80.0),
    (36, 80.0, 16.0, 4.0, 10.0, 90.0),
    (48, 75.0, 19.0, 6.0, 10.0, 90.0),
    (60, 70.0, 22.0, 8.0, 10.0, 90.0),
    (72, 65.0, 24.0, 11.0, 10.0, 90.0),
    (84, 60.0, 25.0, 15.0, 10.0, 90.0),
    (96, 55.0, 26.0, 19.0, 10.0, 90.0),
    (108, 50.0, 26.0, 24.0, 10.0, 90.0),
    (120, 45.0, 25.0, 30.0, 10.0, 90.0),
    (132, 40.0, 24.0, 36.0, 10.0, 90.0),
]

def validar_matriz(dados_matriz, nome_matriz):
    """
    Valida se os percentuais de uma matriz estão corretos
    """
    erros = []
    
    for linha in dados_matriz:
        duracao, baixo, moderado, alto, di, rfx = linha
        
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