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

#SELECIONAR ARQUIVO
    
    def selecionar_arquivo():
        root = tk.Tk()
        root.withdraw()  
        
        # Abre o diálogo para selecionar o arquivo
        arquivo = filedialog.askopenfilename(
            title="Selecione o arquivo",
            filetypes=[("Todos os arquivos", "*.*")]
        )
        print(f"Arquivo Selecionado: {arquivo}\n")
        root.destroy()
        return arquivo

    
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