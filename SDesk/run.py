from app import create_app, db
from app.models import Usuario, Departamento, Chamado

app = create_app('default')

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'Usuario': Usuario, 
        'Departamento': Departamento, 
        'Chamado': Chamado
    }

if __name__ == '__main__':
    app.run(debug=True, port=5000)