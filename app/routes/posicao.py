from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.global_services import login_required, GlobalServices
from app.models.geld_models import create_session, Cliente, InfoFundo, PosicaoFundo, RiscoEnum, StatusFundoEnum
from sqlalchemy import func
from datetime import datetime
import pandas as pd
from datetime import datetime
from app.services.extract_services import ExtractServices

posicao_bp = Blueprint('posicao', __name__)

@posicao_bp.route('/posicao/<int:cliente_id>/listar_posicao')
@login_required

#LISTAR POSICAO
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
        
        return render_template('posicoes/listar_posicao.html', cliente=cliente,montante_cliente=montante_cliente,posicoes = posicoes)

    except Exception as e:
            print(f"ERROR in listar_posicao: {str(e)}")
            print(f'Erro ao acessar área do cliente: {str(e)}')
            return redirect(url_for('cliente.area_cliente',cliente_id=cliente_id))
    
    finally:
        db.close()

#ADD_COTAS
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
                return redirect(url_for('cliente.area_cliente',cliente_id=cliente_id))
            
            # Buscar todos os fundos disponíveis para o dropdown
            fundos = global_service.listar_classe(InfoFundo)
            
            return render_template('posicoes/add_posicao.html',cliente=cliente,fundos=fundos)
        
        except Exception as e:
            print(f'Erro ao carregar formulário: {str(e)}')
            return redirect(url_for('cliente.area_cliente',cliente_id=cliente_id))
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
                cotas = cotas,
                data_atualizacao = data_atualizacao
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

#DELETE_COTAS
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

# UPLOAD_PORTFOLIOS_BTG
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
                        
            # Selecionar arquivo
            file_path = GlobalServices.selecionar_arquivo()
            if not file_path:
                flash("Nenhum arquivo foi selecionado.","error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
            
            # Abrir a aba "Fundos"
            try:
                df = pd.read_excel(file_path, sheet_name="Fundos", header=None)
                
            except Exception as e:
                flash(f"Erro ao abrir o arquivo Excel: {str(e)}", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
            
            # 1. Primeiro, mapear os CNPJs dos fundos da seção "Detalhamento"
            
            cnpjs_fundos = {}
            
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Detalhamento >" in cell_value:
                    try:
                        global_service = GlobalServices(db)
                        parts = cell_value.split(" - ")
                        fund_name = parts[0].replace("Detalhamento > ", "").strip()
                        cnpj_bruto = parts[1].strip()  # Não precisamos mais remover o "*" manualmente
                        
                        # Usar o método de validação para normalizar o CNPJ
                        is_valid, cnpj_normalizado, mensagem = global_service.validar_cnpj(cnpj_bruto)
                        
                        if is_valid:
                            # Usar o método de formatação para armazenar o CNPJ formatado
                            cnpj_formatado = global_service.formatar_cnpj(cnpj_normalizado)
                            cnpjs_fundos[fund_name] = cnpj_formatado
                            print(f"CNPJ mapeado: {cnpj_formatado} para o fundo: {fund_name}", "info")
                        else:
                            print(f"CNPJ inválido na linha {i}: {cnpj_bruto} - {mensagem}", "warning")
                            
                    except Exception as e:
                        print(f"Erro ao extrair CNPJ na linha {i}: {str(e)}", "error")

            flash(f"Total de {len(cnpjs_fundos)} CNPJs mapeados.", "info")
            
            # 2. Encontrar a linha com "Posição > Portfólio de fundos"
            posicao_portfolio_index = None
            for i in range(len(df)):
                cell_value = df.iloc[i, 1] if df.shape[1] > 1 else None
                if isinstance(cell_value, str) and "Posição > Portfólio de fundos" in cell_value:
                    posicao_portfolio_index = i
                    print(f" Encontrada seção 'Posição > Portfólio de fundos' na linha {i}", "info")
                    break
            
            if posicao_portfolio_index is None:
                flash("Não foi possível encontrar a seção de posições no arquivo.", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
            
            # 3. Extrair dados da seção de portfólio
            posicoes = []
            header_row_found = False
            
            # Avançar para encontrar a linha de cabeçalho (Data Referência, Quantidade de Cotas, etc.)
            for i in range(posicao_portfolio_index, min(posicao_portfolio_index + 4, len(df))):
                row = df.iloc[i]
                # Procurando pela linha de cabeçalho que contém "Quantidade de Cotas"
                if any(isinstance(cell, str) and "Quantidade de Cotas" in cell for cell in row):
                    header_row_index = i
                    header_row_found = True
                    print(f"Encontrado cabeçalho na linha {i}", "info")
                    break
            
            if not header_row_found:
                flash("Não foi possível encontrar o cabeçalho da tabela de posições.")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
            
            # Identificar a coluna de quantidade de cotas
            cotas_column = None
            for j in range(len(df.columns)):
                if j < len(df.iloc[header_row_index]) and isinstance(df.iloc[header_row_index, j], str) and "Quantidade de Cotas" in df.iloc[header_row_index, j]:
                    cotas_column = j
                    print(f"[INFO] Coluna de quantidade de cotas encontrada: {j}")
                    break
            
            if cotas_column is None:
                flash("Não foi possível encontrar a coluna de quantidade de cotas.")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
            
            # Identificar a coluna de data
            date_column = None
            for j in range(len(df.columns)):
                if j < len(df.iloc[header_row_index]) and isinstance(df.iloc[header_row_index, j], str) and "Data" in df.iloc[header_row_index, j]:
                    date_column = j
                    print(f"[INFO] Coluna de data encontrada: {j}")
                    break
            
            # Se não encontrou coluna de data, usar a primeira coluna após o cabeçalho
            if date_column is None:
                date_column = 1  # Geralmente a coluna 1 tem a data
                print(f"[INFO] Usando coluna padrão para data: 1")
            
            # Processar os fundos e posições
            for i in range(header_row_index + 1, len(df)):
                # Verificar se chegamos na seção de detalhamento
                if pd.notna(df.iloc[i, 1]) and isinstance(df.iloc[i, 1], str) and ("Detalhamento" in df.iloc[i, 1] or "Rentabilidade" in df.iloc[i, 1]):
                    print(f"[INFO] Seção de {df.iloc[i, 1]} encontrada. Parando extração.")
                    break
                
                # Verificar se é uma linha de fundo
                if pd.notna(df.iloc[i, 1]) and isinstance(df.iloc[i, 1], str) and not df.iloc[i, 1].startswith("Total") and not df.iloc[i, 1].startswith("Data"):
                    fund_name = df.iloc[i, 1]
                    fund_name = fund_name.replace("*", "")
                    
                    # Se a próxima linha contém dados de posição (verificar se há um valor numérico de cotas)
                    if i + 1 < len(df) and pd.notna(df.iloc[i+1, cotas_column]) and isinstance(df.iloc[i+1, cotas_column], (int, float)):
                        date_value = df.iloc[i+1, date_column] if date_column < len(df.columns) and i+1 < len(df) else datetime.now()
                        quotas = df.iloc[i+1, cotas_column]
                        
                        print(f"[INFO] Processando fundo: {fund_name}, Cotas: {quotas}, Data: {date_value}")
                        
                        # Encontrar CNPJ
                        cnpj = None
                        for key, value in cnpjs_fundos.items():
                            if fund_name.lower() == key.lower(): 
                                cnpj = value
                                print(f"[INFO] CNPJ correspondente encontrado: {cnpj}")
                                break
                        if not cnpj:
                            print(f"[AVISO] Nenhum CNPJ correspondente encontrado para o fundo: {fund_name}")

                        # Só adicionar se tiver CNPJ e cotas
                        if cnpj and not pd.isna(quotas):
                            # Garantir que a data é um objeto datetime
                            if not isinstance(date_value, datetime):
                                try:
                                    if isinstance(date_value, str):
                                        date_value = datetime.strptime(date_value, "%Y-%m-%d")
                                except:
                                    date_value = datetime.now()
                            
                            posicoes.append({
                                "cnpj": cnpj,
                                "num_cotas": quotas,
                                "data": date_value
                            })
                            print(f"Posição adicionada para {fund_name} (CNPJ: {cnpj})", "info")
                        
                        # Pular a próxima linha que contém os valores
                        i += 1
            
            if not posicoes:
                flash("Nenhuma posição válida foi extraída do arquivo.")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
            
            flash(f"Total de {len(posicoes)} posições extraídas.", "info")
            
            # 4. Verificar CNPJs existentes e cadastrar novos fundos
            existing_funds = {f.cnpj.replace('.', '').replace('/', '').replace('-', ''): f.id 
                             for f in db.query(InfoFundo.id, InfoFundo.cnpj).all()}
            
            # Identificar CNPJs novos
            new_cnpjs = []
            for pos in posicoes:
                norm_cnpj = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')
                if norm_cnpj not in existing_funds:
                    new_cnpjs.append(pos['cnpj'])
            
            new_cnpjs = list(set(new_cnpjs))  # Remover duplicados
            print(f"CNPJs novos a cadastrar: {len(new_cnpjs)}","info")
            
            # Cadastrar novos fundos
            if new_cnpjs:
                
                extract_service = ExtractServices(db)
                global_service = GlobalServices(db)

                funds_info = extract_service.extracao_cvm_info_batch(new_cnpjs)
                
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
                        valor_cota=0.0,
                        data_atualizacao=datetime.now()
                    )
                            
                    # Atualizar o dicionário de fundos existentes
                    norm_cnpj = cnpj.replace('.', '').replace('/', '').replace('-', '')
                    existing_funds[norm_cnpj] = novo_fundo.id
                    
                # Para CNPJs não encontrados, criar fundos com informações mínimas
                missing_cnpjs = [cnpj for cnpj in new_cnpjs if cnpj not in funds_info]
                for cnpj in missing_cnpjs:
        # Criar fundo com informações mínimas
                    novo_fundo = global_service.create_classe(
                        InfoFundo,
                        nome_fundo=f"Fundo {cnpj}",
                        cnpj=cnpj,
                        classe_anbima="",
                        mov_min=None,
                        risco=RiscoEnum.moderado,
                        status_fundo=StatusFundoEnum.ativo,
                        valor_cota=0.0,
                        data_atualizacao=datetime.now()
                    )
                    # Atualizar o dicionário de fundos existentes
                    norm_cnpj = cnpj.replace('.', '').replace('/', '').replace('-', '')
                    existing_funds[norm_cnpj] = novo_fundo.id
            
            # 5. Registrar posições no banco
            registros_salvos = 0
            registros_atualizados = 0
            registros_falhas = 0
            
            for pos in posicoes:
                # Nova sessão para cada posição
                session = create_session()
                try:
                    norm_cnpj = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')
                    
                    if norm_cnpj in existing_funds:
                        fundo_id = existing_funds[norm_cnpj]
                        
                        # Verificar se já existe posição
                        existing_position = session.query(PosicaoFundo).filter_by(
                            fundo_id=fundo_id,
                            cliente_id=cliente_id
                        ).first()
                        
                        if existing_position:
                            # Atualizar posição existente
                            existing_position.cotas = pos['num_cotas']
                            existing_position.data_atualizacao = pos['data']
                            session.commit()
                            registros_atualizados += 1
                            print(f"Posição atualizada para fundo ID {fundo_id}", "info")
                        else:
                            # Criar nova posição
                            services = GlobalServices(session)
                            new_position = services.create_classe(
                                PosicaoFundo,
                                fundo_id=fundo_id,
                                cliente_id=cliente_id,
                                cotas=pos['num_cotas'],
                                data_atualizacao=pos['data']
                            )
                            registros_salvos += 1
                            flash(f"Nova posição criada para fundo ID {fundo_id}", "info")
                    else:
                        print(f"[AVISO] CNPJ {pos['cnpj']} não encontrado no banco de dados.")
                        registros_falhas += 1
                except Exception as e:
                    print(f"[ERRO] Erro ao registrar posição: {str(e)}")
                    registros_falhas += 1
                    session.rollback()
                finally:
                    session.close()
                    
            
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



#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP
#UPLOAD PORTFOLIOS XP



@posicao_bp.route('/posicao/<int:cliente_id>/upload_xp', methods=['GET', 'POST'])
@login_required
def upload_xp(cliente_id):
    
    if request.method == 'GET':
        try:
            db = create_session()
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            
            if not cliente:
                flash('Cliente não encontrado.', "error")
                return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
            
            return render_template('posicoes/upload_cotas_xp.html', cliente=cliente)
        
        except Exception as e:
            print(f'Erro ao carregar página de upload XP: {str(e)}')
            flash(f'Erro ao carregar página: {str(e)}', "error")
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        finally:
            db.close()
    
    elif request.method == 'POST':
        try:
            db = create_session()
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            
            if not cliente:
                flash('Cliente não encontrado.', "error")
                return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
            
            print(f"[INFO] Processando upload XP para cliente: {cliente.nome} (ID: {cliente_id})")
            
            # Selecionar arquivo
            file_path = GlobalServices.selecionar_arquivo()
            if not file_path:
                flash("Nenhum arquivo foi selecionado.", "warning")
                return redirect(url_for('posicao.upload_cotas_xp', cliente_id=cliente_id))
            
            print(f"[INFO] Arquivo selecionado: {file_path}")
            
            # Criar ExtractServices com sessão de banco de dados
            extract_service = ExtractServices(db)
            
            # Processar o arquivo e registrar posições
            registros_salvos, registros_atualizados, registros_falhas = extract_service.registrar_posicoes_xp(file_path, cliente_id)
            
            # Mensagem para o usuário
            if registros_salvos > 0 or registros_atualizados > 0:
                msg = f"{registros_salvos} novas posições e {registros_atualizados} atualizações registradas com sucesso!"
                if registros_falhas > 0:
                    msg += f" ({registros_falhas} operações falharam)"
                flash(msg, "success")
            else:
                flash("Nenhuma posição foi registrada. Verifique o arquivo ou os logs.", "warning")
            
            print("--- FIM DO PROCESSAMENTO DE UPLOAD XP ---\n")
            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERRO GERAL] Erro ao processar arquivo XP: {str(e)}")
            flash(f"Erro ao processar arquivo: {str(e)}", "error")
            return redirect(url_for('posicao.upload_cotas_xp', cliente_id=cliente_id))
        finally:
            if 'db' in locals() and db:
                db.close()