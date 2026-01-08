"""
Manual Calendar Editor - Synchronization Script - Fase 3
Synchronizes calendar events from multiple sources and applies manual adjustments
NEW: Support for CATEGORIES:MANUAL-BLOCK and CATEGORIES:MANUAL-REMOVE
Version: 3.0
Date: January 8, 2026
"""

import os
import logging
from datetime import datetime, timedelta
from icalendar import Calendar, Event
import requests
from dotenv import load_dotenv
import pytz
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

# Configuration
REPO_PATH = os.getenv('REPO_PATH', '.')
AIRBNB_ICAL_URL = os.getenv('AIRBNB_ICAL_URL', '')
BOOKING_ICAL_URL = os.getenv('BOOKING_ICAL_URL', '')
VRBO_ICAL_URL = os.getenv('VRBO_ICAL_URL', '')
AIRBNB_PREP_HOURS = int(os.getenv('AIRBNB_PREP_HOURS', 24))
BOOKING_PREP_HOURS = int(os.getenv('BOOKING_PREP_HOURS', 24))
VRBO_PREP_HOURS = int(os.getenv('VRBO_PREP_HOURS', 24))

# File paths
IMPORT_CALENDAR_PATH = os.path.join(REPO_PATH, 'import_calendar.ics')
MASTER_CALENDAR_PATH = os.path.join(REPO_PATH, 'master_calendar.ics')
MANUAL_CALENDAR_PATH = os.path.join(REPO_PATH, 'manual_calendar.ics')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(REPO_PATH, 'sync.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_info(msg):
    """Log info message"""
    logger.info(msg)
    print(f"[INFO] {msg}")

def log_warning(msg):
    """Log warning message"""
    logger.warning(msg)
    print(f"[WARNING] {msg}")

def log_error(msg):
    """Log error message"""
    logger.error(msg)
    print(f"[ERROR] {msg}")

def log_success(msg):
    """Log success message"""
    logger.info(msg)
    print(f"[SUCCESS] ✅ {msg}")

def download_calendar(url, source_name):
    """Download calendar from URL"""
    try:
        if not url:
            log_warning(f"No URL configured for {source_name}")
            return None
        
        log_info(f"Downloading {source_name} calendar...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        cal = Calendar.from_ical(response.content)
        events = []
        
        for component in cal.walk():
            if component.name == "VEVENT":
                events.append(component)
        
        log_success(f"Downloaded {len(events)} events from {source_name}")
        return events
    except Exception as e:
        log_error(f"Error downloading {source_name}: {str(e)}")
        return []

def apply_prep_time(event, prep_hours):
    """Apply preparation time before event"""
    try:
        dtstart = event.decoded('dtstart')
        if isinstance(dtstart, datetime):
            # Subtract prep time
            new_start = dtstart - timedelta(hours=prep_hours)
            event['dtstart'].dt = new_start
        return event
    except Exception as e:
        log_warning(f"Could not apply prep time: {str(e)}")
        return event

def load_manual_events():
    """Load manual events from manual_calendar.ics"""
    try:
        if not os.path.isfile(MANUAL_CALENDAR_PATH):
            log_info("No manual calendar found")
            return {
                'manual_blocks': [],
                'manual_removes': []
            }
        
        with open(MANUAL_CALENDAR_PATH, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            manual_blocks = []
            manual_removes = []
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    categories = str(component.get('categories', ''))
                    
                    if categories == 'MANUAL-BLOCK':
                        manual_blocks.append(component)
                    elif categories == 'MANUAL-REMOVE':
                        manual_removes.append(component)
            
            log_success(f"Loaded {len(manual_blocks)} MANUAL-BLOCK and {len(manual_removes)} MANUAL-REMOVE events")
            
            return {
                'manual_blocks': manual_blocks,
                'manual_removes': manual_removes
            }
    except Exception as e:
        log_error(f"Error loading manual events: {str(e)}")
        return {
            'manual_blocks': [],
            'manual_removes': []
        }

def should_remove_event(event, manual_removes):
    """Check if event should be removed based on MANUAL-REMOVE entries"""
    try:
        event_start = event.decoded('dtstart')
        event_end = event.decoded('dtend')
        
        # Convert to date if datetime
        if isinstance(event_start, datetime):
            event_start = event_start.date() if hasattr(event_start, 'date') else event_start
        if isinstance(event_end, datetime):
            event_end = event_end.date() if hasattr(event_end, 'date') else event_end
        
        for remove_event in manual_removes:
            remove_start = remove_event.decoded('dtstart')
            remove_end = remove_event.decoded('dtend')
            
            # Convert to date if datetime
            if isinstance(remove_start, datetime):
                remove_start = remove_start.date() if hasattr(remove_start, 'date') else remove_start
            if isinstance(remove_end, datetime):
                remove_end = remove_end.date() if hasattr(remove_end, 'date') else remove_end
            
            # Check if event falls within removal period
            if remove_start <= event_start < remove_end or remove_start < event_end <= remove_end:
                return True
        
        return False
    except Exception as e:
        log_warning(f"Error checking removal: {str(e)}")
        return False

def event_overlaps_block(event, manual_blocks):
    """Check if event overlaps with MANUAL-BLOCK"""
    try:
        event_start = event.decoded('dtstart')
        event_end = event.decoded('dtend')
        
        # Convert to date if datetime
        if isinstance(event_start, datetime):
            event_start = event_start.date() if hasattr(event_start, 'date') else event_start
        if isinstance(event_end, datetime):
            event_end = event_end.date() if hasattr(event_end, 'date') else event_end
        
        for block_event in manual_blocks:
            block_start = block_event.decoded('dtstart')
            block_end = block_event.decoded('dtend')
            
            # Convert to date if datetime
            if isinstance(block_start, datetime):
                block_start = block_start.date() if hasattr(block_start, 'date') else block_start
            if isinstance(block_end, datetime):
                block_end = block_end.date() if hasattr(block_end, 'date') else block_end
            
            # Check for overlap
            if not (event_end <= block_start or event_start >= block_end):
                return True
        
        return False
    except Exception as e:
        log_warning(f"Error checking block overlap: {str(e)}")
        return False

def deduplicate_events(events):
    """Remove duplicate events"""
    unique_events = {}
    duplicates = 0
    
    for event in events:
        try:
            uid = str(event.get('uid', ''))
            if uid not in unique_events:
                unique_events[uid] = event
            else:
                duplicates += 1
        except:
            unique_events[str(len(unique_events))] = event
    
    if duplicates > 0:
        log_warning(f"Removed {duplicates} duplicate events")
    
    return list(unique_events.values())

def create_master_calendar(all_events):
    """Create master calendar from all events"""
    try:
        cal = Calendar()
        cal.add('prodid', '-//Rental Master Calendar//PT')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('x-wr-calname', 'Master Calendar (Reservations)')
        cal.add('x-wr-timezone', 'Europe/Lisbon')
        
        for event in all_events:
            cal.add_component(event)
        
        return cal
    except Exception as e:
        log_error(f"Error creating master calendar: {str(e)}")
        return None

# ============================================================================
# MAIN SYNCHRONIZATION FUNCTION
# ============================================================================

def synchronize():
    """Main synchronization function"""
    try:
        log_info("=" * 70)
        log_info("STARTING CALENDAR SYNCHRONIZATION - FASE 3")
        log_info(f"Timestamp: {datetime.now().isoformat()}")
        log_info("=" * 70)
        
        # Step 1: Download calendars from sources
        log_info("\n[STEP 1] Downloading calendars from sources...")
        
        airbnb_events = download_calendar(AIRBNB_ICAL_URL, "Airbnb") or []
        booking_events = download_calendar(BOOKING_ICAL_URL, "Booking") or []
        vrbo_events = download_calendar(VRBO_ICAL_URL, "Vrbo") or []
        
        # Apply prep times
        log_info("Applying preparation times...")
        airbnb_events = [apply_prep_time(e, AIRBNB_PREP_HOURS) for e in airbnb_events]
        booking_events = [apply_prep_time(e, BOOKING_PREP_HOURS) for e in booking_events]
        vrbo_events = [apply_prep_time(e, VRBO_PREP_HOURS) for e in vrbo_events]
        
        # Combine all events
        all_imported_events = airbnb_events + booking_events + vrbo_events
        log_success(f"Downloaded {len(all_imported_events)} events total")
        
        # Step 2: Deduplicate
        log_info("\n[STEP 2] Deduplicating events...")
        all_imported_events = deduplicate_events(all_imported_events)
        log_success(f"After deduplication: {len(all_imported_events)} unique events")
        
        # Step 3: Load manual events
        log_info("\n[STEP 3] Loading manual events...")
        manual_data = load_manual_events()
        manual_blocks = manual_data['manual_blocks']
        manual_removes = manual_data['manual_removes']
        
        # Step 4: Apply manual adjustments
        log_info("\n[STEP 4] Applying manual adjustments...")
        
        # Filter out removed events
        filtered_events = []
        removed_count = 0
        
        for event in all_imported_events:
            if should_remove_event(event, manual_removes):
                removed_count += 1
                log_info(f"  Removing: {event.get('summary', 'Unknown')}")
            else:
                filtered_events.append(event)
        
        if removed_count > 0:
            log_success(f"Removed {removed_count} events based on MANUAL-REMOVE")
        
        # Add manual blocks
        all_final_events = filtered_events + manual_blocks
        
        if len(manual_blocks) > 0:
            log_success(f"Added {len(manual_blocks)} MANUAL-BLOCK events")
        
        # Step 5: Create master calendar
        log_info("\n[STEP 5] Creating master calendar...")
        master_cal = create_master_calendar(all_final_events)
        
        if not master_cal:
            log_error("Failed to create master calendar")
            return False
        
        # Step 6: Save master calendar
        log_info("\n[STEP 6] Saving master calendar...")
        try:
            with open(MASTER_CALENDAR_PATH, 'wb') as f:
                f.write(master_cal.to_ical())
            log_success(f"Saved {len(all_final_events)} events to {MASTER_CALENDAR_PATH}")
        except Exception as e:
            log_error(f"Error saving master calendar: {str(e)}")
            return False
        
        # Summary
        log_info("\n" + "=" * 70)
        log_info("SYNCHRONIZATION SUMMARY")
        log_info("=" * 70)
        log_info(f"Imported events: {len(all_imported_events)}")
        log_info(f"  ├─ Airbnb: {len(airbnb_events)}")
        log_info(f"  ├─ Booking: {len(booking_events)}")
        log_info(f"  └─ Vrbo: {len(vrbo_events)}")
        log_info(f"Manual adjustments:")
        log_info(f"  ├─ Removed: {removed_count}")
        log_info(f"  └─ Blocked: {len(manual_blocks)}")
        log_info(f"Final events: {len(all_final_events)}")
        log_success("Synchronization completed successfully!")
        log_info("=" * 70)
        
        return True
        
    except Exception as e:
        log_error(f"Fatal error during synchronization: {str(e)}")
        return False

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        # Create repo directory if it doesn't exist
        Path(REPO_PATH).mkdir(parents=True, exist_ok=True)
        
        # Run synchronization
        success = synchronize()
        
        # Exit with appropriate code
        exit(0 if success else 1)
        
    except KeyboardInterrupt:
        log_warning("Synchronization cancelled by user")
        exit(1)
    except Exception as e:
        log_error(f"Unexpected error: {str(e)}")
        exit(1)
