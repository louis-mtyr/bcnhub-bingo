from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import random
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

USERS_FILE = 'users.json'
ITEMS_FILE = 'items.json'

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_users():
    users = load_json(USERS_FILE)
    if not users:
        users = {}
        save_json(USERS_FILE, users)
    return users

def get_items():
    data = load_json(ITEMS_FILE)
    if isinstance(data, list):
        return [item['item'] for item in data]
    return []

def get_item_votes():
    data = load_json(ITEMS_FILE)
    if isinstance(data, list):
        return {item['item']: item['votes'] for item in data}
    return {}

def save_item_votes(votes):
    data = load_json(ITEMS_FILE)
    if isinstance(data, list):
        for item in data:
            if item['item'] in votes:
                item['votes'] = votes[item['item']]
        save_json(ITEMS_FILE, data)

def generate_bingo_grid(items):
    """Generate a random 5x5 bingo grid"""
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
            
            save_json(USERS_FILE, users)
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
        
        save_json(USERS_FILE, users)
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
    save_json(USERS_FILE, users)
    
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
    save_json(USERS_FILE, users)
    
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
            save_json(USERS_FILE, users)
        session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
