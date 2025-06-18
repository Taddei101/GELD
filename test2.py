#ROTAS fundos
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from functools import wraps
from app.models.geld_models import create_session, InfoFundo, RiscoEnum, StatusFundoEnum
from app.services.global_services import GlobalServices, login_required
from datetime import datetime
from app.services.extract_services import ExtractServices
import pandas as pd
from datetime import datetime
import re

fundos_bp = Blueprint('fundos', __name__)


#LISTAR
@fundos_bp.route('/listar_fundos')
@login_required
def listar_fundos():
    try:
        db = create_session()
        global_service = GlobalServices(db)
        fundos = global_service.listar_classe(InfoFundo)
        
               
        return render_template('fundos/listar_fundos.html', fundos=fundos)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao listar fundos: {str(e)}')
        return redirect(url_for('dashboard.cliente_dashboard'))
    finally:
        if 'db' in locals() and db:
            db.close()

#CADASTRAR FUNDO NA MÃO (está instanciado no momento pois não deverá existir.)
@fundos_bp.route('/add_fundo', methods =['GET', 'POST'])
@login_required
def add_fundo():
    if request.method == 'GET':
        return render_template('fundos/add_fundo.html')
    try:
        db = create_session()
        global_service = GlobalServices(db)
        mov_min = 0 
        permanencia_min= 0
        data_atualizacao = datetime.now()
        status_fundo = StatusFundoEnum["ativo"]
        risco=RiscoEnum["baixo"]

        #cadastrar novo fundo
        novo_fundo = global_service.create_classe(
            InfoFundo,
            nome_fundo=request.form['nome_fundo'],
            cnpj=request.form['cnpj'],
            mov_min=mov_min,
            classe_anbima = request.form['classe_anbima'],
            permanencia_min=permanencia_min,
            risco=risco,
            status_fundo=status_fundo,
            valor_cota = 1,
            data_atualizacao = data_atualizacao          
        )
        flash(f'Fundo {novo_fundo.nome_fundo} cadastrado com sucesso!')
        return redirect(url_for('fundos.listar_fundos'))
    
    except Exception as e:
            import traceback
            traceback.print_exc()
            flash(f'Erro ao cadastrar fundo: {str(e)}')
            return redirect(url_for('fundos.listar_fundos'))
    finally:
        if 'db' in locals() and db:
            db.close()

#DELETAR
@fundos_bp.route('/fundos/<int:fundo_id>/delete', methods=['POST'])
@login_required
def delete_fundo(fundo_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)
        if global_service.delete(InfoFundo, fundo_id):
            flash(f'Fundo deletado com sucesso!',"success")
        else:
            flash('Fundo não encontrado!')
        return redirect(url_for('fundos.listar_fundos'))  
          
    except Exception as e:
        flash(f'Erro ao deletar fundo: {str(e)}')
        return redirect(url_for('fundos.listar_fundos'))
    finally:
        db.close()


#EDITAR
@fundos_bp.route('/fundos/edit/<int:fundo_id>', methods=['GET','POST'])
@login_required
def edit_fundo(fundo_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        if request.method == 'GET':
            fundo = global_service.get_by_id(InfoFundo, fundo_id)
            if not fundo:
                flash('Fundo não encontrado')
                return redirect(url_for('fundos.listar_fundos'))
            return render_template('fundos/edit_fundo.html', fundo=fundo)
        
        elif request.method =='POST':

            mov_min = request.form['mov_min']
            mov_min = None if mov_min == '' else float(mov_min)

            permanencia_min = request.form['permanencia_min']
            permanencia_min = None if permanencia_min == '' else float(permanencia_min)
            
            # Converter a string de data para objeto datetime
            data_atualizacao_str = request.form['data_atualizacao']
            data_atualizacao = datetime.strptime(data_atualizacao_str, '%Y-%m-%d') if data_atualizacao_str else None

            dados_atualizados = {
                
                'nome_fundo': request.form['nome_fundo'],
                'cnpj': request.form['cnpj'],
                'classe_anbima': request.form['classe_anbima'],
                'mov_min': mov_min,
                'permanencia_min': permanencia_min,
                'valor_cota' : request.form['valor_cota'],
                'data_atualizacao' : data_atualizacao
                
            }

            if 'risco' in request.form and request.form['risco']:
                dados_atualizados['risco'] = RiscoEnum[request.form['risco']]

            if 'status_fundo' in request.form and request.form['status_fundo']:
                dados_atualizados['status_fundo'] = StatusFundoEnum[request.form['status_fundo']]
            
            fundo_atualizado = global_service.editar_classe(InfoFundo, fundo_id, **dados_atualizados)

            if fundo_atualizado:
                flash('Fundo atualizado com sucesso!')
            else:
                flash('Fundo não encontrado.')

            return redirect(url_for('fundos.listar_fundos'))

    except ValueError as e:
        flash(f'Erro de validação: {str(e)}')
    except Exception as e:
        flash(f'Erro ao editar fundo: {str(e)}')
    finally:
        if 'db' in locals() and db:
            db.close()
        
    return redirect(url_for('fundos.listar_fundos'))

# ATUALIZAR
@fundos_bp.route('/atualizar_cotas_fundos', methods=['POST'])
@login_required
def atualizar_cotas_fundos():
    try:

        db = create_session()
        extract_service = ExtractServices(db)
        from datetime import datetime, timedelta
        hoje = datetime.now()
        ano = str(hoje.year)
        mes = f"{hoje.month:02d}"
        
        df_cotas = extract_service.extracao_cvm(ano, mes)
        
        if df_cotas.empty:
            mes_anterior = hoje.replace(day=1) - timedelta(days=1)
            ano = str(mes_anterior.year)
            mes = f"{mes_anterior.month:02d}"
            df_cotas = extract_service.extracao_cvm(ano, mes)


        if df_cotas.empty:
            flash('Não foi possível obter dados de cotas. Verifique os logs.')
            return redirect(url_for('fundos.listar_fundos'))
        
        fundos = db.query(InfoFundo).all()
        fundos_atualizados = 0

        for fundo in fundos:

            cnpj_normalizado = fundo.cnpj.replace('.', '').replace('/', '').replace('-', '')
            df_fundo = df_cotas[df_cotas['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '') == cnpj_normalizado]

            if not df_fundo.empty:
                # Pegar o valor mais recente
                df_recente = df_fundo.sort_values('DT_COMPTC', ascending=False).iloc[0]
                valor_cota = df_recente['VL_QUOTA']

                fundo.valor_cota = valor_cota
                fundo.data_atualizacao = datetime.now()
                fundos_atualizados += 1

        if fundos_atualizados > 0:
            db.commit()
            flash(f'Cotas de {fundos_atualizados} fundos atualizadas com sucesso!')
        else:
            flash('Nenhum fundo foi atualizado.')
        
        db.close()
        return redirect(url_for('fundos.listar_fundos'))
        
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao atualizar cotas: {str(e)}')
        
    return redirect(url_for('fundos.listar_fundos'))


# IMPORTAR FUNDO POR CNPJ
   
@fundos_bp.route('/add_fundo_cnpj', methods=['POST'])
@login_required
def add_fundo_cnpj():
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        global_service = GlobalServices(db)
        
        # Pega o cnpj do form no html
        cnpj = request.form['cnpj']
        print(f"CNPJ recebido: {cnpj}")
        
        # Validar apenas o formato do CNPJ (14 dígitos)
        is_valid, cnpj_normalizado, mensagem = global_service.validar_cnpj(cnpj)
        
        if not is_valid:
            flash(mensagem, "error")
            print(mensagem)
            return redirect(url_for('fundos.add_fundo'))
            
        cnpj_formatado = global_service.formatar_cnpj(cnpj_normalizado)
        flash(f'Processando CNPJ: {cnpj_formatado}', "info")
        print(f'Processando CNPJ: {cnpj_formatado}')

        # Verificar se o fundo já existe no banco de dados
        existing_funds = db.query(InfoFundo).all()
        for fund in existing_funds:
            # Normaliza o CNPJ do fundo existente e compara com o normalizado do input
            fund_cnpj_norm = re.sub(r'\D', '', fund.cnpj)
            if fund_cnpj_norm == cnpj_normalizado:
                flash(f'O fundo com CNPJ {cnpj_formatado} já está cadastrado como "{fund.nome_fundo}"!', "warning")
                print(f'O fundo com CNPJ {cnpj_formatado} já está cadastrado como "{fund.nome_fundo}"!')
                return redirect(url_for('fundos.listar_fundos'))
        
        try:
            info = extract_service.extracao_cvm_info(cnpj_normalizado)
            
            if info is None or (isinstance(info, pd.DataFrame) and info.empty):
                flash(f'Não foi possível encontrar informações para o CNPJ: {cnpj_formatado}', "error")
                print(f'Não foi possível encontrar informações para o CNPJ: {cnpj_formatado}')
                return redirect(url_for('fundos.add_fundo'))
            
            novo_fundo = global_service.create_classe(
                InfoFundo,
                nome_fundo=info['DENOM_SOCIAL'],
                cnpj=cnpj_formatado,  # Armazena formatado
                classe_anbima=info['CLASSE_ANBIMA'],
                mov_min=float(info['PR_CIA_MIN']) if info['PR_CIA_MIN'] and info['PR_CIA_MIN'] != 'None' else None,
                risco=RiscoEnum.moderado,  # Default value
                status_fundo=StatusFundoEnum.ativo,
                valor_cota=0.0, 
                data_atualizacao=datetime.now()
            )
            flash(f'Fundo {novo_fundo.nome_fundo} cadastrado com sucesso!', "success")
            print(f'Fundo {novo_fundo.nome_fundo} cadastrado com sucesso!')
            
        except (IndexError, KeyError):
            flash('Não foi possível encontrar informações para o CNPJ informado.', "warning")
            print('Não foi possível encontrar informações para o CNPJ informado.')
        
        return redirect(url_for('fundos.listar_fundos'))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao cadastrar fundo por CNPJ: {str(e)}', "error")
        print(f'Erro ao cadastrar fundo por CNPJ: {str(e)}')
        return redirect(url_for('fundos.add_fundo'))
    finally:
        if 'db' in locals() and db:
            db.close()
# ADICIONE ESTAS ROTAS AO SEU fundos_bp EXISTENTE

# IMPORTAR FUNDO POR CNPJ USANDO ANBIMA
@fundos_bp.route('/add_fundo_cnpj_anbima', methods=['POST'])
@login_required
def add_fundo_cnpj_anbima():
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        global_service = GlobalServices(db)
        
        cnpj = request.form['cnpj']
        print(f"CNPJ recebido para ANBIMA: {cnpj}")
        
        # Usar a mesma validação que você já tem
        is_valid, cnpj_normalizado, mensagem = global_service.validar_cnpj(cnpj)
        
        if not is_valid:
            flash(mensagem, "error")
            return redirect(url_for('fundos.add_fundo'))
            
        cnpj_formatado = global_service.formatar_cnpj(cnpj_normalizado)
        flash(f'Processando CNPJ na ANBIMA: {cnpj_formatado}', "info")
        
        # Verificar se já existe (mesmo código que você usa)
        existing_funds = db.query(InfoFundo).all()
        for fund in existing_funds:
            fund_cnpj_norm = re.sub(r'\D', '', fund.cnpj)
            if fund_cnpj_norm == cnpj_normalizado:
                flash(f'O fundo com CNPJ {cnpj_formatado} já está cadastrado como "{fund.nome_fundo}"!', "warning")
                return redirect(url_for('fundos.listar_fundos'))
        
        # USAR ANBIMA ao invés de CVM
        info = extract_service.extracao_anbima_fundo_cnpj(cnpj_normalizado)
        
        if info is None:
            flash(f'Não foi possível encontrar informações na ANBIMA para o CNPJ: {cnpj_formatado}', "error")
            return redirect(url_for('fundos.add_fundo'))
        
        # Criar fundo com dados da ANBIMA (adapte os campos conforme a resposta da API)
        novo_fundo = global_service.create_classe(
            InfoFundo,
            nome_fundo=info.get('nome_fundo', info.get('denominacao', 'Nome não informado')),
            cnpj=cnpj_formatado,
            classe_anbima=info.get('classe_anbima', info.get('classificacao', 'Não informado')),
            mov_min=float(info.get('aplicacao_minima', 0)) if info.get('aplicacao_minima') else None,
            permanencia_min=float(info.get('prazo_carencia', 0)) if info.get('prazo_carencia') else None,
            risco=RiscoEnum.moderado,  # Default
            status_fundo=StatusFundoEnum.ativo,
            valor_cota=float(info.get('valor_cota', 0)) if info.get('valor_cota') else 0.0,
            data_atualizacao=datetime.now()
        )
        
        flash(f'Fundo {novo_fundo.nome_fundo} cadastrado com sucesso via ANBIMA!', "success")
        return redirect(url_for('fundos.listar_fundos'))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao cadastrar fundo via ANBIMA: {str(e)}', "error")
        return redirect(url_for('fundos.add_fundo'))
    finally:
        if 'db' in locals() and db:
            db.close()


# ATUALIZAR COTAS USANDO ANBIMA (alternativa ao CVM)
@fundos_bp.route('/atualizar_cotas_fundos_anbima', methods=['POST'])
@login_required
def atualizar_cotas_fundos_anbima():
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        
        # Buscar todos os CNPJs dos fundos cadastrados
        fundos = db.query(InfoFundo).all()
        cnpjs = [fundo.cnpj for fundo in fundos]
        
        # Usar o método batch da ANBIMA (similar ao que você fez com CVM)
        info_anbima_batch = extract_service.extracao_anbima_fundos_batch(cnpjs)
        
        if not info_anbima_batch:
            flash('Não foi possível obter dados da ANBIMA.')
            return redirect(url_for('fundos.listar_fundos'))
        
        fundos_atualizados = 0
        
        for fundo in fundos:
            if fundo.cnpj in info_anbima_batch:
                info_anbima = info_anbima_batch[fundo.cnpj]
                
                # Atualizar valor da cota se disponível
                if info_anbima.get('valor_cota'):
                    fundo.valor_cota = float(info_anbima['valor_cota'])
                    fundo.data_atualizacao = datetime.now()
                    fundos_atualizados += 1
        
        if fundos_atualizados > 0:
            db.commit()
            flash(f'Cotas de {fundos_atualizados} fundos atualizadas via ANBIMA!')
        else:
            flash('Nenhum fundo foi atualizado via ANBIMA.')
        
        return redirect(url_for('fundos.listar_fundos'))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao atualizar cotas via ANBIMA: {str(e)}')
        return redirect(url_for('fundos.listar_fundos'))
    finally:
        if 'db' in locals() and db:
            db.close()


# BUSCAR ÍNDICES ANBIMA (similar ao seu BCB)
@fundos_bp.route('/buscar_indices_anbima')
@login_required
def buscar_indices_anbima():
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        
        # Buscar índices dos últimos 30 dias (similar ao seu padrão BCB)
        from datetime import datetime, timedelta
        hoje = datetime.now()
        data_fim = hoje.strftime('%Y-%m-%d')
        data_inicio = (hoje - timedelta(days=30)).strftime('%Y-%m-%d')
        
        df_indices = extract_service.extracao_anbima_indices(data_inicio, data_fim)
        
        if not df_indices.empty:
            flash(f'Índices ANBIMA obtidos: {len(df_indices)} registros', "success")
            # Aqui você pode salvar os índices no banco ou exibir na tela
            print(df_indices.head())  # Para debug
        else:
            flash('Nenhum índice foi obtido da ANBIMA', "warning")
        
        return redirect(url_for('fundos.listar_fundos'))
        
    except Exception as e:
        flash(f'Erro ao buscar índices ANBIMA: {str(e)}', "error")
        return redirect(url_for('fundos.listar_fundos'))
    finally:
        if 'db' in locals() and db:
            db.close()


# EXEMPLO DE USO COMBINADO (CVM + ANBIMA)
@fundos_bp.route('/atualizar_fundos_hibrido', methods=['POST'])
@login_required
def atualizar_fundos_hibrido():
    """
    Usa CVM para cotas (mais confiável) e ANBIMA para dados complementares
    """
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        
        # 1. Tentar CVM primeiro (seu método atual)
        from datetime import datetime, timedelta
        hoje = datetime.now()
        ano = str(hoje.year)
        mes = f"{hoje.month:02d}"
        
        df_cotas = extract_service.extracao_cvm(ano, mes)
        if df_cotas.empty:
            mes_anterior = hoje.replace(day=1) - timedelta(days=1)
            ano = str(mes_anterior.year)
            mes = f"{mes_anterior.month:02d}"
            df_cotas = extract_service.extracao_cvm(ano, mes)
        
        # 2. Complementar com ANBIMA
        fundos = db.query(InfoFundo).all()
        cnpjs = [fundo.cnpj for fundo in fundos]
        info_anbima_batch = extract_service.extracao_anbima_fundos_batch(cnpjs)
        
        fundos_atualizados = 0
        
        for fundo in fundos:
            cnpj_normalizado = fundo.cnpj.replace('.', '').replace('/', '').replace('-', '')
            atualizado = False
            
            # Priorizar CVM para cotas
            if not df_cotas.empty:
                df_fundo = df_cotas[df_cotas['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '') == cnpj_normalizado]
                if not df_fundo.empty:
                    df_recente = df_fundo.sort_values('DT_COMPTC', ascending=False).iloc[0]
                    fundo.valor_cota = df_recente['VL_QUOTA']
                    atualizado = True
            
            # Usar ANBIMA como fallback ou para dados complementares
            elif fundo.cnpj in info_anbima_batch:
                info_anbima = info_anbima_batch[fundo.cnpj]
                if info_anbima.get('valor_cota'):
                    fundo.valor_cota = float(info_anbima['valor_cota'])
                    atualizado = True
            
            if atualizado:
                fundo.data_atualizacao = datetime.now()
                fundos_atualizados += 1
        
        if fundos_atualizados > 0:
            db.commit()
            flash(f'Atualização híbrida concluída: {fundos_atualizados} fundos atualizados!', "success")
        else:
            flash('Nenhum fundo foi atualizado.', "warning")
        
        return redirect(url_for('fundos.listar_fundos'))
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro na atualização híbrida: {str(e)}', "error")
        return redirect(url_for('fundos.listar_fundos'))
    finally:
        if 'db' in locals() and db:
            db.close()