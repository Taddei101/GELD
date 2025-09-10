from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.global_services import login_required, GlobalServices
from app.models.geld_models import create_session, Cliente, InfoFundo, PosicaoFundo, RiscoEnum, StatusFundoEnum
from sqlalchemy import func
from datetime import datetime
import pandas as pd
import hashlib
from app.services.extract_services import ExtractServices

posicao_bp = Blueprint('posicao', __name__)

# =============================================================================
# FUNÇÕES AUXILIARES PARA PROCESSAMENTO UNIFICADO BTG
# =============================================================================

def processar_arquivo_btg_completo(file_path, cliente_id, db, global_services):
    """
    Processa TODAS as abas relevantes do BTG em uma única operação
    """
    todas_posicoes = []
    log_processamento = {
        'fundos': 0,
        'previdencia_individual': 0, 
        'previdencia_externa': 0,
        'erros': []
    }
    
    try:
        # 1. PROCESSAR ABA FUNDOS (lógica atual)
        print("[INFO] Processando aba Fundos...")
        posicoes_fundos = _processar_aba_fundos(file_path, db, global_services)
        todas_posicoes.extend(posicoes_fundos)
        log_processamento['fundos'] = len(posicoes_fundos)
        
        # 2. PROCESSAR PREVIDÊNCIA INDIVIDUAL
        print("[INFO] Processando aba Previdência Individual...")
        posicoes_prev_ind = _processar_aba_previdencia_individual(file_path)
        todas_posicoes.extend(posicoes_prev_ind)
        log_processamento['previdencia_individual'] = len(posicoes_prev_ind)
        
        # 3. PROCESSAR PREVIDÊNCIA EXTERNA  
        print("[INFO] Processando aba Previdência Externa...")
        posicoes_prev_ext = _processar_aba_previdencia_externa(file_path)
        todas_posicoes.extend(posicoes_prev_ext)
        log_processamento['previdencia_externa'] = len(posicoes_prev_ext)
        
        # 4. DEDUPLICAÇÃO POR CNPJ
        posicoes_unicas = _deduplificar_posicoes(todas_posicoes)
        posicoes_removidas = len(todas_posicoes) - len(posicoes_unicas)
        
        if posicoes_removidas > 0:
            print(f"[INFO] {posicoes_removidas} posições duplicadas removidas")
        
        print(f"[INFO] Total final: {len(posicoes_unicas)} posições únicas")
        
        return posicoes_unicas, log_processamento
        
    except Exception as e:
        log_processamento['erros'].append(str(e))
        print(f"[ERRO] Erro no processamento completo: {str(e)}")
        return todas_posicoes, log_processamento

def _processar_aba_fundos(file_path, db, global_services):
    """Extrai a lógica atual de processamento da aba Fundos"""
    posicoes = []
    
    try:
        df = pd.read_excel(file_path, sheet_name="Fundos", header=None)
        
        # 1. Mapear CNPJs (lógica atual)
        cnpjs_fundos = {}
        for i in range(len(df)):
            cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
            if isinstance(cell_value, str) and "Detalhamento >" in cell_value:
                try:
                    parts = cell_value.split(" - ")
                    fund_name = parts[0].replace("Detalhamento > ", "").strip()
                    cnpj_bruto = parts[1].strip()
                    
                    is_valid, cnpj_normalizado, _ = global_services.validar_cnpj(cnpj_bruto)
                    if is_valid:
                        cnpj_formatado = global_services.formatar_cnpj(cnpj_normalizado)
                        cnpjs_fundos[fund_name] = cnpj_formatado
                        print(f"[INFO] CNPJ mapeado: {cnpj_formatado} para {fund_name}")
                except Exception as e:
                    print(f"[AVISO] Erro ao mapear CNPJ na linha {i}: {str(e)}")
                    continue
        
        # 2. Encontrar seção de posições
        posicao_portfolio_index = None
        for i in range(len(df)):
            cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
            if isinstance(cell_value, str) and "Posição > Portfólio de fundos" in cell_value:
                posicao_portfolio_index = i
                break
                
        if posicao_portfolio_index is None:
            print("[AVISO] Seção 'Posição > Portfólio de fundos' não encontrada")
            return posicoes
            
        # 3. Encontrar cabeçalho
        header_row_index = None
        for i in range(posicao_portfolio_index, min(posicao_portfolio_index + 4, len(df))):
            row = df.iloc[i]
            if any(isinstance(cell, str) and "Quantidade de Cotas" in cell for cell in row):
                header_row_index = i
                break
                
        if header_row_index is None:
            print("[AVISO] Cabeçalho não encontrado na aba Fundos")
            return posicoes
            
        # 4. Identificar colunas
        cotas_column = None
        date_column = 1  # Padrão
        
        for j in range(len(df.columns)):
            if (j < len(df.iloc[header_row_index]) and 
                isinstance(df.iloc[header_row_index, j], str) and 
                "Quantidade de Cotas" in df.iloc[header_row_index, j]):
                cotas_column = j
                break
                
        if cotas_column is None:
            print("[AVISO] Coluna de cotas não encontrada na aba Fundos")
            return posicoes
            
        # 5. Processar posições
        for i in range(header_row_index + 1, len(df)):
            if (pd.notna(df.iloc[i, 1]) and isinstance(df.iloc[i, 1], str) and 
                ("Detalhamento" in df.iloc[i, 1] or "Rentabilidade" in df.iloc[i, 1])):
                break
                
            if (pd.notna(df.iloc[i, 1]) and isinstance(df.iloc[i, 1], str) and 
                not df.iloc[i, 1].startswith("Total") and not df.iloc[i, 1].startswith("Data")):
                
                fund_name = str(df.iloc[i, 1]).replace("*", "").strip()
                
                if (i + 1 < len(df) and pd.notna(df.iloc[i+1, cotas_column]) and 
                    isinstance(df.iloc[i+1, cotas_column], (int, float))):
                    
                    date_value = df.iloc[i+1, date_column] if date_column < len(df.columns) else datetime.now()
                    quotas = float(df.iloc[i+1, cotas_column])
                    
                    # Encontrar CNPJ
                    cnpj = None
                    for key, value in cnpjs_fundos.items():
                        if fund_name.lower() == key.lower():
                            cnpj = value
                            break
                            
                    if cnpj:
                        if not isinstance(date_value, datetime):
                            try:
                                date_value = datetime.strptime(str(date_value), "%Y-%m-%d")
                            except:
                                date_value = datetime.now()
                                
                        posicoes.append({
                            "nome_fundo": fund_name,
                            "cnpj": cnpj,
                            "num_cotas": quotas,
                            "data": date_value,
                            "tipo": "fundo_normal"
                        })
                        print(f"[INFO] Fundo encontrado: {fund_name}")
                        
    except Exception as e:
        print(f"[ERRO] Erro na aba Fundos: {str(e)}")
    
    return posicoes


def _processar_aba_previdencia_individual(file_path):
    """Processa aba Previdência Individual - BUSCA INTELIGENTE"""
    posicoes = []
    
    try:
        df = pd.read_excel(file_path, sheet_name="Previdência Individual", header=None)
        print(f"[DEBUG] Previdência Individual - DataFrame shape: {df.shape}")
        
        # 1. Buscar seção que contém "Posição >"
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
            
            # 4. Processar dados após o cabeçalho até encontrar "Total" ou "Rentabilidade"
            linha_atual = linha_cabecalho + 1
            while linha_atual < len(df):
                row = df.iloc[linha_atual]
                
                # Parar se encontrar delimitadores
                if (pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and 
                    (row.iloc[1].strip().lower() in ["total", "rentabilidade"] or 
                     "rentabilidade" in row.iloc[1].lower())):
                    print(f"[DEBUG] Fim da seção encontrado na linha {linha_atual}: {row.iloc[1]}")
                    break
                
                # Verificar se é linha de dados válida
                if (len(row) >= 7 and 
                    pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and
                    pd.notna(row.iloc[2]) and isinstance(row.iloc[2], str) and
                    pd.notna(row.iloc[4]) and isinstance(row.iloc[4], (int, float)) and
                    ("FOF" in str(row.iloc[1]).upper() or "FI" in str(row.iloc[1]).upper()) and
                    len(str(row.iloc[1]).strip()) > 10):  # Nome deve ter tamanho razoável
                    
                    nome_fundo = str(row.iloc[1]).strip()
                    cnpj_bruto = str(row.iloc[2]).strip()
                    data_ref = row.iloc[3] if pd.notna(row.iloc[3]) else datetime.now()
                    quantidade_cotas = float(row.iloc[4])
                    
                    print(f"[DEBUG] Candidato a fundo encontrado na linha {linha_atual}: {nome_fundo}")
                    
                    # Validar CNPJ
                    session_temp = create_session()
                    global_service = GlobalServices(session_temp)
                    is_valid, cnpj_normalizado, msg = global_service.validar_cnpj(cnpj_bruto)
                    session_temp.close()
                    
                    if is_valid:
                        cnpj_formatado = global_service.formatar_cnpj(cnpj_normalizado)
                        
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
                        print(f"[INFO] Previdência Individual encontrada: {nome_fundo}")
                    else:
                        print(f"[DEBUG] CNPJ inválido para {nome_fundo}: {msg}")
                
                linha_atual += 1
                    
    except Exception as e:
        print(f"[ERRO] Erro na Previdência Individual: {str(e)}")
    
    return posicoes

def _processar_aba_previdencia_externa(file_path):
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
                
                # Verificar se é linha de dados válida (estrutura diferente da individual)
                if (len(row) >= 6 and 
                    pd.notna(row.iloc[1]) and isinstance(row.iloc[1], str) and
                    pd.notna(row.iloc[3]) and isinstance(row.iloc[3], (int, float)) and
                    ("FOF" in str(row.iloc[1]).upper() or 
                     "ICATU" in str(row.iloc[1]).upper() or 
                     "SUPERPREVIDENCIA" in str(row.iloc[1]).upper() or
                     "EMPIRICUS" in str(row.iloc[1]).upper()) and
                    len(str(row.iloc[1]).strip()) > 15 and  # Nome deve ter tamanho razoável
                    float(row.iloc[3]) > 100):  # Filtrar rentabilidades pequenas
                    
                    nome_fundo = str(row.iloc[1]).strip()
                    data_ref = row.iloc[2] if pd.notna(row.iloc[2]) else datetime.now()
                    quantidade_cotas = float(row.iloc[3])
                    
                    print(f"[DEBUG] Candidato a fundo encontrado na linha {linha_atual}: {nome_fundo}")
                    
                    # Gerar CNPJ dummy
                    cnpj_dummy = _gerar_cnpj_dummy(nome_fundo)
                    
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



def _gerar_cnpj_dummy(nome_fundo):
    """
    Gera CNPJ dummy baseado no nome normalizado do fundo
    Remove caracteres especiais para evitar duplicação
    """
    import hashlib
    import re
    
    # 1. NORMALIZAR NOME DO FUNDO
    nome_normalizado = nome_fundo.upper()
    
    # Remover caracteres especiais comuns
    nome_normalizado = re.sub(r'[*\s\-_.]+', '', nome_normalizado)  
    nome_normalizado = re.sub(r'[^A-Z0-9]', '', nome_normalizado)   # Só letras e números
    
    print(f"[DEBUG] Nome original: '{nome_fundo}' → Normalizado: '{nome_normalizado}'")
    
    # 2. GERAR HASH DO NOME NORMALIZADO
    hash_object = hashlib.md5(nome_normalizado.encode())
    hash_hex = hash_object.hexdigest()
    
    # Pegar primeiros 12 dígitos do hash e converter para números
    numeros = ''.join([str(int(c, 16) % 10) for c in hash_hex[:12]])
    
    # 3. FORMATO: 99.XXX.XXX/0001-XX (99 = dummy, 0001 = filial padrão)
    cnpj_dummy = f"99.{numeros[:3]}.{numeros[3:6]}/0001-{numeros[6:8]}"
    
    print(f"[DEBUG] CNPJ dummy gerado: {cnpj_dummy}")
    return cnpj_dummy

def _deduplificar_posicoes(posicoes):
    """Remove posições duplicadas baseado em CNPJ"""
    posicoes_unicas = {}
    
    for pos in posicoes:
        cnpj_norm = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')
        
        # Se já existe, manter o mais completo (preferencialmente não-dummy)
        if cnpj_norm in posicoes_unicas:
            pos_existente = posicoes_unicas[cnpj_norm]
            
            # Priorizar: fundo_normal > previdencia_individual > previdencia_externa
            prioridades = {'fundo_normal': 3, 'previdencia_individual': 2, 'previdencia_externa': 1}
            
            prioridade_atual = prioridades.get(pos.get('tipo', ''), 0)
            prioridade_existente = prioridades.get(pos_existente.get('tipo', ''), 0)
            
            if prioridade_atual > prioridade_existente:
                posicoes_unicas[cnpj_norm] = pos
                print(f"[INFO] Substituindo posição duplicada: {pos['nome_fundo']}")
        else:
            posicoes_unicas[cnpj_norm] = pos
    
    return list(posicoes_unicas.values())

# =============================================================================
# ROTAS
# =============================================================================

@posicao_bp.route('/posicao/<int:cliente_id>/listar_posicao')
@login_required
def listar_posicao(cliente_id):
    try:
        db = create_session()
        global_services = GlobalServices(db)
        cliente = global_services.get_by_id(Cliente, cliente_id)
        posicoes = db.query(PosicaoFundo).filter(PosicaoFundo.cliente_id == cliente_id).all()
        montante_cliente = db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id
            ).scalar() or 0.0
        print(f"DEBUG: Found {len(posicoes)} positions")

        if not cliente:
            print('Cliente não encontrado.')
            return redirect(url_for('dashboard.cliente_dashboard'))

        return render_template('posicoes/listar_posicao.html', cliente=cliente, montante_cliente=montante_cliente, posicoes=posicoes)

    except Exception as e:
        print(f"ERROR in listar_posicao: {str(e)}")
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))

    finally:
        db.close()

@posicao_bp.route('/posicao/<int:cliente_id>/add_posicao', methods=['GET', 'POST'])
@login_required
def add_posicao(cliente_id):
    if request.method == 'GET':
        try:
            db = create_session()
            global_service = GlobalServices(db)

            cliente = global_service.get_by_id(Cliente, cliente_id)
            if not cliente:
                print('Cliente não encontrado.')
                return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))

            # Buscar todos os fundos disponíveis para o dropdown
            fundos = global_service.listar_classe(InfoFundo)

            return render_template('posicoes/add_posicao.html', cliente=cliente, fundos=fundos)

        except Exception as e:
            print(f'Erro ao carregar formulário: {str(e)}')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        finally:
            db.close()

    elif request.method == 'POST':
        try:
            db = create_session()
            global_service = GlobalServices(db)

            # Obter dados do formulário
            fundo_id = int(request.form['fundo_id'])
            cotas = float(request.form['quantidade_cotas'])
            data_atualizacao = datetime.now()

            # Criar nova posicao
            nova_posicao = global_service.create_classe(
                PosicaoFundo,
                cliente_id=cliente_id,
                fundo_id=fundo_id,
                cotas=cotas,
                data_atualizacao=data_atualizacao
            )

            print(f'Posição cadastrada com sucesso!')
            flash("Posição registrada com sucesso!", "success")
            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        except ValueError as e:
            flash(f'Erro de validação: {str(e)}')
        except Exception as e:
            flash(f'Erro ao cadastrar posição: {str(e)}')
        finally:
            db.close()

        return redirect(url_for('posicao.add_posicao', cliente_id=cliente_id))

@posicao_bp.route('/posicao/<int:posicao_id>/delete', methods=['POST'])
@login_required
def delete_posicao(posicao_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        # Obter a posição para recuperar o cliente_id
        posicao = global_service.get_by_id(PosicaoFundo, posicao_id)
        if not posicao:
            flash('Posição não encontrada.')
            return redirect(url_for('dashboard.cliente_dashboard'))

        cliente_id = posicao.cliente_id

        # Deletar a posição
        if global_service.delete(PosicaoFundo, posicao_id):
            flash('Posição deletada com sucesso!')
        else:
            flash('Erro ao deletar posição.')

        return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

    except Exception as e:
        flash(f'Erro ao deletar posição: {str(e)}')
        return redirect(url_for('dashboard.cliente_dashboard'))
    finally:
        db.close()

@posicao_bp.route('/posicao/<int:cliente_id>/upload_cotas', methods=['GET', 'POST'])
@login_required
def upload_cotas(cliente_id):
    if request.method == 'GET':
        try:
            db = create_session()
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            return render_template('posicoes/upload_cotas.html', cliente=cliente)
        except Exception as e:
            flash(f'Erro ao carregar página de upload: {str(e)}')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        finally:
            db.close()

    elif request.method == 'POST':
        db = create_session()
        try:
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            global_services = GlobalServices(db)

            # Processar upload via formulário
            sucesso, file_path, mensagem = global_services.processar_upload_arquivo()

            if not sucesso:
                flash(mensagem, "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            # ===== PROCESSAMENTO UNIFICADO =====
            try:
                print("[INFO] Iniciando processamento completo do arquivo BTG...")
                posicoes, log = processar_arquivo_btg_completo(file_path, cliente_id, db, global_services)
                
                # Log detalhado
                total = log['fundos'] + log['previdencia_individual'] + log['previdencia_externa']
                flash(f"Processadas {total} posições: {log['fundos']} fundos, {log['previdencia_individual']} prev.individual, {log['previdencia_externa']} prev.externa", "info")
                
            except Exception as e:
                print(f"[ERRO] Erro no processamento: {str(e)}")
                flash(f"Erro no processamento: {str(e)}", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            if not posicoes:
                flash("Nenhuma posição válida foi extraída do arquivo.")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            # Verificar CNPJs existentes e cadastrar novos fundos
            existing_funds = {f.cnpj.replace('.', '').replace('/', '').replace('-', ''): f.id
                             for f in db.query(InfoFundo.id, InfoFundo.cnpj).all()}

            new_cnpjs = []
            for pos in posicoes:
                norm_cnpj = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')
                if norm_cnpj not in existing_funds:
                    new_cnpjs.append(pos['cnpj'])

            new_cnpjs = list(set(new_cnpjs))
            print(f"CNPJs novos a cadastrar: {len(new_cnpjs)}")

            # Cadastrar novos fundos
            if new_cnpjs:
                extract_service = ExtractServices(db)
                global_service = GlobalServices(db)

                # Separar CNPJs reais dos dummies
                cnpjs_reais = [cnpj for cnpj in new_cnpjs if not cnpj.startswith('99.')]
                cnpjs_dummy = [cnpj for cnpj in new_cnpjs if cnpj.startswith('99.')]

                # Processar CNPJs reais via CVM
                if cnpjs_reais:
                    funds_info = extract_service.extracao_cvm_info_batch(cnpjs_reais)
                    
                    for cnpj, info in funds_info.items():
                        nome_fundo = info['DENOM_SOCIAL']
                        novo_fundo = global_service.create_classe(
                            InfoFundo,
                            nome_fundo=nome_fundo,
                            cnpj=cnpj,
                            classe_anbima=info.get('CLASSE_ANBIMA', ''),
                            mov_min=float(info['PR_CIA_MIN']) if info['PR_CIA_MIN'] != 'None' else None,
                            risco=RiscoEnum.moderado,
                            status_fundo=StatusFundoEnum.ativo,
                            valor_cota=1.0,
                            data_atualizacao=datetime.now()
                        )
                        norm_cnpj = cnpj.replace('.', '').replace('/', '').replace('-', '')
                        existing_funds[norm_cnpj] = novo_fundo.id

                    # CNPJs reais não encontrados na CVM
                    missing_cnpjs = [cnpj for cnpj in cnpjs_reais if cnpj not in funds_info]
                    for cnpj in missing_cnpjs:
                        novo_fundo = global_service.create_classe(
                            InfoFundo,
                            nome_fundo=f"Fundo {cnpj}",
                            cnpj=cnpj,
                            classe_anbima="previdencia",
                            mov_min=None,
                            risco=RiscoEnum.baixo,
                            status_fundo=StatusFundoEnum.ativo,
                            valor_cota=1.0,
                            data_atualizacao=datetime.now()
                        )
                        norm_cnpj = cnpj.replace('.', '').replace('/', '').replace('-', '')
                        existing_funds[norm_cnpj] = novo_fundo.id

                # Processar fundos de previdência (CNPJs dummy)
                for pos in posicoes:
                    if 'tipo' in pos and 'previdencia' in pos['tipo']:
                        norm_cnpj = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')
                        if norm_cnpj not in existing_funds:
                            novo_fundo = global_service.create_classe(
                                InfoFundo,
                                nome_fundo=pos['nome_fundo'],
                                cnpj=pos['cnpj'],
                                classe_anbima="previdencia",
                                mov_min=None,
                                risco=RiscoEnum.baixo,
                                status_fundo=StatusFundoEnum.ativo,
                                valor_cota=1.0,
                                data_atualizacao=datetime.now()
                            )
                            existing_funds[norm_cnpj] = novo_fundo.id
                            print(f"[INFO] Fundo de previdência cadastrado: {pos['nome_fundo']}")

            # Registrar posições no banco
            registros_salvos = 0
            registros_atualizados = 0
            registros_falhas = 0

            for pos in posicoes:
                session = create_session()
                try:
                    norm_cnpj = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')

                    if norm_cnpj in existing_funds:
                        fundo_id = existing_funds[norm_cnpj]

                        existing_position = session.query(PosicaoFundo).filter_by(
                            fundo_id=fundo_id,
                            cliente_id=cliente_id
                        ).first()

                        if existing_position:
                            existing_position.cotas = pos['num_cotas']
                            existing_position.data_atualizacao = pos['data']
                            session.commit()
                            registros_atualizados += 1
                        else:
                            services = GlobalServices(session)
                            new_position = services.create_classe(
                                PosicaoFundo,
                                fundo_id=fundo_id,
                                cliente_id=cliente_id,
                                cotas=pos['num_cotas'],
                                data_atualizacao=pos['data']
                            )
                            registros_salvos += 1
                    else:
                        print(f"[AVISO] CNPJ {pos['cnpj']} não encontrado no banco de dados.")
                        registros_falhas += 1
                except Exception as e:
                    print(f"[ERRO] Erro ao registrar posição: {str(e)}")
                    registros_falhas += 1
                    session.rollback()
                finally:
                    session.close()

            # Remover arquivo após processamento
            try:
                import os
                os.remove(file_path)
            except:
                pass

            # Mensagem para o usuário
            if registros_salvos > 0 or registros_atualizados > 0:
                msg = f"{registros_salvos} novas posições e {registros_atualizados} atualizações registradas com sucesso!"
                if registros_falhas > 0:
                    msg += f" ({registros_falhas} operações falharam)"
                flash(msg)
            else:
                flash("Nenhuma posição foi registrada. Verifique o arquivo ou os logs.")

            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERRO GERAL] Erro ao processar arquivo: {str(e)}")
            flash(f"Erro ao processar arquivo: {str(e)}")
            return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
        finally:
            db.close()