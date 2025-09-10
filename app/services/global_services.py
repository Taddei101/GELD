from sqlalchemy.orm import Session
from typing import TypeVar, Type, Optional
from functools import wraps
from flask import session, redirect, url_for
import tkinter as tk
from tkinter import filedialog
import re

#define classe genérica para abstrair os serviços
class_set = TypeVar('class_set')

#LOGIN REQUIRED

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


class GlobalServices:
    def __init__(self, db:Session):
        self.db=db


#GET BY ID na classe

    def get_by_id(self, model_class: Type[class_set], instance_id: int)-> Optional[class_set]:

        try:
            return self.db.query(model_class).filter(model_class.id == instance_id).first()

        except Exception as e:
            raise e


# CRIAR nova instância de uma CLASSE

    def create_classe(self, model_class: Type[class_set], **kwargs) -> class_set:
        """Args: model_class, atributos da classe"""
        try:
            instance = model_class(**kwargs)
            self.db.add(instance)
            self.db.commit()
            self.db.refresh(instance)
            return instance
        except Exception as e:
            self.db.rollback()
            raise e


#DELETE instancia da classe
    def delete(self, model_class:Type[class_set],instance_id: int ) -> bool:

        try:
            instance = self.get_by_id(model_class, instance_id)
            if not instance:
                return False

            self.db.delete(instance)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e

#LISTAR CLASSE

    def listar_classe(self, model_class:Type[class_set]) -> list[class_set]:

        try:
            query = self.db.query(model_class)
            return query.all()
        except Exception as e:
            raise e


#EDITAR Classe

    def editar_classe(self, model_class:Type[class_set], instance_id: int, **kwargs) -> Optional[class_set]:

        try:
            instance = self.get_by_id(model_class, instance_id)
            if not instance:
                return None

            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            self.db.commit()
            self.db.refresh(instance)
            return instance

        except Exception as e:
            raise e



#Validar CNPJ
    def validar_cnpj(self, cnpj):
        """ARGS: cnpj (qlq formato) retorna: tupla(is_valid, cnpj_normalizado, MSG)"""

        cnpj_normalizado = re.sub(r'\D', '', cnpj)

        if len(cnpj_normalizado) != 14:
            return False, cnpj_normalizado, "CNPJ deve ter 14 dígitos"

        return True, cnpj_normalizado, "CNPJ válido"

    def formatar_cnpj(self, cnpj_normalizado):
        """Formata o CNPJ para o padrão XX.XXX.XXX/XXXX-XX"""

        if len(cnpj_normalizado) != 14:
            return cnpj_normalizado
        return f"{cnpj_normalizado[:2]}.{cnpj_normalizado[2:5]}.{cnpj_normalizado[5:8]}/{cnpj_normalizado[8:12]}-{cnpj_normalizado[12:]}"


# Selecionar arquivo

    def processar_upload_arquivo(self):
        """
        Processa o upload de arquivo via Flask request
        Retorna: (sucesso: bool, caminho_arquivo: str, mensagem: str)
        """
        from flask import request
        from werkzeug.utils import secure_filename
        import os

        try:
            # Configurações
            UPLOAD_FOLDER = 'uploads'
            ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
            MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

            # Criar pasta de uploads se não existir
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)

            # Verifica se há arquivo na requisição
            if 'arquivo' not in request.files:
                return False, None, "Nenhum arquivo foi selecionado"

            file = request.files['arquivo']

            # Verifica se um arquivo foi realmente selecionado
            if file.filename == '':
                return False, None, "Nenhum arquivo foi selecionado"

            # Verifica se o arquivo é permitido
            if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
                return False, None, f"Tipo de arquivo não permitido. Tipos aceitos: {', '.join(ALLOWED_EXTENSIONS)}"

            # Verifica o tamanho do arquivo
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Volta para o início

            if file_size > MAX_FILE_SIZE:
                return False, None, f"Arquivo muito grande. Tamanho máximo: {MAX_FILE_SIZE // (1024*1024)}MB"

            # Salva o arquivo
            filename = secure_filename(file.filename)
            # Adiciona timestamp para evitar conflitos de nome
            import time
            timestamp = str(int(time.time() * 1000))
            filename = f"{timestamp}_{filename}"

            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            return True, filepath, f"Arquivo '{file.filename}' enviado com sucesso"

        except Exception as e:
            return False, None, f"Erro ao processar arquivo: {str(e)}"