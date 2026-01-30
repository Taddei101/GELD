"""
Serviço para processar arquivos Excel do Advisor
Extrai posições da aba "Posição"
"""

import pandas as pd
from datetime import datetime
from app.models.geld_models import RiscoEnum, SubtipoRiscoEnum


class AdvisorExtractService:
    def __init__(self, db):
        self.db = db
    
    def processar_arquivo_advisor(self, file_path, cliente_id):
        """
        Processa arquivo Excel do Advisor
        
        Args:
            file_path: Caminho do arquivo Excel
            cliente_id: ID do cliente
            
        Returns:
            tuple: (lista_posicoes, log_processamento)
        """
        posicoes = []
        log = {
            'total': 0,
            'por_classe': {},
            'erros': []
        }
        
        try:
            print(f"[INFO] Processando arquivo Advisor para cliente {cliente_id}")
            
            # Extrair posições da aba
            posicoes = self._extrair_aba_posicao(file_path)
            
            # Estatísticas
            log['total'] = len(posicoes)
            
            for pos in posicoes:
                classe = pos.get('classe_anbima', 'outros')
                log['por_classe'][classe] = log['por_classe'].get(classe, 0) + 1
            
            print(f"[INFO] Total de posições extraídas: {len(posicoes)}")
            for classe, count in log['por_classe'].items():
                print(f"[INFO]   - {classe}: {count}")
            
            return posicoes, log
            
        except Exception as e:
            log['erros'].append(str(e))
            print(f"[ERRO] Erro ao processar arquivo Advisor: {str(e)}")
            return posicoes, log
    
    def _extrair_aba_posicao(self, file_path):
        """
        Extrai dados da aba 'Posição'
        
        Estrutura das colunas:
        0: Classe (classe_anbima)
        1: Ativo (nome_fundo)
        2: DataUlt (data de atualização)
        3: Quantidade (cotas)
        4: Preco (valor_cota)
        5: SaldoAnterior (saldo_anterior)
        6: Movimento
        7: SaldoBruto (saldo_bruto)
        
        Returns:
            list: Lista de dicionários com dados das posições
        """
        posicoes = []
        
        try:
            # Ler arquivo Excel para listar abas disponíveis
            excel_file = pd.ExcelFile(file_path)
            available_sheets = excel_file.sheet_names
            
            print(f"[INFO] Total de abas no arquivo: {len(available_sheets)}")
            print(f"[INFO] Abas disponíveis: {available_sheets}")
            
            # Buscar aba "Posição" (com variações) OU pela posição (índice 11)
            sheet_name = None
            sheet_index = None
            
            # MÉTODO 1: Tentar por nome
            possible_names = ['Posição', 'Posicao', 'POSIÇÃO', 'POSICAO', 'posição', 'posicao']
            
            for name in possible_names:
                if name in available_sheets:
                    sheet_name = name
                    break
            
            # Busca case-insensitive se não encontrou exato
            if not sheet_name:
                for available in available_sheets:
                    if available.lower().strip() in [n.lower() for n in possible_names]:
                        sheet_name = available
                        break
            
            # MÉTODO 2: Se não encontrou por nome, tentar pelo índice (aba 12 = índice 11)
            if not sheet_name:
                print("[WARN] Não encontrou por nome, tentando pelo índice...")
                # Procurar aba que contenha "posi" no nome (case insensitive)
                for idx, name in enumerate(available_sheets):
                    if 'posi' in name.lower():
                        sheet_index = idx
                        sheet_name = name
                        print(f"[INFO] Encontrou aba similar no índice {idx}: '{name}'")
                        break
            
            if not sheet_name and not sheet_index:
                raise ValueError(f"Aba 'Posição' não encontrada. Abas disponíveis: {available_sheets}")
            
            print(f"[INFO] Usando aba: '{sheet_name}'" + (f" (índice {sheet_index})" if sheet_index is not None else ""))
            
            # Ler aba encontrada
            if sheet_index is not None:
                df = pd.read_excel(file_path, sheet_name=sheet_index, header=0)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)
            
            print(f"[INFO] Aba '{sheet_name}' - {len(df)} linhas x {len(df.columns)} colunas")
            print(f"[INFO] Colunas: {df.columns.tolist()[:5]}...")  # Mostrar primeiras 5 colunas
            
            # Processar cada linha
            for idx, row in df.iterrows():
                try:
                    # Validar se linha tem dados mínimos
                    if pd.isna(row.iloc[1]) or pd.isna(row.iloc[3]):
                        continue
                    
                    # Extrair dados
                    classe_raw = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else "Outros"
                    nome_ativo = str(row.iloc[1]).strip()
                    data_ult = row.iloc[2] if pd.notna(row.iloc[2]) else datetime.now()
                    quantidade = self._parse_numero_br(row.iloc[3])
                    preco = self._parse_numero_br(row.iloc[4]) if pd.notna(row.iloc[4]) else 0.0
                    saldo_anterior = self._parse_numero_br(row.iloc[5]) if pd.notna(row.iloc[5]) else 0.0
                    saldo_bruto = self._parse_numero_br(row.iloc[7]) if pd.notna(row.iloc[7]) else 0.0
                    
                    # Normalizar classe
                    classe_normalizada = self._normalizar_classe(classe_raw)
                    
                    # Determinar risco
                    risco, subtipo_risco = self._determinar_risco(classe_normalizada)
                    
                    # Converter data
                    if not isinstance(data_ult, datetime):
                        try:
                            if isinstance(data_ult, str):
                                # Formato: dd/mm/yyyy
                                data_ult = datetime.strptime(data_ult, "%d/%m/%Y")
                            else:
                                data_ult = datetime.now()
                        except:
                            data_ult = datetime.now()
                    
                    # Montar dicionário da posição
                    posicao = {
                        "nome_fundo": nome_ativo,
                        "cnpj": None,  # Advisor não fornece CNPJ
                        "classe_anbima": classe_normalizada,
                        "num_cotas": quantidade,
                        "valor_cota": preco,
                        "data": data_ult,
                        "risco": risco,
                        "subtipo_risco": subtipo_risco,
                        "saldo_anterior": saldo_anterior,
                        "saldo_bruto": saldo_bruto,
                        "tipo": "advisor"
                    }
                    
                    posicoes.append(posicao)
                    
                    print(f"[INFO] Extraído: {nome_ativo[:50]} | Classe: {classe_normalizada} | Qtd: {quantidade}")
                    
                except Exception as e:
                    print(f"[AVISO] Erro ao processar linha {idx}: {str(e)}")
                    continue
            
            return posicoes
            
        except Exception as e:
            print(f"[ERRO] Erro ao ler aba Posição: {str(e)}")
            raise e
    
    def _parse_numero_br(self, valor):
        """
        Converte número para float
        Formato do Excel Advisor: Internacional (vírgula=milhar, ponto=decimal)
        Ex: '2,542.69915361' → 2542.69915361
        """
        if pd.isna(valor):
            return 0.0
        
        if isinstance(valor, (int, float)):
            return float(valor)
        
        # Se vier como string, remover vírgulas (separador de milhar) e converter
        try:
            valor_str = str(valor).replace(',', '')  # Remove vírgula de milhar
            return float(valor_str)
        except:
            print(f"[WARN] Não foi possível converter '{valor}' para número")
            return 0.0
    
    def _normalizar_classe(self, classe_raw):
        """
        Normaliza nome da classe ANBIMA
        Remove espaços e padroniza nomenclatura
        """
        classe = classe_raw.strip().lower()
        
        # Mapeamento de classes comuns
        mapeamento = {
            'fundos de renda fixa': 'Renda Fixa',
            'renda fixa': 'Renda Fixa',
            'fundos de ações': 'Ações',
            'ações': 'Ações',
            'acoes': 'Ações',
            'multimercado': 'Multimercado',
            'fundos multimercado': 'Multimercado',
            'cambial': 'Cambial',
            'fundos cambiais': 'Cambial',
        }
        
        return mapeamento.get(classe, classe_raw.strip())
    
    def _determinar_risco(self, classe_anbima):
        """
        Determina nível de risco baseado na classe ANBIMA
        
        Regras:
        - Renda Fixa → baixo (subtipo: rfx)
        - Ações → alto
        - Multimercado e outros → moderado
        
        Returns:
            tuple: (RiscoEnum, SubtipoRiscoEnum ou None)
        """
        classe_lower = classe_anbima.lower()
        
        # Renda Fixa → Baixo
        if 'renda fixa' in classe_lower or 'rf' in classe_lower:
            return RiscoEnum.baixo, SubtipoRiscoEnum.rfx
        
        # Ações → Alto
        if 'ações' in classe_lower or 'acoes' in classe_lower or 'acao' in classe_lower:
            return RiscoEnum.alto, None
        
        # Multimercado e resto → Moderado
        return RiscoEnum.moderado, None