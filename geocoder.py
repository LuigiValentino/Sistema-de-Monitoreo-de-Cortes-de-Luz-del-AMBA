from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from models import db, Corte, CoordenadaZona
import time
import hashlib

geolocator = Nominatim(user_agent="cortesluz_monitor_v1")
geocode_cache = {}


COORDENADAS_PREDEFINIDAS = {
    'CAPITAL FEDERAL': (-34.6037, -58.3816),
    'CAPITAL': (-34.6037, -58.3816),
    'LANUS': (-34.7085, -58.3736),
    'LOMAS DE ZAMORA': (-34.7641, -58.4074),
    'AVELLANEDA': (-34.6602, -58.2817),
    'QUILMES': (-34.7293, -58.2657),
    'BERAZATEGUI': (-34.7653, -58.2140),
    'BERAZATEGUI': (-34.7653, -58.2140),
    'ALMIRANTE BROWN': (-34.7646, -58.3820),
    'ESTEBAN ECHEVERRIA': (-34.8225, -58.4716),
    'EZEIZA': (-34.8547, -58.5092),
    'FLORENCIO VARELA': (-34.8237, -58.2799),
    'SAN VICENTE': (-35.0249, -58.4150),
    'VICENTE LOPEZ': (-34.5094, -58.4738),
    'SAN ISIDRO': (-34.4718, -58.5068),
    'SAN MARTIN': (-34.5748, -58.5383),
    'TRES DE FEBRERO': (-34.5986, -58.5646),
    'HURLINGHAM': (-34.5917, -58.6350),
    'ITUZAINGO': (-34.6606, -58.7053),
    'MORON': (-34.6534, -58.6198),
    'MERLO': (-34.6668, -58.7295),
    'MORENO': (-34.6387, -58.7903),
    'LONGCHAMPS': (-34.8518, -58.4458),
    'FLORES': (-34.6500, -58.4167),
    'FLORES RP': (-34.6517, -58.4167),
    'VILLA DEL PARQUE': (-34.5970, -58.4667),
    'GLEW': (-34.8469, -58.3828),
    'GONNET': (-34.8785, -58.1175),
    'PERGAMINO': (-33.8909, -60.5753),
    'ZARATE': (-34.0983, -59.0289),
    'JUNIN': (-34.5833, -60.9447),
    'SAN NICOLAS': (-33.3390, -60.2220),
    'SAN PEDRO': (-33.6790, -59.6660),
    'CAMPANA': (-34.1627, -58.9576),
    'PILAR': (-34.4589, -58.9142),
    'TIGRE': (-34.4257, -58.5797),
    'ESCOBAR': (-34.3500, -58.7833),
    'JOSE C PAZ': (-34.5167, -58.7667),
    'MALVINAS ARGENTINAS': (-34.5000, -58.7000),
    'SAN MIGUEL': (-34.5419, -58.7097),
    'BELEN DE ESCOBAR': (-34.3500, -58.7833),
    'NORDELTA': (-34.4117, -58.6300),
    'GENERAL PACHECO': (-34.4500, -58.5833),
    'DON TORCUATO': (-34.4833, -58.6167),
    'BECCAR': (-34.4583, -58.5333),
    'VICTORIA': (-34.4515, -58.5416),
    'MARTINEZ': (-34.4895, -58.5057),
    'OLIVOS': (-34.5067, -58.4900),
    'FLORIDA': (-34.5200, -58.5000),
    'BOULOGNE': (-34.5167, -58.5667),
    'VILLA ADELINA': (-34.5333, -58.5500),
    'ACASSUSO': (-34.4833, -58.5167),
    'SAN ANDRES': (-34.5500, -58.5333),
    'JOSE INGENIEROS': (-34.5833, -58.5167),
    'VILLA LYNCH': (-34.5667, -58.5667),
    'CASEROS': (-34.6000, -58.5667),
    'GERLI': (-34.6833, -58.3833),
    'WILDE': (-34.6833, -58.3000),
    'DOMINICO': (-34.6667, -58.2833),
    'REMEDIOS DE ESCALADA': (-34.7000, -58.3833),
    'LANUS ESTE': (-34.7167, -58.4000),
    'LANUS OESTE': (-34.7167, -58.3833),
    'MONTE CHINGOLO': (-34.7500, -58.4000),
    'VALENTIN ALSINA': (-34.6667, -58.4167),
    'BERNAL': (-34.7167, -58.3000),
    'QUILMES OESTE': (-34.7500, -58.2833),
    'SAN FRANCISCO SOLANO': (-34.7833, -58.2833),
    'SANTA MARIA': (-34.7833, -58.2500),
    'PLATANOS': (-34.7833, -58.2167),
    'PLATANOS': (-34.7833, -58.2167),
    'PARQUE CHACABUCO': (-34.6167, -58.4500),
    'PARQUE CHACABUCO': (-34.6167, -58.4500),
    'SAN NICOLAS': (-34.6167, -58.3667),
    'SAN NICOLAS': (-34.6167, -58.3667),
    'DELTA 1RA SECCION (ES)': (-34.3453, -58.7951),
    'DELTA 1RA SECCION (TI)': (-34.4235, -58.5818),
    'DELTA 2DA SECCION (SF)': (-34.4472, -58.5702),
    'DELTA 2DA SECCION (SF)': (-34.4472, -58.5702),
    'LIBERTAD': (-34.6709, -58.7272),
    'JOSE MARIA EZEIZA': (-34.8547, -58.5092),
    'GRAL LAS HERAS': (-34.9500, -58.3833),
    'GRAL. LAS HERAS': (-34.9500, -58.3833),
    'GRAL LAS HERAS': (-34.9500, -58.3833),
}


def get_coords(partido, localidad=None):
    partido_upper = partido.upper().strip()
    localidad_upper = localidad.upper().strip() if localidad else None
    
    cache_key = f"{partido_upper}|{localidad_upper or ''}"
    
    if cache_key in geocode_cache:
        return geocode_cache[cache_key]
    
    if partido_upper in COORDENADAS_PREDEFINIDAS:
        coords = COORDENADAS_PREDEFINIDAS[partido_upper]
        geocode_cache[cache_key] = coords
        return coords
    
    if localidad_upper and localidad_upper in COORDENADAS_PREDEFINIDAS:
        coords = COORDENADAS_PREDEFINIDAS[localidad_upper]
        geocode_cache[cache_key] = coords
        return coords
    
    try:
        search_term = f"{localidad}, {partido}, Buenos Aires, Argentina" if localidad else f"{partido}, Buenos Aires, Argentina"
        location = geolocator.geocode(search_term, timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            geocode_cache[cache_key] = coords
            return coords
    except Exception as e:
        print(f"Geocoder error: {e}")
    
    geocode_cache[cache_key] = None
    return None


def update_corte_coords(corte):
    if corte.lat and corte.lon:
        return True
    
    coords = get_coords(corte.partido, corte.localidad)
    if coords:
        corte.lat = coords[0]
        corte.lon = coords[1]
        db.session.commit()
        return True
    return False


def update_all_coords():
    cortes_sin_coords = Corte.query.filter(
        Corte.activo == True
    ).all()
    
    print(f"Buscando coordenadas para {len(cortes_sin_coords)} cortes...")
    
    actualizados = 0
    for i, corte in enumerate(cortes_sin_coords):
        if update_corte_coords(corte):
            actualizados += 1
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(cortes_sin_coords)}")
        time.sleep(0.5)
    
    print(f"Coordenadas actualizadas: {actualizados}")
    return actualizados


if __name__ == '__main__':
    from app import app
    with app.app_context():
        update_all_coords()
