from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get('DB_PATH', 'fiztак.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS hastalar (
            id TEXT PRIMARY KEY,
            ad TEXT NOT NULL,
            soyad TEXT NOT NULL,
            dogum TEXT,
            cins TEXT DEFAULT 'K',
            tel TEXT,
            email TEXT,
            tani TEXT,
            slim INTEGER,
            fiz TEXT DEFAULT 'Fzt. 1',
            anm TEXT,
            not_ TEXT,
            kt TEXT
        );
        CREATE TABLE IF NOT EXISTS randevular (
            id TEXT PRIMARY KEY,
            hasta_id TEXT NOT NULL,
            tarih TEXT NOT NULL,
            saat TEXT NOT NULL,
            fiz TEXT,
            durum TEXT DEFAULT 'Planlandı',
            not_ TEXT,
            FOREIGN KEY (hasta_id) REFERENCES hastalar(id)
        );
        CREATE TABLE IF NOT EXISTS seanslar (
            id TEXT PRIMARY KEY,
            hasta_id TEXT NOT NULL,
            fiz TEXT,
            tarih TEXT NOT NULL,
            saat TEXT,
            islemler TEXT,
            not_ TEXT,
            agri INTEGER DEFAULT 5,
            FOREIGN KEY (hasta_id) REFERENCES hastalar(id)
        );
    ''')
    conn.commit()
    conn.close()

# ── HASTA ──────────────────────────────────────────────────────────────────
@app.route('/api/hastalar', methods=['GET'])
def get_hastalar():
    q = request.args.get('q', '')
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT * FROM hastalar WHERE ad||' '||soyad||' '||COALESCE(tani,'') LIKE ? ORDER BY ad",
            (f'%{q}%',)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM hastalar ORDER BY ad").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/hastalar', methods=['POST'])
def add_hasta():
    d = request.json
    hid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO hastalar VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (hid, d['ad'], d['soyad'], d.get('dogum'), d.get('cins','K'),
         d.get('tel'), d.get('email'), d.get('tani'), d.get('slim'),
         d.get('fiz','Fzt. 1'), d.get('anm'), d.get('not_'), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({'id': hid}), 201

@app.route('/api/hastalar/<hid>', methods=['PUT'])
def update_hasta(hid):
    d = request.json
    conn = get_db()
    conn.execute(
        """UPDATE hastalar SET ad=?,soyad=?,dogum=?,cins=?,tel=?,email=?,tani=?,
           slim=?,fiz=?,anm=?,not_=? WHERE id=?""",
        (d['ad'], d['soyad'], d.get('dogum'), d.get('cins','K'),
         d.get('tel'), d.get('email'), d.get('tani'), d.get('slim'),
         d.get('fiz','Fzt. 1'), d.get('anm'), d.get('not_'), hid)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/hastalar/<hid>', methods=['DELETE'])
def delete_hasta(hid):
    conn = get_db()
    conn.execute("DELETE FROM seanslar WHERE hasta_id=?", (hid,))
    conn.execute("DELETE FROM randevular WHERE hasta_id=?", (hid,))
    conn.execute("DELETE FROM hastalar WHERE id=?", (hid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── RANDEVU ────────────────────────────────────────────────────────────────
@app.route('/api/randevular', methods=['GET'])
def get_randevular():
    tarih = request.args.get('tarih')
    hasta_id = request.args.get('hasta_id')
    conn = get_db()
    sql = "SELECT * FROM randevular WHERE 1=1"
    params = []
    if tarih:
        sql += " AND tarih=?"; params.append(tarih)
    if hasta_id:
        sql += " AND hasta_id=?"; params.append(hasta_id)
    sql += " ORDER BY tarih,saat"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/randevular', methods=['POST'])
def add_randevu():
    d = request.json
    rid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute(
        "INSERT INTO randevular VALUES (?,?,?,?,?,?,?)",
        (rid, d['hasta_id'], d['tarih'], d['saat'],
         d.get('fiz','Fzt. 1'), d.get('durum','Planlandı'), d.get('not_'))
    )
    conn.commit()
    conn.close()
    return jsonify({'id': rid}), 201

@app.route('/api/randevular/<rid>/durum', methods=['PATCH'])
def update_randevu_durum(rid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE randevular SET durum=? WHERE id=?", (d.get('durum','Tamamlandı'), rid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/randevular/<rid>', methods=['DELETE'])
def delete_randevu(rid):
    conn = get_db()
    conn.execute("DELETE FROM randevular WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/randevular/month', methods=['GET'])
def randevu_month():
    year = request.args.get('year')
    month = request.args.get('month')
    prefix = f"{year}-{month.zfill(2)}"
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT tarih FROM randevular WHERE tarih LIKE ?",
        (f'{prefix}%',)
    ).fetchall()
    conn.close()
    return jsonify([r['tarih'] for r in rows])

# ── SEANS ──────────────────────────────────────────────────────────────────
@app.route('/api/seanslar', methods=['GET'])
def get_seanslar():
    hasta_id = request.args.get('hasta_id')
    fiz = request.args.get('fiz')
    bas = request.args.get('bas')
    bit = request.args.get('bit')
    limit = request.args.get('limit', 50)
    conn = get_db()
    sql = "SELECT * FROM seanslar WHERE 1=1"
    params = []
    if hasta_id:
        sql += " AND hasta_id=?"; params.append(hasta_id)
    if fiz:
        sql += " AND fiz=?"; params.append(fiz)
    if bas:
        sql += " AND tarih>=?"; params.append(bas)
    if bit:
        sql += " AND tarih<=?"; params.append(bit)
    sql += " ORDER BY tarih DESC, saat DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/seanslar', methods=['POST'])
def add_seans():
    d = request.json
    sid = str(uuid.uuid4())[:8]
    import json
    conn = get_db()
    conn.execute(
        "INSERT INTO seanslar VALUES (?,?,?,?,?,?,?,?)",
        (sid, d['hasta_id'], d.get('fiz','Fzt. 1'), d['tarih'], d.get('saat'),
         json.dumps(d.get('islemler',[])), d.get('not_'), d.get('agri',5))
    )
    conn.commit()
    conn.close()
    return jsonify({'id': sid}), 201

@app.route('/api/seanslar/<sid>', methods=['DELETE'])
def delete_seans(sid):
    conn = get_db()
    conn.execute("DELETE FROM seanslar WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ── STATS ──────────────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
def get_stats():
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = datetime.now().strftime('%Y-%m-%d')
    from datetime import timedelta
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    conn = get_db()
    h_count = conn.execute("SELECT COUNT(*) as c FROM hastalar").fetchone()['c']
    r_today = conn.execute("SELECT COUNT(*) as c FROM randevular WHERE tarih=?", (today,)).fetchone()['c']
    s_week = conn.execute("SELECT COUNT(*) as c FROM seanslar WHERE tarih>=?", (week_ago,)).fetchone()['c']
    s_total = conn.execute("SELECT COUNT(*) as c FROM seanslar").fetchone()['c']
    conn.close()
    return jsonify({'hastalar': h_count, 'randevu_bugun': r_today, 'seans_hafta': s_week, 'seans_toplam': s_total})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
