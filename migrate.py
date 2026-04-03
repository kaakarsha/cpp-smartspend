#!/usr/bin/env python3
"""
Data Migration Script from SQLite to PostgreSQL RDS
"""

import sqlite3
import psycopg2
from psycopg2 import sql
import os
from datetime import datetime
import sys

# Configuration
SQLITE_DB_PATH = 'finance_tracker.db'  # Your SQLite database file

# PostgreSQL RDS Configuration
POSTGRES_CONFIG = {
    'host': os.environ.get('DB_HOST', 'postgres-rds-cpp.clygm6iaiqxj.us-east-1.rds.amazonaws.com'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'postgres-rds-cpp'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'connect_timeout': 30
}

class DataMigrator:
    def __init__(self):
        self.sqlite_conn = None
        self.postgres_conn = None
        self.postgres_cursor = None
        
    def connect_sqlite(self):
        """Connect to SQLite database"""
        try:
            self.sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
            self.sqlite_conn.row_factory = sqlite3.Row
            print("Connected to SQLite database")
            return True
        except Exception as e:
            print(f" Failed to connect to SQLite: {e}")
            return False
    
    def connect_postgres(self):
        """Connect to PostgreSQL database"""
        try:
            self.postgres_conn = psycopg2.connect(**POSTGRES_CONFIG)
            self.postgres_cursor = self.postgres_conn.cursor()
            print("Connected to PostgreSQL database")
            return True
        except Exception as e:
            print(f" Failed to connect to PostgreSQL: {e}")
            print("\nTroubleshooting tips:")
            print("1. Check if RDS instance is accessible")
            print("2. Verify security group allows your IP")
            print("3. Check credentials")
            return False
    
    def create_postgres_tables(self):
        """Create tables in PostgreSQL if they don't exist"""
        try:
            # Create users table
            self.postgres_cursor.execute('''
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
            
            # Create transactions table
            self.postgres_cursor.execute('''
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
            self.postgres_cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)')
            self.postgres_cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)')
            self.postgres_cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            self.postgres_cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
            
            self.postgres_conn.commit()
            print("PostgreSQL tables created/verified")
            return True
        except Exception as e:
            print(f" Error creating tables: {e}")
            return False
    
    def get_sqlite_users(self):
        """Fetch all users from SQLite"""
        cursor = self.sqlite_conn.cursor()
        
        # Check if columns exist in SQLite
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Build query based on available columns
        select_cols = ['id', 'username', 'email', 'phone', 'password']
        
        if 'full_name' in columns:
            select_cols.append('full_name')
        else:
            select_cols.append("'' as full_name")
            
        if 'profession' in columns:
            select_cols.append('profession')
        else:
            select_cols.append("'' as profession")
            
        if 'monthly_income' in columns:
            select_cols.append('monthly_income')
        else:
            select_cols.append('0 as monthly_income')
            
        if 'savings_goal' in columns:
            select_cols.append('savings_goal')
        else:
            select_cols.append('0 as savings_goal')
            
        if 'created_at' in columns:
            select_cols.append('created_at')
        else:
            select_cols.append('CURRENT_TIMESTAMP as created_at')
        
        query = f"SELECT {', '.join(select_cols)} FROM users"
        cursor.execute(query)
        users = cursor.fetchall()
        
        print(f" Found {len(users)} users in SQLite")
        return users
    
    def get_sqlite_transactions(self):
        """Fetch all transactions from SQLite"""
        cursor = self.sqlite_conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Build query based on available columns
        select_cols = ['id', 'user_id', 'amount', 'category', 'date']
        
        if 'description' in columns:
            select_cols.append('description')
        else:
            select_cols.append("'' as description")
            
        if 'payment_method' in columns:
            select_cols.append('payment_method')
        else:
            select_cols.append("'Cash' as payment_method")
            
        if 'created_at' in columns:
            select_cols.append('created_at')
        else:
            select_cols.append('CURRENT_TIMESTAMP as created_at')
        
        query = f"SELECT {', '.join(select_cols)} FROM transactions"
        cursor.execute(query)
        transactions = cursor.fetchall()
        
        print(f" Found {len(transactions)} transactions in SQLite")
        return transactions
    
    def migrate_users(self, sqlite_users):
        """Migrate users to PostgreSQL"""
        migrated = 0
        failed = 0
        id_mapping = {}  # Map old SQLite IDs to new PostgreSQL IDs
        
        for user in sqlite_users:
            try:
                # Convert user data based on tuple length
                if len(user) >= 5:
                    username = user[1]
                    email = user[2]
                    phone = user[3]
                    password = user[4]
                    full_name = user[5] if len(user) > 5 else ''
                    profession = user[6] if len(user) > 6 else ''
                    monthly_income = user[7] if len(user) > 7 else 0
                    savings_goal = user[8] if len(user) > 8 else 0
                    old_id = user[0]
                    
                    # Check if user already exists
                    self.postgres_cursor.execute(
                        "SELECT id FROM users WHERE username = %s",
                        (username,)
                    )
                    existing = self.postgres_cursor.fetchone()
                    
                    if not existing:
                        # Insert new user
                        self.postgres_cursor.execute("""
                            INSERT INTO users (username, email, phone, password, full_name, 
                                             profession, monthly_income, savings_goal)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (username, email, phone, password, full_name, 
                              profession, monthly_income, savings_goal))
                        
                        new_id = self.postgres_cursor.fetchone()[0]
                        id_mapping[old_id] = new_id
                        migrated += 1
                        print(f"  Migrated user: {username} (ID: {old_id} -> {new_id})")
                    else:
                        id_mapping[old_id] = existing[0]
                        print(f"  User already exists: {username}")
                
            except Exception as e:
                failed += 1
                print(f"   Failed to migrate user {user[1] if len(user) > 1 else 'unknown'}: {e}")
        
        self.postgres_conn.commit()
        print(f"\n Users migration complete: {migrated} migrated, {failed} failed")
        return id_mapping
    
    def migrate_transactions(self, sqlite_transactions, id_mapping):
        """Migrate transactions to PostgreSQL"""
        migrated = 0
        failed = 0
        
        for transaction in sqlite_transactions:
            try:
                old_user_id = transaction[1]
                
                # Map to new user ID
                if old_user_id not in id_mapping:
                    print(f"  Skipping transaction for user_id {old_user_id} (not found in migration)")
                    failed += 1
                    continue
                
                new_user_id = id_mapping[old_user_id]
                amount = float(transaction[2])
                category = transaction[3]
                date = transaction[4]
                description = transaction[5] if len(transaction) > 5 else ''
                payment_method = transaction[6] if len(transaction) > 6 else 'Cash'
                
                # Insert transaction
                self.postgres_cursor.execute("""
                    INSERT INTO transactions (user_id, amount, category, date, description, payment_method)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (new_user_id, amount, category, date, description, payment_method))
                
                migrated += 1
                if migrated % 50 == 0:
                    print(f"  Migrated {migrated} transactions...")
                
            except Exception as e:
                failed += 1
                print(f"   Failed to migrate transaction: {e}")
        
        self.postgres_conn.commit()
        print(f"\n Transactions migration complete: {migrated} migrated, {failed} failed")
    
    def verify_migration(self):
        """Verify data migration"""
        print("\nVerifying migration...")
        
        # Count users
        self.postgres_cursor.execute("SELECT COUNT(*) FROM users")
        user_count = self.postgres_cursor.fetchone()[0]
        
        # Count transactions
        self.postgres_cursor.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = self.postgres_cursor.fetchone()[0]
        
        print(f"PostgreSQL now has:")
        print(f"   - {user_count} users")
        print(f"   - {transaction_count} transactions")
        
        return user_count > 0
    
    def backup_sqlite(self):
        """Create backup of SQLite database"""
        import shutil
        backup_name = f"finance_tracker_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        try:
            shutil.copy2(SQLITE_DB_PATH, backup_name)
            print(f"SQLite database backed up to {backup_name}")
            return True
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")
            return False
    
    def close_connections(self):
        """Close all database connections"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.postgres_cursor:
            self.postgres_cursor.close()
        if self.postgres_conn:
            self.postgres_conn.close()
        print("Database connections closed")
    
    def run_migration(self):
        """Run complete migration process"""
        print("=" * 60)
        print(" Starting Data Migration from SQLite to PostgreSQL RDS")
        print("=" * 60)
        
        # Step 1: Create backup
        print("\n Step 1: Creating backup...")
        self.backup_sqlite()
        
        # Step 2: Connect to databases
        print("\n🔌 Step 2: Connecting to databases...")
        if not self.connect_sqlite():
            return False
        if not self.connect_postgres():
            return False
        
        # Step 3: Create PostgreSQL tables
        print("\n Step 3: Creating PostgreSQL tables...")
        if not self.create_postgres_tables():
            return False
        
        # Step 4: Fetch data from SQLite
        print("\n Step 4: Fetching data from SQLite...")
        users = self.get_sqlite_users()
        transactions = self.get_sqlite_transactions()
        
        if not users and not transactions:
            print(" No data found in SQLite database")
            return True
        
        # Step 5: Migrate users
        print("\n👥 Step 5: Migrating users...")
        id_mapping = self.migrate_users(users)
        
        # Step 6: Migrate transactions
        print("\nStep 6: Migrating transactions...")
        self.migrate_transactions(transactions, id_mapping)
        
        # Step 7: Verify migration
        print("\nStep 7: Verifying migration...")
        success = self.verify_migration()
        
        # Step 8: Close connections
        self.close_connections()
        
        if success:
            print("\n" + "=" * 60)
            print(" MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Update your .env file with PostgreSQL credentials")
            print("2. Restart your Flask application")
            print("3. Verify data in the application")
        else:
            print("\n Migration failed! Check errors above.")
        
        return success

def main():
    """Main function"""
    # Check if PostgreSQL credentials are set
    if not POSTGRES_CONFIG['password']:
        print(" Please set PostgreSQL password in environment variables or directly in the script")
        print("\nYou can set it by:")
        print("1. Creating .env file with DB_PASSWORD=your_password")
        print("2. Or uncomment and set it directly in the script")
        sys.exit(1)
    
    # Run migration
    migrator = DataMigrator()
    success = migrator.run_migration()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()