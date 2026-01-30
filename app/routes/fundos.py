
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from functools import wraps
from app.models.geld_models import create_session, InfoFundo, RiscoEnum, StatusFundoEnum
from app.services.global_services import GlobalServices, login_required
from datetime import datetime
from app.services.extract_services import ExtractServices
from datetime import datetime
import re

fundos_bp = Blueprint('fundos', __name__)


#LISTAR
@fundos_bp.route('/listar_fundos')
@login_required
def listar_fundos():
    try:
        db = create_session()
        global_service = GlobalServices(db)
        fundos = global_service.listar_classe(InfoFundo)


        return render_template('fundos/listar_fundos.html', fundos=fundos)
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao listar fundos: {str(e)}')
        return redirect(url_for('dashboard.cliente_dashboard'))
    finally:
        if 'db' in locals() and db:
            db.close()

#CADASTRAR FUNDO NA MÃO 
@fundos_bp.route('/add_fundo', methods =['GET', 'POST'])
@login_required
def add_fundo():
    if request.method == 'GET':
        return render_template('fundos/add_fundo.html')
    try:
        db = create_session()
        global_service = GlobalServices(db)
        mov_min = 0
        permanencia_min= 0
        data_atualizacao = datetime.now()
        status_fundo = StatusFundoEnum["ativo"]
        risco=RiscoEnum["baixo"]

        #cadastrar novo fundo
        novo_fundo = global_service.create_classe(
            InfoFundo,
            nome_fundo=request.form['nome_fundo'],
            cnpj=request.form['cnpj'],
            mov_min=mov_min,
            classe_anbima = request.form['classe_anbima'],
            permanencia_min=permanencia_min,
            risco=risco,
            status_fundo=status_fundo,
            valor_cota = 1,
            data_atualizacao = data_atualizacao
        )
        flash(f'Fundo {novo_fundo.nome_fundo} cadastrado com sucesso!')
        return redirect(url_for('fundos.listar_fundos'))

    except Exception as e:
            import traceback
            traceback.print_exc()
            flash(f'Erro ao cadastrar fundo: {str(e)}')
            return redirect(url_for('fundos.listar_fundos'))
    finally:
        if 'db' in locals() and db:
            db.close()

#DELETAR
@fundos_bp.route('/fundos/<int:fundo_id>/delete', methods=['POST'])
@login_required
def delete_fundo(fundo_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)
        if global_service.delete(InfoFundo, fundo_id):
            flash(f'Fundo deletado com sucesso!',"success")
        else:
            flash('Fundo não encontrado!')
        return redirect(url_for('fundos.listar_fundos'))

    except Exception as e:
        flash(f'Erro ao deletar fundo: {str(e)}')
        return redirect(url_for('fundos.listar_fundos'))
    finally:
        db.close()


#EDITAR
@fundos_bp.route('/fundos/edit/<int:fundo_id>', methods=['GET','POST'])
@login_required
def edit_fundo(fundo_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        if request.method == 'GET':
            fundo = global_service.get_by_id(InfoFundo, fundo_id)
            if not fundo:
                flash('Fundo não encontrado')
                return redirect(url_for('fundos.listar_fundos'))
            return render_template('fundos/edit_fundo.html', fundo=fundo)

        elif request.method =='POST':

            mov_min = request.form['mov_min']
            mov_min = None if mov_min == '' else float(mov_min)

            permanencia_min = request.form['permanencia_min']
            permanencia_min = None if permanencia_min == '' else float(permanencia_min)

            # Converter a string de data para objeto datetime
            data_atualizacao_str = request.form['data_atualizacao']
            data_atualizacao = datetime.strptime(data_atualizacao_str, '%Y-%m-%d') if data_atualizacao_str else None

            dados_atualizados = {

                'nome_fundo': request.form['nome_fundo'],
                'cnpj': request.form['cnpj'],
                'classe_anbima': request.form['classe_anbima'],
                'mov_min': mov_min,
                'permanencia_min': permanencia_min,
                'valor_cota' : request.form['valor_cota'],
                'data_atualizacao' : data_atualizacao

            }

            if 'risco' in request.form and request.form['risco']:
                dados_atualizados['risco'] = RiscoEnum[request.form['risco']]

            if 'status_fundo' in request.form and request.form['status_fundo']:
                dados_atualizados['status_fundo'] = StatusFundoEnum[request.form['status_fundo']]

            fundo_atualizado = global_service.editar_classe(InfoFundo, fundo_id, **dados_atualizados)

            if fundo_atualizado:
                flash('Fundo atualizado com sucesso!')
            else:
                flash('Fundo não encontrado.')

            return redirect(url_for('fundos.listar_fundos'))

    except ValueError as e:
        flash(f'Erro de validação: {str(e)}')
    except Exception as e:
        flash(f'Erro ao editar fundo: {str(e)}')
    finally:
        if 'db' in locals() and db:
            db.close()

    return redirect(url_for('fundos.listar_fundos'))


# ATUALIZAR
@fundos_bp.route('/atualizar_cotas_fundos', methods=['POST'])
@login_required
def atualizar_cotas_fundos():
    db = None

    def atualizar_fundos_inteligente(extract_service, max_meses=2):
        """
        1. Pega TODOS os fundos cadastrados
        2. Tenta mês atual primeiro
        3. Para cada fundo não encontrado, busca em meses anteriores
        """
        from datetime import datetime, timedelta
        import pandas as pd

        hoje = datetime.now()
        fundos = db.query(InfoFundo).all()

        print(f"=== Atualizando {len(fundos)} fundos ===")

        fundos_atualizados = 0
        fundos_detalhes = []

        # Buscar dados dos últimos meses
        dados_meses = {}

        for meses_atras in range(0, max_meses):
            if meses_atras == 0:
                data_busca = hoje
            else:
                # Voltar meses
                data_busca = hoje.replace(day=1) - timedelta(days=1)
                for _ in range(meses_atras - 1):
                    data_busca = data_busca.replace(day=1) - timedelta(days=1)

            ano = str(data_busca.year)
            mes = f"{data_busca.month:02d}"
            chave_mes = f"{ano}-{mes}"

            try:
                print(f"Baixando dados de {mes}/{ano}...")
                df_mes = extract_service.extracao_cvm(ano, mes)

                if not df_mes.empty:
                    dados_meses[chave_mes] = df_mes
                    print(f"✅ {chave_mes}: {len(df_mes)} registros")
                else:
                    print(f"❌ {chave_mes}: Sem dados")

            except Exception as e:
                print(f"❌ {chave_mes}: Erro - {e}")

        if not dados_meses:
            print("❌ Nenhum dado encontrado em nenhum mês")
            return 0, []

        print(f"\\n=== Processando {len(fundos)} fundos ===")

        # Para cada fundo, procurar nos dados disponíveis
        for fundo in fundos:
            cnpj_normalizado = fundo.cnpj.replace('.', '').replace('/', '').replace('-', '')
            fundo_encontrado = False

            # Tentar nos dados, começando pelo mais recente
            for chave_mes in sorted(dados_meses.keys(), reverse=True):
                df_cotas = dados_meses[chave_mes]

                # Buscar este fundo neste mês
                df_fundo = df_cotas[
                    df_cotas['CNPJ_FUNDO_CLASSE'].str.replace('.', '').str.replace('/', '').str.replace('-', '') == cnpj_normalizado
                ]

                if not df_fundo.empty:
                    # Encontrou! Pegar valor mais recente
                    df_recente = df_fundo.sort_values('DT_COMPTC', ascending=False).iloc[0]
                    valor_novo = float(df_recente['VL_QUOTA'])
                    valor_antigo = float(fundo.valor_cota) if fundo.valor_cota else 0

                    print(f"✅ {fundo.nome_fundo[:35]}: {valor_antigo:.6f} -> {valor_novo:.6f} ({chave_mes})")

                    # Atualizar
                    fundo.valor_cota = valor_novo
                    fundo.data_atualizacao = datetime.now()

                    fundos_atualizados += 1
                    fundos_detalhes.append({
                        'nome': fundo.nome_fundo,
                        'valor_antigo': valor_antigo,
                        'valor_novo': valor_novo,
                        'mes': chave_mes
                    })

                    fundo_encontrado = True
                    break  # Encontrou, não precisa procurar em meses anteriores

            if not fundo_encontrado:
                print(f"❌ {fundo.nome_fundo[:35]}: Não encontrado em nenhum mês")

        return fundos_atualizados, fundos_detalhes

    try:
        db = create_session()
        extract_service = ExtractServices(db)

        # Usar a nova lógica inteligente (apenas 2 meses)
        fundos_atualizados, detalhes = atualizar_fundos_inteligente(extract_service, max_meses=2)

        if fundos_atualizados > 0:
            db.commit()
            print(f"\\n✅ Commit realizado: {fundos_atualizados} fundos atualizados")

            # Criar mensagem detalhada
            total_fundos = len(db.query(InfoFundo).all())
            mensagem = f"Atualizados {fundos_atualizados} de {total_fundos} fundos:\\n"

            for detalhe in detalhes[:3]:  # Mostrar primeiros 3
                mensagem += f"• {detalhe['nome'][:25]}: {detalhe['valor_antigo']:.3f} → {detalhe['valor_novo']:.3f}\\n"

            if len(detalhes) > 3:
                mensagem += f"... e mais {len(detalhes) - 3} fundos"

            flash(mensagem, 'success')
        else:
            print("❌ Nenhum fundo foi atualizado")
            flash('Nenhum fundo foi encontrado nos dados da CVM dos últimos 2 meses.', 'warning')

        db.close()
        return redirect(url_for('fundos.listar_fundos'))

    except Exception as e:
        print(f"❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()

        if db:
            try:
                db.rollback()
                db.close()
            except:
                pass

        flash(f'Erro ao atualizar cotas: {str(e)}', 'error')

    return redirect(url_for('fundos.listar_fundos'))


# IMPORTAR FUNDO POR CNPJ

@fundos_bp.route('/add_fundo_cnpj', methods=['POST'])
@login_required
def add_fundo_cnpj():
    db = None
    try:
        db = create_session()
        extract_service = ExtractServices(db)
        global_service = GlobalServices(db)

        # Pega o cnpj do form no html
        cnpj = request.form['cnpj']
        print(f"CNPJ recebido: {cnpj}")

        # Validar apenas o formato do CNPJ (14 dígitos)
        is_valid, cnpj_normalizado, mensagem = global_service.validar_cnpj(cnpj)

        if not is_valid:
            flash(mensagem, "error")
            print(mensagem)
            return redirect(url_for('fundos.add_fundo'))

        cnpj_formatado = global_service.formatar_cnpj(cnpj_normalizado)
        flash(f'🔍 Processando CNPJ: {cnpj_formatado}', "info")
        print(f'Processando CNPJ: {cnpj_formatado}')

        # Verificar se o fundo já existe no banco de dados
        existing_funds = db.query(InfoFundo).all()
        for fund in existing_funds:
            # Normaliza o CNPJ do fundo existente e compara com o normalizado do input
            fund_cnpj_norm = re.sub(r'\D', '', fund.cnpj)
            if fund_cnpj_norm == cnpj_normalizado:
                flash(f'⚠️ O fundo com CNPJ {cnpj_formatado} já está cadastrado como "{fund.nome_fundo}"!', "warning")
                print(f'O fundo com CNPJ {cnpj_formatado} já está cadastrado como "{fund.nome_fundo}"!')
                return redirect(url_for('fundos.listar_fundos'))

        # NOVA LÓGICA: Busca inteligente com múltiplos meses
        flash(f'🔄 Buscando informações na CVM (até 3 meses)...', "info")
        
        try:
            # Usar a nova função melhorada
            info_fundo, mes_encontrado = extract_service.extracao_cvm_info(cnpj_normalizado, max_meses_anteriores=3)

            if info_fundo is None:
                flash(f'❌ Não foi possível encontrar informações para o CNPJ: {cnpj_formatado} nos últimos 3 meses', "error")
                print(f'Não foi possível encontrar informações para o CNPJ: {cnpj_formatado}')
                return redirect(url_for('fundos.add_fundo'))

            # Criar o fundo com as informações encontradas
            novo_fundo = global_service.create_classe(
                InfoFundo,
                nome_fundo=info_fundo['DENOM_SOCIAL'],
                cnpj=cnpj_formatado,  # Armazena formatado
                classe_anbima=info_fundo['CLASSE_ANBIMA'],
                mov_min=float(info_fundo['PR_CIA_MIN']) if info_fundo['PR_CIA_MIN'] and info_fundo['PR_CIA_MIN'] not in ['None', '', 'nan'] else None,
                risco=RiscoEnum.moderado,  # Default value
                status_fundo=StatusFundoEnum.ativo,
                valor_cota=0.0,  # Será atualizado depois
                data_atualizacao=datetime.now()
            )

            # Flash de sucesso com detalhes
            if mes_encontrado == "atual":
                flash(f'✅ Fundo "{novo_fundo.nome_fundo}" cadastrado com sucesso! (dados atuais)', "success")
            else:
                flash(f'✅ Fundo "{novo_fundo.nome_fundo}" cadastrado com sucesso! (dados de {mes_encontrado})', "success")
            
            print(f'Fundo {novo_fundo.nome_fundo} cadastrado com sucesso!')

        except (IndexError, KeyError) as e:
            flash(f'❌ Erro ao processar dados do fundo: campos obrigatórios não encontrados', "error")
            print(f'Erro ao processar dados do fundo: {str(e)}')
        except ValueError as e:
            flash(f'❌ Erro de validação nos dados do fundo: {str(e)}', "error")
            print(f'Erro de validação: {str(e)}')

        return redirect(url_for('fundos.listar_fundos'))

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'❌ Erro interno ao cadastrar fundo: {str(e)}', "error")
        print(f'Erro ao cadastrar fundo por CNPJ: {str(e)}')
        return redirect(url_for('fundos.add_fundo'))
    finally:
        if db:
            try:
                db.close()
            except:
                pass