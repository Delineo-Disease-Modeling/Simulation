"""
Monthly Patterns Utility Module

Manages monthly SafeGraph patterns files for multi-month simulations.
Files should be named in the format: YYYY-MM-{STATE}.csv (e.g., 2019-01-OK.csv)
"""

import os
import re
import glob
from typing import List, Dict, Optional, Tuple
from datetime import datetime


def discover_monthly_files(folder_path: str, state: Optional[str] = None) -> Dict[str, str]:
    """
    Discover all monthly pattern files in a folder.
    
    Supports multiple naming conventions:
        - YYYY-MM-STATE.csv (e.g., 2019-01-OK.csv)
        - YYYY-MM.csv (e.g., 2019-01.csv) - for state-specific folders
    
    Args:
        folder_path: Path to the folder containing monthly CSV files
        state: Optional state code to filter by (e.g., 'OK', 'MD')
    
    Returns:
        Dict mapping month keys (YYYY-MM) to file paths, sorted chronologically
        e.g., {'2019-01': '/path/2019-01-OK.csv', '2019-02': '/path/2019-02-OK.csv'}
    """
    print(f"[MONTHLY_PATTERNS] Discovering files in: {folder_path} (state filter: {state})")
    if not os.path.isdir(folder_path):
        raise ValueError(f"Folder not found: {folder_path}")
    
    # Patterns to match:
    # 1. YYYY-MM-STATE.csv (e.g., 2019-01-OK.csv)
    # 2. YYYY-MM.csv (e.g., 2019-01.csv)
    pattern_with_state = re.compile(r'^(\d{4}-\d{2})-([A-Z]{2})\.csv$', re.IGNORECASE)
    pattern_simple = re.compile(r'^(\d{4}-\d{2})\.csv$', re.IGNORECASE)
    
    monthly_files = {}
    for filename in os.listdir(folder_path):
        month_key = None
        file_state = None
        
        # Try pattern with state first
        match = pattern_with_state.match(filename)
        if match:
            month_key = match.group(1)  # e.g., "2019-01"
            file_state = match.group(2)  # e.g., "OK"
        else:
            # Try simple pattern
            match = pattern_simple.match(filename)
            if match:
                month_key = match.group(1)
                file_state = None
        
        if month_key:
            # Filter by state if specified
            if state and file_state and file_state.upper() != state.upper():
                print(f"[MONTHLY_PATTERNS]   Skipping {filename} (state mismatch: {file_state} != {state})")
                continue
            
            full_path = os.path.join(folder_path, filename)
            monthly_files[month_key] = full_path
            print(f"[MONTHLY_PATTERNS]   Found: {month_key} -> {full_path}")
    
    print(f"[MONTHLY_PATTERNS] Total files discovered: {len(monthly_files)}")
    # Sort by month chronologically
    return dict(sorted(monthly_files.items()))


def get_months_in_range(start_date: datetime, end_date: datetime) -> List[str]:
    """
    Get list of month keys (YYYY-MM) between two dates.
    
    Args:
        start_date: Start of simulation
        end_date: End of simulation
    
    Returns:
        List of month keys, e.g., ['2019-01', '2019-02', '2019-03']
    """
    months = []
    current = datetime(start_date.year, start_date.month, 1)
    end = datetime(end_date.year, end_date.month, 1)
    
    while current <= end:
        months.append(current.strftime('%Y-%m'))
        # Move to next month
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    
    return months


def get_file_for_month(folder_path: str, month: str, state: Optional[str] = None) -> Optional[str]:
    """
    Get the patterns file for a specific month.
    
    Args:
        folder_path: Path to the folder containing monthly CSV files
        month: Month key in YYYY-MM format (e.g., '2019-01')
        state: Optional state code to filter by
    
    Returns:
        Path to the file, or None if not found
    """
    monthly_files = discover_monthly_files(folder_path, state)
    return monthly_files.get(month)


def validate_monthly_coverage(folder_path: str, start_date: datetime, end_date: datetime, 
                              state: Optional[str] = None) -> Tuple[bool, List[str]]:
    """
    Check if all months in a date range have pattern files available.
    
    Args:
        folder_path: Path to the folder containing monthly CSV files
        start_date: Start of simulation
        end_date: End of simulation
        state: Optional state code to filter by
    
    Returns:
        Tuple of (all_covered: bool, missing_months: List[str])
    """
    required_months = get_months_in_range(start_date, end_date)
    available_files = discover_monthly_files(folder_path, state)
    
    missing = [m for m in required_months if m not in available_files]
    return len(missing) == 0, missing


def get_month_boundaries(year: int, month: int) -> Tuple[datetime, datetime]:
    """
    Get the start and end datetime for a given month.
    
    Returns:
        Tuple of (first_day_midnight, last_day_23:59:59)
    """
    from calendar import monthrange
    
    start = datetime(year, month, 1, 0, 0, 0)
    _, last_day = monthrange(year, month)
    end = datetime(year, month, last_day, 23, 59, 59)
    
    return start, end


def parse_month_key(month_key: str) -> Tuple[int, int]:
    """
    Parse a month key (YYYY-MM) into year and month integers.
    
    Args:
        month_key: String like '2019-01'
    
    Returns:
        Tuple of (year, month) as integers
    """
    parts = month_key.split('-')
    return int(parts[0]), int(parts[1])


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string (YYYY-MM-DD) into a datetime.
    
    Args:
        date_str: String like '2019-01-15'
    
    Returns:
        datetime object
    """
    return datetime.strptime(date_str, '%Y-%m-%d')


def get_simulation_minutes_for_month(month_key: str, start_date: datetime, end_date: datetime) -> int:
    """
    Calculate how many minutes to simulate for a specific month, given the overall date range.
    
    This handles partial months at the start and end of the simulation.
    
    Args:
        month_key: Month key in YYYY-MM format (e.g., '2019-01')
        start_date: Overall simulation start date
        end_date: Overall simulation end date
    
    Returns:
        Number of minutes to simulate for this month
    
    Example:
        If simulating Jan 15 to Feb 20:
        - January: Jan 15 00:00 to Jan 31 23:59 = 17 days
        - February: Feb 1 00:00 to Feb 20 23:59 = 20 days
    """
    year, month = parse_month_key(month_key)
    month_start, month_end = get_month_boundaries(year, month)
    
    # Determine actual start within this month
    actual_start = max(month_start, datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0))
    
    # Determine actual end within this month
    actual_end = min(month_end, datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59))
    
    # Calculate minutes
    if actual_end < actual_start:
        return 0
    
    delta = actual_end - actual_start
    minutes = int(delta.total_seconds() / 60) + 1
    return minutes


def date_to_month_key(date: datetime) -> str:
    """
    Convert a datetime to a month key (YYYY-MM).
    
    Args:
        date: datetime object
    
    Returns:
        Month key string like '2019-01'
    """
    return date.strftime('%Y-%m')

class MonthlyPatternsManager:
    """
    Manager class for multi-month simulations.
    
    Usage:
        manager = MonthlyPatternsManager('./data', state='OK')
        for month, file_path in manager.iter_months('2019-01', '2019-03'):
            # Process each month
            pass
    """
    
    def __init__(self, folder_path: str, state: Optional[str] = None):
        """
        Initialize the manager.
        
        Args:
            folder_path: Path to folder containing monthly pattern files
            state: Optional state code to filter by
        """
        self.folder_path = folder_path
        self.state = state
        self._files = None
    
    @property
    def files(self) -> Dict[str, str]:
        """Lazy-loaded dict of available monthly files."""
        if self._files is None:
            self._files = discover_monthly_files(self.folder_path, self.state)
        return self._files
    
    @property
    def available_months(self) -> List[str]:
        """List of available month keys."""
        return list(self.files.keys())
    
    @property
    def first_month(self) -> Optional[str]:
        """First available month."""
        months = self.available_months
        return months[0] if months else None
    
    @property
    def last_month(self) -> Optional[str]:
        """Last available month."""
        months = self.available_months
        return months[-1] if months else None
    
    def get_file(self, month: str) -> Optional[str]:
        """Get file path for a specific month."""
        return self.files.get(month)
    
    def iter_months(self, start_month: Optional[str] = None, end_month: Optional[str] = None):
        """
        Iterate over months in range.
        
        Args:
            start_month: Starting month key (default: first available)
            end_month: Ending month key (default: last available)
        
        Yields:
            Tuple of (month_key, file_path)
        """
        start = start_month or self.first_month
        end = end_month or self.last_month
        
        if not start or not end:
            return
        
        in_range = False
        for month, path in self.files.items():
            if month == start:
                in_range = True
            if in_range:
                yield month, path
            if month == end:
                break
    
    def validate_range(self, start_month: str, end_month: str) -> Tuple[bool, List[str]]:
        """
        Validate that all months in range are available.
        
        Returns:
            Tuple of (all_available, missing_months)
        """
        start_year, start_m = parse_month_key(start_month)
        end_year, end_m = parse_month_key(end_month)
        
        start_dt = datetime(start_year, start_m, 1)
        end_dt = datetime(end_year, end_m, 1)
        
        required = get_months_in_range(start_dt, end_dt)
        missing = [m for m in required if m not in self.files]
        
        return len(missing) == 0, missing
    
    def __repr__(self):
        return f"MonthlyPatternsManager(folder='{self.folder_path}', state={self.state}, months={len(self.files)})"


if __name__ == "__main__":
    # Example usage
    import sys
    
    folder = sys.argv[1] if len(sys.argv) > 1 else "./data"
    
    print(f"Scanning folder: {folder}")
    
    try:
        manager = MonthlyPatternsManager(folder)
        print(f"Found {len(manager.files)} monthly files:")
        for month, path in manager.files.items():
            print(f"  {month}: {path}")
        
        if manager.available_months:
            print(f"\nRange: {manager.first_month} to {manager.last_month}")
    except Exception as e:
        print(f"Error: {e}")
