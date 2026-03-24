from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name='default'):
    app = Flask(__name__)

    # Carregar configuracoes
    app.config.from_object(config[config_name])

    # Inicializar extensoes
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faca login para acessar esta pagina.'
    login_manager.login_message_category = 'warning'

    # Registrar blueprints
    from app.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Criar pasta de uploads se nao existir
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # 👇 COLOCA AQUI
    from app import models

    return app
