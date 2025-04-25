from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.global_services import GlobalServices, login_required
from app.services.balance_service import Balance
from app.models.geld_models import create_session, Cliente, Objetivo

balanco_bp = Blueprint('balancos', __name__)

@balanco_bp.route('/balanco/<int:cliente_id>/balance_objetivos', methods=['GET', 'POST'])
@login_required
def balance_objetivos(cliente_id):
    db = None
    try:
        db = create_session()
        global_service = GlobalServices(db)
        
        # PEGA O CLIENTE
        cliente = global_service.get_by_id(Cliente, cliente_id)
        if not cliente:
            flash(f"Cliente com ID {cliente_id} não encontrado")
            return redirect(url_for('index'))
                
        # PEGA OS OBJETIVOS
        objetivos = db.query(Objetivo).filter(Objetivo.cliente_id == cliente_id).all()
        for obj in objetivos:
            obj.valor_real = float(obj.valor_real)

        if not objetivos:
            flash("Este cliente não possui objetivos cadastrados")
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))

        if request.method == 'POST':
            try:
                aporte = float(request.form['aporte'])
                if aporte <= 0:
                    flash("O valor do aporte deve ser maior que zero")
                    return render_template('balanco/balance_objetivos.html', 
                                          cliente=cliente, 
                                          objetivos=objetivos,
                                          aporte=None)
                                
                balance_service = Balance(db)
                
                # Agora passamos os objetivos já buscados em vez do cliente_id
                quotas = balance_service.balancear_aporte(aporte, objetivos)
                print(f"Quotas calculadas: {quotas}")
                
                if "error" in quotas:
                    flash(quotas["error"])
                    return redirect(url_for('balancos.balance_objetivos', cliente_id=cliente_id))
                
                # Balancear cada quota por tipo de risco
                resultado_balanceamento = {}
                total_risco_baixo = 0
                total_risco_moderado = 0
                total_risco_alto = 0

                for objetivo_id, quota in quotas.items():
                    # Encontrar o objeto objetivo correspondente ao ID
                    objetivo = next((obj for obj in objetivos if obj.id == objetivo_id), None)
                    
                    # Passar o objeto objetivo em vez do ID
                    balanceamento = balance_service.balancear_quota(quota, objetivo)
                    resultado_balanceamento[objetivo_id] = balanceamento
    
                    # Calcular totais
                    total_risco_baixo += balanceamento['distribuicao']['risco_baixo']['valor']
                    total_risco_moderado += balanceamento['distribuicao']['risco_moderado']['valor']
                    total_risco_alto += balanceamento['distribuicao']['risco_alto']['valor']

                # PASSA O RESULTADO PRO TEMPLATE
                return render_template('balanco/balance_objetivos.html', 
                      cliente=cliente, 
                      objetivos=objetivos,
                      resultado_balanceamento=resultado_balanceamento,
                      total_risco_baixo=total_risco_baixo,
                      total_risco_moderado=total_risco_moderado,
                      total_risco_alto=total_risco_alto,
                      aporte=aporte)
                
            except ValueError:
                flash('Valor de aporte inválido. Por favor, digite um número válido.')
            except Exception as e:
                flash(f'Erro ao calcular balanceamento: {str(e)}')
        
        # MOSTRA O FORMULARIO CASO NAO TENHA METODO
        return render_template('balanco/balance_objetivos.html', 
                              cliente=cliente, 
                              objetivos=objetivos,
                              aporte=None)
        
    except Exception as e:
        flash(f'Erro ao acessar balanceamento: {str(e)}')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    finally:
        if db:
            db.close()