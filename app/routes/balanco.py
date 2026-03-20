"""
Rotas para balanceamento de carteiras
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session as flask_session
from app.models.geld_models import Cliente, Objetivo, create_session, TODAS_CLASSES
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
        
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(Objetivo.prioridade.is_(None), Objetivo.prioridade, Objetivo.data_final).all()
        
        if not objetivos:
            flash('Cliente não possui objetivos. Cadastre objetivos primeiro.', 'warning')
            return redirect(url_for('objetivo.listar_objetivos', cliente_id=cliente_id))
        
        # Totais separados por domínio de fundo
        totais_regular = BalanceamentoService.calcular_totais_por_classe(cliente_id, db, excluir_previdencia=True)
        totais_atuais  = BalanceamentoService.calcular_totais_por_classe(cliente_id, db)

        # Calcular valores atuais por objetivo (pool correto por tipo)
        valores_por_objetivo = BalanceamentoService.calcular_valores_atuais_objetivos(
            cliente_id, totais_regular, db, totais_atuais
        )
        
        # Buscar percentuais salvos (fatias)
        from app.models.geld_models import DistribuicaoObjetivo
        percentuais_salvos = {}
        for objetivo in objetivos:
            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo.id).first()
            if dist:
                percentuais_salvos[objetivo.id] = {
                    c: getattr(dist, f'perc_{c}') for c in TODAS_CLASSES
                }
            else:
                percentuais_salvos[objetivo.id] = {c: 0.0 for c in TODAS_CLASSES}
        
        # Buscar matrizes de risco para cada objetivo
        matrizes_risco = {}
        vp_ideal_por_objetivo = {}
        percentuais_alvo_por_objetivo = {}
        
        # Pegar IPCA para calcular VP Ideal
        from app.models.geld_models import IndicadoresEconomicos
        ipca = db.query(IndicadoresEconomicos).order_by(
            IndicadoresEconomicos.data_atualizacao.desc()
        ).first()
        ipca_anual = ipca.ipca if ipca else 4.5
        
        for objetivo in objetivos:
            matriz = BalanceamentoService.buscar_matriz_alvo(objetivo, db)
            matrizes_risco[objetivo.id] = matriz
            percentuais_alvo_por_objetivo[objetivo.id] = BalanceamentoService._percentuais_da_matriz(matriz)
            
            # Calcular VP Ideal
            vp_ideal = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)
            vp_ideal_por_objetivo[objetivo.id] = vp_ideal
        
        
        # NOVO: Calcular capital órfão
        capital_alocado = {c: 0.0 for c in TODAS_CLASSES}

        for obj_id, valores in valores_por_objetivo.items():
            for classe in TODAS_CLASSES:
                capital_alocado[classe] += valores[classe]

        capital_orfao = {
            c: totais_atuais[c] - capital_alocado[c]
            for c in TODAS_CLASSES
        }

        total_orfao = sum(capital_orfao.values())
        
        
        
        
        return render_template(
            'balanco/balance_objetivos.html',
            cliente=cliente,
            objetivos=objetivos,
            totais_atuais=totais_atuais,
            valores_por_objetivo=valores_por_objetivo,
            percentuais_salvos=percentuais_salvos,  
            matrizes_risco=matrizes_risco,
            vp_ideal_por_objetivo=vp_ideal_por_objetivo,
            capital_orfao=capital_orfao,  
            total_orfao=total_orfao,
            percentuais_alvo_por_objetivo=percentuais_alvo_por_objetivo
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
        
        # Coletar aportes do formulário (incluindo zeros)
        aportes_por_objetivo = []
        
        for key, value in request.form.items():
            if key.startswith('aporte_'):
                objetivo_id = int(key.split('_')[1])
                valor = float(value or 0)
                
                #  Incluir TODOS os objetivos, mesmo com aporte zero
                aportes_por_objetivo.append({
                    'objetivo_id': objetivo_id,
                    'valor_aporte': valor
                })
                      
        
        # Processar balanceamento com cascata de excedentes
        resultado = BalanceamentoService.executar_cascata_e_rebalancear(
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
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(Objetivo.prioridade.is_(None), Objetivo.prioridade, Objetivo.data_final).all()
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





@balanco_bp.route('/editar_fatias/<int:cliente_id>', methods=['GET'])
@login_required
def editar_fatias(cliente_id):
    """Formulário para editar percentuais (fatias) dos objetivos manualmente"""
    from app.models.geld_models import DistribuicaoObjetivo
    
    db = create_session()
    
    try:
        cliente = db.query(Cliente).get(cliente_id)
        if not cliente:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('dashboard.index'))
        
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(Objetivo.prioridade.is_(None), Objetivo.prioridade, Objetivo.data_final).all()
        
        if not objetivos:
            flash('Cliente não possui objetivos cadastrados.', 'warning')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        
        # Buscar percentuais salvos para cada objetivo
        percentuais_salvos = {}
        for objetivo in objetivos:
            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo.id).first()
            if dist:
                percentuais_salvos[objetivo.id] = {
                    c: getattr(dist, f'perc_{c}') for c in TODAS_CLASSES
                }
            else:
                percentuais_salvos[objetivo.id] = {c: 0.0 for c in TODAS_CLASSES}
        
        return render_template(
            'balanco/editar_fatias.html',
            cliente=cliente,
            objetivos=objetivos,
            percentuais_salvos=percentuais_salvos
        )
    
    except Exception as e:
        flash(f'Erro ao carregar edição: {str(e)}', 'error')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    
    finally:
        db.close()


@balanco_bp.route('/salvar_fatias/<int:cliente_id>', methods=['POST'])
@login_required
def salvar_fatias(cliente_id):
    """Salvar percentuais editados manualmente"""
    from app.models.geld_models import DistribuicaoObjetivo
    
    db = create_session()
    
    try:
        cliente = db.query(Cliente).get(cliente_id)
        if not cliente:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('dashboard.index'))
        
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).order_by(Objetivo.prioridade.is_(None), Objetivo.prioridade, Objetivo.data_final).all()
        
        # Coletar dados do formulário
        dados_objetivos = {}
        for objetivo in objetivos:
            dados_objetivos[objetivo.id] = {
                c: float(request.form.get(f'{c}_{objetivo.id}', 0))
                for c in TODAS_CLASSES
            }
        
        # Validação: soma por classe deve ser 100%
        totais_por_classe = {c: 0.0 for c in TODAS_CLASSES}
        for percentuais in dados_objetivos.values():
            for c in TODAS_CLASSES:
                totais_por_classe[c] += percentuais[c]
        
        erros = []
        for c, total in totais_por_classe.items():
            if abs(total - 100.0) > 0.01:
                erros.append(f'{c.replace("_", " ").title()}: {total:.2f}%')
        
        if erros:
            flash(f'Erro: As fatias devem somar 100% por classe. Totais incorretos: {", ".join(erros)}', 'error')
            return redirect(url_for('balanco.editar_fatias', cliente_id=cliente_id))
        
        # Salvar no banco
        for objetivo_id, percentuais in dados_objetivos.items():
            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo_id).first()
            
            if not dist:
                dist = DistribuicaoObjetivo(objetivo_id=objetivo_id)
                db.add(dist)
            
            for c in TODAS_CLASSES:
                setattr(dist, f'perc_{c}', percentuais[c])
        
        db.commit()
        flash('Fatias atualizadas com sucesso!', 'success')
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    
    except ValueError as e:
        flash(f'Erro nos valores informados: {str(e)}', 'error')
        return redirect(url_for('balanco.editar_fatias', cliente_id=cliente_id))
    
    except Exception as e:
        db.rollback()
        flash(f'Erro ao salvar: {str(e)}', 'error')
        return redirect(url_for('balanco.editar_fatias', cliente_id=cliente_id))
    
    finally:
        db.close()