from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3, os, uuid, json
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get('DB_PATH', 'fiztак.db')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS hastalar (
            id TEXT PRIMARY KEY, ad TEXT NOT NULL, soyad TEXT NOT NULL,
            dogum TEXT, cins TEXT DEFAULT 'K', tel TEXT, email TEXT,
            tani TEXT, slim INTEGER, fiz TEXT DEFAULT 'Fzt. 1',
            anm TEXT, not_ TEXT, kt TEXT
        );
        CREATE TABLE IF NOT EXISTS randevular (
            id TEXT PRIMARY KEY, hasta_id TEXT NOT NULL,
            tarih TEXT NOT NULL, saat TEXT NOT NULL,
            fiz TEXT, durum TEXT DEFAULT 'Planlandı', not_ TEXT,
            FOREIGN KEY (hasta_id) REFERENCES hastalar(id)
        );
        CREATE TABLE IF NOT EXISTS seanslar (
            id TEXT PRIMARY KEY, hasta_id TEXT NOT NULL, fiz TEXT,
            tarih TEXT NOT NULL, saat TEXT, islemler TEXT,
            not_ TEXT, agri INTEGER DEFAULT 5,
            FOREIGN KEY (hasta_id) REFERENCES hastalar(id)
        );
        CREATE TABLE IF NOT EXISTS ai_notlar (
            id TEXT PRIMARY KEY, hasta_id TEXT NOT NULL,
            tip TEXT NOT NULL, icerik TEXT NOT NULL, olusturma TEXT NOT NULL,
            FOREIGN KEY (hasta_id) REFERENCES hastalar(id)
        );
    ''')
    conn.commit()
    conn.close()

# ─── HASTA ─────────────────────────────────────────────────────────────────
@app.route('/api/hastalar', methods=['GET'])
def get_hastalar():
    q = request.args.get('q', '')
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT * FROM hastalar WHERE ad||' '||soyad||' '||COALESCE(tani,'') LIKE ? ORDER BY ad",
            (f'%{q}%',)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM hastalar ORDER BY ad").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/hastalar', methods=['POST'])
def add_hasta():
    d = request.json
    hid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute("INSERT INTO hastalar VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (hid, d['ad'], d['soyad'], d.get('dogum'), d.get('cins','K'),
         d.get('tel'), d.get('email'), d.get('tani'), d.get('slim'),
         d.get('fiz','Fzt. 1'), d.get('anm'), d.get('not_'), datetime.now().isoformat()))
    conn.commit(); conn.close()
    return jsonify({'id': hid}), 201

@app.route('/api/hastalar/<hid>', methods=['PUT'])
def update_hasta(hid):
    d = request.json
    conn = get_db()
    conn.execute("""UPDATE hastalar SET ad=?,soyad=?,dogum=?,cins=?,tel=?,email=?,
        tani=?,slim=?,fiz=?,anm=?,not_=? WHERE id=?""",
        (d['ad'],d['soyad'],d.get('dogum'),d.get('cins','K'),d.get('tel'),d.get('email'),
         d.get('tani'),d.get('slim'),d.get('fiz','Fzt. 1'),d.get('anm'),d.get('not_'),hid))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/hastalar/<hid>', methods=['DELETE'])
def delete_hasta(hid):
    conn = get_db()
    for tbl in ['seanslar','randevular','ai_notlar']:
        conn.execute(f"DELETE FROM {tbl} WHERE hasta_id=?", (hid,))
    conn.execute("DELETE FROM hastalar WHERE id=?", (hid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── RANDEVU ───────────────────────────────────────────────────────────────
@app.route('/api/randevular', methods=['GET'])
def get_randevular():
    tarih = request.args.get('tarih')
    hasta_id = request.args.get('hasta_id')
    conn = get_db()
    sql = "SELECT * FROM randevular WHERE 1=1"
    params = []
    if tarih: sql += " AND tarih=?"; params.append(tarih)
    if hasta_id: sql += " AND hasta_id=?"; params.append(hasta_id)
    sql += " ORDER BY tarih,saat"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/randevular', methods=['POST'])
def add_randevu():
    d = request.json
    rid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute("INSERT INTO randevular VALUES (?,?,?,?,?,?,?)",
        (rid, d['hasta_id'], d['tarih'], d['saat'],
         d.get('fiz','Fzt. 1'), d.get('durum','Planlandı'), d.get('not_')))
    conn.commit(); conn.close()
    return jsonify({'id': rid}), 201

@app.route('/api/randevular/<rid>/durum', methods=['PATCH'])
def update_randevu_durum(rid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE randevular SET durum=? WHERE id=?", (d.get('durum','Tamamlandı'), rid))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/randevular/<rid>', methods=['DELETE'])
def delete_randevu(rid):
    conn = get_db()
    conn.execute("DELETE FROM randevular WHERE id=?", (rid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/randevular/month', methods=['GET'])
def randevu_month():
    year = request.args.get('year')
    month = request.args.get('month')
    prefix = f"{year}-{month.zfill(2)}"
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT tarih FROM randevular WHERE tarih LIKE ?", (f'{prefix}%',)).fetchall()
    conn.close()
    return jsonify([r['tarih'] for r in rows])

# ─── SEANS ─────────────────────────────────────────────────────────────────
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
    if hasta_id: sql += " AND hasta_id=?"; params.append(hasta_id)
    if fiz: sql += " AND fiz=?"; params.append(fiz)
    if bas: sql += " AND tarih>=?"; params.append(bas)
    if bit: sql += " AND tarih<=?"; params.append(bit)
    sql += " ORDER BY tarih DESC, saat DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/seanslar', methods=['POST'])
def add_seans():
    d = request.json
    sid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute("INSERT INTO seanslar VALUES (?,?,?,?,?,?,?,?)",
        (sid, d['hasta_id'], d.get('fiz','Fzt. 1'), d['tarih'], d.get('saat'),
         json.dumps(d.get('islemler',[])), d.get('not_'), d.get('agri',5)))
    conn.commit(); conn.close()
    return jsonify({'id': sid}), 201

@app.route('/api/seanslar/<sid>', methods=['DELETE'])
def delete_seans(sid):
    conn = get_db()
    conn.execute("DELETE FROM seanslar WHERE id=?", (sid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── STATS ─────────────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
def get_stats():
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    conn = get_db()
    h_count = conn.execute("SELECT COUNT(*) as c FROM hastalar").fetchone()['c']
    r_today = conn.execute("SELECT COUNT(*) as c FROM randevular WHERE tarih=?", (today,)).fetchone()['c']
    s_week = conn.execute("SELECT COUNT(*) as c FROM seanslar WHERE tarih>=?", (week_ago,)).fetchone()['c']
    s_total = conn.execute("SELECT COUNT(*) as c FROM seanslar").fetchone()['c']
    conn.close()
    return jsonify({'hastalar': h_count, 'randevu_bugun': r_today, 'seans_hafta': s_week, 'seans_toplam': s_total})

# ─── ANALİTİK ──────────────────────────────────────────────────────────────
@app.route('/api/analitik', methods=['GET'])
def get_analitik():
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    next7 = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    fourteen_ago = (datetime.now() - timedelta(days=13)).strftime('%Y-%m-%d')

    total_rdv = conn.execute("SELECT COUNT(*) as c FROM randevular WHERE tarih>=?", (month_ago,)).fetchone()['c']
    done_rdv = conn.execute("SELECT COUNT(*) as c FROM randevular WHERE tarih>=? AND durum='Tamamlandı'", (month_ago,)).fetchone()['c']
    cancelled_rdv = conn.execute("SELECT COUNT(*) as c FROM randevular WHERE tarih>=? AND durum='İptal'", (month_ago,)).fetchone()['c']

    daily = conn.execute(
        "SELECT tarih, COUNT(*) as cnt FROM seanslar WHERE tarih>=? GROUP BY tarih ORDER BY tarih", (fourteen_ago,)).fetchall()

    all_s = conn.execute("SELECT islemler FROM seanslar").fetchall()
    ic = {}
    for row in all_s:
        try:
            for i in json.loads(row['islemler'] or '[]'):
                ic[i] = ic.get(i, 0) + 1
        except: pass
    top_islemler = sorted(ic.items(), key=lambda x: x[1], reverse=True)[:6]

    agri_trend = conn.execute(
        "SELECT tarih, AVG(agri) as avg_agri FROM seanslar WHERE tarih>=? GROUP BY tarih ORDER BY tarih", (month_ago,)).fetchall()

    saat_dist = conn.execute(
        "SELECT saat, COUNT(*) as cnt FROM randevular WHERE saat IS NOT NULL GROUP BY saat ORDER BY cnt DESC LIMIT 8").fetchall()

    hasta_seans = conn.execute("SELECT hasta_id, COUNT(*) as cnt FROM seanslar GROUP BY hasta_id").fetchall()
    avg_seans = round(sum(r['cnt'] for r in hasta_seans)/len(hasta_seans),1) if hasta_seans else 0

    upcoming = conn.execute(
        "SELECT tarih, COUNT(*) as cnt FROM randevular WHERE tarih>=? AND tarih<=? AND durum='Planlandı' GROUP BY tarih ORDER BY tarih",
        (today, next7)).fetchall()

    risk = conn.execute("""
        SELECT h.id, h.ad, h.soyad, h.tani, h.slim,
               MAX(s.tarih) as son_seans, COUNT(s.id) as toplam_seans
        FROM hastalar h LEFT JOIN seanslar s ON h.id=s.hasta_id
        GROUP BY h.id HAVING son_seans < ? OR son_seans IS NULL
        ORDER BY son_seans ASC LIMIT 5""", (week_ago,)).fetchall()

    conn.close()
    return jsonify({
        'tamamlanma_orani': round(done_rdv/total_rdv*100,1) if total_rdv else 0,
        'iptal_orani': round(cancelled_rdv/total_rdv*100,1) if total_rdv else 0,
        'toplam_rdv_30gun': total_rdv,
        'daily_seanslar': [{'tarih': r['tarih'], 'cnt': r['cnt']} for r in daily],
        'top_islemler': [{'id': k, 'cnt': v} for k,v in top_islemler],
        'agri_trend': [{'tarih': r['tarih'], 'avg': round(r['avg_agri'],1)} for r in agri_trend],
        'en_yogun_saatler': [{'saat': r['saat'], 'cnt': r['cnt']} for r in saat_dist],
        'avg_seans_per_hasta': avg_seans,
        'upcoming_randevular': [{'tarih': r['tarih'], 'cnt': r['cnt']} for r in upcoming],
        'risk_hastalar': [dict(r) for r in risk],
    })

# ─── AI NOTLAR ─────────────────────────────────────────────────────────────
@app.route('/api/ai_notlar/<hid>', methods=['GET'])
def get_ai_notlar(hid):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM ai_notlar WHERE hasta_id=? ORDER BY olusturma DESC LIMIT 20", (hid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/ai_notlar', methods=['POST'])
def save_ai_not():
    d = request.json
    nid = str(uuid.uuid4())[:8]
    conn = get_db()
    conn.execute("INSERT INTO ai_notlar VALUES (?,?,?,?,?)",
        (nid, d['hasta_id'], d['tip'], d['icerik'], datetime.now().isoformat()))
    conn.commit(); conn.close()
    return jsonify({'id': nid}), 201

# ─── AI CORE ───────────────────────────────────────────────────────────────
MUAYENEHANE = "Uzm. Dr. Zuhal Karakoyun Fizik Tedavi ve Rehabilitasyon Özel Muayenehanesi"
SYSTEM_BASE = f"""Sen {MUAYENEHANE} için çalışan bir yapay zeka asistanısın.
Fizik tedavi ve rehabilitasyon alanında uzman Türkçe yanıtlar verirsin.
Yanıtların kısa, net ve klinik açıdan doğru olmalı."""

def call_claude(system_prompt, user_prompt, max_tokens=1200):
    import urllib.request, urllib.error
    if not ANTHROPIC_API_KEY:
        raise Exception("ANTHROPIC_API_KEY ayarlanmamış")
    payload = json.dumps({
        "model": "claude-sonnet-4-5",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=payload,
        headers={'Content-Type':'application/json','x-api-key':ANTHROPIC_API_KEY,'anthropic-version':'2023-06-01'},
        method='POST')
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    return data['content'][0]['text']

@app.route('/api/ai/seans-notu', methods=['POST'])
def ai_seans_notu():
    d = request.json
    hasta = d.get('hasta', {})
    seans = d.get('seans', {})
    system = SYSTEM_BASE + "\nGörev: Kısa seans notu yaz. Tıbbi terminoloji kullan. Maksimum 3 cümle."
    user = f"""Hasta: {hasta.get('ad','')} {hasta.get('soyad','')} | Tanı: {hasta.get('tani','—')}
Uygulanan: {', '.join(seans.get('islemler',[]))} | Ağrı: {seans.get('agri','—')}/10
Fizyoterapist notu: {seans.get('not_','—')}
Klinik seans notu yaz."""
    try:
        return jsonify({'not': call_claude(system, user, 350)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/epikriz', methods=['POST'])
def ai_epikriz():
    d = request.json
    hasta = d.get('hasta', {})
    seanslar = d.get('seanslar', [])
    agri_list = [s.get('agri',5) for s in seanslar if s.get('agri') is not None]
    islem_set = set()
    for s in seanslar:
        for i in (s.get('islemler') or []): islem_set.add(i)
    system = SYSTEM_BASE + f"""\nGörev: Resmi hasta epikriz belgesi yaz.
Şu başlıkları kullan: HASTA BİLGİLERİ, TEDAVİ SÜRECİ, UYGULANAN TEDAVİLER, SONUÇ VE ÖNERİLER.
Belge başlığında şunu kullan: {MUAYENEHANE}
Türkçe, profesyonel tıbbi dil."""
    user = f"""Hasta: {hasta.get('ad','')} {hasta.get('soyad','')}
Doğum: {hasta.get('dogum','—')} | Cinsiyet: {'Kadın' if hasta.get('cins')=='K' else 'Erkek'}
Tanı: {hasta.get('tani','—')}
Toplam seans: {len(seanslar)}
İlk seans: {seanslar[-1].get('tarih','—') if seanslar else '—'} | Son: {seanslar[0].get('tarih','—') if seanslar else '—'}
Uygulanan işlemler: {', '.join(islem_set) or '—'}
Başlangıç ağrı: {agri_list[-1] if agri_list else '—'}/10 → Bitiş ağrı: {agri_list[0] if agri_list else '—'}/10
Anamnez: {hasta.get('anm','—')}
Epikriz yaz."""
    try:
        return jsonify({'epikriz': call_claude(system, user, 900)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/randevu-oneri', methods=['POST'])
def ai_randevu_oneri():
    d = request.json
    hasta = d.get('hasta', {})
    seanslar = d.get('seanslar', [])
    rdvlar = d.get('randevular', [])
    system = SYSTEM_BASE + """\nGörev: Hasta için akıllı randevu önerileri ver.
Maddeler halinde: optimal seans sıklığı, risk faktörleri, önerilen sonraki randevu tarihi, uyarılar."""
    iptal_say = sum(1 for r in rdvlar if r.get('durum')=='İptal')
    user = f"""Hasta: {hasta.get('ad','')} {hasta.get('soyad','')} | Tanı: {hasta.get('tani','—')}
Önerilen toplam seans: {hasta.get('slim','—')} | Tamamlanan: {len(seanslar)}
Son seans: {seanslar[0].get('tarih','—') if seanslar else 'Yok'}
Son 30 günde iptal: {iptal_say}
Randevu ve tedavi sıklığı önerisi ver."""
    try:
        return jsonify({'oneri': call_claude(system, user, 500)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/tedavi-protokol', methods=['POST'])
def ai_tedavi_protokol():
    d = request.json
    system = SYSTEM_BASE + """\nGörev: Tanıya göre fizik tedavi protokolü öner.
Maddeler: önerilen modaliteler, seans sıklığı, toplam seans, ev egzersizleri, kontrindikasyonlar."""
    user = f"Tanı: {d.get('tani','')}\nEk bilgi: {d.get('hasta_bilgi','')}\nProtokol öner."
    try:
        return jsonify({'protokol': call_claude(system, user, 600)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/ilerleme-analiz', methods=['POST'])
def ai_ilerleme_analiz():
    d = request.json
    hasta = d.get('hasta', {})
    seanslar = d.get('seanslar', [])
    system = SYSTEM_BASE + "\nGörev: Hasta tedavi ilerlemesini analiz et. Ağrı trendini, seans düzenliliğini, tedavi etkinliğini değerlendir. Maksimum 4 cümle."
    ozet = '\n'.join(f"{s.get('tarih','')}: Ağrı {s.get('agri','?')}/10" for s in seanslar[:10])
    user = f"Hasta: {hasta.get('ad','')} {hasta.get('soyad','')} | Tanı: {hasta.get('tani','—')}\nSeanslar:\n{ozet or 'Yok'}\nİlerleme analizi yap."
    try:
        return jsonify({'analiz': call_claude(system, user, 400)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
