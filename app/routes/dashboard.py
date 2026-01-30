from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.global_services import login_required
from app.services.extract_services import ExtractServices
from app.models.geld_models import create_session, Cliente, StatusEnum, IndicadoresEconomicos, Objetivo, PosicaoFundo, InfoFundo
from sqlalchemy import func, extract
from datetime import datetime, timedelta



dashboard_bp = Blueprint('dashboard', __name__)

#VARIAVEIS PARA EXPOR NO DASHBOARD
@dashboard_bp.route('/dashboard')
@login_required
def cliente_dashboard():
    
    db = create_session()
    num_clientes = 0
    ipca = None
    ipca_mes = None
    data_atualizacao = None
    mes_anterior = None
    ipca_mes_anterior = None
    num_fundos = 0
    capital_administrado = 0  

    try:
        num_clientes = db.query(func.count(Cliente.id)).filter(Cliente.status == StatusEnum.ativo).scalar() or 0
        num_fundos = db.query(func.count(InfoFundo.id)).scalar() or 0
        clientes_inativos = db.query(func.count(Cliente.id)).filter(Cliente.status == StatusEnum.inativo).scalar() or 0
        
        #Obter capital administrado
        capital_administrado = db.query(func.sum(PosicaoFundo.cotas * InfoFundo.valor_cota)
        ).join(InfoFundo, PosicaoFundo.fundo_id == InfoFundo.id).scalar() or 0.0
        

        # Obter a data do mês anterior
        today = datetime.now()
        mes_anterior_obj = today.replace(day=1) - timedelta(days=1)
        mes_anterior = mes_anterior_obj.strftime('%B/%Y')  # Nome do mês/ano
        
        # Buscar indicadores econômicos
        indicadores = db.query(IndicadoresEconomicos).first()
        if indicadores:
            ipca = indicadores.ipca
            ipca_mes = indicadores.ipca_mes
            
            if indicadores.data_atualizacao:                
                try:
                    data_atualizacao = indicadores.data_atualizacao.strftime('%d/%m/%Y')
                except:
                    data_atualizacao = str(indicadores.data_atualizacao)
        
        # Obter IPCA do mês anterior diretamente da API do Banco Central
        data_fim = datetime.now().strftime('%d/%m/%Y')
        data_inicio = (datetime.now() - timedelta(days=60)).strftime('%d/%m/%Y')
        codigo_ipca_mensal = 433  # Código do IPCA do mês anterior
        
        extract_service = ExtractServices(db)
        df_ipca_mensal = extract_service.extracao_bcb(codigo_ipca_mensal, data_inicio, data_fim)
        
        if not df_ipca_mensal.empty:
            ipca_mes_anterior = df_ipca_mensal.iloc[-1]['valor']

                
            if 'data' in df_ipca_mensal.columns:
                mes_referencia = df_ipca_mensal.iloc[-1]['data'].strftime('%m/%Y')
                mes_anterior = mes_referencia
        
    except Exception as e:
        flash(f'Erro ao carregar dashboard: {str(e)}', "error")

    finally:
        db.close()

    return render_template("cliente/dashboard.html",
                          num_clientes=num_clientes,
                          ipca=ipca,
                          ipca_mes=ipca_mes,
                          ipca_mes_anterior=ipca_mes_anterior,
                          data_atualizacao=data_atualizacao,
                          capital_administrado=capital_administrado,
                          clientes_inativos=clientes_inativos,
                          mes_anterior=mes_anterior,
                          num_fundos=num_fundos)
    

@dashboard_bp.route('/atualizar_indicadores', methods=['POST'])
@login_required
def atualizar_indicadores():
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        
        # Buscar o IPCA 12 meses
        data_fim = datetime.now().strftime('%d/%m/%Y')
        data_inicio = (datetime.now() - timedelta(days=60)).strftime('%d/%m/%Y')
        codigo_ipca = 13522  # Código do IPCA 12 meses
        
        df_ipca = extract_service.extracao_bcb(codigo_ipca, data_inicio, data_fim)
        
        if not df_ipca.empty:
            ultimo_ipca = df_ipca.iloc[-1]['valor']
            
            # Buscar registro existente ou cria um novo
            indicadores = db.query(IndicadoresEconomicos).first()
            if not indicadores:
                indicadores = IndicadoresEconomicos()
                db.add(indicadores)
            
            # Atualiza os valores
            indicadores.ipca = ultimo_ipca
            
            # Calcula o IPCA mensal a partir do anual
            ipca_mes_calculado = ((1 + ultimo_ipca/100)**(1/12) - 1) * 100 
            
            # ATUALIZA
            indicadores.ipca_mes = ipca_mes_calculado
            indicadores.data_atualizacao = datetime.now()
            
            # Salva as alterações
            db.commit()
            flash('Indicadores econômicos atualizados com sucesso!', "success")
        else:
            flash('Não foi possível obter dados do IPCA.', "warning")
            
        db.close()
            
    except Exception as e:
        flash(f'Erro ao atualizar indicadores: {str(e)}', "error")
        if 'db' in locals() and db:
            db.close()
    
    return redirect(url_for('dashboard.cliente_dashboard'))