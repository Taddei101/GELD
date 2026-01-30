"""
Serviço para processar arquivos Excel do BTG
Extrai posições de todas as abas: Fundos, Previdência Individual, Previdência Externa, Renda Fixa e Renda Variável
"""

import pandas as pd
from datetime import datetime
from app.models.geld_models import RiscoEnum, SubtipoRiscoEnum, create_session
from app.services.global_services import GlobalServices
import hashlib
import re


class ExtractBTGService:
    
    
    def __init__(self, db, global_services):
        
        self.db = db
        self.global_services = global_services
    
    def processar_arquivo_btg_completo(self, file_path, cliente_id):
        
        todas_posicoes = []
        log_processamento = {
            'fundos': 0,
            'previdencia_individual': 0, 
            'previdencia_externa': 0,
            'renda_fixa': 0,
            'renda_variavel': 0,
            'erros': []
        }
        
        try:
            print(f"[INFO] Processando arquivo BTG para cliente {cliente_id}")
            
            # 1. PROCESSAR ABA FUNDOS
            posicoes_fundos = self._processar_aba_fundos(file_path)
            todas_posicoes.extend(posicoes_fundos)
            log_processamento['fundos'] = len(posicoes_fundos)
            print(f"[INFO] Fundos extraídos: {len(posicoes_fundos)}")
            
            # 2. PROCESSAR PREVIDÊNCIA INDIVIDUAL
            posicoes_prev_ind = self._processar_aba_previdencia_individual(file_path)
            todas_posicoes.extend(posicoes_prev_ind)
            log_processamento['previdencia_individual'] = len(posicoes_prev_ind)
            print(f"[INFO] Previdência Individual extraída: {len(posicoes_prev_ind)}")
            
            # 3. PROCESSAR PREVIDÊNCIA EXTERNA  
            posicoes_prev_ext = self._processar_aba_previdencia_externa(file_path)
            todas_posicoes.extend(posicoes_prev_ext)
            log_processamento['previdencia_externa'] = len(posicoes_prev_ext)
            print(f"[INFO] Previdência Externa extraída: {len(posicoes_prev_ext)}")
            
            # 4. PROCESSAR RENDA FIXA
            posicoes_rf = self._processar_aba_renda_fixa(file_path)
            todas_posicoes.extend(posicoes_rf)
            log_processamento['renda_fixa'] = len(posicoes_rf)
            print(f"[INFO] Renda Fixa extraída: {len(posicoes_rf)}")
            
            # 5. PROCESSAR RENDA VARIÁVEL
            posicoes_rv = self._processar_aba_renda_variavel(file_path)
            todas_posicoes.extend(posicoes_rv)
            log_processamento['renda_variavel'] = len(posicoes_rv)
            print(f"[INFO] Renda Variável extraída: {len(posicoes_rv)}")
            
            # 6. DEDUPLICAÇÃO POR CNPJ
            posicoes_unicas = self._deduplificar_posicoes(todas_posicoes)
            posicoes_removidas = len(todas_posicoes) - len(posicoes_unicas)
            
            if posicoes_removidas > 0:
                print(f"[INFO] {posicoes_removidas} posições duplicadas removidas")
            
            print(f"[INFO] Total de posições únicas: {len(posicoes_unicas)}")
            
            return posicoes_unicas, log_processamento
            
        except Exception as e:
            log_processamento['erros'].append(str(e))
            print(f"[ERRO] Erro no processamento completo BTG: {str(e)}")
            return todas_posicoes, log_processamento
    
    # =========================================================================
    # PROCESSADORES DE ABAS ESPECÍFICAS
    # =========================================================================
    
    def _processar_aba_fundos(self, file_path):
        """Processa aba 'Fundos' extraindo CNPJs e posições"""
        posicoes = []
        
        try:
            df = pd.read_excel(file_path, sheet_name="Fundos", header=None)
            
            # 1. Mapear CNPJs da seção "Detalhamento >"
            cnpjs_fundos = {}
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Detalhamento >" in cell_value:
                    try:
                        parts = cell_value.split(" - ")
                        fund_name = parts[0].replace("Detalhamento > ", "").strip()
                        cnpj_bruto = parts[1].strip()
                        
                        is_valid, cnpj_normalizado, _ = self.global_services.validar_cnpj(cnpj_bruto)
                        if is_valid:
                            cnpj_formatado = self.global_services.formatar_cnpj(cnpj_normalizado)
                            cnpjs_fundos[fund_name] = cnpj_formatado
                    except Exception as e:
                        print(f"[AVISO] Erro ao mapear CNPJ na linha {i}: {str(e)}")
                        continue
            
            print(f"[INFO] CNPJs mapeados: {len(cnpjs_fundos)}")
            
            # 2. Localizar seção de posições
            posicao_portfolio_index = None
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição > Portfólio de fundos" in cell_value:
                    posicao_portfolio_index = i
                    break
                    
            if posicao_portfolio_index is None:
                print("[AVISO] Seção 'Posição > Portfólio de fundos' não encontrada")
                return posicoes
                
            # 3. Localizar cabeçalho com colunas
            header_row_index = None
            for i in range(posicao_portfolio_index, min(posicao_portfolio_index + 4, len(df))):
                row = df.iloc[i]
                if any(isinstance(cell, str) and "Quantidade de Cotas" in cell for cell in row):
                    header_row_index = i
                    break
                    
            if header_row_index is None:
                print("[AVISO] Cabeçalho não encontrado na aba Fundos")
                return posicoes
                
            # 4. Identificar coluna de cotas
            cotas_column = None
            date_column = 1  # Coluna padrão para data
            
            for j in range(len(df.columns)):
                if (j < len(df.iloc[header_row_index]) and 
                    isinstance(df.iloc[header_row_index, j], str) and 
                    "Quantidade de Cotas" in df.iloc[header_row_index, j]):
                    cotas_column = j
                    break
                    
            if cotas_column is None:
                print("[AVISO] Coluna de cotas não encontrada na aba Fundos")
                return posicoes
                
            # 5. Extrair posições dos fundos
            for i in range(header_row_index + 1, len(df)):
                # Parar se chegou ao fim da seção
                if (pd.notna(df.iloc[i, 1]) and isinstance(df.iloc[i, 1], str) and 
                    ("Detalhamento" in df.iloc[i, 1] or "Rentabilidade" in df.iloc[i, 1])):
                    break
                    
                # Processar linha de nome do fundo
                if (pd.notna(df.iloc[i, 1]) and isinstance(df.iloc[i, 1], str) and 
                    not df.iloc[i, 1].startswith("Total") and not df.iloc[i, 1].startswith("Data")):
                    
                    # Extrair nome limpo do fundo
                    fund_name_raw = str(df.iloc[i, 1]).replace("*", "").strip()
                    if " - Classe CNPJ:" in fund_name_raw:
                        fund_name = fund_name_raw.split(" - Classe CNPJ:")[0].strip()
                    else:
                        fund_name = fund_name_raw
                    
                    # Verificar se próxima linha tem dados de cotas
                    if (i + 1 < len(df) and pd.notna(df.iloc[i+1, cotas_column]) and 
                        isinstance(df.iloc[i+1, cotas_column], (int, float))):
                        
                        date_value = df.iloc[i+1, date_column] if date_column < len(df.columns) else datetime.now()
                        quotas = float(df.iloc[i+1, cotas_column])
                        
                        # Buscar CNPJ correspondente
                        cnpj = None
                        for key, value in cnpjs_fundos.items():
                            if fund_name.lower() == key.lower():
                                cnpj = value
                                break
                        
                        if not cnpj:
                            print(f"[AVISO] CNPJ não encontrado para: {fund_name}")
                            cnpj = f"DUMMY-FUNDOS-{len(posicoes):04d}"
                        
                        # Converter data
                        if not isinstance(date_value, datetime):
                            try:
                                if isinstance(date_value, str):
                                    date_value = datetime.strptime(date_value, "%d/%m/%Y")
                                else:
                                    date_value = datetime.now()
                            except:
                                date_value = datetime.now()
                        
                        posicao = {
                            "nome_fundo": fund_name,
                            "cnpj": cnpj,
                            "classe_anbima": "Fundos de Investimento",
                            "num_cotas": quotas,
                            "data": date_value,
                            "tipo": "fundo",
                            "risco": RiscoEnum.moderado,
                            "subtipo_risco": None
                        }
                        
                        posicoes.append(posicao)
                        print(f"[INFO] Fundo: {fund_name[:50]} | CNPJ: {cnpj} | Cotas: {quotas}")
            
            return posicoes
            
        except Exception as e:
            print(f"[ERRO] Erro ao processar aba Fundos: {str(e)}")
            return posicoes
    
    def _processar_aba_previdencia_individual(self, file_path):
        """Processa aba Previdência Individual com busca inteligente por seções"""
        posicoes = []
        
        try:
            df = pd.read_excel(file_path, sheet_name="Previdência Individual", header=None)
            
            # 1. Localizar todas as seções que contêm "Posição >"
            secoes_posicao = []
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição >" in cell_value:
                    secoes_posicao.append(i)
            
            # 2. Processar cada seção de posição encontrada
            for inicio_secao in secoes_posicao:
                # 3. Localizar cabeçalho "Fundo"
                linha_cabecalho = None
                for i in range(inicio_secao, min(inicio_secao + 5, len(df))):
                    cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                    if isinstance(cell_value, str) and cell_value.strip().lower() == "fundo":
                        linha_cabecalho = i
                        break
                
                if linha_cabecalho is None:
                    continue
                
                # 4. Extrair dados da seção até encontrar delimitador
                linha_atual = linha_cabecalho + 1
                while linha_atual < len(df):
                    row = df.iloc[linha_atual]
                    
                    # Parar se encontrar fim da seção
                    if (pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and 
                        (row.iloc[1].strip().lower() in ["total", "rentabilidade"] or 
                         "rentabilidade" in row.iloc[1].lower())):
                        break
                    
                    # Verificar se é linha de dados válida
                    if (len(row) >= 7 and 
                        pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and
                        pd.notna(row.iloc[2]) and isinstance(row.iloc[2], str) and
                        pd.notna(row.iloc[4]) and isinstance(row.iloc[4], (int, float)) and
                        ("FOF" in str(row.iloc[1]).upper() or "FI" in str(row.iloc[1]).upper()) and
                        len(str(row.iloc[1]).strip()) > 10):
                        
                        nome_fundo = str(row.iloc[1]).strip()
                        cnpj_bruto = str(row.iloc[2]).strip()
                        data_ref = row.iloc[3] if pd.notna(row.iloc[3]) else datetime.now()
                        quantidade_cotas = float(row.iloc[4])
                        
                        # Validar CNPJ
                        session_temp = create_session()
                        global_service = GlobalServices(session_temp)
                        is_valid, cnpj_normalizado, msg = global_service.validar_cnpj(cnpj_bruto)
                        session_temp.close()
                        
                        if is_valid:
                            cnpj_formatado = global_service.formatar_cnpj(cnpj_normalizado)
                            
                            # Normalizar data
                            if not isinstance(data_ref, datetime):
                                try:
                                    if isinstance(data_ref, str):
                                        data_ref = datetime.strptime(data_ref, "%Y-%m-%d")
                                except:
                                    data_ref = datetime.now()
                            
                            posicoes.append({
                                "nome_fundo": nome_fundo,
                                "cnpj": cnpj_formatado,
                                "num_cotas": quantidade_cotas,
                                "data": data_ref,
                                "tipo": "previdencia_individual"
                            })
                    
                    linha_atual += 1
                        
        except Exception as e:
            print(f"[ERRO] Erro na Previdência Individual: {str(e)}")
        
        return posicoes
    
    def _processar_aba_previdencia_externa(self, file_path):
        """Processa aba Previdência Externa - BUSCA INTELIGENTE"""
        posicoes = []
        
        try:
            df = pd.read_excel(file_path, sheet_name="Previdência Externa", header=None)
            print(f"[DEBUG] Previdência Externa - DataFrame shape: {df.shape}")
            
            # 1. Buscar seções que contêm "Posição >"
            secoes_posicao = []
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição >" in cell_value:
                    secoes_posicao.append(i)
                    print(f"[DEBUG] Seção de posição encontrada na linha {i}: {cell_value}")
            
            # 2. Para cada seção de posição, procurar dados
            for inicio_secao in secoes_posicao:
                print(f"[DEBUG] Processando seção que inicia na linha {inicio_secao}")
                
                # 3. Procurar linha com cabeçalho "Fundo"
                linha_cabecalho = None
                for i in range(inicio_secao, min(inicio_secao + 5, len(df))):
                    cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                    if isinstance(cell_value, str) and cell_value.strip().lower() == "fundo":
                        linha_cabecalho = i
                        print(f"[DEBUG] Cabeçalho 'Fundo' encontrado na linha {i}")
                        break
                
                if linha_cabecalho is None:
                    print(f"[DEBUG] Cabeçalho 'Fundo' não encontrado para seção {inicio_secao}")
                    continue
                
                # 4. Processar dados após o cabeçalho até encontrar delimitador
                linha_atual = linha_cabecalho + 1
                while linha_atual < len(df):
                    row = df.iloc[linha_atual]
                    
                    # Parar se encontrar delimitadores
                    if (pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and 
                        (row.iloc[1].strip().lower() in ["rentabilidade"] or 
                         "rentabilidade" in row.iloc[1].lower() or
                         "plano >" in row.iloc[1].lower())):
                        print(f"[DEBUG] Fim da seção encontrado na linha {linha_atual}: {row.iloc[1]}")
                        break
                    
                    # Verificar se é linha de dados válida
                    if (len(row) >= 6 and 
                        pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and
                        pd.notna(row.iloc[3]) and isinstance(row.iloc[3], (int, float)) and
                        ("FOF" in str(row.iloc[1]).upper() or 
                         "ICATU" in str(row.iloc[1]).upper() or 
                         "SUPERPREVIDENCIA" in str(row.iloc[1]).upper() or
                         "EMPIRICUS" in str(row.iloc[1]).upper()) and
                        len(str(row.iloc[1]).strip()) > 15 and
                        float(row.iloc[3]) > 100):
                        
                        nome_fundo = str(row.iloc[1]).strip()
                        data_ref = row.iloc[2] if pd.notna(row.iloc[2]) else datetime.now()
                        quantidade_cotas = float(row.iloc[3])
                        
                        print(f"[DEBUG] Candidato a fundo encontrado na linha {linha_atual}: {nome_fundo}")
                        
                        # Gerar CNPJ dummy
                        cnpj_dummy = self._gerar_cnpj_dummy(nome_fundo)
                        
                        if not isinstance(data_ref, datetime):
                            try:
                                if isinstance(data_ref, str):
                                    data_ref = datetime.strptime(data_ref, "%Y-%m-%d")
                            except:
                                data_ref = datetime.now()
                        
                        posicoes.append({
                            "nome_fundo": nome_fundo,
                            "cnpj": cnpj_dummy,
                            "num_cotas": quantidade_cotas,
                            "data": data_ref,
                            "tipo": "previdencia_externa"
                        })
                        print(f"[INFO] Previdência Externa encontrada: {nome_fundo}")
                    
                    linha_atual += 1
                        
        except Exception as e:
            print(f"[ERRO] Erro na Previdência Externa: {str(e)}")
        
        return posicoes
    
    def _processar_aba_renda_fixa(self, file_path):
        """Processa aba Renda Fixa extraindo CDBs, LCIs, etc"""
        posicoes = []
        
        try:
            df = pd.read_excel(file_path, sheet_name="Renda Fixa", header=None)
            print(f"[INFO] Processando Renda Fixa - {len(df)} linhas")
            
            contador_rf = 1
            
            secao_inicio = None
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição > CDB" in cell_value:
                    secao_inicio = i
                    break
            
            if secao_inicio is None:
                print("[AVISO] Seção 'Posição > CDB' não encontrada em Renda Fixa")
                return posicoes
            
            header_row = secao_inicio + 1
            
            if not (isinstance(df.iloc[header_row, 1], str) and "Emissor" in df.iloc[header_row, 1]):
                print("[AVISO] Cabeçalho de Renda Fixa não encontrado")
                return posicoes
            
            for i in range(header_row + 1, len(df)):
                emissor = df.iloc[i, 1] if df.shape[1] > 1 else None
                
                if pd.isna(emissor) or (isinstance(emissor, str) and "Total" in emissor):
                    break
                
                try:
                    codigo_ativo = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else None
                    quantidade = float(df.iloc[i, 9]) if pd.notna(df.iloc[i, 9]) else 0
                    preco = float(df.iloc[i, 10]) if pd.notna(df.iloc[i, 10]) else 0
                    
                    if not codigo_ativo or quantidade == 0:
                        continue
                    
                    cnpj_dummy = f"98.{contador_rf:03d}.001/0001-{contador_rf:02d}"
                    contador_rf += 1
                    
                    nome_fundo = f"{emissor} - {codigo_ativo}"
                    
                    posicoes.append({
                        "nome_fundo": nome_fundo,
                        "cnpj": cnpj_dummy,
                        "num_cotas": quantidade,
                        "data": datetime.now(),
                        "tipo": "renda_fixa",
                        "codigo_ativo": codigo_ativo,
                        "classe_anbima": "renda_fixa",
                        "risco": "baixo",
                        "valor_cota": preco
                    })
                    
                    print(f"[INFO] RF extraída: {nome_fundo[:50]} | Qtd: {quantidade}")
                    
                except Exception as e:
                    print(f"[AVISO] Erro ao processar linha {i} de Renda Fixa: {str(e)}")
                    continue
            
            print(f"[INFO] Total Renda Fixa extraídas: {len(posicoes)}")
            return posicoes
            
        except Exception as e:
            print(f"[ERRO] Erro ao processar aba Renda Fixa: {str(e)}")
            return posicoes
    
    def _processar_aba_renda_variavel(self, file_path):
        """Processa aba Renda Variável extraindo Ações e FIIs"""
        posicoes = []
        
        try:
            df = pd.read_excel(file_path, sheet_name="Renda Variavel", header=None)
            print(f"[INFO] Processando Renda Variável - {len(df)} linhas")
            
            contador_acoes = 1
            contador_fiis = 1
            
            # ===== PROCESSAR AÇÕES =====
            secao_acoes = None
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição > Ações" in cell_value:
                    secao_acoes = i
                    break
            
            if secao_acoes is not None:
                header_acoes = secao_acoes + 1
                
                for i in range(header_acoes + 1, len(df)):
                    codigo = df.iloc[i, 1] if df.shape[1] > 1 else None
                    
                    if pd.isna(codigo) or (isinstance(codigo, str) and "Total" in codigo):
                        break
                    
                    try:
                        nome_acao = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ""
                        quantidade = float(df.iloc[i, 3]) if pd.notna(df.iloc[i, 3]) else 0
                        preco = float(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else 0
                        
                        if quantidade == 0:
                            continue
                        
                        codigo_limpo = str(codigo).replace("*", "").strip()
                        cnpj_dummy = f"97.001.{contador_acoes:03d}/0001-{contador_acoes:02d}"
                        contador_acoes += 1
                        
                        nome_fundo = f"{codigo_limpo} - {nome_acao}"
                        
                        posicoes.append({
                            "nome_fundo": nome_fundo,
                            "cnpj": cnpj_dummy,
                            "num_cotas": quantidade,
                            "data": datetime.now(),
                            "tipo": "acao",
                            "codigo_ativo": codigo_limpo,
                            "classe_anbima": "acoes",
                            "risco": "alto",
                            "valor_cota": preco
                        })
                        
                        print(f"[INFO] Ação extraída: {codigo_limpo} | Qtd: {quantidade}")
                        
                    except Exception as e:
                        print(f"[AVISO] Erro ao processar ação linha {i}: {str(e)}")
                        continue
            
            # ===== PROCESSAR FIIs =====
            secao_fiis = None
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição > Fundos imobiliários" in cell_value:
                    secao_fiis = i
                    break
            
            if secao_fiis is not None:
                header_fiis = secao_fiis + 1
                
                for i in range(header_fiis + 1, len(df)):
                    codigo = df.iloc[i, 1] if df.shape[1] > 1 else None
                    
                    if pd.isna(codigo) or (isinstance(codigo, str) and "Total" in codigo):
                        break
                    
                    try:
                        nome_fii = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ""
                        quantidade = float(df.iloc[i, 3]) if pd.notna(df.iloc[i, 3]) else 0
                        preco = float(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else 0
                        
                        if quantidade == 0:
                            continue
                        
                        codigo_limpo = str(codigo).replace("*", "").strip()
                        cnpj_dummy = f"97.002.{contador_fiis:03d}/0001-{contador_fiis:02d}"
                        contador_fiis += 1
                        
                        nome_fundo = f"{codigo_limpo} - {nome_fii}"
                        
                        posicoes.append({
                            "nome_fundo": nome_fundo,
                            "cnpj": cnpj_dummy,
                            "num_cotas": quantidade,
                            "data": datetime.now(),
                            "tipo": "fii",
                            "codigo_ativo": codigo_limpo,
                            "classe_anbima": "fundos_imobiliarios",
                            "risco": "moderado",
                            "valor_cota": preco
                        })
                        
                        print(f"[INFO] FII extraído: {codigo_limpo} | Qtd: {quantidade}")
                        
                    except Exception as e:
                        print(f"[AVISO] Erro ao processar FII linha {i}: {str(e)}")
                        continue
            
            print(f"[INFO] Total Renda Variável extraídas: {len(posicoes)}")
            return posicoes
            
        except Exception as e:
            print(f"[ERRO] Erro ao processar aba Renda Variável: {str(e)}")
            return posicoes
    
    # =========================================================================
    # FUNÇÕES AUXILIARES
    # =========================================================================
    
    def _gerar_cnpj_dummy(self, nome_fundo):
        """Gera CNPJ dummy baseado no nome normalizado do fundo"""
        nome_normalizado = nome_fundo.upper()
        nome_normalizado = re.sub(r'[*\s\-_.]+', '', nome_normalizado)  
        nome_normalizado = re.sub(r'[^A-Z0-9]', '', nome_normalizado)
        
        print(f"[DEBUG] Nome original: '{nome_fundo}' → Normalizado: '{nome_normalizado}'")
        
        hash_object = hashlib.md5(nome_normalizado.encode())
        hash_hex = hash_object.hexdigest()
        
        numeros = ''.join([str(int(c, 16) % 10) for c in hash_hex[:12]])
        cnpj_dummy = f"99.{numeros[:3]}.{numeros[3:6]}/0001-{numeros[6:8]}"
        
        print(f"[DEBUG] CNPJ dummy gerado: {cnpj_dummy}")
        return cnpj_dummy
    
    def _deduplificar_posicoes(self, posicoes):
        """Remove posições duplicadas baseado em CNPJ"""
        posicoes_unicas = {}
        
        for pos in posicoes:
            cnpj_norm = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')
            
            if cnpj_norm in posicoes_unicas:
                pos_existente = posicoes_unicas[cnpj_norm]
                
                prioridades = {'fundo_normal': 3, 'previdencia_individual': 2, 'previdencia_externa': 1}
                
                prioridade_atual = prioridades.get(pos.get('tipo', ''), 0)
                prioridade_existente = prioridades.get(pos_existente.get('tipo', ''), 0)
                
                if prioridade_atual > prioridade_existente:
                    posicoes_unicas[cnpj_norm] = pos
                    print(f"[INFO] Substituindo posição duplicada: {pos['nome_fundo']}")
            else:
                posicoes_unicas[cnpj_norm] = pos
        
        return list(posicoes_unicas.values())