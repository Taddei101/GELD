"""
Rota para upload e processamento de arquivos Advisor
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.services.global_services import login_required, GlobalServices
from app.models.geld_models import create_session, Cliente, InfoFundo, PosicaoFundo, RiscoEnum, StatusFundoEnum
from app.services.extract_advisor_service import AdvisorExtractService
from datetime import datetime


posicao_advisor_bp = Blueprint('posicao_advisor', __name__)


@posicao_advisor_bp.route('/posicao/<int:cliente_id>/upload_advisor', methods=['GET', 'POST'])
@login_required
def upload_advisor(cliente_id):
    """
    Upload e processamento de arquivo Advisor
    """
    if request.method == 'GET':
        try:
            db = create_session()
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            
            if not cliente:
                flash('Cliente não encontrado.', 'error')
                return redirect(url_for('dashboard.cliente_dashboard'))
            
            return render_template('posicoes/upload_advisor.html', cliente=cliente)
            
        except Exception as e:
            flash(f'Erro ao carregar página de upload: {str(e)}', 'error')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        finally:
            db.close()

    elif request.method == 'POST':
        db = create_session()
        try:
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            
            if not cliente:
                flash('Cliente não encontrado.', 'error')
                return redirect(url_for('dashboard.cliente_dashboard'))
            
            global_services = GlobalServices(db)

            # ===== PROCESSAR UPLOAD =====
            sucesso, file_path, mensagem = global_services.processar_upload_arquivo()

            if not sucesso:
                flash(mensagem, "error")
                return redirect(url_for('posicao_advisor.upload_advisor', cliente_id=cliente_id))

            # ===== PROCESSAR ARQUIVO ADVISOR =====
            try:
                print("[INFO] Iniciando processamento de arquivo Advisor...")
                
                advisor_service = AdvisorExtractService(db)
                posicoes, log = advisor_service.processar_arquivo_advisor(file_path, cliente_id)
                
                # Mensagem informativa
                total = log['total']
                flash(f"Processadas {total} posições do Advisor", "info")
                
            except Exception as e:
                print(f"[ERRO] Erro no processamento: {str(e)}")
                flash(f"Erro ao processar arquivo: {str(e)}", "error")
                return redirect(url_for('posicao_advisor.upload_advisor', cliente_id=cliente_id))

            if not posicoes:
                flash("Nenhuma posição válida foi extraída do arquivo.", "warning")
                return redirect(url_for('posicao_advisor.upload_advisor', cliente_id=cliente_id))

            # ===== IDENTIFICAR FUNDOS EXISTENTES =====
            # Buscar por nome (já que Advisor não tem CNPJ)
            existing_funds_by_name = {}
            for fundo in db.query(InfoFundo).all():
                nome_normalizado = fundo.nome_fundo.strip().upper()
                existing_funds_by_name[nome_normalizado] = fundo.id

            # ===== CADASTRAR FUNDOS NOVOS =====
            fundos_criados = 0
            
            for pos in posicoes:
                nome_normalizado = pos['nome_fundo'].strip().upper()
                
                # Se fundo não existe, criar
                if nome_normalizado not in existing_funds_by_name:
                    novo_fundo = global_services.create_classe(
                        InfoFundo,
                        nome_fundo=pos['nome_fundo'],
                        cnpj=None,  # Advisor não fornece CNPJ
                        classe_anbima=pos['classe_anbima'],
                        mov_min=None,
                        risco=pos['risco'],
                        subtipo_risco=pos.get('subtipo_risco'),
                        status_fundo=StatusFundoEnum.ativo,
                        valor_cota=pos['valor_cota'],
                        data_atualizacao=datetime.now()
                    )
                    
                    existing_funds_by_name[nome_normalizado] = novo_fundo.id
                    fundos_criados += 1
                    
                    print(f"[INFO] Fundo cadastrado: {pos['nome_fundo'][:50]}")
                else:
                    # Atualizar valor da cota se fundo já existe
                    fundo_id = existing_funds_by_name[nome_normalizado]
                    fundo_existente = db.query(InfoFundo).get(fundo_id)
                    
                    if fundo_existente:
                        fundo_existente.valor_cota = pos['valor_cota']
                        fundo_existente.data_atualizacao = datetime.now()
                        db.commit()

            print(f"[INFO] Fundos novos cadastrados: {fundos_criados}")

            # ===== ATUALIZAR LISTA DE FUNDOS =====
            existing_funds_by_name = {}
            for fundo in db.query(InfoFundo).all():
                nome_normalizado = fundo.nome_fundo.strip().upper()
                existing_funds_by_name[nome_normalizado] = fundo.id

            print(f"[INFO] Total de fundos disponíveis: {len(existing_funds_by_name)}")

            # ===== DELETAR POSIÇÕES ANTIGAS DO ADVISOR =====
            print(f"[INFO] Deletando posições anteriores do Advisor para cliente {cliente_id}")
            
            posicoes_deletadas = db.query(PosicaoFundo).filter(
                PosicaoFundo.cliente_id == cliente_id,
                PosicaoFundo.banco_custodia == 'ADVISOR'
            ).delete()
            
            db.commit()
            print(f"[INFO] {posicoes_deletadas} posições antigas do Advisor deletadas")

            # ===== REGISTRAR POSIÇÕES NO BANCO =====
            registros_salvos = 0
            registros_falhas = 0

            for pos in posicoes:
                session = create_session()
                try:
                    nome_normalizado = pos['nome_fundo'].strip().upper()

                    if nome_normalizado in existing_funds_by_name:
                        fundo_id = existing_funds_by_name[nome_normalizado]

                        # Criar nova posição
                        services = GlobalServices(session)
                        new_position = services.create_classe(
                            PosicaoFundo,
                            fundo_id=fundo_id,
                            cliente_id=cliente_id,
                            cotas=pos['num_cotas'],
                            data_atualizacao=pos['data'],
                            banco_custodia='ADVISOR',
                            saldo_anterior=pos.get('saldo_anterior', 0.0),
                            saldo_bruto=pos.get('saldo_bruto', 0.0)
                        )
                        registros_salvos += 1
                    else:
                        print(f"[AVISO] Fundo {pos['nome_fundo'][:50]} não encontrado")
                        registros_falhas += 1
                        
                except Exception as e:
                    print(f"[ERRO] Erro ao registrar posição: {str(e)}")
                    registros_falhas += 1
                    session.rollback()
                finally:
                    session.close()

            # Limpar arquivo temporário
            try:
                import os
                os.remove(file_path)
            except:
                pass

            # ===== MENSAGEM FINAL =====
            if registros_salvos > 0:
                msg = f"{registros_salvos} posições do Advisor registradas com sucesso!"
                if registros_falhas > 0:
                    msg += f" ({registros_falhas} falharam)"
                flash(msg, "success")
            else:
                flash("Nenhuma posição foi registrada. Verifique o arquivo.", "warning")

            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERRO GERAL] Erro ao processar arquivo Advisor: {str(e)}")
            flash(f"Erro ao processar arquivo: {str(e)}", "error")
            return redirect(url_for('posicao_advisor.upload_advisor', cliente_id=cliente_id))
        finally:
            db.close()