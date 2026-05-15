from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from itertools import combinations
from pathlib import Path

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / 'badminton.db'

app = Flask(__name__)
app.secret_key = 'change-this-secret-key'

GROUPS = {
    'A': ['Team Hiếu K-Hoàng', 'Team Đạt Tuấn-Việt', 'Team Hiệp-VNam', 'Team T.Tú-Q.Anh'],
    'B': ['Team Hiếu B-Huy Tú', 'Team Khiêm-P.Anh', 'Team Thắng-B.Nam', 'Team Tùng-Vinh'],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            group_name TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            birth_year TEXT,
            nationality TEXT,
            height TEXT,
            weight TEXT,
            team_id INTEGER NOT NULL,
            image_url TEXT,
            description TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            group_name TEXT,
            round_name TEXT,
            team1_id INTEGER NOT NULL,
            team2_id INTEGER NOT NULL,
            team1_score INTEGER,
            team2_score INTEGER,
            set1_t1 INTEGER,
            set1_t2 INTEGER,
            set2_t1 INTEGER,
            set2_t2 INTEGER,
            set3_t1 INTEGER,
            set3_t2 INTEGER,
            winner_id INTEGER,
            status TEXT DEFAULT 'scheduled',
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY(team1_id) REFERENCES teams(id),
            FOREIGN KEY(team2_id) REFERENCES teams(id),
            FOREIGN KEY(winner_id) REFERENCES teams(id)
        )
    ''')

    for group_name, team_names in GROUPS.items():
        for team_name in team_names:
            cur.execute('INSERT OR IGNORE INTO teams(name, group_name) VALUES (?, ?)', (team_name, group_name))

    cur.execute("SELECT COUNT(*) AS c FROM matches WHERE stage = 'group'")
    if cur.fetchone()['c'] == 0:
        order = 1
        for group_name in ['A', 'B']:
            cur.execute('SELECT id, name FROM teams WHERE group_name=? ORDER BY id', (group_name,))
            teams = cur.fetchall()
            for idx, (t1, t2) in enumerate(combinations(teams, 2), start=1):
                cur.execute('''
                    INSERT INTO matches(stage, group_name, round_name, team1_id, team2_id, display_order)
                    VALUES ('group', ?, ?, ?, ?, ?)
                ''', (group_name, f'Lượt trận {idx}', t1['id'], t2['id'], order))
                order += 1

    conn.commit()
    conn.close()


def fetch_matches(stage=None):
    conn = get_db()
    sql = '''
        SELECT m.*, t1.name AS team1_name, t2.name AS team2_name, tw.name AS winner_name
        FROM matches m
        JOIN teams t1 ON m.team1_id=t1.id
        JOIN teams t2 ON m.team2_id=t2.id
        LEFT JOIN teams tw ON m.winner_id=tw.id
    '''
    params = []
    if stage:
        sql += ' WHERE m.stage=?'
        params.append(stage)
    sql += ' ORDER BY m.display_order, m.id'
    rows = get_db().execute(sql, params).fetchall()
    return rows


def compute_winner_group(team1_id, team2_id, s1, s2):
    if s1 is None or s2 is None or s1 == s2:
        return None
    return team1_id if s1 > s2 else team2_id


def compute_winner_knockout(match, sets):
    wins1 = wins2 = 0
    for a, b in sets:
        if a is None or b is None or a == b:
            continue
        if a > b:
            wins1 += 1
        else:
            wins2 += 1
    if wins1 >= 2:
        return match['team1_id']
    if wins2 >= 2:
        return match['team2_id']
    return None


def group_standings(group_name):
    conn = get_db()
    teams = conn.execute('SELECT * FROM teams WHERE group_name=? ORDER BY id', (group_name,)).fetchall()
    table = {t['id']: {
        'team_id': t['id'], 'team_name': t['name'], 'played': 0, 'wins': 0, 'losses': 0,
        'points': 0, 'points_for': 0, 'points_against': 0, 'diff': 0
    } for t in teams}

    matches = conn.execute('''
        SELECT * FROM matches
        WHERE stage='group' AND group_name=? AND status='finished'
    ''', (group_name,)).fetchall()

    h2h = {}
    for m in matches:
        t1, t2 = m['team1_id'], m['team2_id']
        s1, s2 = m['team1_score'] or 0, m['team2_score'] or 0
        winner = m['winner_id']
        loser = t2 if winner == t1 else t1
        table[t1]['played'] += 1
        table[t2]['played'] += 1
        table[t1]['points_for'] += s1
        table[t1]['points_against'] += s2
        table[t2]['points_for'] += s2
        table[t2]['points_against'] += s1
        if winner:
            table[winner]['wins'] += 1
            table[winner]['points'] += 1
            table[loser]['losses'] += 1
            h2h[frozenset([t1, t2])] = winner

    for row in table.values():
        row['diff'] = row['points_for'] - row['points_against']

    ranked = list(table.values())
    ranked.sort(key=lambda x: (-x['points'], -x['diff'], x['team_id']))

    # Nếu 2 đội bằng điểm và hiệu số thì xét đối đầu.
    i = 0
    while i < len(ranked) - 1:
        a, b = ranked[i], ranked[i + 1]
        if a['points'] == b['points'] and a['diff'] == b['diff']:
            winner = h2h.get(frozenset([a['team_id'], b['team_id']]))
            if winner == b['team_id']:
                ranked[i], ranked[i + 1] = ranked[i + 1], ranked[i]
        i += 1
    return ranked


def all_group_matches_finished():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='group' AND status!='finished'").fetchone()
    return row['c'] == 0


def generate_semifinals_if_ready():
    if not all_group_matches_finished():
        return False
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='semifinal'")
    if cur.fetchone()['c'] > 0:
        conn.close()
        return True
    a = group_standings('A')
    b = group_standings('B')
    if len(a) < 2 or len(b) < 2:
        conn.close()
        return False
    sf1 = (a[0]['team_id'], b[1]['team_id'], 'Bán kết 1: Nhất A - Nhì B')
    sf2 = (a[1]['team_id'], b[0]['team_id'], 'Bán kết 2: Nhì A - Nhất B')
    cur.execute('''INSERT INTO matches(stage, round_name, team1_id, team2_id, display_order)
                   VALUES ('semifinal', ?, ?, ?, 100)''', (sf1[2], sf1[0], sf1[1]))
    cur.execute('''INSERT INTO matches(stage, round_name, team1_id, team2_id, display_order)
                   VALUES ('semifinal', ?, ?, ?, 101)''', (sf2[2], sf2[0], sf2[1]))
    conn.commit()
    conn.close()
    return True


def generate_final_if_ready():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='final'")
    if cur.fetchone()['c'] > 0:
        conn.close()
        return True
    semis = conn.execute("SELECT * FROM matches WHERE stage='semifinal' ORDER BY display_order").fetchall()
    if len(semis) != 2 or any(m['status'] != 'finished' or not m['winner_id'] for m in semis):
        conn.close()
        return False
    cur.execute('''INSERT INTO matches(stage, round_name, team1_id, team2_id, display_order)
                   VALUES ('final', 'Chung kết vô địch', ?, ?, 200)''', (semis[0]['winner_id'], semis[1]['winner_id']))
    conn.commit()
    conn.close()
    return True


def roadmap_status():
    conn = get_db()
    total_group = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='group'").fetchone()['c']
    done_group = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='group' AND status='finished'").fetchone()['c']
    total_sf = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='semifinal'").fetchone()['c']
    done_sf = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='semifinal' AND status='finished'").fetchone()['c']
    total_final = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='final'").fetchone()['c']
    done_final = conn.execute("SELECT COUNT(*) AS c FROM matches WHERE stage='final' AND status='finished'").fetchone()['c']
    champion = conn.execute('''
        SELECT t.name FROM matches m JOIN teams t ON m.winner_id=t.id
        WHERE m.stage='final' AND m.status='finished'
    ''').fetchone()
    conn.close()
    return {
        'group': (done_group, total_group),
        'semifinal': (done_sf, total_sf),
        'final': (done_final, total_final),
        'champion': champion['name'] if champion else None
    }


@app.route('/')
def index():
    generate_semifinals_if_ready()
    generate_final_if_ready()
    return render_template('index.html', roadmap=roadmap_status(), standings_a=group_standings('A'), standings_b=group_standings('B'))


@app.route('/matches')
def matches():
    generate_semifinals_if_ready()
    generate_final_if_ready()
    return render_template('matches.html', matches=fetch_matches(), standings_a=group_standings('A'), standings_b=group_standings('B'))


@app.route('/matches/<int:match_id>/score', methods=['POST'])
def update_score(match_id):
    conn = get_db()
    match = conn.execute('SELECT * FROM matches WHERE id=?', (match_id,)).fetchone()
    if not match:
        flash('Không tìm thấy trận đấu.', 'error')
        return redirect(url_for('matches'))

    cur = conn.cursor()
    try:
        if match['stage'] == 'group':
            s1 = int(request.form.get('team1_score', ''))
            s2 = int(request.form.get('team2_score', ''))
            if s1 == s2:
                raise ValueError('Tỉ số không được hòa.')
            winner = compute_winner_group(match['team1_id'], match['team2_id'], s1, s2)
            cur.execute('''
                UPDATE matches SET team1_score=?, team2_score=?, winner_id=?, status='finished'
                WHERE id=?
            ''', (s1, s2, winner, match_id))
        else:
            sets = []
            data = {}
            for n in [1, 2, 3]:
                a_raw = request.form.get(f'set{n}_t1', '').strip()
                b_raw = request.form.get(f'set{n}_t2', '').strip()
                a = int(a_raw) if a_raw != '' else None
                b = int(b_raw) if b_raw != '' else None
                data[f'set{n}_t1'] = a
                data[f'set{n}_t2'] = b
                sets.append((a, b))
            winner = compute_winner_knockout(match, sets)
            status = 'finished' if winner else 'scheduled'
            cur.execute('''
                UPDATE matches
                SET set1_t1=?, set1_t2=?, set2_t1=?, set2_t2=?, set3_t1=?, set3_t2=?, winner_id=?, status=?
                WHERE id=?
            ''', (data['set1_t1'], data['set1_t2'], data['set2_t1'], data['set2_t2'], data['set3_t1'], data['set3_t2'], winner, status, match_id))
        conn.commit()
        flash('Đã cập nhật tỉ số trận đấu.', 'success')
    except ValueError as e:
        flash(f'Tỉ số chưa hợp lệ: {e}', 'error')
    finally:
        conn.close()

    generate_semifinals_if_ready()
    generate_final_if_ready()
    return redirect(url_for('matches'))


@app.route('/standings')
def standings():
    generate_semifinals_if_ready()
    return render_template('standings.html', standings_a=group_standings('A'), standings_b=group_standings('B'))


@app.route('/players', methods=['GET', 'POST'])
def players():
    conn = get_db()
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        team_id = request.form.get('team_id')
        if full_name and team_id:
            conn.execute('''
                INSERT INTO players(full_name, birth_year, nationality, height, weight, team_id, image_url, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                full_name,
                request.form.get('birth_year', '').strip(),
                request.form.get('nationality', '').strip(),
                request.form.get('height', '').strip(),
                request.form.get('weight', '').strip(),
                team_id,
                request.form.get('image_url', '').strip(),
                request.form.get('description', '').strip(),
            ))
            conn.commit()
            flash('Đã thêm VĐV mới.', 'success')
        else:
            flash('Vui lòng nhập tên VĐV và chọn đội.', 'error')
        conn.close()
        return redirect(url_for('players'))

    players_data = conn.execute('''
        SELECT p.*, t.name AS team_name FROM players p JOIN teams t ON p.team_id=t.id ORDER BY t.id, p.full_name
    ''').fetchall()
    teams = conn.execute('SELECT * FROM teams ORDER BY id').fetchall()
    conn.close()
    return render_template('players.html', players=players_data, teams=teams)


@app.route('/players/<int:player_id>')
def player_detail(player_id):
    conn = get_db()
    player = conn.execute('''
        SELECT p.*, t.name AS team_name, t.group_name FROM players p JOIN teams t ON p.team_id=t.id WHERE p.id=?
    ''', (player_id,)).fetchone()
    conn.close()
    if not player:
        flash('Không tìm thấy VĐV.', 'error')
        return redirect(url_for('players'))
    return render_template('player_detail.html', player=player)


@app.route('/players/<int:player_id>/edit', methods=['POST'])
def edit_player(player_id):
    conn = get_db()
    conn.execute('''
        UPDATE players
        SET full_name=?, birth_year=?, nationality=?, height=?, weight=?, team_id=?, image_url=?, description=?
        WHERE id=?
    ''', (
        request.form.get('full_name', '').strip(),
        request.form.get('birth_year', '').strip(),
        request.form.get('nationality', '').strip(),
        request.form.get('height', '').strip(),
        request.form.get('weight', '').strip(),
        request.form.get('team_id'),
        request.form.get('image_url', '').strip(),
        request.form.get('description', '').strip(),
        player_id
    ))
    conn.commit()
    conn.close()
    flash('Đã cập nhật thông tin VĐV.', 'success')
    return redirect(url_for('players'))


@app.route('/players/<int:player_id>/delete', methods=['POST'])
def delete_player(player_id):
    conn = get_db()
    conn.execute('DELETE FROM players WHERE id=?', (player_id,))
    conn.commit()
    conn.close()
    flash('Đã xóa VĐV.', 'success')
    return redirect(url_for('players'))


if __name__ == "__main__":
    app.run(debug=True)