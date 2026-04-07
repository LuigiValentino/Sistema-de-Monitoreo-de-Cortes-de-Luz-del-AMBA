from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
from datetime import datetime

scheduler = BackgroundScheduler(timezone='America/Argentina/Buenos_Aires')


def init_scheduler(app):
    from scraper import scrape_all
    from geocoder import update_all_coords
    
    def job_contexto():
        with app.app_context():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ejecutando scrape programado...")
            scrape_all()
    
    scheduler.add_job(
        func=job_contexto,
        trigger=IntervalTrigger(minutes=5),
        id='scrape_cortes',
        name='Scrapeo de cortes cada 5 minutos',
        replace_existing=True
    )
    
    def job_geocoding():
        with app.app_context():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ejecutando geocoding...")
            update_all_coords()
    
    scheduler.add_job(
        func=job_geocoding,
        trigger=IntervalTrigger(hours=1),
        id='geocode_zonas',
        name='Geocodificación cada hora',
        replace_existing=True
    )
    
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    
    print("Scheduler iniciado - Scrape cada 5 minutos")


def run_scrape_now(app):
    from scraper import scrape_all
    with app.app_context():
        return scrape_all()
