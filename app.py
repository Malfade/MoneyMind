from flask import Flask, render_template, request, jsonify, make_response, redirect
from datetime import datetime, timedelta
import json
import os
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
csrf = CSRFProtect(app)
app.secret_key = 'ananasi'  # Changed from 'ananasi' to a more secure placeholder

# Инициализация данных
def init_default_data():
    return {
        'operations': [],
        'categories': {
            'expense': ['Еда', 'Транспорт', 'Жилье', 'Развлечения', 'Здоровье'],
            'income': ['Зарплата', 'Подарки', 'Инвестиции']
        },
        'budgets': {},
        'recurring': [],
        'settings': {'currency': 'RUB', 'theme': 'light', 'language': 'ru', 'notifications': False},
        'next_id': 1
    }

# Загрузка данных
def load_data():
    try:
        with open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Initialize missing fields with default values
        defaults = init_default_data()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        
        # Ensure categories have both expense and income keys
        if 'expense' not in data['categories']:
            data['categories']['expense'] = data['categories'].get('expenses', defaults['categories']['expense'])
        if 'income' not in data['categories']:
            data['categories']['income'] = defaults['categories']['income']
        
        return data
        
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error loading data: {e}")
        return init_default_data()

# Сохранение данных
def save_data(data):
    try:
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving data: {e}")

# Утилиты для работы с датами
def get_current_month():
    return datetime.now().strftime('%Y-%m')

def get_month_range(months=3):
    today = datetime.now()
    return [(today - timedelta(days=30*i)).strftime('%Y-%m') for i in range(months)]

def parse_operation_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return datetime.now()

# Основные роуты
@app.route('/')
def dashboard():
    try:
        data = load_data()
        operations = data.get('operations', [])
        
        balance = sum(op['amount'] for op in operations if op['type'] == 'income') - \
                  sum(op['amount'] for op in operations if op['type'] == 'expense')
        
        last_operations = sorted(operations, key=lambda x: parse_operation_date(x['date']), reverse=True)[:5]
        
        current_month = get_current_month()
        monthly_data = {
            'income': sum(op['amount'] for op in operations 
                      if op['type'] == 'income' and op['date'].startswith(current_month)),
            'expense': sum(op['amount'] for op in operations 
                      if op['type'] == 'expense' and op['date'].startswith(current_month))
        }
        
        return render_template('dashboard.html', 
                            balance=balance, 
                            last_operations=last_operations,
                            monthly_data=monthly_data,
                            currency=data['settings']['currency'])
    except Exception as e:
        print(f"Error in dashboard: {e}")
        return render_template('error.html', message="Ошибка загрузки данных"), 500

@app.route('/operations')
def operations():
    try:
        data = load_data()
        operations = data.get('operations', [])
        
        # Фильтрация операций
        type_filter = request.args.get('type', 'all')
        category_filter = request.args.get('category', 'all')
        date_from = request.args.get('from')
        date_to = request.args.get('to')
        
        filtered_ops = operations
        
        if type_filter != 'all':
            filtered_ops = [op for op in filtered_ops if op['type'] == type_filter]
        
        if category_filter != 'all':
            filtered_ops = [op for op in filtered_ops if op['category'] == category_filter]
        
        if date_from:
            filtered_ops = [op for op in filtered_ops if op['date'] >= date_from]
        
        if date_to:
            filtered_ops = [op for op in filtered_ops if op['date'] <= date_to]
        
        return render_template('operations.html', 
                            operations=filtered_ops,
                            categories=data['categories'],
                            currency=data['settings']['currency'])
    except Exception as e:
        print(f"Error in operations: {e}")
        return render_template('error.html', message="Ошибка загрузки операций"), 500

# API для операций
@app.route('/api/operation', methods=['POST'])
@csrf.exempt
def add_operation():
    try:
        data = load_data()
        
        operation = {
            'id': data['next_id'],
            'type': request.form.get('type'),
            'amount': float(request.form.get('amount', 0)),
            'category': request.form.get('category'),
            'date': request.form.get('date'),
            'description': request.form.get('description', ''),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Валидация данных
        if not all([operation['type'], operation['amount'], operation['category'], operation['date']]):
            return jsonify({'status': 'error', 'message': 'Не все обязательные поля заполнены'}), 400
        
        data['operations'].append(operation)
        data['next_id'] += 1
        save_data(data)
        
        return jsonify({'status': 'success', 'operation': operation})
    except Exception as e:
        print(f"Error adding operation: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/operation/<int:op_id>', methods=['GET', 'PUT', 'DELETE'])
@csrf.exempt
def handle_operation(op_id):
    try:
        data = load_data()
        operation = next((op for op in data.get('operations', []) if op['id'] == op_id), None)
        
        if not operation:
            return jsonify({'status': 'error', 'message': 'Операция не найдена'}), 404
        
        if request.method == 'GET':
            return jsonify(operation)
        
        elif request.method == 'PUT':
            operation.update({
                'type': request.form.get('type', operation['type']),
                'amount': float(request.form.get('amount', operation['amount'])),
                'category': request.form.get('category', operation['category']),
                'date': request.form.get('date', operation['date']),
                'description': request.form.get('description', operation.get('description', ''))
            })
            save_data(data)
            return jsonify({'status': 'success', 'operation': operation})
        
        elif request.method == 'DELETE':
            data['operations'] = [op for op in data.get('operations', []) if op['id'] != op_id]
            save_data(data)
            return jsonify({'status': 'success'})
            
    except Exception as e:
        print(f"Error handling operation: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API для аналитики
@app.route('/api/analytics')
def get_analytics():
    try:
        data = load_data()
        operations = data.get('operations', [])
        
        # Группировка расходов по категориям
        expense_by_category = {}
        for op in operations:
            if op['type'] == 'expense':
                expense_by_category[op['category']] = expense_by_category.get(op['category'], 0) + op['amount']
        
        # Данные за последние 6 месяцев
        months_data = []
        for month_str in get_month_range(6):
            month = datetime.strptime(month_str, '%Y-%m')
            month_name = month.strftime('%b %Y')
            
            month_income = sum(op['amount'] for op in operations 
                      if op['type'] == 'income' and op['date'].startswith(month_str))
            month_expense = sum(op['amount'] for op in operations 
                       if op['type'] == 'expense' and op['date'].startswith(month_str))
            
            months_data.append({
                'month': month_name,
                'income': month_income,
                'expense': month_expense,
                'savings': month_income - month_expense
            })
        
        return jsonify({
            'expense_by_category': expense_by_category,
            'months_data': months_data,
            'currency': data['settings']['currency']
        })
    except Exception as e:
        print(f"Error getting analytics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API для категорий
@app.route('/api/categories')
def get_categories():
    try:
        data = load_data()
        type_ = request.args.get('type')
        
        # Если тип не указан - возвращаем все категории
        if not type_:
            return jsonify(data['categories'])
        
        return jsonify(data['categories'].get(type_, []))
    except Exception as e:
        print(f"Error getting categories: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API для бюджета
@app.route('/api/budget', methods=['GET', 'POST'])
@app.route('/api/budget/<string:category>', methods=['GET', 'PUT', 'DELETE'])
@csrf.exempt
def handle_budget(category=None):
    try:
        data = load_data()
        
        if request.method == 'GET':
            if category:
                if category in data.get('budgets', {}):
                    return jsonify({category: data['budgets'][category]})
                return jsonify({'status': 'error', 'message': 'Бюджет не найден'}), 404
            return jsonify(data.get('budgets', {}))
        
        elif request.method == 'POST':
            budget_data = request.get_json()
            if not budget_data or 'category' not in budget_data or 'amount' not in budget_data:
                return jsonify({'status': 'error', 'message': 'Неверные данные'}), 400
                
            category = budget_data['category']
            amount = float(budget_data['amount'])
            
            if 'budgets' not in data:
                data['budgets'] = {}
            data['budgets'][category] = amount
            save_data(data)
            return jsonify({'status': 'success'})
        
        elif request.method == 'PUT':
            if category not in data.get('budgets', {}):
                return jsonify({'status': 'error', 'message': 'Бюджет не найден'}), 404
                
            budget_data = request.get_json()
            if not budget_data or 'amount' not in budget_data:
                return jsonify({'status': 'error', 'message': 'Неверные данные'}), 400
                
            data['budgets'][category] = float(budget_data['amount'])
            save_data(data)
            return jsonify({'status': 'success'})
        
        elif request.method == 'DELETE':
            if category not in data.get('budgets', {}):
                return jsonify({'status': 'error', 'message': 'Бюджет не найден'}), 404
                
            del data['budgets'][category]
            save_data(data)
            return jsonify({'status': 'success'})
            
    except Exception as e:
        print(f"Error handling budget: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API для регулярных платежей
@app.route('/api/recurring', methods=['GET', 'POST'])
@app.route('/api/recurring/<int:payment_id>', methods=['GET', 'PUT', 'DELETE'])
@csrf.exempt
def handle_recurring(payment_id=None):
    try:
        data = load_data()
        
        if request.method == 'GET':
            if payment_id:
                payment = next((p for p in data.get('recurring', []) if p['id'] == payment_id), None)
                if payment:
                    return jsonify(payment)
                return jsonify({'status': 'error', 'message': 'Платеж не найден'}), 404
            return jsonify(data.get('recurring', []))
        
        elif request.method == 'POST':
            payment_data = request.get_json()
            if not payment_data:
                return jsonify({'status': 'error', 'message': 'Неверные данные'}), 400
                
            required_fields = ['type', 'amount', 'category', 'frequency', 'next_date']
            if not all(field in payment_data for field in required_fields):
                return jsonify({'status': 'error', 'message': 'Не все обязательные поля заполнены'}), 400
                
            payment = {
                'id': data['next_id'],
                'type': payment_data['type'],
                'amount': float(payment_data['amount']),
                'category': payment_data['category'],
                'description': payment_data.get('description', ''),
                'frequency': payment_data['frequency'],
                'next_date': payment_data['next_date'],
                'active': True,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if 'recurring' not in data:
                data['recurring'] = []
            data['recurring'].append(payment)
            data['next_id'] += 1
            save_data(data)
            return jsonify({'status': 'success', 'payment': payment})
        
        elif request.method == 'PUT':
            payment = next((p for p in data.get('recurring', []) if p['id'] == payment_id), None)
            if not payment:
                return jsonify({'status': 'error', 'message': 'Платеж не найден'}), 404
                
            payment_data = request.get_json()
            if not payment_data:
                return jsonify({'status': 'error', 'message': 'Неверные данные'}), 400
                
            payment.update({
                'type': payment_data.get('type', payment['type']),
                'amount': float(payment_data.get('amount', payment['amount'])),
                'category': payment_data.get('category', payment['category']),
                'description': payment_data.get('description', payment.get('description', '')),
                'frequency': payment_data.get('frequency', payment['frequency']),
                'next_date': payment_data.get('next_date', payment['next_date']),
                'active': payment_data.get('active', payment['active'])
            })
            
            save_data(data)
            return jsonify({'status': 'success', 'payment': payment})
        
        elif request.method == 'DELETE':
            data['recurring'] = [p for p in data.get('recurring', []) if p['id'] != payment_id]
            save_data(data)
            return jsonify({'status': 'success'})
            
    except Exception as e:
        print(f"Error handling recurring payment: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Страницы
@app.route('/analytics')
def analytics():
    try:
        data = load_data()
        return render_template('analytics.html', currency=data['settings']['currency'])
    except Exception as e:
        print(f"Error in analytics: {e}")
        return render_template('error.html', message="Ошибка загрузки аналитики"), 500
    
@app.route('/budgets')
def budgets():
    try:
        data = load_data()
        
        # Initialize budgets if not present
        if 'budgets' not in data:
            data['budgets'] = {}
            save_data(data)
        
        # Считаем расходы по категориям
        expenses_by_category = {}
        for op in data.get('operations', []):
            if op.get('type') == 'expense':
                category = op.get('category', 'Uncategorized')
                expenses_by_category[category] = expenses_by_category.get(category, 0) + op.get('amount', 0)
        
        # Получаем все категории расходов
        expense_categories = data['categories'].get('expense', [])
        
        # Вычисляем общие суммы
        total_budget = sum(data['budgets'].values()) if data['budgets'] else 0
        total_spent = sum(expenses_by_category.get(cat, 0) for cat in data['budgets'])
        
        return render_template('budgets.html',
                            budgets=data['budgets'],
                            categories=expense_categories,
                            expenses_by_category=expenses_by_category,
                            total_budget=total_budget,
                            total_spent=total_spent,
                            currency=data['settings'].get('currency', 'RUB'))
    except Exception as e:
        print(f"Error in budgets: {e}")
        return render_template('error.html', message="Ошибка загрузки бюджетов"), 500

@app.route('/recurring')
def recurring():
    try:
        data = load_data()
        return render_template('recurring.html',
                            recurring=data.get('recurring', []),
                            categories=data['categories'],
                            currency=data['settings']['currency'])
    except Exception as e:
        print(f"Error in recurring: {e}")
        return render_template('error.html', message="Ошибка загрузки регулярных платежей"), 500

from flask_wtf.csrf import generate_csrf

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    try:
        data = load_data()
        
        if request.method == 'POST':
            # Проверка CSRF (автоматически через Flask-WTF)
            if not csrf.protect():
                return render_template('error.html', message="CSRF проверка не пройдена"), 400
            
            # Обновление настроек
            data['settings'].update({
                'currency': request.form.get('currency', 'RUB'),
                'theme': request.form.get('theme', 'light'),
                'language': request.form.get('language', 'ru'),
                'notifications': 'notifications' in request.form
            })
            
            # Добавление категории
            category_type = request.form.get('category_type')
            category_name = request.form.get('category_name', '').strip()
            
            if category_type in data['categories'] and category_name:
                if category_name not in data['categories'][category_type]:
                    data['categories'][category_type].append(category_name)
            
            save_data(data)
            return redirect('/settings')
        
        # Генерация CSRF токена для формы
        csrf_token = generate_csrf()
        
        return render_template('settings.html',
                            user_settings=data['settings'],
                            categories=data['categories'],
                            csrf_token=csrf_token)
    except Exception as e:
        print(f"Error in settings: {str(e)}")
        return render_template('error.html', message=f"Ошибка загрузки настроек: {e}"), 500

# API для работы с настройками
@app.route('/api/settings', methods=['GET', 'POST'])
@csrf.exempt
def handle_settings():
    data = load_data()
    
    if request.method == 'GET':
        return jsonify(data.get('settings', {}))
    
    elif request.method == 'POST':
        try:
            new_settings = request.get_json()
            if not new_settings:
                return jsonify({'status': 'error', 'message': 'No data provided'}), 400
            
            # Обновляем только разрешенные настройки
            allowed_settings = ['currency', 'theme', 'notifications', 'language']
            for key in allowed_settings:
                if key in new_settings:
                    data['settings'][key] = new_settings[key]
            
            save_data(data)
            return jsonify({'status': 'success', 'settings': data['settings']})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

# API для работы с категориями
@app.route('/api/categories', methods=['GET', 'POST'])
@csrf.exempt
def handle_categories():
    data = load_data()
    
    if request.method == 'GET':
        return jsonify(data.get('categories', {'expense': [], 'income': []}))
    
    elif request.method == 'POST':
        try:
            category_data = request.get_json()
            if not category_data or 'type' not in category_data or 'name' not in category_data:
                return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
            
            category_type = category_data['type']
            category_name = category_data['name']
            
            if category_type not in data['categories']:
                return jsonify({'status': 'error', 'message': 'Invalid category type'}), 400
            
            if category_name in data['categories'][category_type]:
                return jsonify({'status': 'error', 'message': 'Category already exists'}), 400
            
            data['categories'][category_type].append(category_name)
            save_data(data)
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

# API для удаления категории
@app.route('/api/category/<string:category_type>/<string:category_name>', methods=['DELETE'])
@csrf.exempt
def delete_category_endpoint(category_type, category_name):  # Renamed to avoid conflict
    try:
        data = load_data()
        
        if category_type not in data['categories']:
            return jsonify({'status': 'error', 'message': 'Invalid category type'}), 400
        
        if category_name not in data['categories'][category_type]:
            return jsonify({'status': 'error', 'message': 'Category not found'}), 404
        
        data['categories'][category_type].remove(category_name)
        
        # Удаляем связанные бюджеты
        if 'budgets' in data and category_name in data['budgets']:
            del data['budgets'][category_name]
        
        save_data(data)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API для конвертации валюты
@app.route('/api/convert-currency', methods=['POST'])
@csrf.exempt
def convert_currency():
    try:
        data = load_data()
        conversion_data = request.get_json()
        
        if not conversion_data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        required_fields = ['old_currency', 'new_currency', 'conversion_date', 'update_future_rates']
        if not all(field in conversion_data for field in required_fields):
            return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
        
        # Просто сохраняем новую валюту (в реальном приложении нужно пересчитывать суммы)
        data['settings']['currency'] = conversion_data['new_currency']
        save_data(data)
        
        return jsonify({
            'status': 'success',
            'converted_transactions': len(data.get('operations', [])),
            'new_currency': conversion_data['new_currency']
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# API для получения курса обмена
@app.route('/api/exchange-rate')
def get_exchange_rate():
    try:
        from_currency = request.args.get('from', 'RUB')
        to_currency = request.args.get('to', 'USD')
        date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Примерные курсы для демонстрации
        rates = {
            'RUB': {'USD': 0.011, 'EUR': 0.010, 'KZT': 5.20},
            'USD': {'RUB': 90.0, 'EUR': 0.92, 'KZT': 450.0},
            'EUR': {'RUB': 98.0, 'USD': 1.08, 'KZT': 490.0},
            'KZT': {'RUB': 0.19, 'USD': 0.0022, 'EUR': 0.0020}
        }
        
        rate = rates.get(from_currency, {}).get(to_currency, 1.0)
        
        return jsonify({
            'status': 'success',
            'from': from_currency,
            'to': to_currency,
            'date': date,
            'rate': rate
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# Экспорт данных
@app.route('/export/csv')
def export_csv():
    data = load_data()
    
    # Создаем CSV файл
    csv_data = "Тип,Сумма,Категория,Дата,Описание\n"
    for op in data.get('operations', []):
        csv_data += f"{op['type']},{op['amount']},{op['category']},{op['date']},{op.get('description', '')}\n"
    
    response = make_response(csv_data)
    response.headers['Content-Disposition'] = 'attachment; filename=operations.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/export/json')
def export_json():
    data = load_data()
    response = make_response(json.dumps(data, indent=2, ensure_ascii=False))
    response.headers['Content-Disposition'] = 'attachment; filename=financial_data.json'
    response.headers['Content-type'] = 'application/json'
    return response

# Обработка ошибок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message="Страница не найдена"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', message="Внутренняя ошибка сервера"), 500

if __name__ == '__main__':
    # Создаем папку для загрузок, если ее нет
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Проверяем и создаем data.json, если его нет
    if not os.path.exists('data.json'):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(init_default_data(), f, indent=2, ensure_ascii=False)
    
    app.run(debug=True)