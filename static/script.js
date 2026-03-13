document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const tabName = this.getAttribute('data-tab');

        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelectorAll('.tab-btn').forEach(b => {
            b.classList.remove('active');
        });

        document.getElementById(tabName).classList.add('active');
        this.classList.add('active');
    });
});

document.getElementById('formLogin').addEventListener('submit', function(e) {
    e.preventDefault();
    const nome = document.getElementById('loginNome').value;
    const senha = document.getElementById('loginSenha').value;

    fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            nome: nome,
            senha: senha,
            criar_conta: false
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            window.location.href = '/dashboard';
        } else {
            alert(data.mensagem);
        }
    })
    .catch(error => {
        alert('Erro ao fazer login');
        console.error('Erro:', error);
    });
});

document.getElementById('formRegistro').addEventListener('submit', function(e) {
    e.preventDefault();
    const nome = document.getElementById('registroNome').value;
    const senha = document.getElementById('registroSenha').value;
    const senhaConfirm = document.getElementById('registroSenhaConfirm').value;

    if (senha !== senhaConfirm) {
        alert('As senhas não conferem!');
        return;
    }

    fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            nome: nome,
            senha: senha,
            criar_conta: true
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            alert('Conta criada com sucesso! Redirecionando...');
            window.location.href = '/dashboard';
        } else {
            alert(data.mensagem);
        }
    })
    .catch(error => {
        alert('Erro ao criar conta');
        console.error('Erro:', error);
    });
});

function carregarAgendamentosSemana() {
    fetch('/api/agendamentos')
        .then(response => response.json())
        .then(agendamentos => {
            exibirAgendamentosSemana(agendamentos);
        })
        .catch(error => {
            console.error('Erro ao carregar agendamentos:', error);
        });
}

function exibirAgendamentosSemana(agendamentos) {
    const lista = document.getElementById('agendamentosSemanaLogin');

    if (!lista) {
        return;
    }

    if (agendamentos.length === 0) {
        lista.innerHTML = '<p class="no-agendamentos">Não há agendamentos até o momento.</p>';
        return;
    }

    agendamentos.sort((a, b) => new Date(a.data) - new Date(b.data));

    lista.innerHTML = agendamentos.map(agendamento => `
        <div class="agendamento-card">
            <h4>${agendamento.disciplina}</h4>
            <p><strong>Professor:</strong> ${agendamento.professor}</p>
            <p><strong>Data:</strong> ${new Date(agendamento.data + 'T00:00:00').toLocaleDateString('pt-BR')}</p>
            <p><strong>Aula:</strong> ${agendamento.aula}ª | <strong>Turma:</strong> ${agendamento.turma}</p>
            <p><strong>Sala:</strong> ${agendamento.sala}</p>
        </div>
    `).join('');
}

function fazerLogout() {
    if (confirm('Tem certeza que deseja sair?')) {
        window.location.href = '/logout';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('agendamentosSemanaLogin')) {
        carregarAgendamentosSemana();
    }
});