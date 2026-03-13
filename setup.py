from app import app, db, Professor, Turma

with app.app_context():
    # Deletar todas as tabelas (limpar banco)
    db.drop_all()

    # Criar todas as tabelas novamente
    db.create_all()

    # Criar admin
    admin = Professor(
        nome='admin',
        senha='admin123',
        email='admin@escola.com',
        disciplina='Administrador',
        eh_admin=True
    )
    db.session.add(admin)
    db.session.commit()

    # Criar turmas
    turmas_padrao = [
        ('1º 1', 'Anos Iniciais'),
        ('1º 2', 'Anos Iniciais'),
        ('2º 1', 'Anos Iniciais'),
        ('2º 2', 'Anos Iniciais'),
        ('3º 1', 'Anos Iniciais'),
        ('3º 2', 'Anos Iniciais'),
        ('4º 1', 'Anos Iniciais'),
        ('4º 2', 'Anos Iniciais'),
        ('5º 1', 'Anos Iniciais'),
        ('5º 2', 'Anos Iniciais'),
        ('6º 1', 'Anos Finais'),
        ('6º 2', 'Anos Finais'),
        ('7º 1', 'Anos Finais'),
        ('7º 2', 'Anos Finais'),
        ('8º 1', 'Anos Finais'),
        ('8º 2', 'Anos Finais'),
        ('9º 1', 'Anos Finais'),
        ('9º 2', 'Anos Finais'),
        ('1º EM 1', 'Ensino Médio'),
        ('1º EM 2', 'Ensino Médio'),
        ('2º EM 1', 'Ensino Médio'),
        ('2º EM 2', 'Ensino Médio'),
        ('3º EM 1', 'Ensino Médio'),
        ('3º EM 2', 'Ensino Médio'),
        ('CEJA E.F.', 'CEJA'),
        ('CEJA E.M.', 'CEJA'),
    ]

    for nome, serie in turmas_padrao:
        turma = Turma(nome=nome, serie=serie)
        db.session.add(turma)

    db.session.commit()

    print('✅ Banco criado com sucesso!')
    print('✅ Admin: admin / admin123')
    print('✅ 26 turmas adicionadas!')