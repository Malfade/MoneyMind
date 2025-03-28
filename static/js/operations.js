// Инициализация модального окна
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('operationModal');
    const closeModal = () => modal.style.display = 'none';
    
    // Установка текущей даты
    document.getElementById('operationDate').valueAsDate = new Date();
    
    // Обработчики закрытия
    document.querySelector('.modal-close').addEventListener('click', closeModal);
    document.getElementById('cancelOperation').addEventListener('click', closeModal);
    window.addEventListener('click', (e) => e.target === modal && closeModal());
    
    // Открытие модального окна
    document.querySelectorAll('[data-action="add-operation"]').forEach(btn => {
        btn.addEventListener('click', function() {
            const type = this.getAttribute('data-type');
            document.getElementById('operationType').value = type;
            document.getElementById('modalTitle').textContent = 
                type === 'income' ? 'Добавить доход' : 'Добавить расход';
            
            // Загрузка категорий
            fetch(`/api/categories?type=${type === 'income' ? 'income' : 'expenses'}`)
                .then(res => res.json())
                .then(categories => {
                    const select = document.getElementById('operationCategory');
                    select.innerHTML = '<option value="">Выберите категорию</option>';
                    categories.forEach(cat => {
                        const option = new Option(cat, cat);
                        select.add(option);
                    });
                    modal.style.display = 'flex';
                })
                .catch(err => {
                    console.error('Ошибка загрузки категорий:', err);
                    alert('Не удалось загрузить категории');
                });
        });
    });
    
    // Отправка формы
    document.getElementById('operationForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        
        fetch('/api/operation', {
            method: 'POST',
            body: formData
        })
        .then(res => {
            if (res.ok) {
                window.location.reload();
            } else {
                return res.json().then(err => {
                    throw new Error(err.message || 'Ошибка при добавлении операции');
                });
            }
        })
        .catch(err => {
            console.error('Error:', err);
            alert(err.message || 'Не удалось добавить операцию');
        });
    });
});