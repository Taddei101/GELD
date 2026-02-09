from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.services.global_services import GlobalServices,login_required
from app.models.geld_models import create_session, Objetivo, Cliente, IndicadoresEconomicos
from datetime import datetime
from functools import wraps
from app.services.objetivo_services import ObjetivoServices

objetivo_bp = Blueprint('objetivo', __name__)


# CRIAR OBJETIVO
@objetivo_bp.route('/cliente/<int:cliente_id>/add_objetivo', methods=['GET', 'POST'])
@login_required
def add_objetivo(cliente_id):
    if request.method == 'GET':
        # Buscar o cliente para mostrar informações no formulário
        db = create_session()
        global_service = GlobalServices(db)
        cliente = global_service.get_by_id(Cliente, cliente_id)
        db.close()
        
        if not cliente:
            flash('Cliente não encontrado.')
            return redirect(url_for('cliente.listar_clientes'))
            
        return render_template('objetivo/add_objetivo.html', cliente=cliente)
    
    #CREATE
    try:
        db = create_session()
        global_service = GlobalServices(db)
        
        cliente = global_service.get_by_id(Cliente, cliente_id)
        if not cliente:
            flash('Cliente não encontrado.')
            return redirect(url_for('cliente.listar_clientes'))
        
        
        data_inicial = datetime.strptime(request.form['data_inicial'], '%Y-%m-%d')
        data_final = datetime.strptime(request.form['data_final'], '%Y-%m-%d')
        
                        
        
        novo_objetivo = global_service.create_classe(
            Objetivo,
            cliente_id=cliente_id,
            nome_objetivo=request.form['nome_objetivo'],
            tipo_objetivo=request.form['tipo_objetivo'],
            valor_final=float(request.form['valor_final']),
            valor_inicial=float(request.form['valor_inicial']),
            data_inicial=data_inicial,
            data_final=data_final
        )
        
        flash(f'Objetivo "{novo_objetivo.nome_objetivo}" criado com sucesso!')
        return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
        
    except ValueError as e:
        flash(f'Erro de validação: {str(e)}')
    except Exception as e:
        flash(f'Erro ao cadastrar objetivo: {str(e)}')
    finally:
        db.close()
    
    return redirect(url_for('objetivo.add_objetivo', cliente_id=cliente_id))

# EDITAR OBJETIVO
@objetivo_bp.route('/objetivo/<int:objetivo_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_objetivo(objetivo_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)
        
        if request.method == 'GET':
            objetivo = global_service.get_by_id(Objetivo, objetivo_id)
            print(f"Objetivo encontrado: {objetivo.id}")

            if not objetivo:
                flash('Objetivo não encontrado.')
                return redirect(url_for('objetivo.listar_objetivos'))
            
            # Buscar o cliente associado
            cliente = global_service.get_by_id(Cliente, objetivo.cliente_id)
            print(f"Cliente encontrado: {cliente.nome}")
            
            return render_template('objetivo/edit_objetivo.html', objetivo=objetivo,  cliente=cliente)
        
        elif request.method == 'POST':
            
            # Atualizar objetivo
            print("Recebida solicitação POST para editar objetivo.")
            dados_atualizados = {
                'nome_objetivo': request.form['nome_objetivo'],
                'tipo_objetivo': request.form['tipo_objetivo'],
                'valor_final': float(request.form['valor_final']),
                'data_final': datetime.strptime(request.form['data_final'], '%Y-%m-%d')
            }
            
            objetivo_atualizado = global_service.editar_classe(Objetivo, objetivo_id, **dados_atualizados)
            
            if objetivo_atualizado:
                flash('Objetivo atualizado com sucesso!')
                return redirect(url_for('objetivo.listar_objetivos', cliente_id=objetivo_atualizado.cliente_id))
            else:
                flash('Objetivo não encontrado.')
                return redirect(url_for('cliente.dashboard'))
    
    except Exception as e:
        print(f"Erro inesperado: {e}")  
        flash(f'Erro ao processar objetivo: {str(e)}')
        cliente_id = None
        if 'objetivo' in locals() and objetivo:
            cliente_id = objetivo.cliente_id

        return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id if cliente_id else 1)) 
    finally:
        db.close()

# DELETAR OBJETIVO
@objetivo_bp.route('/objetivo/<int:objetivo_id>/delete', methods=['POST'])
@login_required
def delete_objetivo(objetivo_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)
                
        objetivo = global_service.get_by_id(Objetivo, objetivo_id)
        if not objetivo:
            flash('Objetivo não encontrado.')
            return redirect(url_for('cliente.dashboard'))
            
        cliente_id = objetivo.cliente_id
        
        # Deletar o objetivo
        if global_service.delete(Objetivo, objetivo_id):
            flash('Objetivo deletado com sucesso!')
            return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
        else:
            flash('Objetivo não encontrado.')
            return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
        
    except Exception as e:
        flash(f'Erro ao deletar objetivo: {str(e)}')
        return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
    finally:
        db.close()


#LISTAR
@objetivo_bp.route('/cliente/<int:cliente_id>/listar_objetivos')
@login_required
def listar_objetivos(cliente_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        cliente = global_service.get_by_id(Cliente, cliente_id)
        if not cliente:
            flash('Cliente não encontrado')
            return redirect(url_for('cliente.listar_clientes'))
        
        objetivos = db.query(Objetivo).filter(Objetivo.cliente_id == cliente_id).all()
        
        # ✅ CALCULAR VALORES ATUAIS DINAMICAMENTE (mesma lógica do balanceamento)
        from app.services.balance_service import BalanceamentoService
        
        totais_atuais = BalanceamentoService.calcular_totais_por_classe(cliente_id, db)
        valores_por_objetivo = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_atuais, db
        )
        
        ipca_mes = db.query(IndicadoresEconomicos.ipca_mes).order_by(
            IndicadoresEconomicos.data_atualizacao.desc()
        ).scalar() or 0
        
        # Check if the "calcular" parameter is present in the URL
        calcular_aporte = request.args.get('calcular', 'false') == 'true'
        
        calculo_aportes = None
        if calcular_aporte:
            # Fixed additional annual rate of 3.5%
            taxa_anual_adicional = 3.5
            
            # Calculate the required contributions
            objetivo_service = ObjetivoServices(db)
            calculo_aportes = objetivo_service.calc_aportes_cliente(cliente_id, taxa_anual_adicional)
            
            if "error" in calculo_aportes:
                flash(f'Erro ao calcular aportes: {calculo_aportes["error"]}')
                calcular_aporte = False
        
        return render_template('objetivo/listar_objetivos.html', 
                              objetivos=objetivos, 
                              cliente=cliente, 
                              valores_por_objetivo=valores_por_objetivo,  # ✅ NOVA VARIÁVEL
                              ipca_mes=ipca_mes,
                              calculo_aportes=calculo_aportes,
                              mostrar_calculo=calcular_aporte)

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao listar objetivos: {str(e)}')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    finally:
        if 'db' in locals() and db:
            db.close()