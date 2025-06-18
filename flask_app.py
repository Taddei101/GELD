from app.app_config import app
from app.models.geld_models import init_db

# Inicializar o banco de dados
init_db()

if __name__ == '__main__':
    app.run(debug=True)