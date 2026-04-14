from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
import psycopg2
from psycopg2 import sql
from psycopg2.pool import SimpleConnectionPool
import os
import re
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

application = Flask(__name__)

app = application

app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')

# PostgreSQL RDS Configuration
DATABASE_CONFIG = {
    'host': os.environ.get('DB_HOST', 'postgres-rds-cpp.clygm6iaiqxj.us-east-1.rds.amazonaws.com'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'postgres-rds-cpp'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres-rds-cpp'),
    'connect_timeout': 30,
    'keepalives': 1,
    'keepalives_idle': 5,
    'keepalives_interval': 2,
    'keepalives_count': 2
}

# Global variables
connection_pool = None
USE_POSTGRES = False
pool_initialized = False

def init_connection_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool, USE_POSTGRES, pool_initialized
    
    if pool_initialized:
        print("Connection pool already initialized")
        return True
        
    try:
        # First test basic connection
        test_conn = psycopg2.connect(
            host=DATABASE_CONFIG['host'],
            port=DATABASE_CONFIG['port'],
            user=DATABASE_CONFIG['user'],
            password=DATABASE_CONFIG['password'],
            connect_timeout=10
        )
        test_conn.close()
        
        # Create connection pool
        connection_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            **DATABASE_CONFIG
        )
        USE_POSTGRES = True
        pool_initialized = True
        print(" PostgreSQL connection pool created successfully!")
        return True
    except Exception as e:
        print(f" Failed to create connection pool: {e}")
        USE_POSTGRES = False
        pool_initialized = False
        return False

def get_db_connection():
    """Get database connection from pool or create new one"""
    if USE_POSTGRES and connection_pool and pool_initialized:
        try:
            return connection_pool.getconn()
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
            return psycopg2.connect(**DATABASE_CONFIG)


def return_db_connection(conn):
    """Return connection to pool"""
    if USE_POSTGRES and connection_pool and pool_initialized and conn:
        try:
            connection_pool.putconn(conn)
        except Exception as e:
            print(f"Error returning connection to pool: {e}")
            try:
                conn.close()
            except:
                pass
    elif conn:
        try:
            conn.close()
        except:
            pass

def init_db():
    """Initialize database tables"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if USE_POSTGRES:
            # PostgreSQL schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    phone VARCHAR(20) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    full_name VARCHAR(200),
                    profession VARCHAR(100),
                    monthly_income DECIMAL(10,2) DEFAULT 0,
                    savings_goal DECIMAL(10,2) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    amount DECIMAL(10,2) NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    date DATE NOT NULL,
                    description TEXT,
                    payment_method VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        # else:
            
        #     cursor.execute('''
        #         CREATE TABLE IF NOT EXISTS users (
        #             id INTEGER PRIMARY KEY AUTOINCREMENT,
        #             username TEXT NOT NULL UNIQUE,
        #             email TEXT NOT NULL UNIQUE,
        #             phone TEXT NOT NULL,
        #             password TEXT NOT NULL,
        #             full_name TEXT,
        #             profession TEXT,
        #             monthly_income REAL DEFAULT 0,
        #             savings_goal REAL DEFAULT 0,
        #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        #         )
        #     ''')
            
        #     cursor.execute('''
        #         CREATE TABLE IF NOT EXISTS transactions (
        #             id INTEGER PRIMARY KEY AUTOINCREMENT,
        #             user_id INTEGER NOT NULL,
        #             amount REAL NOT NULL,
        #             category TEXT NOT NULL,
        #             date TEXT NOT NULL,
        #             description TEXT,
        #             payment_method TEXT NOT NULL,
        #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        #             FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        #         )
        #     ''')
        
        conn.commit()
        print(" Database tables created successfully!")
        
    except Exception as e:
        print(f" Error initializing database: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Execute database query"""
    conn = None
    cursor = None
    result = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Handle parameter placeholders
        if not USE_POSTGRES and params and '%s' in query:
            query = query.replace('%s', '?')
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        
        if commit:
            conn.commit()
        
        return result
        
    except Exception as e:
        print(f"Database error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_db_connection(conn)

def get_transaction_value(transaction, index, default=None):
    """Safely get value from transaction (handles both tuple and dict)"""
    try:
        if transaction is None:
            return default
        if isinstance(transaction, tuple):
            return transaction[index] if len(transaction) > index else default
        elif isinstance(transaction, dict):
            # Handle dictionary access
            keys = ['id', 'user_id', 'amount', 'category', 'date', 'description', 'payment_method', 'created_at']
            return transaction.get(keys[index], default)
        else:
            return default
    except:
        return default

# Initialize database connection
print("Initializing database connection...")
if init_connection_pool():
    init_db()



from average_expense_lib import calculate_average_expense as pypi_avg_calc

def calculate_average_expense(user_id):
    """Calculate average expense per transaction for a user using PyPI library"""
    try:
        # Fetch all expense amounts for the user
        result = execute_query("""
            SELECT amount FROM transactions
            WHERE user_id = %s
        """, (user_id,), fetch_all=True)
        
        # Extract amounts from query result
        amounts = []
        if result:
            for row in result:
                if isinstance(row, tuple):
                    amounts.append(float(row[0]))
                else:
                    amounts.append(float(row))
        
        # Use PyPI library to calculate average
        return pypi_avg_calc(amounts)
        
    except Exception as e:
        print(f"Error calculating average expense: {e}")
        return 0
    


def handle_budget_flash(alert_data):
    """Flash message based on Lambda response"""
    if alert_data.get("message"):
        flash(alert_data["message"], alert_data.get("type", "info"))


import requests

def get_budget_alert_from_lambda(monthly_income, total_expenses):
    """Call Lambda API and return alert + usage percentage"""
    try:
        response = requests.post(
            "https://zq33g01d14.execute-api.us-east-1.amazonaws.com/default/lambda-cpp-x25105990",
            json={
                "monthly_income": monthly_income,
                "total_expenses": total_expenses
            },
            timeout=5
        )

        data = response.json()

        return {
            "message": data.get("message"),
            "type": data.get("type"),
            "usage_percent": data.get("usage_percent", 0)
        }

    except Exception as e:
        print(f"Lambda API error: {e}")
        return {
            "message": None,
            "type": None,
            "usage_percent": 0
        }






# Routes
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    username = session['username']
    
    try:
        # Get user profile data
        
        average_expense = calculate_average_expense(user_id)
        # average_expense = 7000
        user_profile = execute_query(
            "SELECT full_name, profession, monthly_income, savings_goal FROM users WHERE id = %s",
            (user_id,), fetch_one=True
        )
        
        # Fetch all transactions for the user
        transactions = execute_query(
            "SELECT * FROM transactions WHERE user_id = %s ORDER BY date DESC",
            (user_id,), fetch_all=True
        ) or []
        
        # Calculate totals - Fixed to handle tuples correctly
        total_amount = 0
        total_upi = 0
        total_cash = 0
        
        for transaction in transactions:
            # Transaction structure for SELECT *:
            # Index 0: id, 1: user_id, 2: amount, 3: category, 4: date, 5: description, 6: payment_method
            try:
                amount = float(transaction[2]) if len(transaction) > 2 else 0
                payment_method = transaction[6] if len(transaction) > 6 else ''
                
                total_amount += amount
                if payment_method == 'UPI':
                    total_upi += amount
                elif payment_method == 'Cash':
                    total_cash += amount
            except (IndexError, TypeError) as e:
                print(f"Error processing transaction: {e}, transaction: {transaction}")
                continue
        
        # Financial summary
        monthly_income = float(user_profile[2]) if user_profile and len(user_profile) > 2 and user_profile[2] else 0
        savings_goal = float(user_profile[3]) if user_profile and len(user_profile) > 3 and user_profile[3] else 0
        remaining_budget = monthly_income - total_amount if monthly_income > total_amount else 0
        savings_progress = (remaining_budget / savings_goal * 100) if savings_goal > 0 else 0
        savings_progress = min(max(savings_progress, 0), 100)
        
        # Call Lambda for budget alert
        alert_data = get_budget_alert_from_lambda(monthly_income, total_amount)
        
        # Flash message
        handle_budget_flash(alert_data)
        
        # Get usage percentage for UI
        usage_percent = alert_data.get("usage_percent", 0)
        
        # Get expense by category
        expense_by_category = execute_query("""
            SELECT category, COALESCE(SUM(amount), 0) as total 
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY category 
            ORDER BY total DESC 
            LIMIT 5
        """, (user_id,), fetch_all=True) or []
        
        # Get recent transactions (last 5)
        recent_transactions = execute_query("""
            SELECT * FROM transactions 
            WHERE user_id = %s 
            ORDER BY date DESC 
            LIMIT 5
        """, (user_id,), fetch_all=True) or []
        
        # Prepare data for charts
        categories = []
        category_amounts = []
        for row in expense_by_category:
            if row and len(row) >= 2:
                categories.append(str(row[0]))
                category_amounts.append(float(row[1]))
        
        # Format recent transactions for template
        formatted_recent = []
        for trans in recent_transactions:
            if trans and len(trans) >= 7:
                formatted_recent.append({
                    'date': trans[4] if len(trans) > 4 else '',
                    'category': trans[3] if len(trans) > 3 else '',
                    'amount': float(trans[2]) if len(trans) > 2 else 0,
                    'payment_method': trans[6] if len(trans) > 6 else '',
                    'description': trans[5] if len(trans) > 5 and trans[5] else ''
                })
        
        return render_template('index.html', 
                             username=username,
                             full_name=user_profile[0] if user_profile and len(user_profile) > 0 else username,
                             profession=user_profile[1] if user_profile and len(user_profile) > 1 else 'Not specified',
                             monthly_income=monthly_income,
                             savings_goal=savings_goal,
                             remaining_budget=remaining_budget,
                             savings_progress=savings_progress,
                             total_amount=total_amount,
                             total_upi=total_upi,
                             total_cash=total_cash,
                             expense_by_category=expense_by_category,
                             recent_transactions=formatted_recent,
                             categories=categories,
                             category_amounts=category_amounts,
                             average_expense=average_expense,
                             usage_percent=usage_percent)
    except Exception as e:
        print(f"Error in index: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading dashboard', 'error')
        return redirect(url_for('login'))




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            user = execute_query(
                "SELECT id, username FROM users WHERE username = %s AND password = %s",
                (username, password), fetch_one=True
            )
            
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password. Please try again.', 'error')
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        profession = request.form['profession']
        monthly_income = request.form['monthly_income']
        saving_goal = request.form['savings_goal']
        username = request.form['username']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        
        try:
            # Check if user exists
            existing_user = execute_query(
                "SELECT id FROM users WHERE username = %s",
                (username,), fetch_one=True
            )
            
            if existing_user:
                flash('Username already exists. Please choose a different one.', 'error')
            else:
                execute_query(
                    "INSERT INTO users (username, email, phone, password, full_name, profession, monthly_income, savings_goal) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (username, email, phone, password, full_name, profession, monthly_income, saving_goal), commit=True
                )
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            print(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/transactions')
def transactions():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    username = session['username']
    
    transactions_raw = execute_query(
        "SELECT * FROM transactions WHERE user_id = %s ORDER BY date DESC",
        (user_id,), fetch_all=True
    ) or []
    
    # Format transactions for template
    formatted_transactions = []
    for trans in transactions_raw:
        if trans and len(trans) >= 7:
            formatted_transactions.append({
                'id': trans[0],
                'user_id': trans[1],
                'amount': trans[2],
                'category': trans[3],
                'date': trans[4],
                'description': trans[5] if trans[5] else '',
                'payment_method': trans[6]
            })
    
    return render_template('transaction.html', transactions=formatted_transactions, username=username)




@app.route('/get_transaction/<int:transaction_id>')
def get_transaction(transaction_id):
    """Get transaction data as JSON (for AJAX)"""
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    user_id = session['user_id']
    
    transaction = execute_query("""
        SELECT id, date, category, amount, payment_method, COALESCE(description, '') as notes
        FROM transactions 
        WHERE id = %s AND user_id = %s
    """, (transaction_id, user_id), fetch_one=True)
    
    if transaction and len(transaction) >= 6:
        return jsonify({
            'success': True,
            'transaction': {
                'id': transaction[0],
                'date': transaction[1],
                'category': transaction[2],
                'amount': float(transaction[3]),
                'payment_method': transaction[4],
                'notes': transaction[5] if transaction[5] else ''
            }
        })
    else:
        return jsonify({'success': False, 'message': 'Transaction not found'}), 404

@app.route('/edit_transaction/<int:transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    """Edit transaction"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        try:
            date = request.form['date']
            category = request.form['category']
            amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            notes = request.form.get('notes', '')
            
            execute_query("""
                UPDATE transactions 
                SET date = %s, category = %s, amount = %s, payment_method = %s, description = %s
                WHERE id = %s AND user_id = %s
            """, (date, category, amount, payment_method, notes, transaction_id, user_id), commit=True)
            
            flash('Transaction updated successfully!', 'success')
            
        except Exception as e:
            print(f"Error updating transaction: {e}")
            flash(f'Error updating transaction: {str(e)}', 'danger')
        
        return redirect(url_for('transactions'))
    
    # GET request - Get transaction data for display
    transaction = execute_query("""
        SELECT id, user_id, amount, category, date, COALESCE(description, '') as description, payment_method 
        FROM transactions 
        WHERE id = %s AND user_id = %s
    """, (transaction_id, user_id), fetch_one=True)
    
    if not transaction:
        flash('Transaction not found', 'danger')
        return redirect(url_for('transactions'))
    
    return render_template('edit_transaction.html', transaction=transaction)


import boto3

def send_email_using_sns(name, email, amount, category, transaction_medium):
    SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:211125648713:sns-cpp-x25105990"
    
    subject = "Expense Added Successfully"
    
    full_message = f"""
    Expense Details:
    
    User Name: {name}
    Email: {email}
    Amount: €{amount}
    Category: {category}
    Transaction Medium: {transaction_medium}
"""

    try:
        sns_client = boto3.client("sns", region_name="us-east-1")
        
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=full_message,
            Subject=subject
        )
        
        print(f"SNS Message sent! ID: {response['MessageId']}")
        return True

    except Exception as e:
        print(f"Error sending SNS email: {e}")
        return False
    
    

# @app.route('/add_transaction', methods=['POST'])
# def add_transaction():
#     if 'username' not in session:
#         return redirect(url_for('login'))
    
#     user_id = session['user_id']
#     date = request.form['date']
#     category = request.form['category']
#     amount = float(request.form['amount'])
#     payment_method = request.form['payment_method']
#     description = request.form.get('notes', '')
    
#     try:
#         execute_query("""
#             INSERT INTO transactions (user_id, date, category, amount, payment_method, description) 
#             VALUES (%s, %s, %s, %s, %s, %s)
#         """, (user_id, date, category, amount, payment_method, description), commit=True)
        
#         flash('Transaction added successfully!', 'success')
#         send_email_using_sns()
#     except Exception as e:
#         print(f"Error adding transaction: {e}")
#         flash('Failed to add transaction', 'error')
    
#     return redirect(url_for('transactions'))




import boto3
import uuid
from flask import jsonify

@app.route('/download_csv')
def download_csv():
    if 'username' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    user_id = session['user_id']

    try:
        transactions = execute_query("""
            SELECT date, category, amount, payment_method, description
            FROM transactions
            WHERE user_id = %s
            ORDER BY date DESC
        """, (user_id,), fetch_all=True) or []

        import csv, io
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['Date', 'Category', 'Amount', 'Payment Method', 'Notes'])

        for row in transactions:
            writer.writerow([
                row[0], row[1], float(row[2]), row[3], row[4] or ''
            ])

        csv_data = output.getvalue()

        file_url = upload_to_s3(csv_data, user_id)
        send_sns_with_link(user_id, file_url)

        return jsonify({
            "success": True,
            "message": "CSV generated and sent to email!",
            "download_url": file_url
        })

    except Exception as e:
        print(e)
        return jsonify({
            "success": False,
            "message": "Failed to generate CSV"
        })


def upload_to_s3(csv_data, user_id):
    s3 = boto3.client('s3')
    
    bucket_name = 'cpp-s3-x25105990'
    file_name = f"exports/user_{user_id}_{uuid.uuid4()}.csv"

    # Upload file
    s3.put_object(
        Bucket=bucket_name,
        Key=file_name,
        Body=csv_data,
        ContentType='text/csv'
    )

    # Generate pre-signed URL (valid for 1 hour)
    file_url = s3.generate_presigned_url(
    'get_object',
    Params={
        'Bucket': bucket_name,
        'Key': file_name,
        'ResponseContentDisposition': 'attachment; filename="transactions.csv"'
    },
    ExpiresIn=3600
)

    return file_url



def send_sns_with_link(user_id, file_url):
    sns = boto3.client('sns', region_name='us-east-1')

    SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:211125648713:sns-cpp-x25105990"

    # Get user info
    user = execute_query(
        "SELECT full_name, email FROM users WHERE id = %s",
        (user_id,), fetch_one=True
    )

    name = user[0] if user else "User"
    email = user[1] if user else ""

    message = f"""
    Hello {name},
    
    Your transaction CSV file is ready.
    
    Download here:
    {file_url}
    
    Email: {email}
    """

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="Your CSV Export is Ready",
        Message=message
    )



@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    date = request.form['date']
    category = request.form['category']
    amount = float(request.form['amount'])
    payment_method = request.form['payment_method']
    description = request.form.get('notes', '')
    
    try:
        # Insert transaction
        execute_query("""
            INSERT INTO transactions (user_id, date, category, amount, payment_method, description) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, date, category, amount, payment_method, description), commit=True)
        
        #  Get user details
        user_data = execute_query(
            "SELECT full_name, email FROM users WHERE id = %s",
            (user_id,), fetch_one=True
        )
        
        name = user_data[0] if user_data and user_data[0] else session['username']
        email = user_data[1] if user_data and user_data[1] else None
        
        #  Send SNS notification
        if email:
            send_email_using_sns(name, email, amount, category, payment_method)
        
        flash('Transaction added successfully!', 'success')
    
    except Exception as e:
        print(f"Error adding transaction: {e}")
        flash('Failed to add transaction', 'error')
    
    return redirect(url_for('transactions'))



@app.route('/delete_transaction/<int:transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        execute_query("DELETE FROM transactions WHERE id = %s", (transaction_id,), commit=True)
        flash('Transaction deleted successfully.', 'success')
    except Exception as e:
        print(f"Error deleting transaction: {e}")
        flash('Error deleting transaction.', 'error')
    
    return redirect(url_for('transactions'))




@app.route('/daily_spending_data')
def daily_spending_data():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    
    data = execute_query("""
        SELECT date, SUM(amount) 
        FROM transactions 
        WHERE user_id = %s 
        GROUP BY date 
        ORDER BY date
    """, (user_id,), fetch_all=True) or []
    
    labels = [str(row[0]) for row in data]
    amounts = [float(row[1]) for row in data]
    
    return jsonify({'labels': labels, 'amounts': amounts})

@app.route('/monthly_spending_data')
def monthly_spending_data():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    
    if USE_POSTGRES:
        data = execute_query("""
            SELECT TO_CHAR(date, 'YYYY-MM') AS month, 
                   COALESCE(SUM(amount), 0) as total 
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY TO_CHAR(date, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 6
        """, (user_id,), fetch_all=True) or []
    else:
        data = execute_query("""
            SELECT strftime('%Y-%m', date) AS month, 
                   COALESCE(SUM(amount), 0) as total 
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month DESC
            LIMIT 6
        """, (user_id,), fetch_all=True) or []
    
    # Reverse to show chronological order
    data = list(reversed(data))
    
    labels = [datetime.strptime(row[0], '%Y-%m').strftime('%b %Y') for row in data]
    amounts = [float(row[1]) for row in data]
    
    return jsonify({'labels': labels, 'amounts': amounts})

@app.route('/weekly_spending_data')
def weekly_spending_data():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    
    if USE_POSTGRES:
        data = execute_query("""
            SELECT TO_CHAR(date, 'IYYY-IW') AS week, 
                   MIN(date) as week_start,
                   COALESCE(SUM(amount), 0) as total 
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY TO_CHAR(date, 'IYYY-IW')
            ORDER BY week DESC
            LIMIT 8
        """, (user_id,), fetch_all=True) or []
    else:
        data = execute_query("""
            SELECT strftime('%Y-W%W', date) AS week, 
                   MIN(date) as week_start,
                   COALESCE(SUM(amount), 0) as total 
            FROM transactions 
            WHERE user_id = %s 
            GROUP BY strftime('%Y-W%W', date)
            ORDER BY week DESC
            LIMIT 8
        """, (user_id,), fetch_all=True) or []
    
    # Reverse to show chronological order
    data = list(reversed(data))
    
    labels = [f"Week of {row[1]}" for row in data]
    amounts = [float(row[2]) for row in data]
    
    return jsonify({'labels': labels, 'amounts': amounts})


@app.route('/statistics')
def statistics():
    user_id = session.get('user_id')
    
    if not user_id:
        return redirect(url_for('login'))
    
    # Fetch total expenses
    total_expenses_result = execute_query(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = %s",
        (user_id,), fetch_one=True
    )
    total_expenses = total_expenses_result[0] if total_expenses_result else 0
    
    # Fetch expense breakdown by category
    expense_by_category_result = execute_query("""
        SELECT category, COALESCE(SUM(amount), 0) 
        FROM transactions 
        WHERE user_id = %s 
        GROUP BY category
    """, (user_id,), fetch_all=True) or []
    expense_by_category = dict(expense_by_category_result) if expense_by_category_result else {}
    
    # Fetch top spending categories
    top_spending_result = execute_query("""
        SELECT category, COALESCE(SUM(amount), 0) 
        FROM transactions 
        WHERE user_id = %s 
        GROUP BY category 
        ORDER BY SUM(amount) DESC 
        LIMIT 5
    """, (user_id,), fetch_all=True) or []
    top_spending_categories = dict(top_spending_result) if top_spending_result else {}
    
    return render_template('statistics.html', 
                         total_expenses=total_expenses, 
                         expense_by_category=expense_by_category,
                         top_spending_categories=top_spending_categories)



from decimal import Decimal

@app.route('/profile')
def profile():
    """View user profile"""
    if 'username' not in session:
        flash('Please login to view profile', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Fix: Remove duplicate column names
    user_data = execute_query("""
        SELECT id, username, email, phone, full_name, profession, 
               monthly_income, savings_goal, created_at
        FROM users WHERE id = %s
    """, (user_id,), fetch_one=True)
    
    # Convert tuple to dictionary
    if user_data and isinstance(user_data, tuple):
        user = {
            'id': user_data[0],
            'username': user_data[1],
            'email': user_data[2],
            'phone': user_data[3] if user_data[3] else '',
            'full_name': user_data[4] if user_data[4] else '',  # Index 4
            'profession': user_data[5] if user_data[5] else '',  # Index 5
            'monthly_income': float(user_data[6]) if user_data[6] else 0,  # Convert to float
            'savings_goal': float(user_data[7]) if user_data[7] else 0,  # Convert to float
            'created_at': user_data[8].strftime('%Y-%m-%d') if len(user_data) > 8 and user_data[8] else None  # Index 8
        }
    else:
        user = user_data
        # Format datetime if it exists
        # if user and user.get('created_at') and hasattr(user['created_at'], 'strftime'):
        #     user['created_at'] = user['created_at'].strftime('%Y-%m-%d')
        
        if user and user['created_at'] and hasattr(user['created_at'], 'strftime'):
            user['created_at'] = user['created_at'].strftime('%Y-%m-%d')
            
        # Convert Decimal to float
        if user:
            if user.get('monthly_income'):
                user['monthly_income'] = float(user['monthly_income'])
            if user.get('savings_goal'):
                user['savings_goal'] = float(user['savings_goal'])
    
    # Calculate savings progress
    savings_progress = 0
    if user and user.get('savings_goal') and user['savings_goal'] > 0:
        total_expenses_result = execute_query(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = %s",
            (user_id,), fetch_one=True
        )
        
        # Convert Decimal to float - FIX HERE
        if total_expenses_result:
            if isinstance(total_expenses_result, tuple):
                total_expenses = float(total_expenses_result[0]) if total_expenses_result[0] else 0
            else:
                total_expenses = float(total_expenses_result) if total_expenses_result else 0
        else:
            total_expenses = 0
        
        monthly_income = user.get('monthly_income', 0)
        # Convert to float if it's Decimal
        if isinstance(monthly_income, Decimal):
            monthly_income = float(monthly_income)
        
        current_savings = monthly_income - total_expenses if monthly_income > total_expenses else 0
        savings_progress = (current_savings / user['savings_goal']) * 100 if user['savings_goal'] > 0 else 0
        savings_progress = min(max(savings_progress, 0), 100)
    
    # Debug print to verify data
    print(f"User data: {user}")
    print(f"Savings progress: {savings_progress}")
    
    return render_template('profile.html', user=user, savings_progress=savings_progress)




from flask import request, session, redirect, url_for, flash, render_template
import re

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """Edit user profile"""
    
    if 'username' not in session:
        flash('Please login to edit profile', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']

    # -------------------- POST --------------------
    if request.method == 'POST':
        try:
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            profession = request.form.get('profession', '').strip()

            # Safe numeric conversion
            monthly_income = float(request.form.get('monthly_income') or 0)
            savings_goal = float(request.form.get('savings_goal') or 0)

            # Email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash('Invalid email address', 'error')
                return redirect(url_for('edit_profile'))

            # Update query
            execute_query("""
                UPDATE users 
                SET full_name = %s,
                    email = %s,
                    phone = %s,
                    profession = %s,
                    monthly_income = %s,
                    savings_goal = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (full_name, email, phone, profession, monthly_income, savings_goal, user_id), commit=True)

            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))

        except Exception as e:
            print(f"Error updating profile: {e}")
            flash('Something went wrong while updating profile.', 'error')
            return redirect(url_for('edit_profile'))

    # -------------------- GET --------------------
    try:
        user_data = execute_query("""
            SELECT id, username, email, phone, full_name, profession,
                   monthly_income, savings_goal
            FROM users WHERE id = %s
        """, (user_id,), fetch_one=True)

        # Convert tuple → dictionary
        if user_data and isinstance(user_data, tuple):
            user = {
                'id': user_data[0],
                'username': user_data[1],
                'email': user_data[2],
                'phone': user_data[3] or '',
                'full_name': user_data[4] or '',
                'profession': user_data[5] or '',
                'monthly_income': float(user_data[6]) if user_data[6] else 0,
                'savings_goal': float(user_data[7]) if user_data[7] else 0,
            }
        else:
            user = user_data or {}

            # Convert Decimal → float if needed
            if user:
                if user.get('monthly_income'):
                    user['monthly_income'] = float(user['monthly_income'])
                if user.get('savings_goal'):
                    user['savings_goal'] = float(user['savings_goal'])

    except Exception as e:
        print(f"Error fetching user data: {e}")
        flash('Unable to load profile data.', 'error')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=user)



@app.route('/change_password', methods=['POST'])
def change_password():
    """Change user password"""
    if 'username' not in session:
        flash('Please login to change password', 'error')
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Verify current password
    user = execute_query(
        "SELECT password FROM users WHERE id = %s",
        (user_id,), fetch_one=True
    )
    
    if not user or user[0] != current_password:
        flash('Current password is incorrect', 'error')
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('profile'))
    
    if len(new_password) < 6:
        flash('Password must be at least 6 characters', 'error')
        return redirect(url_for('profile'))
    
    # Update password
    execute_query(
        "UPDATE users SET password = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (new_password, user_id), commit=True
    )
    
    flash('Password changed successfully!', 'success')
    return redirect(url_for('profile'))

@app.route('/financial_summary')
def financial_summary():
    """Get financial summary for dashboard"""
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    
    # Get total expenses
    total_expenses_result = execute_query(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = %s",
        (user_id,), fetch_one=True
    )
    total_expenses = total_expenses_result[0] if total_expenses_result else 0
    
    # Get user financial goals
    user = execute_query(
        "SELECT monthly_income, savings_goal FROM users WHERE id = %s",
        (user_id,), fetch_one=True
    )
    
    monthly_income = user[0] if user else 0
    savings_goal = user[1] if user else 0
    remaining_budget = monthly_income - total_expenses
    savings_progress = (remaining_budget / savings_goal * 100) if savings_goal > 0 else 0
    
    return jsonify({
        'monthly_income': float(monthly_income),
        'total_expenses': float(total_expenses),
        'remaining_budget': float(remaining_budget),
        'savings_goal': float(savings_goal),
        'savings_progress': min(max(float(savings_progress), 0), 100)
    })

        


# Keep all other routes (daily_spending_data, monthly_spending_data, weekly_spending_data, statistics, profile, edit_profile, change_password, financial_summary)
# ... (these remain the same as in the previous version)

# Only close connections on app shutdown, not on every request
import atexit
def cleanup():
    """Clean up connections on app shutdown"""
    global connection_pool, pool_initialized
    if USE_POSTGRES and connection_pool and pool_initialized:
        try:
            connection_pool.closeall()
            print("All database connections closed on shutdown.")
        except Exception as e:
            print(f"Error closing connections: {e}")
    pool_initialized = False

# Register cleanup function to run on exit
atexit.register(cleanup)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
    cleanup()