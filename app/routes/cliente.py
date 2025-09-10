from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from app.services.global_services import GlobalServices,login_required
from app.models.geld_models import create_session,RiscoEnum, BancoEnum, Cliente, StatusEnum, PosicaoFundo, InfoFundo, Objetivo
from datetime import datetime
from functools import wraps
from sqlalchemy import func

cliente_bp = Blueprint('cliente', __name__)



#REGISTRAR CLIENTE
@cliente_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_client():
    if request.method == 'GET':
        return render_template('cliente/register_client.html')
        
    try:
        db = create_session()
        global_service = GlobalServices(db)

        # Get form data
        nascimento = datetime.strptime(request.form['nascimento'], '%Y-%m-%d')
        banco = BancoEnum[request.form['banco']]
        cep = ''.join(filter(str.isdigit, request.form['cep']))
                
        # Criar novo cliente
        novo_cliente = global_service.create_classe(
            Cliente,
            nome=request.form['nome'],
            nascimento=nascimento,
            cpf=request.form['cpf'],
            email=request.form['email'],
            telefone=request.form['telefone'],
            banco=banco,
            cep=cep,
            endereco=request.form.get('endereco'),
            escolaridade=request.form.get('escolaridade'),
            status=StatusEnum.ativo
        )
        
        flash(f'Cliente {novo_cliente.nome} cadastrado com sucesso!',"success")

        return redirect(url_for('cliente.listar_clientes'))
        
    except ValueError as e:
        
        flash(f'Não foi possível cadastrar. {str(e)}',"error")
    except Exception as e:
        
        print(f'Não foi possível cadastrar. {str(e)}', "error")
    finally:
        db.close()
    
    return redirect(url_for('cliente.register_client'))

#LISTAR 

@cliente_bp.route('/clientes')
@login_required
def listar_clientes():
    try:
        db = create_session()
        global_service = GlobalServices(db)
        clientes = global_service.listar_classe(Cliente)
        return render_template('cliente/listar_clientes.html', clientes=clientes)
    except Exception as e:
        flash(f'Erro ao listar clientes: {str(e)}',"error")
        return redirect(url_for('dashboard.cliente_dashboard'))
    finally:
        db.close()

#DELETAR 
@cliente_bp.route('/delete/<int:cliente_id>', methods=['POST'])
@login_required
def delete_client(cliente_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)
        
        if global_service.delete(Cliente, cliente_id):
            flash('Cliente deletado com sucesso!', "success")
        else:
            flash('Cliente não encontrado.', "error")
            
        return redirect(url_for('cliente.listar_clientes'))
        
    except Exception as e:
        flash(f'Erro ao deletar cliente: {str(e)}')
        return redirect(url_for('cliente.listar_clientes'))
    finally:
        db.close()

#EDITAR 
@cliente_bp.route('/edit/<int:cliente_id>', methods=['GET','POST'])
@login_required
def edit_client(cliente_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        if request.method == 'GET':
            cliente = global_service.get_by_id(Cliente, cliente_id)
            if not cliente:
                flash('Cliente não encontrado', "error")
                return redirect(url_for('cliente.listar_clientes'))
            return render_template('cliente/edit_client.html', cliente=cliente)
        
        elif request.method =='POST':
            dados_atualizados = {
                
                'nome': request.form['nome'],
                'email': request.form['email'],
                'telefone': request.form['telefone'],
                'cep': int(request.form['cep']),
                'endereco': request.form.get('endereco'),
                'escolaridade': request.form.get('escolaridade')
                
            }

            # Trata o campo nascimento (se presente no formulário)
            if 'nascimento' in request.form and request.form['nascimento']:
                dados_atualizados['nascimento'] = datetime.strptime(request.form['nascimento'], '%Y-%m-%d')
            
            # Trata o campo banco (se presente no formulário)
            if 'banco' in request.form and request.form['banco']:
                dados_atualizados['banco'] = BancoEnum[request.form['banco']]

            #trata o campo status
            if 'status' in request.form and request.form['status']:
                dados_atualizados['status'] = StatusEnum[request.form['status']]

            cliente_atualizado = global_service.editar_classe(Cliente, cliente_id, **dados_atualizados)
            
            if cliente_atualizado:
                flash('Cliente atualizado com sucesso!', "success")
                return redirect(url_for('cliente.info_cliente', cliente_id=cliente_id))
            else:
                flash('Cliente não encontrado.',"error")
                return redirect(url_for('cliente.listar_clientes'))
                
            
        

    except ValueError as e:
        flash(f'Erro de validação: {str(e)}',"error")
    except Exception as e:
        flash(f'Erro ao editar cliente: {str(e)}',"error")
    finally:
        db.close()
        
    

#AREA CLIENTE
@cliente_bp.route('/cliente/<int:cliente_id>/area')
@login_required
def area_cliente(cliente_id):
    try:
        db = create_session()
        global_services = GlobalServices(db)
        n_objetivos = 0
        n_fundos = 0
        cliente = global_services.get_by_id(Cliente, cliente_id)
        if not cliente:
            flash('Cliente não encontrado.',"error")
            return redirect(url_for('cliente.listar_clientes'))

        has_positions = db.query(PosicaoFundo).filter(PosicaoFundo.cliente_id == cliente_id).first() is not None

        montante_cliente = 0.0
        
        n_objetivos = db.query(func.count(Objetivo.id).filter(Objetivo.cliente_id==cliente_id)).scalar() or 0
        n_fundos = db.query(func.count(PosicaoFundo.id).filter(PosicaoFundo.cliente_id==cliente_id)).scalar() or 0

        # NOVOS CÁLCULOS POR RISCO
        saldo_baixo = 0.0
        saldo_moderado = 0.0
        saldo_alto = 0.0
        saldo_fundo_di = 0.0

        if has_positions:
            # Montante total
            montante_cliente = float(db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id
            ).scalar() or 0.0)

            # Saldos por risco
            saldo_baixo = float(db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id,
                InfoFundo.risco == RiscoEnum.baixo
            ).scalar() or 0.0)

            saldo_moderado = float(db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id,
                InfoFundo.risco == RiscoEnum.moderado
            ).scalar() or 0.0)

            saldo_alto = float(db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id,
                InfoFundo.risco == RiscoEnum.alto
            ).scalar() or 0.0)

            saldo_fundo_di = float(db.query(
                func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
            ).join(
                InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id
            ).filter(
                PosicaoFundo.cliente_id == cliente_id,
                InfoFundo.risco == RiscoEnum.fundo_DI
            ).scalar() or 0.0)
        
        return render_template('cliente/area_cliente.html', 
                              cliente=cliente, 
                              montante_cliente=montante_cliente,
                              has_positions=has_positions,
                              n_objetivos=n_objetivos, 
                              n_fundos=n_fundos,
                              saldo_baixo=saldo_baixo,
                              saldo_moderado=saldo_moderado,
                              saldo_alto=saldo_alto,
                              saldo_fundo_di=saldo_fundo_di)

    except Exception as e:
        print(f'Erro ao acessar área do cliente: {str(e)}', "error")
        return redirect(url_for('cliente.listar_clientes'))
    
    finally:
        db.close()

        
#INFORMACAO PESSOAL
@cliente_bp.route('/cliente/<int:cliente_id>/info')
@login_required
def info_cliente(cliente_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)
        
        # Get client information
        cliente = global_service.get_by_id(Cliente, cliente_id)
        if not cliente:
            flash('Cliente não encontrado.', "error")
            return redirect(url_for('cliente.listar_clientes'))
        
        return render_template('cliente/info_cliente.html', cliente=cliente)
    
    except Exception as e:
        flash(f'Erro ao buscar informações do cliente: {str(e)}', "error")
        return redirect(url_for('cliente.area_cliente',cliente_id=cliente_id))
    
    finally:
        db.close()