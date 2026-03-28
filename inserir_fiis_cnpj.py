import sqlite3
import json

DB_PATH = r"C:\Users\utadd\Documents\geld\geld_database.db"
JSON_PATH_FII = r"C:\Users\utadd\Documents\geld\fiis_cnpj.json"
JSON_PATH_MULTI = r"C:\Users\utadd\Documents\geld\multimercados_cnpj.json"
JSON_PATH_RFX = r"C:\Users\utadd\Documents\geld\renda_fixa_cnpj.json"

def atualizar_cnpjs(cursor, dados, label):
    atualizados, nao_encontrados = [], []
    for nome, cnpj in dados.items():
        cursor.execute(
            "UPDATE info_fundos SET cnpj = ? WHERE UPPER(nome_fundo) = UPPER(?)",
            (cnpj, nome)
        )
        if cursor.rowcount > 0:
            atualizados.append(nome)
        else:
            nao_encontrados.append(nome)
    print(f"\n[{label}] ✅ Atualizados ({len(atualizados)}): {', '.join(atualizados)}")
    if nao_encontrados:
        print(f"[{label}] ⚠️  Não encontrados ({len(nao_encontrados)}): {', '.join(nao_encontrados)}")

with open(JSON_PATH_FII, encoding="utf-8") as f:
    fiis = json.load(f)
with open(JSON_PATH_MULTI, encoding="utf-8") as f:
    multis = json.load(f)
with open(JSON_PATH_RFX, encoding="utf-8") as f:
    rfxs = json.load(f)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

atualizar_cnpjs(cursor, fiis, "FIIs")
atualizar_cnpjs(cursor, multis, "Multimercados")
atualizar_cnpjs(cursor, rfxs, "Renda Fixa")

conn.commit()
conn.close()