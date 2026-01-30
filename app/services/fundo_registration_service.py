"""
Serviço para cadastro automático de fundos via CVM
Responsável por registrar novos fundos no sistema, seja via API CVM ou cadastro direto
"""

from datetime import datetime
from app.models.geld_models import InfoFundo, RiscoEnum, SubtipoRiscoEnum, StatusFundoEnum
from app.services.extract_services import ExtractServices
from app.services.global_services import GlobalServices


class FundoRegistrationService:
    """
    Service para cadastro automático de fundos
    
    Responsabilidades:
    - Verificar CNPJs existentes no banco
    - Separar CNPJs reais de CNPJs dummy
    - Buscar informações na CVM
    - Cadastrar fundos via CVM
    - Cadastrar fundos com CNPJs dummy (previdência, RF, RV)
    - Retornar mapeamento atualizado de fundos
    """
    
    def __init__(self, db):
        """
        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.global_services = GlobalServices(db)
        self.extract_services = ExtractServices(db)
    
    def cadastrar_fundos_automaticamente(self, posicoes):
        """
        Cadastra automaticamente fundos que não existem no banco
        
        Args:
            posicoes: Lista de posições extraídas (cada posição tem 'cnpj' e dados do fundo)
            
        Returns:
            dict: Mapeamento {cnpj_normalizado: fundo_id} de TODOS os fundos (novos + existentes)
        """
        # 1. Verificar fundos existentes
        existing_funds = self._get_existing_funds()
        print(f"[INFO] Fundos já cadastrados no banco: {len(existing_funds)}")
        
        # 2. Identificar novos CNPJs
        new_cnpjs = self._identificar_novos_cnpjs(posicoes, existing_funds)
        
        if not new_cnpjs:
            print("[INFO] Todos os CNPJs já estão cadastrados")
            return existing_funds
        
        print(f"[INFO] CNPJs novos a cadastrar: {len(new_cnpjs)}")
        
        # 3. Separar CNPJs reais dos dummy
        cnpjs_reais, cnpjs_dummy = self._separar_cnpjs_reais_e_dummy(new_cnpjs)
        
        # 4. Cadastrar CNPJs reais via CVM
        if cnpjs_reais:
            print(f"[INFO] Cadastrando {len(cnpjs_reais)} fundos via CVM...")
            self._cadastrar_fundos_cvm(cnpjs_reais, existing_funds)
        
        # 5. Cadastrar CNPJs dummy
        if cnpjs_dummy:
            print(f"[INFO] Cadastrando {len(cnpjs_dummy)} fundos com CNPJ dummy...")
            self._cadastrar_fundos_dummy(cnpjs_dummy, posicoes, existing_funds)
        
        # 6. Atualizar lista de fundos existentes
        existing_funds = self._get_existing_funds()
        print(f"[INFO] Total de fundos disponíveis no banco: {len(existing_funds)}")
        
        return existing_funds
    
    # =========================================================================
    # MÉTODOS AUXILIARES
    # =========================================================================
    
    def _get_existing_funds(self):
        """
        Retorna dicionário de fundos existentes no banco
        
        Returns:
            dict: {cnpj_normalizado: fundo_id}
        """
        existing_funds = {}
        
        for fundo in self.db.query(InfoFundo).all():
            if fundo.cnpj:
                cnpj_normalizado = self._normalizar_cnpj(fundo.cnpj)
                existing_funds[cnpj_normalizado] = fundo.id
        
        return existing_funds
    
    def _identificar_novos_cnpjs(self, posicoes, existing_funds):
        """
        Identifica CNPJs que ainda não existem no banco
        
        Args:
            posicoes: Lista de posições
            existing_funds: Dicionário de fundos existentes
            
        Returns:
            list: Lista de CNPJs novos (sem duplicatas)
        """
        new_cnpjs = []
        
        for pos in posicoes:
            cnpj = pos.get('cnpj')
            if cnpj:
                cnpj_normalizado = self._normalizar_cnpj(cnpj)
                if cnpj_normalizado not in existing_funds:
                    new_cnpjs.append(cnpj)
        
        # Remover duplicatas
        return list(set(new_cnpjs))
    
    def _separar_cnpjs_reais_e_dummy(self, cnpjs):
        """
        Separa CNPJs reais (a buscar na CVM) de CNPJs dummy (cadastro direto)
        
        CNPJs dummy começam com:
        - DUMMY- (formato explícito)
        - 99.xxx (Previdência)
        - 98.xxx (Renda Fixa)
        - 97.xxx (Renda Variável)
        
        Args:
            cnpjs: Lista de CNPJs
            
        Returns:
            tuple: (cnpjs_reais, cnpjs_dummy)
        """
        cnpjs_reais = []
        cnpjs_dummy = []
        
        for cnpj in cnpjs:
            # Verificar se é CNPJ dummy
            if (cnpj.startswith('DUMMY-') or 
                cnpj.startswith('99.') or 
                cnpj.startswith('98.') or 
                cnpj.startswith('97.')):
                cnpjs_dummy.append(cnpj)
            else:
                cnpjs_reais.append(cnpj)
        
        print(f"[INFO] CNPJs reais: {len(cnpjs_reais)}")
        print(f"[INFO] CNPJs dummy: {len(cnpjs_dummy)}")
        
        return cnpjs_reais, cnpjs_dummy
    
    def _cadastrar_fundos_cvm(self, cnpjs_reais, existing_funds):
        """
        Busca informações na CVM e cadastra fundos
        
        Args:
            cnpjs_reais: Lista de CNPJs a buscar na CVM
            existing_funds: Dicionário de fundos existentes (será atualizado in-place)
        """
        funds_info = {}
        
        # Buscar informações na CVM
        for cnpj in cnpjs_reais:
            try:
                info = self.extract_services.extracao_cvm_info(cnpj)
                if info is not None:
                    funds_info[cnpj] = info
                    print(f"[INFO] Dados CVM encontrados: {cnpj}")
                else:
                    print(f"[AVISO] CNPJ não encontrado na CVM: {cnpj}")
            except Exception as e:
                print(f"[ERRO] Erro ao buscar CNPJ {cnpj} na CVM: {str(e)}")
        
        # Cadastrar fundos encontrados na CVM
        for cnpj, info in funds_info.items():
            try:
                self._cadastrar_fundo_cvm(cnpj, info, existing_funds)
            except Exception as e:
                print(f"[ERRO] Erro ao cadastrar fundo {cnpj}: {str(e)}")
        
        # Cadastrar fundos não encontrados na CVM como genéricos
        missing_cnpjs = [cnpj for cnpj in cnpjs_reais if cnpj not in funds_info]
        for cnpj in missing_cnpjs:
            try:
                self._cadastrar_fundo_generico(cnpj, existing_funds)
            except Exception as e:
                print(f"[ERRO] Erro ao cadastrar fundo genérico {cnpj}: {str(e)}")
    
    def _cadastrar_fundo_cvm(self, cnpj, info, existing_funds):
        """
        Cadastra um fundo usando dados da CVM
        
        Args:
            cnpj: CNPJ do fundo
            info: Dicionário com informações da CVM
            existing_funds: Dicionário de fundos existentes (será atualizado)
        """
        # Validar que info é um dicionário
        if not isinstance(info, dict):
            print(f"[AVISO] Dados inválidos para CNPJ {cnpj}: {type(info)}")
            return
        
        # Extrair dados
        nome_fundo = info.get('DENOM_SOCIAL', f'Fundo {cnpj}')
        
        # Validar classe_anbima
        classe_anbima = info.get('CLASSE_ANBIMA', '')
        if not isinstance(classe_anbima, str):
            classe_anbima = ''
        
        # Validar mov_min
        try:
            pr_cia_min = info.get('PR_CIA_MIN', 'None')
            mov_min = float(pr_cia_min) if pr_cia_min != 'None' else None
        except (ValueError, TypeError):
            mov_min = None
        
        # Criar fundo
        novo_fundo = self.global_services.create_classe(
            InfoFundo,
            nome_fundo=nome_fundo,
            cnpj=cnpj,
            classe_anbima=classe_anbima,
            mov_min=mov_min,
            risco=RiscoEnum.moderado,
            status_fundo=StatusFundoEnum.ativo,
            valor_cota=1.0,
            data_atualizacao=datetime.now()
        )
        
        # Atualizar dicionário
        cnpj_normalizado = self._normalizar_cnpj(cnpj)
        existing_funds[cnpj_normalizado] = novo_fundo.id
        
        print(f"[INFO] Fundo CVM cadastrado: {nome_fundo[:80]}")
    
    def _cadastrar_fundo_generico(self, cnpj, existing_funds):
        """
        Cadastra um fundo genérico (não encontrado na CVM)
        
        Args:
            cnpj: CNPJ do fundo
            existing_funds: Dicionário de fundos existentes (será atualizado)
        """
        novo_fundo = self.global_services.create_classe(
            InfoFundo,
            nome_fundo=f"Fundo {cnpj}",
            cnpj=cnpj,
            classe_anbima="Outros",
            mov_min=None,
            risco=RiscoEnum.moderado,
            status_fundo=StatusFundoEnum.ativo,
            valor_cota=1.0,
            data_atualizacao=datetime.now()
        )
        
        # Atualizar dicionário
        cnpj_normalizado = self._normalizar_cnpj(cnpj)
        existing_funds[cnpj_normalizado] = novo_fundo.id
        
        print(f"[INFO] Fundo genérico cadastrado: {cnpj}")
    
    def _cadastrar_fundos_dummy(self, cnpjs_dummy, posicoes, existing_funds):
        """
        Cadastra fundos com CNPJs dummy (previdência, RF, RV)
        
        Args:
            cnpjs_dummy: Lista de CNPJs dummy
            posicoes: Lista de posições (para obter dados do fundo)
            existing_funds: Dicionário de fundos existentes (será atualizado)
        """
        # Criar mapeamento CNPJ -> dados da posição
        cnpj_to_posicao = {}
        for pos in posicoes:
            if pos['cnpj'] in cnpjs_dummy:
                cnpj_to_posicao[pos['cnpj']] = pos
        
        # Cadastrar cada fundo dummy
        for cnpj in cnpjs_dummy:
            if cnpj not in cnpj_to_posicao:
                print(f"[AVISO] Dados não encontrados para CNPJ dummy: {cnpj}")
                continue
            
            try:
                pos_data = cnpj_to_posicao[cnpj]
                
                # Determinar risco baseado no tipo
                risco = self._determinar_risco_por_tipo(pos_data.get('tipo'))
                
                # Determinar subtipo de risco
                subtipo_risco = pos_data.get('subtipo_risco')
                
                # Usar valor_cota do Excel se disponível, senão 1.0
                valor_cota = pos_data.get('valor_cota', 1.0)
                
                # Criar fundo
                novo_fundo = self.global_services.create_classe(
                    InfoFundo,
                    nome_fundo=pos_data['nome_fundo'],
                    cnpj=cnpj,
                    classe_anbima=pos_data.get('classe_anbima', 'Outros'),
                    mov_min=None,
                    risco=risco,
                    subtipo_risco=subtipo_risco,
                    status_fundo=StatusFundoEnum.ativo,
                    valor_cota=valor_cota,
                    data_atualizacao=datetime.now()
                )
                
                # Atualizar dicionário
                cnpj_normalizado = self._normalizar_cnpj(cnpj)
                existing_funds[cnpj_normalizado] = novo_fundo.id
                
                tipo_label = pos_data.get('tipo', 'Ativo').upper()
                nome_curto = pos_data['nome_fundo'][:50]
                print(f"[INFO] {tipo_label} cadastrado: {nome_curto} | Cota: {valor_cota}")
                
            except Exception as e:
                print(f"[ERRO] Erro ao cadastrar fundo dummy {cnpj}: {str(e)}")
    
    def _determinar_risco_por_tipo(self, tipo):
        """
        Determina nível de risco baseado no tipo do ativo
        
        Args:
            tipo: Tipo do ativo (fundo, previdencia_individual, renda_fixa, acao, fii)
            
        Returns:
            RiscoEnum: Nível de risco
        """
        risco_map = {
            'renda_fixa': RiscoEnum.baixo,
            'acao': RiscoEnum.alto,
            'fii': RiscoEnum.moderado,
            'previdencia_individual': RiscoEnum.baixo,
            'previdencia_externa': RiscoEnum.baixo,
            'fundo': RiscoEnum.moderado
        }
        
        return risco_map.get(tipo, RiscoEnum.moderado)
    
    def _normalizar_cnpj(self, cnpj):
        """
        Normaliza CNPJ removendo pontuação
        
        Args:
            cnpj: CNPJ formatado
            
        Returns:
            str: CNPJ sem pontuação
        """
        return cnpj.replace('.', '').replace('/', '').replace('-', '')