import tkinter as tk
from tkinter import filedialog
from pdf2image import convert_from_path
import pytesseract
import os
from pathlib import Path
import re

# Passo 1: Selecionar o arquivo
def selecionar_arquivo_pdf():
    root = tk.Tk()
    root.withdraw()
    arquivo = filedialog.askopenfilename(
        title="Selecione o arquivo PDF",
        filetypes=[("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
    )
    root.destroy()
    return arquivo

# Passo 2: Extrair texto do PDF usando OCR
def extrair_texto_ocr(arquivo_pdf):
    try:
        print("Convertendo PDF em imagens...")
        imagens = convert_from_path(arquivo_pdf)
        print(f"PDF convertido em {len(imagens)} imagens.")
        
        texto_completo = ""
        for i, img in enumerate(imagens):
            print(f"Processando página {i+1}/{len(imagens)} com OCR...")
            try:
                texto_pagina = pytesseract.image_to_string(img, lang="por")
            except:
                texto_pagina = pytesseract.image_to_string(img)
            
            texto_completo += texto_pagina + "\n\n"
            
            # Mostrar amostra do texto extraído
            amostra = texto_pagina[:100].replace('\n', ' ')
            print(f"Amostra: {amostra}...")
        
        # Salvar o texto extraído em um arquivo para referência
        arquivo_texto = Path(arquivo_pdf).with_suffix('.txt')
        with open(arquivo_texto, 'w', encoding='utf-8') as f:
            f.write(texto_completo)
        print(f"Texto extraído salvo em: {arquivo_texto}")
        
        # Abrir o arquivo de texto
        os.startfile(arquivo_texto)
        
        return texto_completo, arquivo_texto
    except Exception as e:
        print(f"Erro ao processar o PDF: {e}")
        return "", None

# Função para extrair CNPJs do texto
def extrair_cnpjs(texto):
    # Padrão de CNPJ regular: XX.XXX.XXX/XXXX-XX
    padrao_cnpj = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
    cnpjs = re.findall(padrao_cnpj, texto)
    
    # Remover duplicatas mantendo a ordem
    cnpjs_unicos = []
    for cnpj in cnpjs:
        if cnpj not in cnpjs_unicos:
            cnpjs_unicos.append(cnpj)
    
    return cnpjs_unicos

# Função principal
def main():
    # Selecionar arquivo
    arquivo_pdf = selecionar_arquivo_pdf()
    if not arquivo_pdf:
        print("Nenhum arquivo selecionado.")
        return
    
    print(f"Processando arquivo: {arquivo_pdf}")
    
    # Extrair texto usando OCR
    texto, arquivo_texto = extrair_texto_ocr(arquivo_pdf)
    if not texto or not arquivo_texto:
        return
    
    # Extrair CNPJs do texto
    cnpjs = extrair_cnpjs(texto)
    
    if cnpjs:
        print(f"\nForam encontrados {len(cnpjs)} CNPJs únicos no documento:")
        for cnpj in cnpjs:
            print(cnpj)
        
        # Salvar a lista de CNPJs em um arquivo separado
        nome_base = Path(arquivo_pdf).stem
        arquivo_cnpjs = Path(arquivo_pdf).parent / f"{nome_base}_CNPJs.txt"
        
        with open(arquivo_cnpjs, 'w', encoding='utf-8') as f:
            f.write(f"Lista de CNPJs encontrados em {Path(arquivo_pdf).name}:\n\n")
            for i, cnpj in enumerate(cnpjs, 1):
                f.write(f"{i}. {cnpj}\n")
        
        print(f"\nLista de CNPJs salvos em: {arquivo_cnpjs}")
        
        # Abrir o arquivo com a lista de CNPJs
        os.startfile(arquivo_cnpjs)
    else:
        print("Nenhum CNPJ encontrado no documento.")

if __name__ == "__main__":
    main()