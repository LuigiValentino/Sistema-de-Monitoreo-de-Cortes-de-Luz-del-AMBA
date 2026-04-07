import os
import requests
from flask import Flask, render_template, jsonify, request, Response
from datetime import datetime, timedelta
import json

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "data", "cortes.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, Corte, Snapshot

db.init_app(app)


def crear_tablas():
    with app.app_context():
        db.create_all()
        print("Tablas creadas/verificadas")


crear_tablas()


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/enre-data')
def get_enre_data():
    try:
        resp = requests.get('https://www.enre.gov.ar/mapaCortes/datos/Datos_PaginaWeb.js', timeout=10)
        resp.raise_for_status()
        
        text = resp.text
        
        import re
        points_match = re.search(r'addressPoints_Cuadro_D\s*=\s*\[(.*?)\];', text, re.DOTALL)
        
        if not points_match:
            return jsonify({'error': 'No se encontraron datos', 'puntos': []})
        
        points_text = points_match.group(1)
        
        coord_regex = re.compile(r'\[(-?\d+\.?\d*),\s*(-?\d+\.?\d*),\s*(\d+),\s*"([^"]*)"\]')
        
        puntos = []
        
        for match in coord_regex.finditer(points_text):
            lat = float(match.group(1))
            lon = float(match.group(2))
            users = int(match.group(3)) if match.group(3) else 0
            info = match.group(4) or ''
            
            if lat < -40 or lat > -30 or lon < -70 or lon > -50:
                continue
            
            is_edesur = 'EDESUR' in info.upper()
            is_edenor = 'EDENOR' in info.upper()
            
            if not is_edesur and not is_edenor:
                continue
            
            partido_match = re.search(r'Partido:\s*([^,]+)', info)
            partido = partido_match.group(1).strip() if partido_match else 'Desconocido'
            
            localidad_match = re.search(r'Localidad:\s*([^,]+)', info)
            localidad = localidad_match.group(1).strip() if localidad_match else ''
            
            tipo = 'Media Tensión' if 'MEDIA' in info.upper() else 'Baja Tensión'
            
            puntos.append({
                'lat': lat,
                'lon': lon,
                'users': users,
                'empresa': 'EDESUR' if is_edesur else 'EDENOR',
                'partido': partido,
                'localidad': localidad,
                'tipo': tipo
            })
        
        return jsonify({'puntos': puntos, 'total': len(puntos)})
        
    except Exception as e:
        return jsonify({'error': str(e), 'puntos': []})


@app.route('/api/scrape', methods=['POST'])
def trigger_scrape():
    from scheduler import run_scrape_now
    try:
        resultados = run_scrape_now(app)
        return jsonify({'success': True, 'resultados': resultados})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/estadisticas')
def get_estadisticas():
    now = datetime.utcnow()
    hoy = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    Cortes_activos = Corte.query.filter_by(activo=True).all()
    
    stats = {
        'total_cortes_activos': len(Cortes_activos),
        'total_usuarios_afectados': sum(c.usuarios_afectados for c in Cortes_activos),
        'cortes_por_empresa': {},
        'cortes_por_tipo': {},
        'cortes_por_partido': {},
        'promedio_duracion_horas': 0,
        'timestamp': now.isoformat()
    }
    
    for corte in Cortes_activos:
        stats['cortes_por_empresa'][corte.empresa] = stats['cortes_por_empresa'].get(corte.empresa, 0) + 1
        stats['cortes_por_tipo'][corte.tipo_corte] = stats['cortes_por_tipo'].get(corte.tipo_corte, 0) + 1
        stats['cortes_por_partido'][corte.partido] = stats['cortes_por_partido'].get(corte.partido, 0) + 1
    
    Cortes_activos_con_duracion = [c for c in Cortes_activos if c.get_duracion_horas()]
    if Cortes_activos_con_duracion:
        stats['promedio_duracion_horas'] = round(
            sum(c.get_duracion_horas() for c in Cortes_activos_con_duracion) / len(Cortes_activos_con_duracion), 1
        )
    
    stats['top_10_partidos'] = sorted(
        stats['cortes_por_partido'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:10]
    
    snapshots = Snapshot.query.filter(Snapshot.timestamp >= hoy).order_by(Snapshot.timestamp).all()
    stats['snapshots_hoy'] = [s.to_dict() for s in snapshots]
    
    return jsonify(stats)


@app.route('/api/cortes')
def get_cortes():
    empresa = request.args.get('empresa')
    tipo = request.args.get('tipo')
    partido = request.args.get('partido')
    activo = request.args.get('activo', 'true').lower() == 'true'
    limite = int(request.args.get('limite', 100))
    
    query = Corte.query
    
    if empresa:
        query = query.filter_by(empresa=empresa)
    if tipo:
        query = query.filter_by(tipo_corte=tipo)
    if partido:
        query = query.filter(Corte.partido.ilike(f'%{partido}%'))
    
    query = query.filter_by(activo=activo)
    
    cortes = query.order_by(Corte.actualizado_en.desc()).limit(limite).all()
    
    return jsonify({
        'cortes': [c.to_dict() for c in cortes],
        'total': len(cortes)
    })


@app.route('/api/mapa')
def get_mapa_data():
    Cortes_activos = Corte.query.filter(
        Corte.activo == True,
        Corte.lat.isnot(None),
        Corte.lon.isnot(None)
    ).all()
    
    features = []
    for corte in Cortes_activos:
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [corte.lon, corte.lat]
            },
            'properties': {
                'id': corte.id,
                'empresa': corte.empresa,
                'partido': corte.partido,
                'localidad': corte.localidad,
                'usuarios': corte.usuarios_afectados,
                'tipo': corte.tipo_corte,
                'normalizacion': corte.normalizacion_estimada.isoformat() if corte.normalizacion_estimada else None,
                'inicio': corte.inicio_corte.isoformat() if corte.inicio_corte else None,
                'duracion_horas': corte.get_duracion_horas()
            }
        })
    
    return jsonify({
        'type': 'FeatureCollection',
        'features': features
    })


@app.route('/api/evolucion')
def get_evolucion():
    dias = int(request.args.get('dias', 7))
    desde = datetime.utcnow() - timedelta(days=dias)
    
    snapshots = Snapshot.query.filter(
        Snapshot.timestamp >= desde
    ).order_by(Snapshot.timestamp).all()
    
    data = {}
    for s in snapshots:
        key = s.timestamp.strftime('%Y-%m-%d %H:%M')
        if key not in data:
            data[key] = {'eds': [], 'edn': []}
        if s.empresa == 'EDESUR':
            data[key]['eds'].append(s.to_dict())
        else:
            data[key]['edn'].append(s.to_dict())
    
    result = []
    for ts, empresas in sorted(data.items()):
        entry = {'timestamp': ts}
        for emp in ['eds', 'edn']:
            if empresas[emp]:
                e = empresas[emp][-1]
                entry[f'{emp}_sin'] = e['total_sin_suministro']
                entry[f'{emp}_cortes'] = e['total_cortes_activos']
        result.append(entry)
    
    return jsonify(result)


@app.route('/api/ranking_partidos')
def get_ranking():
    limite = int(request.args.get('limite', 20))
    dias = int(request.args.get('dias', 30))
    desde = datetime.utcnow() - timedelta(days=dias)
    
    from sqlalchemy import func
    
    rankings = db.session.query(
        Corte.partido,
        Corte.empresa,
        func.count(Corte.id).label('total_cortes'),
        func.sum(Corte.usuarios_afectados).label('total_usuarios')
    ).filter(
        Corte.inicio_corte >= desde
    ).group_by(
        Corte.partido, Corte.empresa
    ).order_by(
        func.count(Corte.id).desc()
    ).limit(limite).all()
    
    return jsonify([{
        'partido': r[0],
        'empresa': r[1],
        'total_cortes': r[2],
        'total_usuarios': r[3]
    } for r in rankings])


@app.route('/api/snapshots_recientes')
def get_snapshots():
    limite = int(request.args.get('limite', 100))
    snapshots = Snapshot.query.order_by(
        Snapshot.timestamp.desc()
    ).limit(limite).all()
    return jsonify([s.to_dict() for s in snapshots])


@app.route('/api/tipos_corte')
def get_tipos_corte():
    from sqlalchemy import func
    
    tipos = db.session.query(
        Corte.tipo_corte,
        func.count(Corte.id).label('cantidad'),
        func.sum(Corte.usuarios_afectados).label('usuarios')
    ).filter(
        Corte.activo == True
    ).group_by(
        Corte.tipo_corte
    ).all()
    
    return jsonify([{
        'tipo': t[0],
        'cantidad': t[1],
        'usuarios': t[2]
    } for t in tipos])


if __name__ == '__main__':
    from scheduler import init_scheduler
    
    init_scheduler(app)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
