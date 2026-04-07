import requests
import re
import hashlib
from datetime import datetime
from models import db, Corte, Snapshot

URLS = {
    'EDESUR': 'https://www.enre.gov.ar/paginacorte/js/data_EDS.js',
    'EDENOR': 'https://www.enre.gov.ar/paginacorte/js/data_EDN.js'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

TIPO_CORTE_MAP = {
    'cortesPreventivos': 'preventiva',
    'cortesProgramados': 'programado',
    'cortesServicioMedia': 'media_tension',
    'cortesComunicados': 'comunicado',
    'cortesServicioBaja': 'baja_tension'
}


def fetch_data(empresa):
    url = URLS.get(empresa)
    if not url:
        return None
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        content = response.text
        
        json_match = re.search(r'var\s+data\s*=\s*(\{.*)', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            data = parse_js_object(json_str, empresa)
            if data:
                return data
    except Exception as e:
        print(f"Error fetching {empresa}: {e}")
    return None


def parse_js_object(content, empresa):
    data = {}
    
    empresa_match = re.search(r'empresa:\s*[\'"](\w+)[\'"]', content)
    if empresa_match:
        data['empresa'] = empresa_match.group(1)
    
    sin_match = re.search(r'totalUsuariosSinSuministro:\s*[\'"]?([\d.]+)[\'"]?', content)
    if sin_match:
        data['totalUsuariosSinSuministro'] = sin_match.group(1)
    
    con_match = re.search(r'totalUsuariosConSuministro:\s*[\'"]?([\d.]+)[\'"]?', content)
    if con_match:
        data['totalUsuariosConSuministro'] = con_match.group(1)
    
    data['cortesPreventivos'] = extract_cortes_array(content, 'cortesPreventivos')
    data['cortesProgramados'] = extract_cortes_array(content, 'cortesProgramados')
    data['cortesServicioMedia'] = extract_cortes_array(content, 'cortesServicioMedia')
    data['cortesComunicados'] = extract_cortes_array(content, 'cortesComunicados')
    data['cortesServicioBaja'] = extract_cortes_array(content, 'cortesServicioBaja')
    
    return {
        'empresa': empresa,
        'total_sin_suministro': parse_number(data.get('totalUsuariosSinSuministro', 0)),
        'total_con_suministro': parse_number(data.get('totalUsuariosConSuministro', 0)),
        'ultima_actualizacion': '',
        'cortes': extract_cortes(data, empresa)
    }


def extract_cortes_array(content, key):
    pattern = rf'{key}:\s*\[(.*?)\]'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []
    
    array_content = match.group(1)
    if not array_content.strip() or array_content.strip() == '':
        return []
    
    cortes = []
    obj_pattern = r'\{([^}]+)\}'
    objects = re.findall(obj_pattern, array_content)
    
    for obj in objects:
        corte = {}
        
        partido = re.search(r'partido:\s*[\'"]?([^\'",}]+)[\'"]?', obj)
        if partido:
            corte['partido'] = partido.group(1).strip()
        
        localidad = re.search(r'localidad:\s*[\'"]?([^\'",}]+)[\'"]?', obj)
        if localidad:
            corte['localidad'] = localidad.group(1).strip()
        
        subestacion = re.search(r'subestacion_alimentador:\s*[\'"]?([^\'",}]+)[\'"]?', obj)
        if subestacion:
            corte['subestacion_alimentador'] = subestacion.group(1).strip()
        
        usuarios = re.search(r'usuarios:\s*[\'"]?([^\'",}]+)[\'"]?', obj)
        if usuarios:
            corte['usuarios'] = usuarios.group(1).strip()
        
        normalizacion = re.search(r'normalizacion:\s*[\'"]?([^\'",}]+)[\'"]?', obj)
        if normalizacion:
            corte['normalizacion'] = normalizacion.group(1).strip()
        
        if corte:
            cortes.append(corte)
    
    return cortes


def parse_number(value):
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r'[^\d]', '', value)
        return int(cleaned) if cleaned else 0
    return 0


def extract_cortes(data, empresa):
    cortes = []
    
    for key, tipo in TIPO_CORTE_MAP.items():
        items = data.get(key, [])
        if not items:
            continue
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            corte = {
                'empresa': empresa,
                'partido': item.get('partido', '').strip().upper(),
                'localidad': item.get('localidad', '').strip().upper(),
                'subestacion': item.get('subestacion_alimentador', '').strip() if tipo != 'baja_tension' else None,
                'usuarios': parse_number(item.get('usuarios', 0)),
                'tipo_corte': tipo,
                'normalizacion': parse_datetime(item.get('normalizacion', ''))
            }
            cortes.append(corte)
    
    return cortes


def parse_datetime(date_str):
    if not date_str:
        return None
    
    formats = [
        '%Y-%m-%d %H:%M',
        '%d/%m/%Y %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%H:%M'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None


def generar_hash(corte):
    raw = f"{corte['empresa']}{corte['partido']}{corte['localidad']}{corte.get('subestacion', '')}{corte['tipo_corte']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def save_cortes(cortes_data, empresa):
    nuevos = 0
    actualizados = 0
    terminados = 0
    
    hashes_actuales = set()
    empresa_actual = None
    
    for corte_data in cortes_data:
        empresa_actual = corte_data['empresa']
        hash_unico = generar_hash(corte_data)
        hashes_actuales.add(hash_unico)
        
        existente = Corte.query.filter_by(hash_unico=hash_unico).first()
        
        if existente:
            if existente.usuarios_afectados != corte_data['usuarios']:
                existente.usuarios_afectados = corte_data['usuarios']
                existente.actualizado_en = datetime.utcnow()
                actualizados += 1
            
            if existente.fin_corte:
                existente.fin_corte = None
                existente.activo = True
                existente.actualizado_en = datetime.utcnow()
        else:
            nuevo_corte = Corte(
                empresa=corte_data['empresa'],
                partido=corte_data['partido'],
                localidad=corte_data['localidad'],
                subestacion=corte_data.get('subestacion'),
                usuarios_afectados=corte_data['usuarios'],
                tipo_corte=corte_data['tipo_corte'],
                normalizacion_estimada=corte_data.get('normalizacion'),
                hash_unico=hash_unico,
                activo=True
            )
            db.session.add(nuevo_corte)
            nuevos += 1
    
    cortes_activos = Corte.query.filter(
        Corte.activo == True,
        Corte.empresa == empresa,
        Corte.hash_unico.notin_(hashes_actuales)
    ).all()
    
    for corte in cortes_activos:
        corte.fin_corte = datetime.utcnow()
        corte.activo = False
        terminados += 1
    
    db.session.commit()
    
    return {'nuevos': nuevos, 'actualizados': actualizados, 'terminados': terminados}


def save_snapshot(empresa, total_sin, total_con, cortes_activos_count):
    snapshot = Snapshot(
        empresa=empresa,
        total_sin_suministro=total_sin,
        total_con_suministro=total_con,
        total_cortes_activos=cortes_activos_count
    )
    db.session.add(snapshot)
    db.session.commit()


def scrape_all():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando scrape...")
    resultados = []
    
    for empresa in ['EDESUR', 'EDENOR']:
        data = fetch_data(empresa)
        
        if data:
            stats = save_cortes(data['cortes'], empresa)
            cortes_activos = Corte.query.filter_by(empresa=empresa, activo=True).count()
            save_snapshot(
                empresa,
                data['total_sin_suministro'],
                data['total_con_suministro'],
                cortes_activos
            )
            
            resultados.append({
                'empresa': empresa,
                'total_sin': data['total_sin_suministro'],
                'total_con': data['total_con_suministro'],
                'cortes_activos': cortes_activos,
                'stats': stats
            })
            
            print(f"  {empresa}: {cortes_activos} cortes activos, "
                  f"+{stats['nuevos']} nuevos, ~{stats['actualizados']} actualizados, "
                  f"{stats['terminados']} terminados")
        else:
            print(f"  {empresa}: Error al obtener datos")
    
    # Actualizar coordenadas de cortes sin coords
    from geocoder import update_all_coords
    coords_actualizados = update_all_coords()
    print(f"  Coordenadas actualizadas: {coords_actualizados}")
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scrape completado")
    return resultados


if __name__ == '__main__':
    from app import app
    with app.app_context():
        scrape_all()
