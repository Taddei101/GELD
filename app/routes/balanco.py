"""
Rotas para balanceamento de carteiras
"""

import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
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
        
        # Buscar percentuais salvos (% de cada objetivo sobre o total da
        # classe, somando regular + previdência — mesmo denominador para
        # todos os objetivos, para a linha somar 100% de fato)
        from app.models.geld_models import DistribuicaoObjetivo, TipoObjetivoEnum
        percentuais_salvos = {}
        for objetivo in objetivos:
            if objetivo.tipo_objetivo == TipoObjetivoEnum.previdencia:
                percentuais_salvos[objetivo.id] = {
                    c: ((totais_atuais.get(c, 0.0) - totais_regular.get(c, 0.0)) / totais_atuais[c] * 100)
                       if totais_atuais.get(c) else 0.0
                    for c in TODAS_CLASSES
                }
                continue

            dist = db.query(DistribuicaoObjetivo).filter_by(objetivo_id=objetivo.id).first()
            if dist:
                percentuais_salvos[objetivo.id] = {
                    c: (getattr(dist, f'perc_{c}') * totais_regular.get(c, 0.0) / totais_atuais[c])
                       if totais_atuais.get(c) else 0.0
                    for c in TODAS_CLASSES
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
        ipca_anual = ipca.ipca if ipca else 4.5      #REVER ESTA ESQUISITO ISSO AQUI
        
        for objetivo in objetivos:
            matriz = BalanceamentoService.buscar_matriz_alvo(objetivo, db)
            matrizes_risco[objetivo.id] = matriz
            percentuais_alvo_por_objetivo[objetivo.id] = BalanceamentoService._percentuais_da_matriz(matriz)
            
            # Calcular VP Ideal
            vp_ideal = BalanceamentoService.calcular_vp_ideal(objetivo, ipca_anual)
            vp_ideal_por_objetivo[objetivo.id] = vp_ideal
        
        
        # Calcular capital órfão
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

        # Operações sem previdência: soma o gap_individual só dos objetivos
        # não-previdência por classe — ignora inteiramente o que a previdência
        # precisa organicamente e o que ela recebe de excedente via cascata.
        todas_classes = ['baixo_di', 'baixo_rfx', 'moderado', 'alto', 'ouro', 'dolar', 'cripto', 'internacional', 'fii']
        operacoes_sem_prev = {}
        for classe in todas_classes:
            valor = sum(
                obj['gap_individual'].get(classe, 0.0)
                for obj in resultado.get('resultados_por_objetivo', [])
                if obj.get('tipo_objetivo') != 'previdencia'
            )
            if valor > 100:
                operacoes_sem_prev[classe] = {'tipo': 'COMPRAR', 'valor': round(valor, 2)}
            elif valor < -100:
                operacoes_sem_prev[classe] = {'tipo': 'VENDER', 'valor': round(abs(valor), 2)}
        resultado['operacoes_sem_prev'] = operacoes_sem_prev or None

        # novos_percentuais (usado para persistir DistribuicaoObjetivo.perc_*)
        # tem como denominador só o pool regular — nas classes onde só a
        # previdência tem saldo (ex: ouro, cripto), isso fica sempre 0% pra
        # todo mundo. percentuais_exibicao é só para a tabela da tela,
        # normalizando pelo total real (regular + previdência) por classe.
        totais_atuais_dict = resultado.get('totais_atuais', {})
        totais_regular_dict = resultado.get('totais_regular', {})
        for obj_resultado in resultado.get('resultados_por_objetivo', []):
            if obj_resultado.get('tipo_objetivo') == 'previdencia':
                obj_resultado['percentuais_exibicao'] = {
                    c: ((totais_atuais_dict.get(c, 0.0) - totais_regular_dict.get(c, 0.0)) / totais_atuais_dict[c] * 100)
                       if totais_atuais_dict.get(c) else 0.0
                    for c in todas_classes
                }
            else:
                obj_resultado['percentuais_exibicao'] = {
                    c: (obj_resultado['novos_percentuais'][c] * totais_regular_dict.get(c, 0.0) / totais_atuais_dict[c])
                       if totais_atuais_dict.get(c) else 0.0
                    for c in todas_classes
                }

        # Salvar no banco (evita limite de 4KB do cookie de sessão)
        cliente.balanceamento_pendente_json = json.dumps(resultado)
        db.commit()

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
        # Recuperar resultado do banco
        cliente = db.query(Cliente).get(cliente_id)
        raw = cliente.balanceamento_pendente_json if cliente else None
        resultado = json.loads(raw) if raw else None

        if not resultado or resultado.get('cliente_id') != cliente_id:
            flash('Resultado não encontrado. Calcule novamente.', 'error')
            return redirect(url_for('balanco.iniciar', cliente_id=cliente_id))
        
        # Aplicar
        BalanceamentoService.aplicar_balanceamento(resultado, db)

        # Persistir operações e limpar pendente
        operacoes = resultado.get('operacoes_liquidas', {})
        cliente.ultimo_balanceamento_json = json.dumps({
            **operacoes,
            'sem_prev': resultado.get('operacoes_sem_prev'),
        })
        cliente.balanceamento_pendente_json = None
        db.commit()

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
    db = create_session()
    try:
        cliente = db.query(Cliente).get(cliente_id)
        if cliente:
            cliente.balanceamento_pendente_json = None
            db.commit()
    finally:
        db.close()
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


