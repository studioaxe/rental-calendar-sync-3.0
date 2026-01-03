#!/usr/bin/env python3
"""
Calendário Sync - Integração com sync_calendars.py v2.0
Sincroniza calendários importados com eventos manuais

Fluxo:
1. Lê import_calendar.ics (calendário externo)
2. Lê manual_calendar.ics (eventos manuais)
3. Processa manipulações (bloqueios, ocultações, etc)
4. Gera master_calendar.ics (resultado final)

Status: Production Ready
Versão: 1.0
Data: Janeiro 2026
"""

import os
from datetime import datetime, date
from pathlib import Path
from icalendar import Calendar, Event
from typing import List, Dict, Optional
import json


class CalendarSync:
    """Sincronizador de calendários com eventos manuais"""
    
    def __init__(self, data_dir: str = 'data'):
        """
        Inicializar sincronizador
        
        Args:
            data_dir: Diretório com ficheiros calendário
        """
        self.data_dir = Path(data_dir)
        self.import_file = self.data_dir / 'import_calendar.ics'
        self.manual_file = self.data_dir / 'manual_calendar.ics'
        self.manual_json_file = self.data_dir / 'manual_events.json'
        self.output_file = self.data_dir / 'master_calendar.ics'
        
        # Caches
        self._import_cal = None
        self._manual_events = None
    
    # ========================================================================
    # CARREGAMENTO DE CALENDÁRIOS
    # ========================================================================
    
    def load_import_calendar(self) -> Optional[Calendar]:
        """Carregar calendário de importação"""
        if not self.import_file.exists():
            print(f"Aviso: {self.import_file} não encontrado")
            return None
        
        try:
            with open(self.import_file, 'rb') as f:
                self._import_cal = Calendar.from_ical(f.read())
            print(f"✓ Calendário de importação carregado")
            return self._import_cal
        except Exception as e:
            print(f"✗ Erro ao carregar calendário: {e}")
            return None
    
    def load_manual_events(self) -> Dict:
        """Carregar eventos manuais (JSON ou ICS)"""
        events = {}
        
        # Tentar carregar JSON primeiro
        if self.manual_json_file.exists():
            try:
                with open(self.manual_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for event in data.get('events', []):
                        events[event['id']] = event
                print(f"✓ Eventos manuais carregados ({len(events)} eventos)")
                return events
            except Exception as e:
                print(f"Aviso: Erro ao carregar JSON: {e}")
        
        # Tentar carregar ICS se JSON não existir
        if self.manual_file.exists():
            try:
                with open(self.manual_file, 'rb') as f:
                    cal = Calendar.from_ical(f.read())
                    
                    for component in cal.walk():
                        if component.name == "VEVENT":
                            event_id = str(component.get('uid', 'unknown'))
                            events[event_id] = {
                                'id': event_id,
                                'type': str(component.get('x-event-type', 'BLOCK_DATE')),
                                'summary': str(component.get('summary', '')),
                                'dtstart': component.get('dtstart'),
                                'dtend': component.get('dtend'),
                                'class': str(component.get('class', 'PUBLIC'))
                            }
                    
                    print(f"✓ Eventos manuais carregados ({len(events)} eventos)")
                    return events
            except Exception as e:
                print(f"Aviso: Erro ao carregar ICS: {e}")
        
        print("Aviso: Nenhum arquivo de eventos manuais encontrado")
        return {}
    
    # ========================================================================
    # PROCESSAMENTO
    # ========================================================================
    
    def _should_hide_event(self, event: Event) -> bool:
        """
        Verificar se evento deve ser ocultado
        Critérios:
        - CLASS:PRIVATE
        - Evento em HIDE_EVENT manual
        """
        # Verificar CLASS:PRIVATE
        if event.get('class', '').upper() == 'PRIVATE':
            return True
        
        # Verificar eventos manuais de ocultação
        for manual in self._manual_events.values():
            if manual.get('type') == 'HIDE_EVENT':
                # Comparar por resumo ou data
                if event.get('summary') == manual.get('summary'):
                    return True
        
        return False
    
    def _is_blocked_date(self, event_date: date) -> bool:
        """Verificar se data está bloqueada"""
        for manual in self._manual_events.values():
            event_type = manual.get('type')
            
            if event_type == 'BLOCK_DATE':
                # Data específica bloqueada
                block_date = self._parse_date(manual.get('dtstart', manual.get('date_start')))
                if block_date == event_date:
                    return True
            
            elif event_type == 'REMOVE_DATE':
                # Período removido
                start = self._parse_date(manual.get('dtstart', manual.get('date_start')))
                end = self._parse_date(manual.get('dtend', manual.get('date_end')))
                if start and end and start <= event_date <= end:
                    return True
        
        return False
    
    @staticmethod
    def _parse_date(date_obj) -> Optional[date]:
        """Converter datetime/date para date object"""
        if not date_obj:
            return None
        
        if isinstance(date_obj, date):
            return date_obj
        
        try:
            if hasattr(date_obj, 'dt'):
                return date_obj.dt.date() if hasattr(date_obj.dt, 'date') else date_obj.dt
            return date_obj
        except:
            return None
    
    # ========================================================================
    # SINCRONIZAÇÃO
    # ========================================================================
    
    def sync(self) -> bool:
        """
        Executar sincronização completa
        
        Returns:
            True se sucesso, False se erro
        """
        print("\n" + "="*60)
        print("SINCRONIZANDO CALENDÁRIOS")
        print("="*60)
        
        # 1. Carregar calendários
        import_cal = self.load_import_calendar()
        if not import_cal:
            return False
        
        # 2. Carregar eventos manuais
        self._manual_events = self.load_manual_events()
        
        # 3. Processar
        print("\nProcessando eventos...")
        output_cal = Calendar()
        output_cal.add('prodid', '-//Calendário Sync//Master Calendar//PT')
        output_cal.add('version', '2.0')
        output_cal.add('method', 'PUBLISH')
        output_cal.add('x-wr-calname', 'Master Calendar')
        output_cal.add('x-wr-timezone', 'Europe/Lisbon')
        
        processed = 0
        hidden = 0
        blocked = 0
        
        for component in import_cal.walk():
            if component.name != "VEVENT":
                continue
            
            # Fazer cópia do evento
            event_copy = component.copy()
            processed += 1
            
            # Verificar se deve ser ocultado
            if self._should_hide_event(event_copy):
                event_copy['class'] = 'PRIVATE'
                hidden += 1
            
            # Verificar se data está bloqueada
            event_date = self._parse_date(event_copy.get('dtstart'))
            if event_date and self._is_blocked_date(event_date):
                blocked += 1
                continue  # Pular evento
            
            # Processar FORCE_AVAILABILITY
            for manual in self._manual_events.values():
                if manual.get('type') == 'FORCE_AVAILABILITY':
                    manual_date = self._parse_date(manual.get('dtstart', manual.get('date_start')))
                    if manual_date == event_date:
                        event_copy['transp'] = 'TRANSPARENT'
            
            output_cal.add_component(event_copy)
        
        # 4. Guardar output
        try:
            with open(self.output_file, 'wb') as f:
                f.write(output_cal.to_ical())
            
            print(f"\n{'='*60}")
            print(f"RESULTADO:")
            print(f"  • Eventos processados: {processed}")
            print(f"  • Eventos ocultados:   {hidden}")
            print(f"  • Eventos bloqueados:  {blocked}")
            print(f"  • Eventos finais:      {processed - blocked}")
            print(f"  • Output: {self.output_file}")
            print(f"{'='*60}\n")
            
            return True
        
        except Exception as e:
            print(f"✗ Erro ao guardar output: {e}")
            return False


# ============================================================================
# FUNÇÃO DE CONVENIÊNCIA
# ============================================================================

def sync_with_manual_events(
    import_cal_path: str = 'data/import_calendar.ics',
    manual_cal_path: str = 'data',
    output_path: str = 'data/master_calendar.ics'
) -> bool:
    """
    Sincronizar calendários com eventos manuais
    
    Args:
        import_cal_path: Caminho calendário importação
        manual_cal_path: Diretório eventos manuais
        output_path: Caminho output master calendar
        
    Returns:
        True se sucesso
    """
    syncer = CalendarSync(data_dir=manual_cal_path)
    return syncer.sync()


# ============================================================================
# INTEGRAÇÃO COM sync_calendars.py v2.0
# ============================================================================

def integrate_with_sync_calendars(
    sync_calendars_script_path: str,
    data_dir: str = 'data'
) -> bool:
    """
    Integrar com script sync_calendars.py v2.0 existente
    
    Fluxo:
    1. sync_calendars.py gera import_calendar.ics
    2. Esta função processa com eventos manuais
    3. Resultado: master_calendar.ics
    
    Args:
        sync_calendars_script_path: Caminho do sync_calendars.py
        data_dir: Diretório de dados
        
    Returns:
        True se integração bem-sucedida
    """
    print(f"Integrando com {sync_calendars_script_path}...")
    
    # Executar sync_calendars.py primeiro
    import subprocess
    try:
        result = subprocess.run(
            ['python3', sync_calendars_script_path],
            cwd=data_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"Erro ao executar sync_calendars.py:\n{result.stderr}")
            return False
        
        print("✓ sync_calendars.py executado com sucesso")
    
    except Exception as e:
        print(f"Erro ao executar sync_calendars.py: {e}")
        return False
    
    # Agora processar com eventos manuais
    syncer = CalendarSync(data_dir=data_dir)
    return syncer.sync()


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == '__main__':
    # Usar com data_dir padrão
    syncer = CalendarSync()
    success = syncer.sync()
    
    if success:
        print("✓ Sincronização completada com sucesso!")
    else:
        print("✗ Erro durante sincronização")