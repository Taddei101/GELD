from flask import Blueprint, render_template, redirect, url_for, flash, session
from app.services.global_services import login_required, GlobalServices
from app.services.distribuicao_capital_service import DistribuicaoCapitalService
from app.models.geld_models import create_session, Cliente, Objetivo
from decimal import Decimal

distribuicao_bp = Blueprint('distribuicao', __name__)

@distribuicao_bp.route('/cliente/<int:cliente_id>/distribuicao_capital')
@login_required
def distribuicao_capital(cliente_id):
    
    try:
        db = create_session()
        
        # Verificar se o cliente existe
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        if not cliente:
            flash("Cliente não encontrado")
            return redirect(url_for('dashboard.cliente_dashboard'))
        
        # Realizar a distribuição de capital
        servico = DistribuicaoCapitalService(db)
        resultado = servico.distribuir_capital(cliente_id)
        
        if "error" in resultado:
            flash(resultado["error"])
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        
        # Salvar o resultado na sessão para uso posterior
        session['distribuicao_resultado'] = resultado
        
        # Renderizar o template com o resultado
        return render_template('distribuicao/resultado_distribuicao.html', 
                              cliente=cliente,
                              resultado=resultado)
                              
    except Exception as e:
        flash(f"Erro ao gerar distribuição de capital: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    finally:
        if 'db' in locals():
            db.close()


@distribuicao_bp.route('/cliente/<int:cliente_id>/aplicar_alocacao')
@login_required
def aplicar_alocacao(cliente_id):
    """
    Aplica a alocação simulada, atualizando o valor_real de cada objetivo
    """
    try:
        # Verificar se há resultado na sessão
        if 'distribuicao_resultado' not in session:
            flash("Resultado da distribuição não encontrado. Por favor, realize a distribuição novamente.")
            return redirect(url_for('distribuicao.distribuicao_capital', cliente_id=cliente_id))
        
        resultado = session['distribuicao_resultado']
        
        db = create_session()
        global_service = GlobalServices(db)
        
        # Atualizar cada objetivo com o valor alocado
        for objetivo_id, objetivo_data in resultado['alocacao_por_objetivo'].items():
            try:
                objetivo_id = int(objetivo_id)  # Converter para inteiro
                valor_alocado = Decimal(str(objetivo_data['alocacao_total']))
                
                # Buscar o objetivo atual
                objetivo = global_service.get_by_id(Objetivo, objetivo_id)
                if objetivo:
                    # Atualizar o valor_real
                    global_service.editar_classe(
                        Objetivo, 
                        objetivo_id, 
                        valor_real=valor_alocado
                    )
                    
            except Exception as e:
                flash(f"Erro ao atualizar objetivo {objetivo_id}: {str(e)}")
                continue
        
        # Limpar a sessão
        if 'distribuicao_resultado' in session:
            del session['distribuicao_resultado']
        
        flash("Alocação aplicada com sucesso! Os valores reais dos objetivos foram atualizados.")
        return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
        
    except Exception as e:
        flash(f"Erro ao aplicar alocação: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    finally:
        if 'db' in locals():
            db.close()