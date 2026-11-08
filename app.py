"""Sistema web de gestión de tareas. Contrato: ver ESPECIFICACION.md, sección 3."""
import sqlite3
from datetime import datetime

from flask import Flask, g, jsonify, request
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

        titulo = datos.get("titulo")
        if not isinstance(titulo, str):
            return error("El título debe tener entre 3 y 100 caracteres", 400)
        titulo = titulo.strip()
        if len(titulo) < 3 or len(titulo) > 100:
            return error("El título debe tener entre 3 y 100 caracteres", 400)

        descripcion = datos.get("descripcion")
        if descripcion is None:
            descripcion = ""
        if not isinstance(descripcion, str):
            return error("La descripción debe ser texto", 400)
        descripcion = descripcion.strip()

        prioridad = datos.get("prioridad", "media")
        if prioridad not in ("alta", "media", "baja"):
            return error("La prioridad debe ser alta, media o baja", 400)

        fecha_limite = datos.get("fecha_limite")
        if fecha_limite is not None and not isinstance(fecha_limite, str):
            return error("La fecha límite no es válida", 400)

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

    return app