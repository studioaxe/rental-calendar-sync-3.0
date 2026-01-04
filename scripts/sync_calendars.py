#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""
DESENVOLVIDO POR PBRANDÃO 2025
VERSÃO 2.0
"""

import os
import sys
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional, Set

try:
    from icalendar import Calendar, Event
    import requests
    from dotenv import load_dotenv
    import pytz
except ImportError as e:
    print(f"ERRO de importacao: {e}")
    print("Execute: pip install icalendar requests python-dotenv pytz")
    sys.exit(1)

# ==================== CONFIGURAÇÃO ====================

load_dotenv()

LOG_FILE = "sync.log"
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

BUFFER_DAYS_BEFORE = int(os.getenv('BUFFER_DAYS_BEFORE', 1))
BUFFER_DAYS_AFTER = int(os.getenv('BUFFER_DAYS_AFTER', 1))
IMPORT_FILE = "import_calendar.ics"
MANUAL_FILE = "manual_calendar.ics"
MASTER_FILE = "master_calendar.ics"
AIRBNB_URL = os.getenv('AIRBNB_ICAL_URL')
BOOKING_URL = os.getenv('BOOKING_ICAL_URL')
VRBO_URL = os.getenv('VRBO_ICAL_URL')
EMAIL_ON_ERROR = os.getenv('EMAIL_ON_ERROR', 'true').lower() == 'true'
ERROR_EMAIL = os.getenv('ERROR_EMAIL', 'studioaxe1014@gmail.com')

# ==================== HELPER FUNCTIONS ====================

def to_datetime(dt_obj) -> Optional[datetime]:
    """Converte date ou datetime para datetime"""
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        if dt_obj.tzinfo is None:
            return dt_obj.replace(tzinfo=pytz.UTC)
        return dt_obj
    elif isinstance(dt_obj, date):
        return datetime.combine(dt_obj, datetime.min.time()).replace(tzinfo=pytz.UTC)
    return None

def to_date(dt_obj) -> Optional[date]:
    """Extrai data de date ou datetime"""
    if dt_obj is None:
        return None
    if isinstance(dt_obj, datetime):
        return dt_obj.date()
    elif isinstance(dt_obj, date):
        return dt_obj
    return None

def normalize_uid(uid: str) -> str:
    """Normaliza UID para comparação (case-insensitive, trim)"""
    if not uid:
        return ""
    return str(uid).strip().lower()

# ==================== LOGGING & MONITORING ====================

def log_start():
    """Log de inicio de execucao"""
    logger.info("=" * 70)
    logger.info("SINCRONIZACAO DE CALENDARIOS - Desenvolvido por PBRANDÃO")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info(f"Configuracao: TP antes={BUFFER_DAYS_BEFORE}, TP depois={BUFFER_DAYS_AFTER}")
    logger.info("=" * 70)

def log_end(success: bool, error_msg: Optional[str] = None):
    """Log de fim de execucao"""
    logger.info("=" * 70)
    if success:
        logger.info("[OK] SINCRONIZACAO COMPLETA COM SUCESSO")
    else:
        logger.error(f"[ERRO] SINCRONIZACAO FALHOU: {error_msg}")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info("=" * 70)

def send_error_email(error_msg: str) -> bool:
    """Envia email com erro + log"""
    if not EMAIL_ON_ERROR:
        logger.debug("Email de erro desativado")
        return False
    try:
        logger.info(f"[EMAIL] Enviando email de erro para: {ERROR_EMAIL}")
        logger.info(f"Erro: {error_msg}")
        logger.info(f"Log: {LOG_FILE}")
        return True
    except Exception as e:
        logger.error(f"[ERRO] ao enviar email: {e}")
        return False

# ==================== VALIDAÇÃO ====================

def validate_urls() -> bool:
    """Valida se URLs estao configuradas"""
    missing = []
    if not AIRBNB_URL:
        missing.append("AIRBNB_ICAL_URL")
    if not BOOKING_URL:
        missing.append("BOOKING_ICAL_URL")
    if not VRBO_URL:
        missing.append("VRBO_ICAL_URL")
    if missing:
        msg = f"URLs nao configuradas: {', '.join(missing)}"
        logger.error(msg)
        return False
    logger.info("[OK] URLs configuradas")
    return True

def validate_calendar(cal: Calendar, source: str) -> bool:
    """Valida integridade do calendario"""
    try:
        if not cal:
            logger.error(f"[ERRO] Calendario {source} vazio")
            return False
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        logger.info(f"{source}: {len(events)} eventos importados")
        return True
    except Exception as e:
        logger.error(f"[ERRO] ao validar {source}: {e}")
        return False

# ==================== IMPORTAÇÃO ====================

def fetch_calendar(url: str, source: str) -> Optional[Calendar]:
    """Descarrega calendario de URL"""
    try:
        logger.info(f"[IMPORT] Importando {source}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        cal = Calendar.from_ical(response.content)
        if validate_calendar(cal, source):
            logger.info(f"[OK] {source} importado com sucesso")
            return cal
        else:
            return None
    except requests.RequestException as e:
        logger.error(f"[ERRO] ao descarregar {source}: {e}")
        return None
    except Exception as e:
        logger.error(f"[ERRO] ao processar {source}: {e}")
        return None

def fetch_all_calendars() -> Optional[Dict[str, Optional[Calendar]]]:
    """Descarrega todos os 3 calendarios"""
    logger.info("PASSO 1: Importacao de calendarios...")
    calendars = {
        'AIRBNB': fetch_calendar(AIRBNB_URL, 'AIRBNB'),
        'BOOKING': fetch_calendar(BOOKING_URL, 'BOOKING'),
        'VRBO': fetch_calendar(VRBO_URL, 'VRBO'),
    }
    if all(v is None for v in calendars.values()):
        logger.error("[ERRO] Nenhum calendario foi importado com sucesso")
        return None
    return calendars

# ==================== PROCESSAMENTO ====================

def extract_events(calendars: Dict[str, Calendar]) -> List[Dict]:
    """Extrai eventos de todos os calendarios"""
    logger.info("PASSO 2: Extracao de eventos...")
    all_events = []
    for source, cal in calendars.items():
        if cal is None:
            continue
        try:
            for component in cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get('DTSTART')
                    dtend = component.get('DTEND')
                    event = {
                        'source': source,
                        'uid': str(component.get('UID', '')),
                        'summary': str(component.get('SUMMARY', 'Sem titulo')),
                        'dtstart': dtstart.dt if dtstart else None,
                        'dtend': dtend.dt if dtend else None,
                        'description': str(component.get('DESCRIPTION', '')),
                        'location': str(component.get('LOCATION', '')),
                        'component': component,
                    }
                    all_events.append(event)
        except Exception as e:
            logger.error(f"[ERRO] ao extrair eventos de {source}: {e}")
            continue
    logger.info(f"Eventos extraidos: {len(all_events)}")
    return all_events

def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Deduplica eventos por data, titulo e origem"""
    logger.info("PASSO 3: Deduplicacao de eventos...")
    if not events:
        logger.warning("Nenhum evento para deduplicar")
        return []
    groups = {}
    for event in events:
        key = (
            to_date(event['dtstart']),
            to_date(event['dtend']),
            event['summary']
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(event)
    deduplicated = []
    for key, group in groups.items():
        best = max(group, key=lambda e: len(e.get('description', '')))
        deduplicated.append(best)
    removed = len(events) - len(deduplicated)
    logger.info(f"Duplicados removidos: {removed}")
    return deduplicated

def validate_integrity(events: List[Dict]) -> bool:
    """Valida integridade dos eventos"""
    logger.info("PASSO 4: Validacao de integridade...")
    if not events:
        logger.error("[ERRO] Nenhum evento para validar")
        return False
    errors = []
    no_dates = [e for e in events if not e.get('dtstart') or not e.get('dtend')]
    if no_dates:
        errors.append(f"Eventos sem data: {len(no_dates)}")
    invalid_range = []
    for e in events:
        if e.get('dtstart') and e.get('dtend'):
            start = to_datetime(e['dtstart'])
            end = to_datetime(e['dtend'])
            if start and end and start >= end:
                invalid_range.append(e)
    if invalid_range:
        errors.append(f"Eventos com dtstart >= dtend: {len(invalid_range)}")
    uids = [e.get('uid') for e in events]
    duplicates = len(uids) - len(set(uids))
    if duplicates:
        errors.append(f"UIDs duplicados: {duplicates}")
    if errors:
        for error in errors:
            logger.warning(error)
    logger.info(f"[OK] Validacao completa: {len(events)} eventos validos")
    return True

# ==================== MANUAL BLOCKS ====================

def load_manual_blocks() -> Optional[Calendar]:
    """Carrega ficheiro de bloqueios manuais"""
    try:
        if not Path(MANUAL_FILE).exists():
            logger.info(f"[INFO] {MANUAL_FILE} nao existe (nenhum bloqueio manual)")
            return None
        with open(MANUAL_FILE, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            logger.info(f"[OK] {MANUAL_FILE} carregado")
            return cal
    except Exception as e:
        logger.debug(f"[MANUAL BLOCKS] Erro ao carregar {MANUAL_FILE}: {e}")
        return None

def get_blocked_uids(manual_calendar: Optional[Calendar]) -> Set[str]:
    """
    Extrai UIDs de eventos com CLASS:PRIVATE (bloqueios manuais)
    Estes eventos serão removidos do master_calendar.ics
    Retorna: conjunto com UIDs bloqueados
    """
    blocked_uids = set()
    if not manual_calendar:
        return blocked_uids
    
    try:
        for component in manual_calendar.walk():
            if component.name == "VEVENT":
                event_class = component.get('CLASS')
                
                if event_class and str(event_class).lower() == 'private':
                    uid = normalize_uid(str(component.get('UID', '')))
                    if uid:
                        blocked_uids.add(uid)
                        summary = str(component.get('SUMMARY', 'evento'))
                        logger.info(f"[BLOQUEIO MANUAL] ⏸️  {summary} -> {uid}")
    except Exception as e:
        logger.debug(f"[MANUAL BLOCKS] Erro ao procurar bloqueios: {e}")
    
    if blocked_uids:
        logger.info(f"[BLOQUEIO MANUAL] Total: {len(blocked_uids)} eventos bloqueados")
    
    return blocked_uids

# ==================== EXPORTAÇÃO ====================

def create_import_calendar(events: List[Dict]) -> Calendar:
    """
    Cria calendario de importacao com:
    1. RESERVA (nativa, original)
    2. TP ANTES (bloqueio, público)
    3. TP DEPOIS (bloqueio, público)
    """
    logger.info("PASSO 5: Criacao do calendario de importacao...")
    
    import_cal = Calendar()
    import_cal.add('prodid', '-//Rental Import Calendar//PT')
    import_cal.add('version', '2.0')
    import_cal.add('calscale', 'GREGORIAN')
    import_cal.add('x-wr-calname', 'Rental Calendar Import')
    import_cal.add('x-wr-timezone', 'Europe/Lisbon')
    
    event_count = 0
    for event in events:
        try:
            dtstart = to_datetime(event['dtstart'])
            dtend = to_datetime(event['dtend'])
            if not dtstart or not dtend:
                continue
            
            source = event.get('source', 'UNKNOWN')
            uid_base = event.get('uid', '')
            summary = event.get('summary', 'Sem titulo')
            start_date = to_date(dtstart)
            end_date = to_date(dtend)
            
            # EVENTO 1: RESERVA NATIVA
            reserva_event = Event()
            reserva_event.add('uid', f"{uid_base}")
            reserva_event.add('summary', f"Reserva importada de {source}")
            reserva_event.add('dtstart', dtstart)
            reserva_event.add('dtend', dtend)
            reserva_event.add('description', 
                f"Data check-in: {start_date}\nData check-out: {end_date}")
            reserva_event.add('location', event.get('location', ''))
            reserva_event.add('created', datetime.now(pytz.UTC))
            reserva_event.add('last-modified', datetime.now(pytz.UTC))
            reserva_event.add('status', 'CONFIRMED')
            reserva_event.add('categories', 'RESERVATION-NATIVE')
            import_cal.add_component(reserva_event)
            event_count += 1
            logger.debug(f"[1/3] Reserva: {summary} [{start_date} - {end_date}]")
            
            # EVENTO 2: TP ANTES (bloqueio público)
            tp_before_uid = f"{uid_base}-tp-before"
            tp_before_start_date = start_date - timedelta(days=BUFFER_DAYS_BEFORE)
            tp_before_end_date = start_date
            
            tp_before_event = Event()
            tp_before_event.add('uid', tp_before_uid)
            tp_before_event.add('summary', f"TP Antes / {tp_before_start_date}")
            tp_before_event.add('dtstart', tp_before_start_date)
            tp_before_event.add('dtend', tp_before_end_date)
            tp_before_event.add('description', "Tempo de Preparação")
            tp_before_event.add('location', event.get('location', ''))
            tp_before_event.add('created', datetime.now(pytz.UTC))
            tp_before_event.add('last-modified', datetime.now(pytz.UTC))
            tp_before_event.add('status', 'CONFIRMED')
            tp_before_event.add('transp', 'TRANSPARENT')
            tp_before_event.add('categories', 'PREP-TIME-BEFORE')
            tp_before_event.add('class', 'PUBLIC')
            import_cal.add_component(tp_before_event)
            event_count += 1
            logger.debug(f"[2/3] TP Antes: [{tp_before_start_date} - {tp_before_end_date}]")
            
            # EVENTO 3: TP DEPOIS (bloqueio público)
            tp_after_uid = f"{uid_base}-tp-after"
            tp_after_start_date = end_date
            tp_after_end_date = end_date + timedelta(days=BUFFER_DAYS_AFTER)
            
            tp_after_event = Event()
            tp_after_event.add('uid', tp_after_uid)
            tp_after_event.add('summary', f"TP Depois / {tp_after_start_date}")
            tp_after_event.add('dtstart', tp_after_start_date)
            tp_after_event.add('dtend', tp_after_end_date)
            tp_after_event.add('description', "Tempo de Preparação")
            tp_after_event.add('location', event.get('location', ''))
            tp_after_event.add('created', datetime.now(pytz.UTC))
            tp_after_event.add('last-modified', datetime.now(pytz.UTC))
            tp_after_event.add('status', 'CONFIRMED')
            tp_after_event.add('transp', 'TRANSPARENT')
            tp_after_event.add('categories', 'PREP-TIME-AFTER')
            tp_after_event.add('class', 'PUBLIC')
            import_cal.add_component(tp_after_event)
            event_count += 1
            logger.debug(f"[3/3] TP Depois: [{tp_after_start_date} - {tp_after_end_date}]")
        
        except Exception as e:
            logger.error(f"[ERRO] ao adicionar evento: {e}")
            continue
    
    logger.info(f"[OK] Calendario de importacao criado: {event_count} eventos ({len(events)} reservas)")
    return import_cal

def create_master_calendar(import_calendar: Calendar, blocked_uids: Set[str]) -> Calendar:
    """
    Cria calendario master filtrando eventos bloqueados
    Remove UIDs presentes em manual_calendar.ics (CLASS:PRIVATE)
    """
    logger.info("PASSO 6: Criacao do calendario master (com bloqueios aplicados)...")
    
    master = Calendar()
    master.add('prodid', '-//Rental Master Calendar//PT')
    master.add('version', '2.0')
    master.add('calscale', 'GREGORIAN')
    master.add('x-wr-calname', 'Rental Calendar Master')
    master.add('x-wr-timezone', 'Europe/Lisbon')
    
    event_count = 0
    skipped_count = 0
    
    try:
        for component in import_calendar.walk():
            if component.name == "VEVENT":
                uid = normalize_uid(str(component.get('UID', '')))
                
                if uid in blocked_uids:
                    summary = str(component.get('SUMMARY', 'evento'))
                    logger.info(f"[BLOQUEIO] ⏸️  Removendo do master: {summary} ({uid})")
                    skipped_count += 1
                else:
                    master.add_component(component)
                    event_count += 1
    except Exception as e:
        logger.error(f"[ERRO] ao processar eventos: {e}")
    
    logger.info(f"[OK] Master criado: {event_count} eventos (removidos: {skipped_count})")
    return master

def export_to_file(calendar: Calendar, filename: str) -> bool:
    """Exporta calendario para ficheiro .ics"""
    try:
        logger.info(f"Exportando para {filename}...")
        with open(filename, 'wb') as f:
            f.write(calendar.to_ical())
        file_size = os.path.getsize(filename)
        logger.info(f"[OK] {filename} ({file_size} bytes)")
        return True
    except Exception as e:
        logger.error(f"[ERRO] ao exportar {filename}: {e}")
        return False

# ==================== MAIN ====================

def main() -> int:
    """Funcao principal"""
    log_start()
    try:
        if not validate_urls():
            msg = "URLs de calendarios nao configuradas"
            log_end(False, msg)
            send_error_email(msg)
            return 1
        
        calendars = fetch_all_calendars()
        if calendars is None:
            msg = "Erro ao importar calendarios"
            log_end(False, msg)
            send_error_email(msg)
            return 2
        
        events = extract_events(calendars)
        if not events:
            msg = "Nenhum evento importado"
            log_end(False, msg)
            send_error_email(msg)
            return 3
        
        logger.info("PROCESSAMENTO DE EVENTOS:")
        events = deduplicate_events(events)
        
        if not validate_integrity(events):
            msg = "Validacao de integridade falhou"
            log_end(False, msg)
            send_error_email(msg)
            return 3
        
        # PASSO 5: Criar calendario de importacao
        import_calendar = create_import_calendar(events)
        
        # PASSO 6: Carregar bloqueios manuais
        manual_calendar = load_manual_blocks()
        blocked_uids = get_blocked_uids(manual_calendar)
        
        # PASSO 7: Criar master com bloqueios aplicados
        master_calendar = create_master_calendar(import_calendar, blocked_uids)
        
        # PASSO 8: Exportar ficheiros
        if not export_to_file(import_calendar, IMPORT_FILE):
            msg = "Erro ao exportar import_calendar.ics"
            log_end(False, msg)
            send_error_email(msg)
            return 4
        
        if not export_to_file(master_calendar, MASTER_FILE):
            msg = "Erro ao exportar master_calendar.ics"
            log_end(False, msg)
            send_error_email(msg)
            return 4
        
        log_end(True)
        print(f"\n[OK] Sincronizacao completa!")
        print(f"Ficheiros gerados:")
        print(f"  - {IMPORT_FILE} (com TPs públicos)")
        print(f"  - {MASTER_FILE} (sem eventos bloqueados)")
        if Path(MANUAL_FILE).exists():
            print(f"  - {MANUAL_FILE} (controlo manual)")
        print(f"Log: {LOG_FILE}")
        return 0
    
    except Exception as e:
        msg = f"Erro nao esperado: {str(e)}"
        logger.error(msg)
        log_end(False, msg)
        send_error_email(msg)
        return 3

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)