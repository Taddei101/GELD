#services extract
import pandas as pd
from sqlalchemy.orm import Session
import os, requests, zipfile
from io import StringIO
from app.models.geld_models import create_session, InfoFundo, PosicaoFundo, RiscoEnum, StatusFundoEnum
from app.services.global_services import GlobalServices
from datetime import datetime, timedelta
from flask import flash

#quem vai usar: dashboard vai mostrar IPCA e data da atualização
##info_fundos vao ser atualizados com vcm valor da cota e informações da lamina

#definir a classe

class ExtractServices:
   # No __init__ da sua classe, adicione apenas estas linhas:
    def __init__(self, db: Session = None):
        self.db = db
        # Credenciais ANBIMA
        self.anbima_client_id = "KIPU2wewJpEY"
        self.anbima_client_secret = "xWuRtFekHlUt"
        self.anbima_base_url = "https://api.anbima.com.br"
        self.anbima_access_token = None
        self.anbima_token_expires_at = None

    # MÉTODOS PRIVADOS ANBIMA (adicione à sua classe)
    def _get_anbima_token(self):
        """Obtém token de acesso da ANBIMA"""
        try:
            import base64
            credentials = f"{self.anbima_client_id}:{self.anbima_client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            data = {"grant_type": "client_credentials"}
            
            response = requests.post(f"{self.anbima_base_url}/oauth/access-token", 
                                headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.anbima_access_token = token_data["access_token"]
                
                expires_in = token_data.get("expires_in", 3600)
                self.anbima_token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                print(f"Token ANBIMA obtido com sucesso. Expira em: {self.anbima_token_expires_at}")
                return self.anbima_access_token
            else:
                print(f"Erro ao obter token ANBIMA: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Erro na requisição do token ANBIMA: {e}")
            return None

    def _is_anbima_token_valid(self):
        """Verifica se o token ANBIMA ainda é válido"""
        if not self.anbima_access_token or not self.anbima_token_expires_at:
            return False
        return datetime.now() < (self.anbima_token_expires_at - timedelta(minutes=5))

    def _ensure_anbima_token(self):
        """Garante que temos um token ANBIMA válido"""
        if not self._is_anbima_token_valid():
            return self._get_anbima_token()
        return self.anbima_access_token

    # MÉTODO PRINCIPAL - EXTRAÇÃO ANBIMA
    def extracao_anbima(self, endpoint, params=None):
        """
        Método principal para extrair dados da ANBIMA
        Similar aos seus métodos extracao_bcb e extracao_cvm
        """
        try:
            if not self._ensure_anbima_token():
                print("Erro: Não foi possível obter token ANBIMA válido")
                return pd.DataFrame()
            
            headers = {
                "Authorization": f"Bearer {self.anbima_access_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.anbima_base_url}{endpoint}"
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"Erro ao acessar API ANBIMA. Status: {response.status_code}")
                print(f"Resposta: {response.text}")
                return pd.DataFrame()
            
            data = response.json()
            
            # Converte para DataFrame
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Se retornar um dict, normaliza para DataFrame
                df = pd.json_normalize(data)
            else:
                print("Formato de resposta inesperado da ANBIMA")
                return pd.DataFrame()
            
            print(f"Dados ANBIMA extraídos com sucesso: {len(df)} registros")
            return df
            
        except Exception as e:
            print(f"Erro ao extrair dados da ANBIMA: {str(e)}")
            return pd.DataFrame()

    # MÉTODOS ESPECÍFICOS PARA DIFERENTES DADOS
    def extracao_anbima_fundos(self, data_inicio=None, data_fim=None):
        """Extrai dados de fundos da ANBIMA"""
        params = {}
        if data_inicio:
            params['dataInicio'] = data_inicio
        if data_fim:
            params['dataFim'] = data_fim
        
        return self.extracao_anbima("/feed/fundos", params)

    def extracao_anbima_indices(self, data_inicio=None, data_fim=None):
        """Extrai índices da ANBIMA"""
        params = {}
        if data_inicio:
            params['dataInicio'] = data_inicio
        if data_fim:
            params['dataFim'] = data_fim
        
        df = self.extracao_anbima("/indices/v1/indices", params)
        
        # Ajusta formato similar ao BCB se tiver coluna de data
        if not df.empty and 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'], dayfirst=True)
            df.set_index('data', inplace=True)
        
        return df

    def extracao_anbima_fundo_cnpj(self, cnpj):
        """
        Busca informações de um fundo específico pelo CNPJ
        Similar ao seu método extracao_cvm_info
        """
        try:
            cnpj_normalizado = cnpj.replace('.', '').replace('/', '').replace('-', '')
            
            params = {'cnpj': cnpj_normalizado}
            df = self.extracao_anbima("/fundos/v1/fundos", params)
            
            if df.empty:
                print(f"Nenhum fundo encontrado na ANBIMA para CNPJ: {cnpj}")
                return None
            
            # Retorna a primeira linha como Series (similar ao seu padrão CVM)
            resultado = df.iloc[0]
            print(f"Fundo encontrado na ANBIMA: {resultado.get('nome', 'N/A')}")
            return resultado
            
        except Exception as e:
            print(f"Erro ao buscar fundo por CNPJ na ANBIMA: {str(e)}")
            return None

    def extracao_anbima_fundos_batch(self, cnpjs):
        """
        Busca informações de múltiplos fundos
        Similar ao seu método extracao_cvm_info_batch
        """
        try:
            result_dict = {}
            
            print(f"Processando {len(cnpjs)} CNPJs na ANBIMA...")
            
            for cnpj in cnpjs:
                try:
                    fundo_data = self.extracao_anbima_fundo_cnpj(cnpj)
                    if fundo_data is not None:
                        result_dict[cnpj] = fundo_data
                    
                    # Pausa para não sobrecarregar a API
                    import time
                    time.sleep(0.2)
                    
                except Exception as e:
                    print(f"Erro ao processar CNPJ {cnpj}: {e}")
                    continue
            
            print(f"Processamento concluído: {len(result_dict)} fundos encontrados de {len(cnpjs)}")
            return result_dict
            
        except Exception as e:
            print(f"Erro no processamento batch ANBIMA: {str(e)}")
            return {}

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
    
