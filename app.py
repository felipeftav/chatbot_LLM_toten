"""
Ponto de entrada principal da aplicação LIA - Totem Meta Day.
Inicializa o servidor Flask de forma enxuta, segura e modular.
"""

from flask import Flask
from flask_cors import CORS
from src.config import STATIC_DIR, TEMPLATES_DIR
from src.routes import register_routes

# Inicialização do aplicativo Flask apontando para pastas seguras
app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)

# Habilita CORS
CORS(app)

# Registra rotas da aplicação
register_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)