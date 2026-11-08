"""Sistema web de gestión de tareas. Contrato: ver ESPECIFICACION.md, sección 3."""
import sqlite3
from datetime import date, datetime

from flask import Flask, g, jsonify, render_template, request
from werkzeug.exceptions import HTTPException


def get_db(db_path):
    if "db" not in g:
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT NOT NULL DEFAULT '',
            prioridad TEXT NOT NULL DEFAULT 'media',
            fecha_limite TEXT,
            completada INTEGER NOT NULL DEFAULT 0,
            creada_en TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def fila_a_dict(fila):
    return {
        "id": fila["id"],
        "titulo": fila["titulo"],
        "descripcion": fila["descripcion"],
        "prioridad": fila["prioridad"],
        "fecha_limite": fila["fecha_limite"],
        "completada": bool(fila["completada"]),
        "creada_en": fila["creada_en"],
    }


def error(mensaje, codigo):
    return jsonify({"error": mensaje}), codigo


def validar_titulo(valor):
    if not isinstance(valor, str):
        return None, "El título debe tener entre 3 y 100 caracteres"
    valor = valor.strip()
    if len(valor) < 3 or len(valor) > 100:
        return None, "El título debe tener entre 3 y 100 caracteres"
    return valor, None


def validar_descripcion(valor):
    if valor is None:
        return "", None
    if not isinstance(valor, str):
        return None, "La descripción debe ser texto"
    valor = valor.strip()
    if len(valor) > 500:
        return None, "La descripción no puede superar los 500 caracteres"
    return valor, None


def validar_prioridad(valor):
    if valor not in ("alta", "media", "baja"):
        return None, "La prioridad debe ser alta, media o baja"
    return valor, None


def validar_fecha_limite(valor):
    if valor is None:
        return None, None
    if not isinstance(valor, str):
        return None, "La fecha límite no es válida"
    try:
        fecha = datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None, "La fecha límite no es válida"
    if fecha < date.today():
        return None, "La fecha límite no puede ser anterior a hoy"
    return valor, None


def create_app(db_path: str = "tareas.db") -> Flask:
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path
    init_db(db_path)

    @app.teardown_appcontext
    def cerrar_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(HTTPException)
    def manejar_http_error(e):
        return jsonify({"error": e.description}), e.code

    @app.post("/api/tareas")
    def crear_tarea():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return error("El cuerpo debe ser un objeto JSON", 400)

        titulo, err = validar_titulo(datos.get("titulo"))
        if err:
            return error(err, 400)

        descripcion, err = validar_descripcion(datos.get("descripcion"))
        if err:
            return error(err, 400)

        prioridad, err = validar_prioridad(datos.get("prioridad", "media"))
        if err:
            return error(err, 400)

        fecha_limite, err = validar_fecha_limite(datos.get("fecha_limite"))
        if err:
            return error(err, 400)

        creada_en = datetime.now().isoformat(timespec="seconds")

        db = get_db(app.config["DB_PATH"])
        cur = db.execute(
            "INSERT INTO tareas (titulo, descripcion, prioridad, fecha_limite, completada, creada_en) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (titulo, descripcion, prioridad, fecha_limite, creada_en),
        )
        db.commit()
        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(fila_a_dict(fila)), 201

    @app.get("/api/tareas")
    def listar_tareas():
        q = request.args.get("q", "").strip()
        estado = request.args.get("estado")

        if estado is not None and estado not in ("pendiente", "completada"):
            return error("El estado debe ser pendiente o completada", 400)

        sql = "SELECT * FROM tareas WHERE 1=1"
        params = []

        if q:
            sql += " AND (LOWER(titulo) LIKE ? OR LOWER(descripcion) LIKE ?)"
            patron = "%" + q.lower() + "%"
            params.append(patron)
            params.append(patron)

        if estado == "pendiente":
            sql += " AND completada = 0"
        elif estado == "completada":
            sql += " AND completada = 1"

        sql += " ORDER BY id ASC"

        db = get_db(app.config["DB_PATH"])
        filas = db.execute(sql, params).fetchall()
        return jsonify([fila_a_dict(f) for f in filas])

    @app.get("/api/tareas/<int:tarea_id>")
    def obtener_tarea(tarea_id):
        db = get_db(app.config["DB_PATH"])
        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        if fila is None:
            return error("La tarea no existe", 404)
        return jsonify(fila_a_dict(fila))

    @app.put("/api/tareas/<int:tarea_id>")
    def editar_tarea(tarea_id):
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return error("El cuerpo debe ser un objeto JSON", 400)

        db = get_db(app.config["DB_PATH"])
        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        if fila is None:
            return error("La tarea no existe", 404)
        if fila["completada"]:
            return error("La tarea ya está completada", 409)

        campos = {}
        if "titulo" in datos:
            campos["titulo"], err = validar_titulo(datos["titulo"])
            if err:
                return error(err, 400)
        if "descripcion" in datos:
            campos["descripcion"], err = validar_descripcion(datos["descripcion"])
            if err:
                return error(err, 400)
        if "prioridad" in datos:
            campos["prioridad"], err = validar_prioridad(datos["prioridad"])
            if err:
                return error(err, 400)
        if "fecha_limite" in datos:
            campos["fecha_limite"], err = validar_fecha_limite(datos["fecha_limite"])
            if err:
                return error(err, 400)

        if not campos:
            return error("No se enviaron campos editables", 400)

        sql = "UPDATE tareas SET " + ", ".join(c + " = ?" for c in campos) + " WHERE id = ?"
        db.execute(sql, list(campos.values()) + [tarea_id])
        db.commit()

        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        return jsonify(fila_a_dict(fila))

    @app.post("/api/tareas/<int:tarea_id>/completar")
    def completar_tarea(tarea_id):
        db = get_db(app.config["DB_PATH"])
        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        if fila is None:
            return error("La tarea no existe", 404)
        if fila["completada"]:
            return error("La tarea ya está completada", 409)

        db.execute("UPDATE tareas SET completada = 1 WHERE id = ?", (tarea_id,))
        db.commit()

        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        return jsonify(fila_a_dict(fila))

    @app.delete("/api/tareas/<int:tarea_id>")
    def eliminar_tarea(tarea_id):
        db = get_db(app.config["DB_PATH"])
        fila = db.execute("SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        if fila is None:
            return error("La tarea no existe", 404)

        db.execute("DELETE FROM tareas WHERE id = ?", (tarea_id,))
        db.commit()
        return "", 204

    @app.get("/")
    def index():
        return render_template("index.html")

    return app