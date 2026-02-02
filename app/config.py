import os

# Para PythonAnywhere, usar caminho absoluto
if os.environ.get('PYTHONANYWHERE_DOMAIN'):
    # Produção no PythonAnywhere
    BASE_DIR = '/home/Geld/projeto'
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'geld_database.db')}"
else:
    # Desenvolvimento local
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'geld_database.db')}"

# Configurações adicionais para produção
SECRET_KEY = os.environ.get('SECRET_KEY', 'lkj12tu6')  # Use variável de ambiente
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'