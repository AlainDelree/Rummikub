import sqlite3, json, uuid
from datetime import datetime
from rummikub.config import RACINE_DATA, FICHIER_DB

def _conn():
    RACINE_DATA.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(FICHIER_DB)
    cx.execute("""CREATE TABLE IF NOT EXISTS parties (
        id TEXT PRIMARY KEY, date TEXT, joueurs TEXT,
        terminee INTEGER DEFAULT 0, etat TEXT)""")
    cx.commit()
    return cx

def sauvegarder_partie(etat: dict):
    cx = _conn()
    pid = etat.get("id") or str(uuid.uuid4())[:8]
    etat["id"] = pid
    joueurs_json = json.dumps([{"nom": j["nom"], "score": j["score_cumul"]}
                               for j in etat["joueurs"]], ensure_ascii=False)
    cx.execute("""INSERT OR REPLACE INTO parties (id, date, joueurs, terminee, etat)
                  VALUES (?,?,?,?,?)""",
               (pid, datetime.now().isoformat(timespec="minutes"),
                joueurs_json, int(etat.get("terminee", False)),
                json.dumps(etat, ensure_ascii=False)))
    cx.commit(); cx.close()
    return pid

def charger_parties():
    cx = _conn()
    rows = cx.execute("SELECT id,date,joueurs,terminee FROM parties "
                      "ORDER BY date DESC LIMIT 5").fetchall()
    cx.close()
    return [{"id": r[0], "date": r[1],
             "joueurs": json.loads(r[2]), "terminee": bool(r[3])} for r in rows]

def charger_partie(pid: str):
    cx = _conn()
    row = cx.execute("SELECT etat FROM parties WHERE id=?", (pid,)).fetchone()
    cx.close()
    return json.loads(row[0]) if row else None

def marquer_terminee(pid: str):
    cx = _conn(); cx.execute("UPDATE parties SET terminee=1 WHERE id=?", (pid,)); cx.commit(); cx.close()

def supprimer_partie(pid: str):
    cx = _conn(); cx.execute("DELETE FROM parties WHERE id=?", (pid,)); cx.commit(); cx.close()
