from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.global_services import GlobalServices, login_required
from app.models.geld_models import create_session, Cliente, Objetivo
from app.services.balance_service import balance_objective

balanco_bp = Blueprint('balancos', __name__)

@balanco_bp.route('/objetivo/<int:objetivo_id>/balancear', methods=['GET', 'POST'])
@login_required
def balancear_objetivo(objetivo_id):
    """
    Balanceia um aporte para um objetivo específico segundo a matriz de risco
    """
    db = None
    try:
        db = create_session()
        
        # Buscar objetivo
        objetivo = db.query(Objetivo).get(objetivo_id)
        if not objetivo:
            flash("Objetivo não encontrado", "error")
            return redirect(url_for('dashboard.index'))
        
        # Buscar cliente para passar pro template
        cliente = db.query(Cliente).get(objetivo.cliente_id)
        if not cliente:
            flash("Cliente não encontrado", "error")
            return redirect(url_for('dashboard.index'))
        
        if request.method == 'POST':
            try:
                # Pegar valor do aporte
                aporte = float(request.form.get('aporte', 0))
                
                if aporte <= 0:
                    flash("O valor do aporte deve ser maior que zero", "warning")
                    return render_template('balanco/balancear_objetivo.html',
                                         objetivo=objetivo,
                                         cliente=cliente,
                                         resultado=None)
                
                # Chamar a função de balanceamento
                resultado = balance_objective(aporte, objetivo)
                
                # Renderizar com resultado
                return render_template('balanco/balancear_objetivo.html',
                                     objetivo=objetivo,
                                     cliente=cliente,
                                     resultado=resultado)
                
            except ValueError:
                flash("Valor de aporte inválido. Digite um número válido.", "error")
            except Exception as e:
                flash(f"Erro ao calcular balanceamento: {str(e)}", "error")
        
        # GET: Mostrar formulário
        return render_template('balanco/balancear_objetivo.html',
                             objetivo=objetivo,
                             cliente=cliente,
                             resultado=None)
        
    except Exception as e:
        flash(f"Erro ao acessar balanceamento: {str(e)}", "error")
        return redirect(url_for('dashboard.index'))
    finally:
        if db:
            db.close()