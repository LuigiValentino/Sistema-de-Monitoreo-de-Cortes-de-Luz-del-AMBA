from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib

db = SQLAlchemy()


class Corte(db.Model):
    __tablename__ = 'cortes'

    id = db.Column(db.Integer, primary_key=True)
    empresa = db.Column(db.String(20), nullable=False)
    partido = db.Column(db.String(100), nullable=False)
    localidad = db.Column(db.String(100), nullable=False)
    subestacion = db.Column(db.String(200), nullable=True)
    usuarios_afectados = db.Column(db.Integer, default=0)
    tipo_corte = db.Column(db.String(50), nullable=False)
    normalizacion_estimada = db.Column(db.DateTime, nullable=True)
    inicio_corte = db.Column(db.DateTime, default=datetime.utcnow)
    fin_corte = db.Column(db.DateTime, nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    hash_unico = db.Column(db.String(64), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Corte {self.empresa} - {self.partido}/{self.localidad}>'

    def generar_hash(self):
        raw = f"{self.empresa}{self.partido}{self.localidad}{self.subestacion or ''}{self.tipo_corte}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self):
        return {
            'id': self.id,
            'empresa': self.empresa,
            'partido': self.partido,
            'localidad': self.localidad,
            'subestacion': self.subestacion,
            'usuarios_afectados': self.usuarios_afectados,
            'tipo_corte': self.tipo_corte,
            'normalizacion_estimada': self.normalizacion_estimada.isoformat() if self.normalizacion_estimada else None,
            'inicio_corte': self.inicio_corte.isoformat() if self.inicio_corte else None,
            'fin_corte': self.fin_corte.isoformat() if self.fin_corte else None,
            'lat': self.lat,
            'lon': self.lon,
            'activo': self.activo,
            'duracion_horas': self.get_duracion_horas()
        }

    def get_duracion_horas(self):
        if self.inicio_corte:
            end = self.fin_corte or datetime.utcnow()
            delta = end - self.inicio_corte
            return round(delta.total_seconds() / 3600, 1)
        return None


class Snapshot(db.Model):
    __tablename__ = 'snapshots'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    empresa = db.Column(db.String(20), nullable=False)
    total_sin_suministro = db.Column(db.Integer, default=0)
    total_con_suministro = db.Column(db.Integer, default=0)
    total_cortes_activos = db.Column(db.Integer, default=0)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Snapshot {self.empresa} - {self.timestamp}>'

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'empresa': self.empresa,
            'total_sin_suministro': self.total_sin_suministro,
            'total_con_suministro': self.total_con_suministro,
            'total_cortes_activos': self.total_cortes_activos
        }


class CoordenadaZona(db.Model):
    __tablename__ = 'coordenadas_zonas'

    id = db.Column(db.Integer, primary_key=True)
    partido = db.Column(db.String(100), nullable=False)
    localidad = db.Column(db.String(100), nullable=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    hash_key = db.Column(db.String(100), unique=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Coordenada {self.partido}/{self.localidad}>'

    def generar_hash_key(self):
        return hashlib.md5(f"{self.partido}|{self.localidad or ''}".encode()).hexdigest()
