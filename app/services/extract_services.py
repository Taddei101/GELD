import pandas as pd
from sqlalchemy.orm import Session
import os, requests, zipfile
from io import StringIO
from app.models.geld_models import create_session, InfoFundo, PosicaoFundo, RiscoEnum, StatusFundoEnum
from app.services.global_services import GlobalServices
from datetime import datetime, timedelta
# REMOVIDO: from flask import flash - não deve ser usado aqui

class ExtractServices:
    def __init__(self, db:Session = None):
        self.db=db

    #IPCA
    def extracao_bcb(self, codigo, data_inicio, data_fim):
        """Extrai dados do Banco Central do Brasil"""
        try:
            url = f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={data_inicio}&dataFinal={data_fim}'
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"Erro ao acessar API do BCB. Status: {response.status_code}")
                return pd.DataFrame()
            
            df = pd.read_json(StringIO(response.text))
            
            df.set_index('data', inplace=True)
            df.index = pd.to_datetime(df.index, dayfirst=True)
            return df
    
        except Exception as e:
            print(f"Erro ao extrair dados do BCB: {str(e)}")
            return pd.DataFrame()

    #VALOR DA COTA  
    def extracao_cvm(self):
        """
        Extrai dados de cotas da CVM
        Tenta mês atual primeiro, se não disponível tenta mês anterior
        
        Returns:
            DataFrame com colunas: CNPJ_FUNDO_CLASSE, VL_QUOTA, DT_COMPTC, DENOM_SOCIAL
        """
        from datetime import datetime, timedelta
        import zipfile
        
        hoje = datetime.now()
        
        # Tentar mês atual primeiro
        tentativas = [
            (hoje.year, hoje.month, "atual"),
            # Mês anterior
            ((hoje.replace(day=1) - timedelta(days=1)).year, 
            (hoje.replace(day=1) - timedelta(days=1)).month, 
            "anterior")
        ]
        
        temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        for ano, mes, label in tentativas:
            ano_str = str(ano)
            mes_str = f"{mes:02d}"
            
            url = f'https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ano_str}{mes_str}.zip'
            zip_path = os.path.join(temp_dir, f"inf_diario_fi_{ano_str}{mes_str}.zip")
            
            try:
                print(f"Baixando dados de {mes_str}/{ano_str} (mês {label})...")
                
                response = requests.get(url, timeout=30)
                
                if response.status_code == 404:
                    print(f"❌ {mes_str}/{ano_str} não disponível")
                    continue  # Tenta próximo mês
                
                if response.status_code != 200:
                    print(f"Erro HTTP {response.status_code}")
                    continue
                
                # Salvar ZIP
                with open(zip_path, "wb") as arquivo_cvm:
                    arquivo_cvm.write(response.content)
                
                # Extrair e ler CSV
                with zipfile.ZipFile(zip_path) as arquivo_zip:
                    df = pd.read_csv(arquivo_zip.open(arquivo_zip.namelist()[0]), sep=";", encoding='ISO-8859-1')
                
                print(f"✅ {len(df)} registros de {mes_str}/{ano_str}")
                return df
                
            except Exception as e:
                print(f"Erro ao processar {mes_str}/{ano_str}: {str(e)}")
                continue
                
            finally:
                # Limpar arquivo temporário
                try:
                    if os.path.exists(zip_path):
                        os.remove(zip_path)
                except:
                    pass
    
        # Se chegou aqui, nenhum mês funcionou
        print("❌ Não foi possível baixar dados da CVM")
        return pd.DataFrame()

    # NOVA FUNÇÃO INFO DOS FUNDOS CVM - SUBSTITUIR A ANTIGA
    def extracao_cvm_info(self, cnpj, max_meses_anteriores=3):
        """
        Busca informações do fundo por CNPJ de forma inteligente.
        Tenta mês atual, depois meses anteriores até encontrar.
        
        Args:
            cnpj: CNPJ normalizado (só números)
            max_meses_anteriores: Quantos meses tentar (padrão: 3)
        
        Returns:
            tuple: (dados_fundo, mes_encontrado) ou (None, None)
        """
        hoje = datetime.now()
        cnpj_norm = cnpj.replace('.', '').replace('/', '').replace('-', '')
        
        print(f"[INFO] Buscando fundo CNPJ: {cnpj} em até {max_meses_anteriores} meses")
        
        # Tentar diferentes meses, começando pelo atual
        for meses_atras in range(0, max_meses_anteriores):
            try:
                # Calcular data de busca
                if meses_atras == 0:
                    data_busca = hoje
                    mes_label = "atual"
                else:
                    # Voltar meses
                    data_busca = hoje.replace(day=1) - timedelta(days=1)
                    for _ in range(meses_atras - 1):
                        data_busca = data_busca.replace(day=1) - timedelta(days=1)
                    mes_label = f"{data_busca.month:02d}/{data_busca.year}"
                
                print(f"[INFO] Tentativa {meses_atras + 1}: buscando no mês {mes_label}...")
                
                # Fazer a requisição
                url = "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
                
                # Timeout progressivo: 30s, 45s, 60s...
                timeout = 30 + (meses_atras * 15)
                response = requests.get(url, timeout=timeout)
                
                if response.status_code != 200:
                    print(f"[WARN] Erro HTTP {response.status_code} para mês {mes_label}")
                    continue
                
                # Processar CSV
                csv_data = StringIO(response.text)
                df = pd.read_csv(csv_data, sep=';', encoding='latin1', dtype=str)
                
                # Normalizar CNPJs
                df['CNPJ_NORM'] = df['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '')
                
                # Buscar o fundo
                resultado = df[df['CNPJ_NORM'] == cnpj_norm]
                
                if not resultado.empty:
                    # Encontrou! Pegar o registro mais recente
                    fundo_data = resultado.sort_values(by='DT_COMPTC', ascending=False).iloc[0]
                    
                    print(f"[SUCCESS] Fundo encontrado no mês {mes_label}: {fundo_data['DENOM_SOCIAL']}")
                    
                    
                    dados_dict = {
                        'DENOM_SOCIAL': fundo_data['DENOM_SOCIAL'],
                        'CLASSE_ANBIMA': fundo_data['CLASSE_ANBIMA'],
                        'PR_CIA_MIN': fundo_data['PR_CIA_MIN'],
                        'FUNDO_COTAS': fundo_data.get('FUNDO_COTAS', 'N')
                    }
                    return dados_dict
                    
                else:
                    print(f"[INFO] Fundo não encontrado no mês {mes_label}")
                    
            except requests.Timeout:
                print(f"[WARN] Timeout ({timeout}s) ao buscar dados do mês {mes_label}")
                continue
            except Exception as e:
                print(f"[ERROR] Erro ao processar mês {mes_label}: {str(e)}")
                continue
        
        print(f"[ERROR] Fundo CNPJ {cnpj} não encontrado em nenhum dos {max_meses_anteriores} meses tentados")
        return None

    #INFO FUNDOS DE UMA LISTA de CNPJs
    def extracao_cvm_info_batch(self, cnpjs):
        url = "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
        
        print(f"Baixando CSV da CVM para {len(cnpjs)} CNPJs...")
        
        try:
            df = pd.read_csv(url, sep=';', encoding='latin1', dtype=str)
            
            # ADICIONANDO DEBUG
            print(f"[DEBUG] Total de registros no CSV: {len(df)}")
            print(f"[DEBUG] Colunas disponíveis: {df.columns.tolist()}")
            print(f"[DEBUG] Primeiros 3 CNPJs do arquivo: {df['CNPJ_FUNDO_CLASSE'].head(3).tolist()}")
            
            # Normalizar os CNPJs (remover pontuação) para facilitar a correspondência
            df['CNPJ_NORMALIZADO'] = df['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '')
            
            normalized_cnpjs = [cnpj.replace('.', '').replace('/', '').replace('-', '') for cnpj in cnpjs]
            
            print(f"[DEBUG] CNPJs procurados: {cnpjs}")
            print(f"[DEBUG] CNPJs normalizados: {normalized_cnpjs}")
            
            # Criar dicionário para armazenar os resultados
            result_dict = {}
            
            # DEBUG: Verificar cada CNPJ individualmente
            for i, cnpj_original in enumerate(cnpjs):
                cnpj_norm = normalized_cnpjs[i]
                print(f"\n[DEBUG] Procurando: {cnpj_original} -> normalizado: {cnpj_norm}")
                
                # Busca exata
                matches = df[df['CNPJ_NORMALIZADO'] == cnpj_norm]
                print(f"[DEBUG] Matches encontrados: {len(matches)}")
                
                if len(matches) > 0:
                    print(f"[DEBUG] ENCONTRADO: {matches['DENOM_SOCIAL'].iloc[0]}")
                    # Adicionar ao resultado
                    fund_data = matches.sort_values(by='DT_COMPTC', ascending=False).iloc[0]
                    result_dict[cnpj_original] = fund_data
                else:
                    # Busca similar para debug
                    similar = df[df['CNPJ_NORMALIZADO'].str.contains(cnpj_norm[:8], na=False)]
                    print(f"[DEBUG] CNPJs similares (primeiros 8 dígitos): {len(similar)}")
                    if len(similar) > 0:
                        print(f"[DEBUG] Exemplos similares:")
                        for idx, row in similar.head(3).iterrows():
                            print(f"  - {row['CNPJ_FUNDO_CLASSE']} | {row['DENOM_SOCIAL']}")
            
            print(f"\n[DEBUG] Total de fundos encontrados: {len(result_dict)}")
            return result_dict
            
        except Exception as e:
            print(f"[DEBUG] Erro na requisição: {type(e).__name__}: {e}")
            return {}