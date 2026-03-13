import os
from app import app, db, Professor

# Deletar banco de dados se existir
if os.path.exists('agendamentos.db'):
    os.remove('agendamentos.db')
    print("✅ Banco de dados antigo deletado!")

# Criar novo banco de dados
with app.app_context():
    db.create_all()
    print("✅ Novo banco de dados criado!")

    # Criar usuário admin
    admin = Professor(nome='admin', senha='admin123', eh_admin=True)
    db.session.add(admin)
    db.session.commit()
    print("✅ Usuário admin criado! (usuário: admin, senha: admin123)")
