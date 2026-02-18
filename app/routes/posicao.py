"""
Rotas de posições em fundos de investimento (Blueprint: posicao_bp)
Gerencia as cotas que um cliente possui em fundos: listagem com saldos por classe
de risco, cadastro/edição/exclusão manual e importação via planilha BTG.

Depende de PosicaoService para cálculos de saldo, ExtractBTGService para parsing
da planilha e FundoRegistrationService para cadastro automático de fundos via CVM.
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
from app.services.global_services import login_required, GlobalServices
from app.models.geld_models import create_session, Cliente, InfoFundo, PosicaoFundo, RiscoEnum, SubtipoRiscoEnum
from app.services.posicao_service import PosicaoService   # NOVO
from sqlalchemy import func
from datetime import datetime
import os
import time
import traceback
from app.services.extract_btg_service import ExtractBTGService
from app.services.fundo_registration_service import FundoRegistrationService


posicao_bp = Blueprint('posicao', __name__)


# =============================================================================
# ROTAS CRUD DE POSIÇÕES
# =============================================================================

@posicao_bp.route('/posicao/<int:cliente_id>/listar', methods=['GET'])
@login_required
def listar_posicao(cliente_id):
    try:
        db = create_session()
        global_services = GlobalServices(db)
        cliente = global_services.get_by_id(Cliente, cliente_id)

        if not cliente:
            print('Cliente não encontrado.')
            return redirect(url_for('dashboard.cliente_dashboard'))

        posicoes = db.query(PosicaoFundo).filter(PosicaoFundo.cliente_id == cliente_id).all()

       
        montante_cliente = PosicaoService.calcular_montante_total(cliente_id, db)
        totais = PosicaoService.calcular_totais_por_classe(cliente_id, db)

        saldo_fundo_di = totais['baixo_di']
        saldo_baixo    = totais['baixo_rfx']
        saldo_moderado = totais['moderado']
        saldo_alto     = totais['alto']

        print(f"DEBUG: Found {len(posicoes)} positions")
        print(f"DEBUG: Saldos por risco - DI: {saldo_fundo_di}, RFx: {saldo_baixo}, Moderado: {saldo_moderado}, Alto: {saldo_alto}")

        return render_template('posicoes/listar_posicao.html',
                             cliente=cliente,
                             montante_cliente=montante_cliente,
                             posicoes=posicoes,
                             saldo_fundo_di=saldo_fundo_di,
                             saldo_baixo=saldo_baixo,
                             saldo_moderado=saldo_moderado,
                             saldo_alto=saldo_alto)

    except Exception as e:
        print(f"ERROR in listar_posicao: {str(e)}")
        return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
    finally:
        db.close()


@posicao_bp.route('/posicao/<int:cliente_id>/add_posicao', methods=['GET', 'POST'])
@login_required
def add_posicao(cliente_id):
    if request.method == 'GET':
        try:
            db = create_session()
            global_service = GlobalServices(db)

            cliente = global_service.get_by_id(Cliente, cliente_id)
            if not cliente:
                print('Cliente não encontrado.')
                return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))

            fundos = global_service.listar_classe(InfoFundo)
            return render_template('posicoes/add_posicao.html', cliente=cliente, fundos=fundos)

        except Exception as e:
            print(f'Erro ao carregar formulário: {str(e)}')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        finally:
            db.close()

    elif request.method == 'POST':
        try:
            db = create_session()
            global_service = GlobalServices(db)

            fundo_id = int(request.form['fundo_id'])
            cotas = float(request.form['quantidade_cotas'])
            data_atualizacao = datetime.now()

            nova_posicao = global_service.create_classe(
                PosicaoFundo,
                fundo_id=fundo_id,
                cliente_id=cliente_id,
                cotas=cotas,
                data_atualizacao=data_atualizacao
            )

            flash('Posição cadastrada com sucesso!')
            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        except ValueError as e:
            flash(f'Erro de validação: {str(e)}')
        except Exception as e:
            flash(f'Erro ao cadastrar posição: {str(e)}')
        finally:
            db.close()

        return redirect(url_for('posicao.add_posicao', cliente_id=cliente_id))


@posicao_bp.route('/posicao/<int:posicao_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_posicao(posicao_id):
    if request.method == 'GET':
        try:
            db = create_session()
            global_service = GlobalServices(db)

            posicao = global_service.get_by_id(PosicaoFundo, posicao_id)
            if not posicao:
                flash('Posição não encontrada.')
                return redirect(url_for('dashboard.cliente_dashboard'))

            return render_template('posicoes/edit_posicao.html', posicao=posicao)

        except Exception as e:
            flash(f'Erro ao buscar posição: {str(e)}')
            return redirect(url_for('dashboard.cliente_dashboard'))
        finally:
            db.close()

    elif request.method == 'POST':
        try:
            db = create_session()
            global_service = GlobalServices(db)

            posicao = global_service.get_by_id(PosicaoFundo, posicao_id)
            if not posicao:
                flash('Posição não encontrada.')
                return redirect(url_for('dashboard.cliente_dashboard'))

            cliente_id = posicao.cliente_id

            cotas = float(request.form['quantidade_cotas'])
            data_atualizacao = datetime.now()

            posicao.cotas = cotas
            posicao.data_atualizacao = data_atualizacao
            db.commit()

            print(f'Posição atualizada com sucesso!')
            flash("Posição atualizada com sucesso!", "success")
            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        except ValueError as e:
            flash(f'Erro de validação: {str(e)}')
        except Exception as e:
            flash(f'Erro ao atualizar posição: {str(e)}')
        finally:
            db.close()

        return redirect(url_for('posicao.edit_posicao', posicao_id=posicao_id))


@posicao_bp.route('/posicao/<int:posicao_id>/delete', methods=['POST'])
@login_required
def delete_posicao(posicao_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        posicao = global_service.get_by_id(PosicaoFundo, posicao_id)
        if not posicao:
            flash('Posição não encontrada.')
            return redirect(url_for('dashboard.cliente_dashboard'))

        cliente_id = posicao.cliente_id

        if global_service.delete(PosicaoFundo, posicao_id):
            flash('Posição deletada com sucesso!')
        else:
            flash('Erro ao deletar posição.')

        return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

    except Exception as e:
        flash(f'Erro ao deletar posição: {str(e)}')
        return redirect(url_for('dashboard.cliente_dashboard'))
    finally:
        db.close()


@posicao_bp.route('/posicao/<int:cliente_id>/delete_multiple', methods=['POST'])
@login_required
def delete_multiple_posicoes(cliente_id):
    try:
        db = create_session()
        global_service = GlobalServices(db)

        posicao_ids = request.form.getlist('posicao_ids')

        if not posicao_ids:
            flash('Nenhuma posição foi selecionada.', 'warning')
            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        posicao_ids = [int(pid) for pid in posicao_ids]

        deleted_count = 0
        failed_count = 0

        for posicao_id in posicao_ids:
            try:
                posicao = global_service.get_by_id(PosicaoFundo, posicao_id)

                if posicao and posicao.cliente_id == cliente_id:
                    if global_service.delete(PosicaoFundo, posicao_id):
                        deleted_count += 1
                    else:
                        failed_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                print(f"[ERRO] Erro ao deletar posição {posicao_id}: {str(e)}")
                failed_count += 1

        if deleted_count > 0:
            flash(f'{deleted_count} posição(ões) deletada(s) com sucesso!', 'success')

        if failed_count > 0:
            flash(f'{failed_count} posição(ões) não puderam ser deletadas.', 'error')

        return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

    except Exception as e:
        flash(f'Erro ao deletar posições: {str(e)}', 'error')
        return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))
    finally:
        db.close()


# =============================================================================
# ROTA DE UPLOAD E PROCESSAMENTO DE PLANILHAS
# =============================================================================

@posicao_bp.route('/posicao/<int:cliente_id>/upload_cotas', methods=['GET', 'POST'])
@login_required
def upload_cotas(cliente_id):
    if request.method == 'GET':
        try:
            db = create_session()
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            return render_template('posicoes/upload_cotas.html', cliente=cliente)
        except Exception as e:
            flash(f'Erro ao carregar página de upload: {str(e)}')
            return redirect(url_for('cliente.area_cliente', cliente_id=cliente_id))
        finally:
            db.close()

    elif request.method == 'POST':
        db = create_session()
        try:
            cliente = db.query(Cliente).filter_by(id=cliente_id).first()
            global_services = GlobalServices(db)

            UPLOAD_FOLDER = 'uploads'
            ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
            MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)

            if 'arquivo' not in request.files:
                flash("Nenhum arquivo foi selecionado", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            file = request.files['arquivo']

            if file.filename == '':
                flash("Nenhum arquivo foi selecionado", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
                flash(f"Tipo de arquivo não permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > MAX_FILE_SIZE:
                flash(f"Arquivo muito grande. Máximo: {MAX_FILE_SIZE // (1024*1024)}MB", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            filename = secure_filename(file.filename)
            timestamp = str(int(time.time() * 1000))
            filename = f"{timestamp}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)

            print(f"[INFO] Arquivo salvo: {file_path}")

            try:
                print("[INFO] Iniciando processamento completo do arquivo BTG...")
                btg_service = ExtractBTGService(db, global_services)
                posicoes, log = btg_service.processar_arquivo_btg_completo(file_path, cliente_id)

                total = log['fundos'] + log['previdencia_individual'] + log['previdencia_externa'] + log['renda_fixa'] + log['renda_variavel']
                flash(f"Processadas {total} posições: {log['fundos']} fundos, {log['previdencia_individual']} prev.ind, {log['previdencia_externa']} prev.ext, {log['renda_fixa']} RF, {log['renda_variavel']} RV", "info")

                banco_custodia = 'BTG'

            except Exception as e:
                print(f"[ERRO] Erro no processamento: {str(e)}")
                flash(f"Erro no processamento: {str(e)}", "error")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            if not posicoes:
                flash("Nenhuma posição válida foi extraída do arquivo.")
                return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))

            print("[INFO] Cadastrando novos fundos automaticamente...")
            registration_service = FundoRegistrationService(db)
            existing_funds = registration_service.cadastrar_fundos_automaticamente(posicoes)

            print(f"[INFO] Deletando posições anteriores do {banco_custodia} para cliente {cliente_id}")
            posicoes_deletadas = db.query(PosicaoFundo).filter(
                PosicaoFundo.cliente_id == cliente_id,
                PosicaoFundo.banco_custodia == banco_custodia
            ).delete()
            db.commit()
            print(f"[INFO] {posicoes_deletadas} posições antigas do {banco_custodia} deletadas")

            registros_salvos = 0
            registros_atualizados = 0
            registros_falhas = 0

            for pos in posicoes:
                session = create_session()
                try:
                    norm_cnpj = pos['cnpj'].replace('.', '').replace('/', '').replace('-', '')

                    if norm_cnpj in existing_funds:
                        fundo_id = existing_funds[norm_cnpj]

                        existing_position = session.query(PosicaoFundo).filter_by(
                            fundo_id=fundo_id,
                            cliente_id=cliente_id
                        ).first()

                        if existing_position:
                            existing_position.cotas = pos['num_cotas']
                            existing_position.data_atualizacao = pos['data']
                            existing_position.banco_custodia = banco_custodia
                            session.commit()
                            registros_atualizados += 1
                        else:
                            services = GlobalServices(session)
                            new_position = services.create_classe(
                                PosicaoFundo,
                                fundo_id=fundo_id,
                                cliente_id=cliente_id,
                                cotas=pos['num_cotas'],
                                data_atualizacao=pos['data'],
                                banco_custodia=banco_custodia
                            )
                            registros_salvos += 1
                    else:
                        print(f"[AVISO] CNPJ {pos['cnpj']} não encontrado no banco de dados.")
                        registros_falhas += 1
                except Exception as e:
                    print(f"[ERRO] Erro ao registrar posição: {str(e)}")
                    registros_falhas += 1
                    session.rollback()
                finally:
                    session.close()

            try:
                os.remove(file_path)
            except:
                pass

            if registros_salvos > 0 or registros_atualizados > 0:
                msg = f"{registros_salvos} novas posições e {registros_atualizados} atualizações registradas com sucesso!"
                if registros_falhas > 0:
                    msg += f" ({registros_falhas} operações falharam)"
                flash(msg)
            else:
                flash("Nenhuma posição foi registrada. Verifique o arquivo ou os logs.")

            return redirect(url_for('posicao.listar_posicao', cliente_id=cliente_id))

        except Exception as e:
            traceback.print_exc()
            print(f"[ERRO GERAL] Erro ao processar arquivo: {str(e)}")
            flash(f"Erro ao processar arquivo: {str(e)}")
            return redirect(url_for('posicao.upload_cotas', cliente_id=cliente_id))
        finally:
            db.close()