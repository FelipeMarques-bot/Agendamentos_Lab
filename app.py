import io
import csv
import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///agendamentos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== MODELOS ====================

class Professor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    senha = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=False, nullable=True)
    disciplina = db.Column(db.String(80), nullable=True)
    eh_admin = db.Column(db.Boolean, default=False)
    agendamentos = db.relationship('Agendamento', backref='professor', lazy=True)

    def __init__(self, nome, senha, email=None, disciplina=None, eh_admin=None):
        self.nome = nome
        self.senha = generate_password_hash(senha)
        self.email = email if email else None
        self.disciplina = disciplina
        self.eh_admin = eh_admin if eh_admin is not None else False

    def check_password(self, password):
        return check_password_hash(self.senha, password)

class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(db.Integer, db.ForeignKey('professor.id'), nullable=False)
    data = db.Column(db.String(10), nullable=False)
    aula = db.Column(db.String(255), nullable=False) # Ex: "1ª Aula (Matutino)"
    disciplina = db.Column(db.String(80), nullable=False)
    turma = db.Column(db.String(80), nullable=False)
    tema = db.Column(db.String(255), nullable=False)
    recurso = db.Column(db.String(80), nullable=False) # Novo campo para o recurso agendado

class Aula(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False) # Ex: "1ª Aula"
    turno = db.Column(db.String(20), nullable=False) # Ex: "Matutino", "Vespertino", "Noturno"
    __table_args__ = (db.UniqueConstraint('numero', 'turno', name='_numero_turno_uc'),)

class Disciplina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)

class Turma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    serie = db.Column(db.String(20), nullable=True)

class Recurso(db.Model): # Novo modelo para recursos
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False) # Ex: "Sala de Informática", "Laboratório de Ciências"

class ConfiguracaoEscola(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_escola = db.Column(db.String(100), nullable=False, default="Minha Escola")
    sigla = db.Column(db.String(20), nullable=False, default="MESC")
    telefone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    logo_url = db.Column(db.String(255), nullable=True, default='/static/logo_default.png') # Default logo

# ==================== DECORADORES DE AUTENTICAÇÃO ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROTAS ====================

@app.route('/')
def index():
    # Se não houver administradores, redireciona para a configuração inicial
    with app.app_context():
        if not Professor.query.filter_by(eh_admin=True).first():
            return redirect(url_for('setup_admin'))
    return redirect(url_for('login'))

@app.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    with app.app_context():
        if Professor.query.filter_by(eh_admin=True).first():
            return redirect(url_for('login')) # Já existe admin, não permite criar outro

        if request.method == 'POST':
            nome = request.form['nome']
            senha = request.form['senha']
            email = request.form.get('email') # E-mail é opcional

            if not nome or not senha:
                return render_template('setup_admin.html', error='Nome e senha são obrigatórios.')

            # Verifica se o nome de usuário já existe
            if Professor.query.filter_by(nome=nome).first():
                return render_template('setup_admin.html', error='Nome de usuário já existe.')

            # Se e-mail for fornecido, verifica se já existe
            if email and Professor.query.filter_by(email=email).first():
                return render_template('setup_admin.html', error='E-mail já em uso.')

            admin = Professor(nome=nome, senha=senha, email=email, eh_admin=True)
            db.session.add(admin)
            db.session.commit()

            # Cria a configuração da escola com valores padrão se não existir
            if not ConfiguracaoEscola.query.first():
                config = ConfiguracaoEscola()
                db.session.add(config)
                db.session.commit()

            # Cria aulas, disciplinas e recursos padrão se não existirem
            criar_dados_padrao()

            session['logged_in'] = True
            session['user_id'] = admin.id
            session['username'] = admin.nome
            session['is_admin'] = True
            session['user_type'] = 'admin'
            return redirect(url_for('admin_panel'))

        # Para a página de setup_admin, a logo é sempre a padrão
        default_logo_url = url_for('static', filename='logo_default.png')
        return render_template('setup_admin.html', logo_url=default_logo_url)

@app.route('/login', methods=['GET', 'POST'])
def login():
    with app.app_context():
        # Se não houver administradores, redireciona para a configuração inicial
        if not Professor.query.filter_by(eh_admin=True).first():
            return redirect(url_for('setup_admin'))

        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            professor = Professor.query.filter_by(nome=username).first()

            if professor and professor.check_password(password):
                session['logged_in'] = True
                session['user_id'] = professor.id
                session['username'] = professor.nome
                session['is_admin'] = professor.eh_admin
                session['user_type'] = 'admin' if professor.eh_admin else 'professor'
                if professor.eh_admin:
                    return redirect(url_for('admin_panel'))
                else:
                    return redirect(url_for('professor_panel'))
            else:
                error = 'Usuário ou senha inválidos.'
                # Para a página de login, a logo é sempre a padrão
                default_logo_url = url_for('static', filename='logo_default.png')
                return render_template('login.html', error=error, logo_url=default_logo_url)

        # Para a página de login, a logo é sempre a padrão
        default_logo_url = url_for('static', filename='logo_default.png')
        return render_template('login.html', logo_url=default_logo_url)

@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    session.pop('user_type', None)
    return redirect(url_for('login'))

@app.route('/admin_panel')
@admin_required
def admin_panel():
    with app.app_context():
        config = ConfiguracaoEscola.query.first()
        logo_url = config.logo_url if config else url_for('static', filename='logo_default.png')
        return render_template('admin.html', logo_url=logo_url)

@app.route('/professor_panel')
@login_required
def professor_panel():
    with app.app_context():
        config = ConfiguracaoEscola.query.first()
        logo_url = config.logo_url if config else url_for('static', filename='logo_default.png')
        return render_template('professor.html', logo_url=logo_url)

# ==================== ROTAS DA API PARA ADMIN ====================

@app.route('/api/admin/professores', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_admin_professores():
    with app.app_context():
        if request.method == 'GET':
            professores = Professor.query.order_by(Professor.nome).all()
            professores_data = []
            for p in professores:
                professores_data.append({
                    'id': p.id,
                    'nome': p.nome,
                    'email': p.email,
                    'disciplina': p.disciplina,
                    'eh_admin': p.eh_admin
                })
            return jsonify(professores_data)

        elif request.method == 'POST':
            data = request.get_json()
            nome = data.get('nome')
            senha = data.get('senha')
            email = data.get('email')
            disciplina = data.get('disciplina')
            eh_admin = data.get('eh_admin', False)

            if not nome or not senha:
                return jsonify({'sucesso': False, 'mensagem': 'Nome e senha são obrigatórios.'}), 400

            if Professor.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Nome de usuário já existe.'}), 409

            novo_professor = Professor(nome=nome, senha=senha, email=email, disciplina=disciplina, eh_admin=eh_admin)
            db.session.add(novo_professor)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Professor adicionado com sucesso!', 'id': novo_professor.id})

        elif request.method == 'PUT':
            data = request.get_json()
            id = data.get('id')
            nome = data.get('nome')
            senha = data.get('senha')
            email = data.get('email')
            disciplina = data.get('disciplina')
            eh_admin = data.get('eh_admin', False)

            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID do professor é obrigatório.'}), 400

            professor = Professor.query.get(id)
            if not professor:
                return jsonify({'sucesso': False, 'mensagem': 'Professor não encontrado.'}), 404

            # Verifica se o novo nome já existe e não é o do próprio professor
            if nome and nome != professor.nome and Professor.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Nome de usuário já existe.'}), 409

            professor.nome = nome
            if senha: # Atualiza a senha apenas se uma nova for fornecida
                professor.senha = generate_password_hash(senha)
            professor.email = email
            professor.disciplina = disciplina
            professor.eh_admin = eh_admin
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Professor atualizado com sucesso!'})

        elif request.method == 'DELETE':
            id = request.args.get('id')
            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID do professor é obrigatório.'}), 400

            professor = Professor.query.get(id)
            if not professor:
                return jsonify({'sucesso': False, 'mensagem': 'Professor não encontrado.'}), 404

            db.session.delete(professor)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Professor removido com sucesso!'})

@app.route('/api/admin/disciplinas', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_admin_disciplinas():
    with app.app_context():
        if request.method == 'GET':
            disciplinas = Disciplina.query.order_by(Disciplina.nome).all()
            return jsonify([{'id': d.id, 'nome': d.nome} for d in disciplinas])

        elif request.method == 'POST':
            data = request.get_json()
            nome = data.get('nome')
            if not nome:
                return jsonify({'sucesso': False, 'mensagem': 'Nome da disciplina é obrigatório.'}), 400
            if Disciplina.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Disciplina já existe.'}), 409
            nova_disciplina = Disciplina(nome=nome)
            db.session.add(nova_disciplina)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Disciplina adicionada com sucesso!', 'id': nova_disciplina.id})

        elif request.method == 'PUT':
            data = request.get_json()
            id = data.get('id')
            nome = data.get('nome')
            if not id or not nome:
                return jsonify({'sucesso': False, 'mensagem': 'ID e nome da disciplina são obrigatórios.'}), 400
            disciplina = Disciplina.query.get(id)
            if not disciplina:
                return jsonify({'sucesso': False, 'mensagem': 'Disciplina não encontrada.'}), 404
            if nome != disciplina.nome and Disciplina.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Disciplina já existe.'}), 409
            disciplina.nome = nome
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Disciplina atualizada com sucesso!'})

        elif request.method == 'DELETE':
            id = request.args.get('id')
            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID da disciplina é obrigatório.'}), 400
            disciplina = Disciplina.query.get(id)
            if not disciplina:
                return jsonify({'sucesso': False, 'mensagem': 'Disciplina não encontrada.'}), 404
            db.session.delete(disciplina)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Disciplina removida com sucesso!'})

@app.route('/api/admin/aulas', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_admin_aulas():
    with app.app_context():
        if request.method == 'GET':
            aulas = Aula.query.order_by(Aula.turno, Aula.numero).all()
            return jsonify([{'id': a.id, 'numero': a.numero, 'turno': a.turno} for a in aulas])

        elif request.method == 'POST':
            data = request.get_json()
            numero = data.get('numero')
            turno = data.get('turno')
            if not numero or not turno:
                return jsonify({'sucesso': False, 'mensagem': 'Número e turno da aula são obrigatórios.'}), 400
            if Aula.query.filter_by(numero=numero, turno=turno).first():
                return jsonify({'sucesso': False, 'mensagem': 'Aula já existe para este turno.'}), 409
            nova_aula = Aula(numero=numero, turno=turno)
            db.session.add(nova_aula)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Aula adicionada com sucesso!', 'id': nova_aula.id})

        elif request.method == 'PUT':
            data = request.get_json()
            id = data.get('id')
            numero = data.get('numero')
            turno = data.get('turno')
            if not id or not numero or not turno:
                return jsonify({'sucesso': False, 'mensagem': 'ID, número e turno da aula são obrigatórios.'}), 400
            aula = Aula.query.get(id)
            if not aula:
                return jsonify({'sucesso': False, 'mensagem': 'Aula não encontrada.'}), 404
            if (numero != aula.numero or turno != aula.turno) and Aula.query.filter_by(numero=numero, turno=turno).first():
                return jsonify({'sucesso': False, 'mensagem': 'Aula já existe para este turno.'}), 409
            aula.numero = numero
            aula.turno = turno
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Aula atualizada com sucesso!'})

        elif request.method == 'DELETE':
            id = request.args.get('id')
            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID da aula é obrigatório.'}), 400
            aula = Aula.query.get(id)
            if not aula:
                return jsonify({'sucesso': False, 'mensagem': 'Aula não encontrada.'}), 404
            db.session.delete(aula)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Aula removida com sucesso!'})

@app.route('/api/admin/turmas', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_admin_turmas():
    with app.app_context():
        if request.method == 'GET':
            turmas = Turma.query.order_by(Turma.nome).all()
            return jsonify([{'id': t.id, 'nome': t.nome, 'serie': t.serie} for t in turmas])

        elif request.method == 'POST':
            data = request.get_json()
            nome = data.get('nome')
            serie = data.get('serie')
            if not nome:
                return jsonify({'sucesso': False, 'mensagem': 'Nome da turma é obrigatório.'}), 400
            if Turma.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Turma já existe.'}), 409
            nova_turma = Turma(nome=nome, serie=serie)
            db.session.add(nova_turma)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Turma adicionada com sucesso!', 'id': nova_turma.id})

        elif request.method == 'PUT':
            data = request.get_json()
            id = data.get('id')
            nome = data.get('nome')
            serie = data.get('serie')
            if not id or not nome:
                return jsonify({'sucesso': False, 'mensagem': 'ID e nome da turma são obrigatórios.'}), 400
            turma = Turma.query.get(id)
            if not turma:
                return jsonify({'sucesso': False, 'mensagem': 'Turma não encontrada.'}), 404
            if nome != turma.nome and Turma.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Turma já existe.'}), 409
            turma.nome = nome
            turma.serie = serie
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Turma atualizada com sucesso!'})

        elif request.method == 'DELETE':
            id = request.args.get('id')
            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID da turma é obrigatório.'}), 400
            turma = Turma.query.get(id)
            if not turma:
                return jsonify({'sucesso': False, 'mensagem': 'Turma não encontrada.'}), 404
            db.session.delete(turma)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Turma removida com sucesso!'})

@app.route('/api/admin/recursos', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def api_admin_recursos():
    with app.app_context():
        if request.method == 'GET':
            recursos = Recurso.query.order_by(Recurso.nome).all()
            return jsonify([{'id': r.id, 'nome': r.nome} for r in recursos])

        elif request.method == 'POST':
            data = request.get_json()
            nome = data.get('nome')
            if not nome:
                return jsonify({'sucesso': False, 'mensagem': 'Nome do recurso é obrigatório.'}), 400
            if Recurso.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Recurso já existe.'}), 409
            novo_recurso = Recurso(nome=nome)
            db.session.add(novo_recurso)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Recurso adicionado com sucesso!', 'id': novo_recurso.id})

        elif request.method == 'PUT':
            data = request.get_json()
            id = data.get('id')
            nome = data.get('nome')
            if not id or not nome:
                return jsonify({'sucesso': False, 'mensagem': 'ID e nome do recurso são obrigatórios.'}), 400
            recurso = Recurso.query.get(id)
            if not recurso:
                return jsonify({'sucesso': False, 'mensagem': 'Recurso não encontrado.'}), 404
            if nome != recurso.nome and Recurso.query.filter_by(nome=nome).first():
                return jsonify({'sucesso': False, 'mensagem': 'Recurso já existe.'}), 409
            recurso.nome = nome
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Recurso atualizado com sucesso!'})

        elif request.method == 'DELETE':
            id = request.args.get('id')
            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID do recurso é obrigatório.'}), 400
            recurso = Recurso.query.get(id)
            if not recurso:
                return jsonify({'sucesso': False, 'mensagem': 'Recurso não encontrado.'}), 404
            db.session.delete(recurso)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Recurso removido com sucesso!'})

@app.route('/api/config/escola', methods=['GET', 'POST'])
@admin_required
def api_config_escola():
    with app.app_context():
        config = ConfiguracaoEscola.query.first()
        if not config:
            config = ConfiguracaoEscola()
            db.session.add(config)
            db.session.commit()

        if request.method == 'GET':
            return jsonify({
                'sucesso': True,
                'nome_escola': config.nome_escola,
                'sigla': config.sigla,
                'telefone': config.telefone,
                'email': config.email,
                'endereco': config.endereco,
                'logo_url': config.logo_url
            })

        elif request.method == 'POST':
            config.nome_escola = request.form.get('nome_escola', config.nome_escola)
            config.sigla = request.form.get('sigla', config.sigla)
            config.telefone = request.form.get('telefone', config.telefone)
            config.email = request.form.get('email', config.email)
            config.endereco = request.form.get('endereco', config.endereco)

            # Lógica para remover a logo
            remover_logo = request.form.get('remover_logo') == 'true'
            if remover_logo:
                if config.logo_url and config.logo_url != '/static/logo_default.png':
                    try:
                        # Remove o arquivo físico se não for a logo padrão
                        # O caminho precisa ser absoluto para os.remove
                        logo_path = os.path.join(app.root_path, 'static', 'uploads', os.path.basename(config.logo_url))
                        if os.path.exists(logo_path):
                            os.remove(logo_path)
                    except Exception as e:
                        print(f"Erro ao remover arquivo de logo: {e}") # Para debug
                        pass # Ignora se o arquivo já não existir ou houver outro erro
                config.logo_url = '/static/logo_default.png' # Volta para a logo padrão

            # Lógica para upload de nova logo
            if 'logo' in request.files:
                file = request.files['logo']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Garante que a pasta 'uploads' exista dentro de 'static'
                    upload_dir = os.path.join(app.root_path, 'static', app.config['UPLOAD_FOLDER'])
                    os.makedirs(upload_dir, exist_ok=True) # Cria a pasta se não existir

                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    config.logo_url = url_for('static', filename=f'{app.config["UPLOAD_FOLDER"]}/{filename}') # Salva o caminho relativo
                elif file and file.filename == '': # Se o campo de arquivo foi enviado mas vazio (não selecionou novo arquivo)
                    pass # Não faz nada, mantém a logo existente ou a padrão

            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Configurações da escola salvas com sucesso!', 'logo_url': config.logo_url})

@app.route('/api/admin/agendamentos_todos', methods=['GET'])
@admin_required
def api_admin_agendamentos_todos():
    with app.app_context():
        agendamentos = Agendamento.query.join(Professor).order_by(Agendamento.data.desc()).all()
        agendamentos_data = []
        for ag in agendamentos:
            agendamentos_data.append({
                'id': ag.id,
                'professor_nome': ag.professor.nome,
                'data': ag.data,
                'aula': ag.aula,
                'disciplina': ag.disciplina,
                'turma': ag.turma,
                'tema': ag.tema,
                'recurso': ag.recurso
            })
        return jsonify(agendamentos_data)

@app.route('/api/admin/agendamentos_todos/<int:agendamento_id>', methods=['DELETE'])
@admin_required
def api_admin_delete_agendamento(agendamento_id):
    with app.app_context():
        agendamento = Agendamento.query.get(agendamento_id)
        if not agendamento:
            return jsonify({'sucesso': False, 'mensagem': 'Agendamento não encontrado.'}), 404
        db.session.delete(agendamento)
        db.session.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Agendamento removido com sucesso!'})

# Rotas de exportação CSV
@app.route('/api/admin/exportar_agendamentos_csv', methods=['GET'])
@admin_required
def exportar_agendamentos_csv():
    with app.app_context():
        si = io.StringIO()
        cw = csv.writer(si)

        # Cabeçalho
        cw.writerow(['ID', 'Professor', 'Data', 'Aula', 'Disciplina', 'Turma', 'Tema', 'Recurso'])

        # Dados
        agendamentos = Agendamento.query.join(Professor).order_by(Agendamento.data.desc()).all()
        for ag in agendamentos:
            cw.writerow([ag.id, ag.professor.nome, ag.data, ag.aula, ag.disciplina, ag.turma, ag.tema, ag.recurso])

        output = io.BytesIO(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='agendamentos.csv')

@app.route('/api/admin/exportar_professores_csv', methods=['GET'])
@admin_required
def exportar_professores_csv():
    with app.app_context():
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Nome', 'Email', 'Disciplina', 'Admin'])
        professores = Professor.query.order_by(Professor.nome).all()
        for p in professores:
            cw.writerow([p.id, p.nome, p.email, p.disciplina, 'Sim' if p.eh_admin else 'Não'])
        output = io.BytesIO(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='professores.csv')

@app.route('/api/admin/exportar_disciplinas_csv', methods=['GET'])
@admin_required
def exportar_disciplinas_csv():
    with app.app_context():
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Nome'])
        disciplinas = Disciplina.query.order_by(Disciplina.nome).all()
        for d in disciplinas:
            cw.writerow([d.id, d.nome])
        output = io.BytesIO(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='disciplinas.csv')

@app.route('/api/admin/exportar_aulas_csv', methods=['GET'])
@admin_required
def exportar_aulas_csv():
    with app.app_context():
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Numero', 'Turno'])
        aulas = Aula.query.order_by(Aula.turno, Aula.numero).all()
        for a in aulas:
            cw.writerow([a.id, a.numero, a.turno])
        output = io.BytesIO(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='aulas.csv')

@app.route('/api/admin/exportar_turmas_csv', methods=['GET'])
@admin_required
def exportar_turmas_csv():
    with app.app_context():
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Nome', 'Serie'])
        turmas = Turma.query.order_by(Turma.nome).all()
        for t in turmas:
            cw.writerow([t.id, t.nome, t.serie])
        output = io.BytesIO(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='turmas.csv')

@app.route('/api/admin/exportar_recursos_csv', methods=['GET'])
@admin_required
def exportar_recursos_csv():
    with app.app_context():
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Nome'])
        recursos = Recurso.query.order_by(Recurso.nome).all()
        for r in recursos:
            cw.writerow([r.id, r.nome])
        output = io.BytesIO(si.getvalue().encode('utf-8'))
        output.seek(0)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='recursos.csv')

# ==================== ROTAS DA API PARA PROFESSOR  ====================

@app.route('/api/agendamentos', methods=['GET', 'POST', 'DELETE'])
@login_required
def api_agendamentos():
    with app.app_context():
        if request.method == 'GET':
            professor_id = session.get('user_id')
            if not professor_id:
                return jsonify({'sucesso': False, 'mensagem': 'Professor não logado.'}), 401

            agendamentos = Agendamento.query.filter_by(professor_id=professor_id).order_by(Agendamento.data.desc()).all()
            agendamentos_data = []
            for ag in agendamentos:
                agendamentos_data.append({
                    'id': ag.id,
                    'data': ag.data,
                    'aula': ag.aula,
                    'disciplina': ag.disciplina,
                    'turma': ag.turma,
                    'tema': ag.tema,
                    'recurso': ag.recurso
                })
            return jsonify(agendamentos_data)

        elif request.method == 'POST':
            professor_id = session.get('user_id')
            if not professor_id:
                return jsonify({'sucesso': False, 'mensagem': 'Professor não logado.'}), 401

            data = request.get_json()
            data_agendamento = data.get('data')
            aula_display = data.get('aula') # Ex: "1ª Aula (Matutino)"
            disciplina = data.get('disciplina')
            turma = data.get('turma')
            tema = data.get('tema')
            recurso = data.get('recurso')

            if not all([data_agendamento, aula_display, disciplina, turma, tema, recurso]):
                return jsonify({'sucesso': False, 'mensagem': 'Todos os campos são obrigatórios.'}), 400

            # Verifica se já existe um agendamento para o mesmo recurso, data e aula
            # Isso impede que dois professores agendem o mesmo recurso para a mesma aula no mesmo dia
            agendamento_existente = Agendamento.query.filter_by(
                data=data_agendamento,
                aula=aula_display,
                recurso=recurso
            ).first()

            if agendamento_existente:
                return jsonify({'sucesso': False, 'mensagem': f'O recurso "{recurso}" já está agendado para a "{aula_display}" em {data_agendamento}.'}), 409

            novo_agendamento = Agendamento(
                professor_id=professor_id,
                data=data_agendamento,
                aula=aula_display,
                disciplina=disciplina,
                turma=turma,
                tema=tema,
                recurso=recurso
            )
            db.session.add(novo_agendamento)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Agendamento realizado com sucesso!', 'id': novo_agendamento.id})

        elif request.method == 'DELETE':
            professor_id = session.get('user_id')
            if not professor_id:
                return jsonify({'sucesso': False, 'mensagem': 'Professor não logado.'}), 401

            id = request.args.get('id')
            if not id:
                return jsonify({'sucesso': False, 'mensagem': 'ID do agendamento é obrigatório.'}), 400

            agendamento = Agendamento.query.filter_by(id=id, professor_id=professor_id).first()
            if not agendamento:
                return jsonify({'sucesso': False, 'mensagem': 'Agendamento não encontrado ou você não tem permissão para removê-lo.'}), 404

            db.session.delete(agendamento)
            db.session.commit()
            return jsonify({'sucesso': True, 'mensagem': 'Agendamento removido com sucesso!'})

@app.route('/api/config/aulas', methods=['GET'])
@login_required
def api_config_aulas():
    with app.app_context():
        aulas = Aula.query.order_by(Aula.turno, Aula.numero).all()
        return jsonify([{'id': a.id, 'numero': a.numero, 'turno': a.turno, 'display': f"{a.numero} ({a.turno})"} for a in aulas])

@app.route('/api/config/disciplinas', methods=['GET'])
@login_required
def api_config_disciplinas():
    with app.app_context():
        disciplinas = Disciplina.query.order_by(Disciplina.nome).all()
        return jsonify([{'id': d.id, 'nome': d.nome} for d in disciplinas])

@app.route('/api/config/turmas', methods=['GET'])
@login_required
def api_config_turmas():
    with app.app_context():
        turmas = Turma.query.order_by(Turma.nome).all()
        return jsonify([{'id': t.id, 'nome': t.nome} for t in turmas])

@app.route('/api/config/recursos', methods=['GET'])
@login_required
def api_config_recursos():
    with app.app_context():
        recursos = Recurso.query.order_by(Recurso.nome).all()
        return jsonify([{'id': r.id, 'nome': r.nome} for r in recursos])

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(os.path.join(app.root_path, 'static', app.config['UPLOAD_FOLDER']), filename)

# ==================== FUNÇÕES DE INICIALIZAÇÃO ====================

def criar_dados_padrao():
    with app.app_context():
        # Aulas padrão
        if not Aula.query.first():
            aulas_padrao = [
                {'numero': '1ª Aula', 'turno': 'Matutino'},
                {'numero': '2ª Aula', 'turno': 'Matutino'},
                {'numero': '3ª Aula', 'turno': 'Matutino'},
                {'numero': '4ª Aula', 'turno': 'Matutino'},
                {'numero': '5ª Aula', 'turno': 'Matutino'},
                {'numero': '1ª Aula', 'turno': 'Vespertino'},
                {'numero': '2ª Aula', 'turno': 'Vespertino'},
                {'numero': '3ª Aula', 'turno': 'Vespertino'},
                {'numero': '4ª Aula', 'turno': 'Vespertino'},
                {'numero': '5ª Aula', 'turno': 'Vespertino'},
                {'numero': '1ª Aula', 'turno': 'Noturno'},
                {'numero': '2ª Aula', 'turno': 'Noturno'},
                {'numero': '3ª Aula', 'turno': 'Noturno'},
                {'numero': '4ª Aula', 'turno': 'Noturno'},
                {'numero': '5ª Aula', 'turno': 'Noturno'},
            ]
            for aula_data in aulas_padrao:
                if not Aula.query.filter_by(numero=aula_data['numero'], turno=aula_data['turno']).first():
                    db.session.add(Aula(**aula_data))
            db.session.commit()

        # Recursos padrão
        if not Recurso.query.first():
            recursos_padrao = ['Sala de Informática', 'Laboratório de Ciências', 'Projetor Portátil', 'Quadra Esportiva']
            for nome_recurso in recursos_padrao:
                if not Recurso.query.filter_by(nome=nome_recurso).first():
                    db.session.add(Recurso(nome=nome_recurso))
            db.session.commit()

@app.before_request
def before_request_func():
    # Isso garante que o contexto da aplicação esteja disponível para db.create_all()
    # e que os dados padrão sejam criados apenas uma vez.
    if not hasattr(app, '_database_initialized'):
        with app.app_context():
            db.create_all()
            criar_dados_padrao()
            app._database_initialized = True # Marca que o banco de dados foi inicializado

if __name__ == '__main__':
    # Garante que o banco de dados e os dados padrão sejam criados na primeira execução
    # ou se o app for reiniciado e o flag não estiver setado.
    with app.app_context():
        db.create_all()
        criar_dados_padrao()
    app.run(debug=True)
