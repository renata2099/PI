// JavaScript do Sistema de Chamados

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts apos 5 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Confirmar acoes destrutivas
    const confirmForms = document.querySelectorAll('form[data-confirm]');
    confirmForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.getAttribute('data-confirm') || 'Tem certeza?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // Filtros de relatorio - auto-submit
    const filterSelects = document.querySelectorAll('.auto-submit');
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            this.closest('form').submit();
        });
    });

    // Scroll automatico para ultima mensagem no chat
    const chatContainer = document.querySelector('.chat-container');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Validacao de formularios
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
});

// Funcao para confirmar exclusao
function confirmarExclusao(mensagem) {
    return confirm(mensagem || 'Tem certeza que deseja excluir este item?');
}

// Funcao para formatar datas
function formatarData(dataString) {
    const data = new Date(dataString);
    return data.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Atualizar pagina automaticamente (para dashboards)
function habilitarAutoRefresh(intervalo = 30000) {
    setInterval(() => {
        location.reload();
    }, intervalo);
}