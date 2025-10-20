function showSucursalForm() {
    document.getElementById('sucursalFormModal').style.display = 'block';
    // Carregar formulário via AJAX
    fetch('/admin/empresa/sucursal/add/?_to_field=id')
        .then(response => response.text())
        .then(html => {
            document.getElementById('sucursalForm').innerHTML = html;
        });
}

function hideSucursalForm() {
    document.getElementById('sucursalFormModal').style.display = 'none';
}

function editSucursal(id) {
    document.getElementById('sucursalFormModal').style.display = 'block';
    // Carregar formulário de edição via AJAX
    fetch(`/admin/empresa/sucursal/${id}/change/?_to_field=id`)
        .then(response => response.text())
        .then(html => {
            document.getElementById('sucursalForm').innerHTML = html;
        });
}

function desativarSucursal(id) {
    if (confirm('Tem certeza que deseja desativar esta sucursal?')) {
        // Enviar requisição para desativar
        fetch(`/admin/empresa/sucursal/${id}/desativar/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
    }
}

function ativarSucursal(id) {
    if (confirm('Tem certeza que deseja ativar esta sucursal?')) {
        // Enviar requisição para ativar
        fetch(`/admin/empresa/sucursal/${id}/ativar/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
    }
}

// Fechar modal quando clicar fora
document.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal-overlay')) {
        hideSucursalForm();
    }
});
