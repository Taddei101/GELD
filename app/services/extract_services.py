import pandas as pd
from sqlalchemy.orm import Session
import os, requests, zipfile
from io import StringIO
from app.models.geld_models import create_session, InfoFundo, PosicaoFundo, RiscoEnum, StatusFundoEnum
from app.services.global_services import GlobalServices
from datetime import datetime
from flask import flash

#quem vai usar: dashboard vai mostrar IPCA e data da atualização
##info_fundos vao ser atualizados com vcm valor da cota e informações da lamina

#definir a classe

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
    def extracao_cvm(self, ano, mes):
        """Extrai dados de fundos da CVM"""
        url = f'https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ano}{mes}.zip'
        
        # Cria pasta temporária se não existir
        temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        zip_path = os.path.join(temp_dir, f"inf_diario_fi_{ano}{mes}.zip")
        
        try:
            # Faz download do arquivo
            response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"Erro ao baixar dados de FI da CVM. Status: {response.status_code}")
                return pd.DataFrame()
                
            # Salva o arquivo zip
            with open(zip_path, "wb") as arquivo_cvm:
                arquivo_cvm.write(response.content)
            
            # Extrai e lê o CSV
            with zipfile.ZipFile(zip_path) as arquivo_zip:
                df = pd.read_csv(arquivo_zip.open(arquivo_zip.namelist()[0]), sep=";", encoding='ISO-8859-1')
                
            return df
            
        except Exception as e:
            print(f"Erro ao processar arquivo de FI: {str(e)}")
            return pd.DataFrame()
            
        finally:
            # Limpa o arquivo temporário
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except:
                pass

#INFO DOS FUNDOS CVM
    def extracao_cvm_info(self, cnpj):
        """Pega um CNPJ e devolve uma lista com 'DENOM_SOCIAL','CLASSE_ANBIMA','PR_CIA_MIN', 'FUNDO_COTAS'"""
        try:
                    
            # URL do arquivo CSV
            url = "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
            
            flash(f"Iniciando download do CSV da CVM para CNPJ {cnpj}...","info")
            
            # Fazer a requisição com timeout
            response = requests.get(url, timeout=30)  # 30 segundos de timeout
            
            if response.status_code != 200:
                print(f"Erro ao baixar dados da CVM: Status code {response.status_code}")
                return None
            
            print("Download concluído. Processando CSV...")
            
            # Usar os dados já baixados em vez de fazer outro download
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data, sep=';', encoding='latin1', dtype=str)
            
            # Normalizar CNPJs para comparação
            cnpj_norm = cnpj.replace('.', '').replace('/', '').replace('-', '')
            df['CNPJ_NORM'] = df['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '')
            
            # Filtrar pelo CNPJ normalizado
            resultado = df[df['CNPJ_NORM'] == cnpj_norm]
            
            if resultado.empty:
                flash(f"Nenhum fundo encontrado com o CNPJ: {cnpj}","error")
                return None
            
            print(f"Fundo encontrado: {resultado['DENOM_SOCIAL'].iloc[0]}")
            return resultado[['DENOM_SOCIAL','CLASSE_ANBIMA','PR_CIA_MIN', 'FUNDO_COTAS']].iloc[0]
            
        except requests.Timeout:
            print(f"Timeout ao baixar dados da CVM após 30 segundos")
            return None
        except Exception as e:
            print(f"Erro ao buscar informação do fundo pelo CNPJ: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


    #INFO FUNDOS DE UMA LISTA de CNPJs
    def extracao_cvm_info_batch(self, cnpjs):
                
        url = "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
                
        flash(f"Baixando CSV da CVM para {len(cnpjs)} CNPJs...","info")
        df = pd.read_csv(url, sep=';', encoding='latin1', dtype=str)
        
        # Normalizar os CNPJs (remover pontuação) para facilitar a correspondência
        df['CNPJ_NORMALIZADO'] = df['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '')
                
        normalized_cnpjs = [cnpj.replace('.', '').replace('/', '').replace('-', '') for cnpj in cnpjs]
        
        # Criar dicionário para armazenar os resultados
        result_dict = {}
        
        # Filtrar o DataFrame apenas uma vez para todos os CNPJs
        filtered_df = df[df['CNPJ_NORMALIZADO'].isin(normalized_cnpjs)]
        
        # Processar os resultados filtrados
        for cnpj_norm in normalized_cnpjs:
            
            fund_data = filtered_df[filtered_df['CNPJ_NORMALIZADO'] == cnpj_norm]
            
            if not fund_data.empty:
                
                fund_data = fund_data.sort_values(by='DT_COMPTC', ascending=False).iloc[0]
                original_cnpj = cnpjs[normalized_cnpjs.index(cnpj_norm)]
                result_dict[original_cnpj] = fund_data
        
        return result_dict
    





