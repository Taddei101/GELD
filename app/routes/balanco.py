# app/routes/balanco.py
"""
Rotas para balanceamento de carteiras
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session as flask_session
from app.models.geld_models import Cliente, Objetivo, create_session
from app.services.balance_service import BalanceamentoService
from app.services.global_services import login_required

balanco_bp = Blueprint('balanco', __name__, url_prefix='/balanco')


@balanco_bp.route('/iniciar/<int:cliente_id>', methods=['GET'])
@login_required
def iniciar(cliente_id):
    """Formulário inicial - informar aportes por objetivo"""
    db = create_session()
    
    try:
        cliente = db.query(Cliente).get(cliente_id)
        if not cliente:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('dashboard.index'))
        
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        
        if not objetivos:
            flash('Cliente não possui objetivos. Cadastre objetivos primeiro.', 'warning')
            return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
        
        # Calcular totais atuais por classe (do Advisor)
        totais_atuais = BalanceamentoService.calcular_totais_por_classe(cliente_id, db)
        
        # Calcular valores atuais por objetivo (aplicando % salvos)
        valores_por_objetivo = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_atuais, db
        )
        
        # Buscar matrizes de risco para cada objetivo
        matrizes_risco = {}
        vp_ideal_por_objetivo = {}
        
        # Pegar IPCA para calcular VP Ideal
        from app.models.geld_models import IndicadoresEconomicos
        ipca = db.query(IndicadoresEconomicos).order_by(
            IndicadoresEconomicos.data_atualizacao.desc()
        ).first()
        ipca_anual = ipca.ipca if ipca else 4.5
        
        for objetivo in objetivos:
            matriz = BalanceamentoService.buscar_matriz_alvo(objetivo, db)
            matrizes_risco[objetivo.id] = matriz
            
            # Calcular VP Ideal
            vp_ideal = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)
            vp_ideal_por_objetivo[objetivo.id] = vp_ideal
        
        return render_template(
            'balanco/balance_objetivos.html',
            cliente=cliente,
            objetivos=objetivos,
            totais_atuais=totais_atuais,
            valores_por_objetivo=valores_por_objetivo,
            matrizes_risco=matrizes_risco,
            vp_ideal_por_objetivo=vp_ideal_por_objetivo
        )
    
    except Exception as e:
        flash(f'Erro ao carregar balanceamento: {str(e)}', 'error')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    
    finally:
        db.close()


@balanco_bp.route('/calcular/<int:cliente_id>', methods=['POST'])
@login_required
def calcular(cliente_id):
    """Processar balanceamento"""
    db = create_session()
    
    try:
        cliente = db.query(Cliente).get(cliente_id)
        if not cliente:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('dashboard.index'))
        
        # Coletar aportes do formulário
        # Formato: aporte_1=10000, aporte_2=5000, etc
        aportes_por_objetivo = []
        
        for key, value in request.form.items():
            if key.startswith('aporte_'):
                objetivo_id = int(key.split('_')[1])
                valor = float(value or 0)
                
                if valor > 0:
                    aportes_por_objetivo.append({
                        'objetivo_id': objetivo_id,
                        'valor_aporte': valor
                    })
        
        if not aportes_por_objetivo:
            flash('Informe ao menos um aporte', 'warning')
            return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
        
        # Processar balanceamento
        resultado = BalanceamentoService.processar_balanceamento(
            cliente_id, aportes_por_objetivo, db
        )
        
        # Salvar na sessão Flask
        flask_session['balanceamento_resultado'] = resultado
        
        return render_template(
            'balanco/resultado.html',
            cliente=cliente,
            resultado=resultado
        )
    
    except ValueError as e:
        flash(f'Erro nos dados: {str(e)}', 'error')
        return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao calcular: {str(e)}', 'error')
        return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
    
    finally:
        db.close()


@balanco_bp.route('/aplicar/<int:cliente_id>', methods=['POST'])
@login_required
def aplicar(cliente_id):
    """Aplicar balanceamento - salvar percentuais"""
    db = create_session()
    
    try:
        # Recuperar resultado da sessão
        resultado = flask_session.get('balanceamento_resultado')
        
        if not resultado or resultado.get('cliente_id') != cliente_id:
            flash('Resultado não encontrado. Calcule novamente.', 'error')
            return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
        
        # Aplicar
        BalanceamentoService.aplicar_balanceamento(resultado, db)
        
        # Limpar sessão
        flask_session.pop('balanceamento_resultado', None)
        
        flash('Balanceamento aplicado com sucesso!', 'success')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    
    except Exception as e:
        db.rollback()
        flash(f'Erro ao aplicar: {str(e)}', 'error')
        return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
    
    finally:
        db.close()


@balanco_bp.route('/descartar/<int:cliente_id>', methods=['POST'])
@login_required
def descartar(cliente_id):
    """Descartar balanceamento"""
    flask_session.pop('balanceamento_resultado', None)
    flash('Balanceamento descartado', 'info')
    return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))


@balanco_bp.route('/resetar/<int:cliente_id>', methods=['POST'])
@login_required
def resetar_distribuicao(cliente_id):
    """Resetar/deletar todas as distribuições do cliente"""
    from app.models.geld_models import DistribuicaoObjetivo, Objetivo
    
    db = create_session()
    try:
        # Buscar objetivos do cliente
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        objetivo_ids = [obj.id for obj in objetivos]
        
        # Deletar distribuições
        deletados = db.query(DistribuicaoObjetivo).filter(
            DistribuicaoObjetivo.objetivo_id.in_(objetivo_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        flash(f'{deletados} distribuições resetadas com sucesso!', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'Erro ao resetar: {str(e)}', 'error')
    finally:
        db.close()
    
    return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))