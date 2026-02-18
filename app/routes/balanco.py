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
        
        # Buscar percentuais salvos (fatias)
        from app.models.geld_models import DistribuicaoObjetivo
        percentuais_salvos = {}
        for objetivo in objetivos:
            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo.id).first()
            if dist:
                percentuais_salvos[objetivo.id] = {
                    'baixo_di': dist.perc_baixo_di,
                    'baixo_rfx': dist.perc_baixo_rfx,
                    'moderado': dist.perc_moderado,
                    'alto': dist.perc_alto
                }
            else:
                percentuais_salvos[objetivo.id] = {
                    'baixo_di': 0.0,
                    'baixo_rfx': 0.0,
                    'moderado': 0.0,
                    'alto': 0.0
                }
        
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
        
        
        # ✅ NOVO: Calcular capital órfão
        capital_alocado = {
            'baixo_di': 0.0, 'baixo_rfx': 0.0, 'moderado': 0.0, 'alto': 0.0
        }

        for obj_id, valores in valores_por_objetivo.items():
            for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
                capital_alocado[classe] += valores[classe]

        capital_orfao = {
            classe: totais_atuais[classe] - capital_alocado[classe]
            for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']
        }

        total_orfao = sum(capital_orfao.values())
        
        # ✅ VALIDAR FATIAS (detectar inconsistências)
        fatias_validas, somas_fatias = BalanceamentoService.validar_fatias(cliente_id, db)
        
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
            fatias_validas=fatias_validas,
            somas_fatias=somas_fatias
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


@balanco_bp.route('/recalcular_fatias/<int:cliente_id>', methods=['POST'])
@login_required
def recalcular_fatias(cliente_id):
    """Recalcular fatias automaticamente baseado no pool real"""
    db = create_session()
    
    try:
        cliente = db.query(Cliente).get(cliente_id)
        if not cliente:
            flash('Cliente não encontrado', 'error')
            return redirect(url_for('dashboard.index'))
        
        # Verificar se há objetivos
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        if not objetivos:
            flash('Cliente não possui objetivos para recalcular.', 'warning')
            return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
        
        # Recalcular fatias
        BalanceamentoService.recalcular_fatias_do_pool(cliente_id, db)
        
        flash('✅ Fatias recalculadas com sucesso! Capital órfão foi redistribuído proporcionalmente.', 'success')
        return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        flash(f'Erro ao recalcular: {str(e)}', 'error')
        return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
    
    finally:
        db.close()


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
        
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        
        if not objetivos:
            flash('Cliente não possui objetivos cadastrados.', 'warning')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        
        # Buscar percentuais salvos para cada objetivo
        percentuais_salvos = {}
        for objetivo in objetivos:
            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo.id).first()
            if dist:
                percentuais_salvos[objetivo.id] = {
                    'baixo_di': dist.perc_baixo_di,
                    'baixo_rfx': dist.perc_baixo_rfx,
                    'moderado': dist.perc_moderado,
                    'alto': dist.perc_alto
                }
            else:
                # Se não existe distribuição, inicializa com zeros
                percentuais_salvos[objetivo.id] = {
                    'baixo_di': 0.0,
                    'baixo_rfx': 0.0,
                    'moderado': 0.0,
                    'alto': 0.0
                }
        
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
        
        objetivos = db.query(Objetivo).filter_by(cliente_id=cliente_id).all()
        
        # Coletar dados do formulário
        dados_objetivos = {}
        for objetivo in objetivos:
            dados_objetivos[objetivo.id] = {
                'baixo_di': float(request.form.get(f'baixo_di_{objetivo.id}', 0)),
                'baixo_rfx': float(request.form.get(f'baixo_rfx_{objetivo.id}', 0)),
                'moderado': float(request.form.get(f'moderado_{objetivo.id}', 0)),
                'alto': float(request.form.get(f'alto_{objetivo.id}', 0))
            }
        
        # Validação: Soma por classe de risco deve ser 100%
        totais_por_classe = {
            'baixo_di': 0.0,
            'baixo_rfx': 0.0,
            'moderado': 0.0,
            'alto': 0.0
        }
        
        for objetivo_id, percentuais in dados_objetivos.items():
            for classe in ['baixo_di', 'baixo_rfx', 'moderado', 'alto']:
                totais_por_classe[classe] += percentuais[classe]
        
        # Verificar se cada classe soma 100% (tolerância de 0.01 para arredondamento)
        erros = []
        for classe, total in totais_por_classe.items():
            if abs(total - 100.0) > 0.01:
                nome_classe = classe.replace('_', ' ').title()
                erros.append(f'{nome_classe}: {total:.2f}%')
        
        if erros:
            flash(f'Erro: As fatias devem somar 100% por classe. Totais incorretos: {", ".join(erros)}', 'error')
            return redirect(url_for('balanco.editar_fatias', cliente_id=cliente_id))
        
        # Salvar no banco
        for objetivo_id, percentuais in dados_objetivos.items():
            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo_id).first()
            
            if dist:
                # Atualizar existente
                dist.perc_baixo_di = percentuais['baixo_di']
                dist.perc_baixo_rfx = percentuais['baixo_rfx']
                dist.perc_moderado = percentuais['moderado']
                dist.perc_alto = percentuais['alto']
            else:
                # Criar novo
                nova_dist = DistribuicaoObjetivo(
                    objetivo_id=objetivo_id,
                    perc_baixo_di=percentuais['baixo_di'],
                    perc_baixo_rfx=percentuais['baixo_rfx'],
                    perc_moderado=percentuais['moderado'],
                    perc_alto=percentuais['alto']
                )
                db.add(nova_dist)
        
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