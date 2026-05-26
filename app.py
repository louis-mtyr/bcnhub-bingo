from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import random
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database connection
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Render uses postgres:// but psycopg2 needs postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return psycopg2.connect(database_url)
    else:
        # Fallback to local SQLite-like behavior for development
        return None

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        print("No database connection available, using JSON files as fallback")
        return
    
    try:
        with conn.cursor() as cur:
            # Create items table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    item_text TEXT UNIQUE NOT NULL,
                    votes INTEGER DEFAULT 0
                )
            ''')
            
            # Create users table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    is_connected BOOLEAN DEFAULT FALSE,
                    has_bingo BOOLEAN DEFAULT FALSE,
                    grid JSONB,
                    manifest_choices JSONB DEFAULT '[]',
                    manifest_submitted BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Check if items table is empty and populate from items.json
            cur.execute('SELECT COUNT(*) FROM items')
            count = cur.fetchone()[0]
            
            if count == 0 and os.path.exists('items.json'):
                with open('items.json', 'r', encoding='utf-8-sig') as f:
                    items_data = json.load(f)
                    for item in items_data:
                        cur.execute(
                            'INSERT INTO items (item_text, votes) VALUES (%s, %s) ON CONFLICT (item_text) DO NOTHING',
                            (item['item'], item['votes'])
                        )
            
            conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_users():
    """Get all users from database"""
    conn = get_db_connection()
    if not conn:
        # Fallback to JSON file
        if os.path.exists('users.json'):
            with open('users.json', 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        return {}
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM users')
            rows = cur.fetchall()
            users = {}
            for row in rows:
                users[row['username']] = {
                    'is_connected': row['is_connected'],
                    'has_bingo': row['has_bingo'],
                    'grid': row['grid'],
                    'manifest_choices': row['manifest_choices'],
                    'manifest_submitted': row['manifest_submitted']
                }
            return users
    except Exception as e:
        print(f"Error getting users: {e}")
        return {}
    finally:
        conn.close()

def save_user(username, user_data):
    """Save or update a user in the database"""
    conn = get_db_connection()
    if not conn:
        # Fallback to JSON file
        users = {}
        if os.path.exists('users.json'):
            with open('users.json', 'r', encoding='utf-8-sig') as f:
                users = json.load(f)
        users[username] = user_data
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return
    
    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO users (username, is_connected, has_bingo, grid, manifest_choices, manifest_submitted)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) 
                DO UPDATE SET 
                    is_connected = EXCLUDED.is_connected,
                    has_bingo = EXCLUDED.has_bingo,
                    grid = EXCLUDED.grid,
                    manifest_choices = EXCLUDED.manifest_choices,
                    manifest_submitted = EXCLUDED.manifest_submitted
            ''', (
                username,
                user_data.get('is_connected', False),
                user_data.get('has_bingo', False),
                json.dumps(user_data.get('grid', [])),
                json.dumps(user_data.get('manifest_choices', [])),
                user_data.get('manifest_submitted', False)
            ))
            conn.commit()
    except Exception as e:
        print(f"Error saving user: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_items():
    """Get all item texts from database"""
    conn = get_db_connection()
    if not conn:
        # Fallback to JSON file
        if os.path.exists('items.json'):
            with open('items.json', 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                return [item['item'] for item in data]
        return []
    
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT item_text FROM items ORDER BY id')
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"Error getting items: {e}")
        return []
    finally:
        conn.close()

def get_item_votes():
    """Get votes for all items"""
    conn = get_db_connection()
    if not conn:
        # Fallback to JSON file
        if os.path.exists('items.json'):
            with open('items.json', 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                return {item['item']: item['votes'] for item in data}
        return {}
    
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT item_text, votes FROM items')
            return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        print(f"Error getting item votes: {e}")
        return {}
    finally:
        conn.close()

def save_item_votes(votes):
    """Update votes for items"""
    conn = get_db_connection()
    if not conn:
        # Fallback to JSON file
        if os.path.exists('items.json'):
            with open('items.json', 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            for item in data:
                if item['item'] in votes:
                    item['votes'] = votes[item['item']]
            with open('items.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return
    
    try:
        with conn.cursor() as cur:
            for item_text, vote_count in votes.items():
                cur.execute(
                    'UPDATE items SET votes = %s WHERE item_text = %s',
                    (vote_count, item_text)
                )
            conn.commit()
    except Exception as e:
        print(f"Error saving item votes: {e}")
        conn.rollback()
    finally:
        conn.close()

def generate_bingo_grid(items):
    """Generate a random 5x5 bingo grid"""
    if not items or len(items) == 0:
        # Return empty grid if no items available
        return []
    
    if len(items) < 25:
        # If not enough items, repeat them
        pool = items * (25 // len(items) + 1)
    else:
        pool = items.copy()
    
    random.shuffle(pool)
    selected = pool[:25]
    
    # Create grid with False values
    grid = []
    for i in range(25):
        grid.append({
            'text': selected[i],
            'marked': False
        })
    
    return grid

def check_bingo(grid):
    """Check if there's a bingo (row, column, or diagonal)"""
    # Convert grid to 5x5 matrix
    matrix = [[grid[i*5 + j]['marked'] for j in range(5)] for i in range(5)]
    
    # Check rows
    for row in matrix:
        if all(row):
            return True
    
    # Check columns
    for col in range(5):
        if all(matrix[row][col] for row in range(5)):
            return True
    
    # Check diagonals
    if all(matrix[i][i] for i in range(5)):
        return True
    if all(matrix[i][4-i] for i in range(5)):
        return True
    
    return False

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('bingo'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if username:
            users = get_users()
            
            # Create new user or update existing
            if username not in users:
                items = get_items()
                users[username] = {
                    'is_connected': True,
                    'has_bingo': False,
                    'grid': generate_bingo_grid(items),
                    'manifest_choices': [],
                    'manifest_submitted': False
                }
            else:
                users[username]['is_connected'] = True
            
            save_user(username, users[username])
            session['username'] = username
            return redirect(url_for('bingo'))
    
    return render_template('login.html')

@app.route('/bingo')
def bingo():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('bingo.html', username=session['username'])

@app.route('/manifest')
def manifest():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('manifest.html', username=session['username'])

@app.route('/api/toggle_cell', methods=['POST'])
def toggle_cell():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    username = session['username']
    cell_index = request.json.get('index')
    
    users = get_users()
    if username in users:
        users[username]['grid'][cell_index]['marked'] = not users[username]['grid'][cell_index]['marked']
        
        # Check for bingo
        has_bingo = check_bingo(users[username]['grid'])
        users[username]['has_bingo'] = has_bingo
        
        save_user(username, users[username])
        return jsonify({'success': True, 'has_bingo': has_bingo})
    
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/get_users')
def get_users_api():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    users = get_users()
    user_list = []
    
    for uname, data in users.items():
        user_list.append({
            'username': uname,
            'is_connected': data.get('is_connected', False),
            'has_bingo': data.get('has_bingo', False)
        })
    
    return jsonify({'users': user_list, 'current_user': session['username']})

@app.route('/api/get_user_grid/<username>')
def get_user_grid(username):
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    users = get_users()
    if username in users:
        return jsonify({
            'grid': users[username]['grid'],
            'has_bingo': users[username].get('has_bingo', False)
        })
    
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/get_my_grid')
def get_my_grid():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    username = session['username']
    users = get_users()
    
    if username in users:
        return jsonify({
            'grid': users[username]['grid'],
            'has_bingo': users[username].get('has_bingo', False)
        })
    
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/manifest/items')
def get_manifest_items():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    items = get_items()
    votes = get_item_votes()
    username = session['username']
    users = get_users()
    
    user_choices = users.get(username, {}).get('manifest_choices', [])
    has_submitted = users.get(username, {}).get('manifest_submitted', False)
    
    return jsonify({
        'items': items,
        'votes': votes,
        'user_choices': user_choices,
        'has_submitted': has_submitted
    })

@app.route('/api/manifest/toggle', methods=['POST'])
def toggle_manifest_item():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    username = session['username']
    item_text = request.json.get('item')
    
    users = get_users()
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user has already submitted
    if users[username].get('manifest_submitted', False):
        return jsonify({'error': 'You have already submitted your predictions'}), 403
    
    choices = users[username].get('manifest_choices', [])
    
    if item_text in choices:
        choices.remove(item_text)
    else:
        if len(choices) < 10:
            choices.append(item_text)
        else:
            return jsonify({'error': 'Maximum 10 items allowed'}), 400
    
    users[username]['manifest_choices'] = choices
    save_user(username, users[username])
    
    return jsonify({'success': True, 'choices': choices})

@app.route('/api/manifest/submit', methods=['POST'])
def submit_manifest():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    username = session['username']
    users = get_users()
    
    if username not in users:
        return jsonify({'error': 'User not found'}), 404
    
    choices = users[username].get('manifest_choices', [])
    if len(choices) != 10:
        return jsonify({'error': 'Please select exactly 10 items'}), 400
    
    # Check if user has already submitted
    if users[username].get('manifest_submitted', False):
        return jsonify({'error': 'You have already submitted your predictions'}), 403
    
    # Update votes
    votes = get_item_votes()
    for item in choices:
        votes[item] = votes.get(item, 0) + 1
    
    save_item_votes(votes)
    
    # Mark user as submitted
    users[username]['manifest_submitted'] = True
    save_user(username, users[username])
    
    # Get top 10
    sorted_items = sorted(votes.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return jsonify({
        'success': True,
        'top_items': sorted_items
    })

@app.route('/logout')
def logout():
    if 'username' in session:
        username = session['username']
        users = get_users()
        if username in users:
            users[username]['is_connected'] = False
            save_user(username, users[username])
        session.pop('username', None)
    return redirect(url_for('login'))

# Initialize database when module loads (works with both Flask dev server and gunicorn)
try:
    init_db()
except Exception as e:
    print(f"Warning: Could not initialize database on startup: {e}")
    print("Database will be initialized on first request if needed")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
