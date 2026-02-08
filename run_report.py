"""
Run Report Utility for Delineo Services

This module provides a simple interface for capturing run logs and sending
them to the DB API as structured reports. Used by both Algorithms and Simulation servers.

Usage:
    from run_report import RunReport

    # Start a report
    report = RunReport(
        run_type="simulation",  # or "cz_generation"
        name="Simulation: Hagerstown",
        parameters={"location": "hagerstown", "length": 1440}
    )
    
    # Log messages during the run
    report.info("Loading papdata...")
    report.info(f"Loaded {len(people)} people")
    report.warn("DMP API not available, using fallback")
    
    # Complete the report
    report.complete(summary={
        "people_count": 500,
        "infection_rate": 0.15,
        "total_infections": 75
    })
    
    # Or if it failed:
    report.fail("Connection refused to DB API")
"""

import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
import traceback
import sys

DB_API_URL = "http://localhost:1890"


class RunReport:
    """Captures logs and metadata for a run, sends to DB API."""
    
    def __init__(
        self,
        run_type: str,  # "cz_generation" or "simulation"
        name: str,
        parameters: Optional[Dict[str, Any]] = None,
        czone_id: Optional[int] = None,
        sim_id: Optional[int] = None,
        user_id: Optional[str] = None,
        auto_print: bool = True,  # Also print logs to stdout
    ):
        self.run_type = run_type
        self.name = name
        self.parameters = parameters or {}
        self.czone_id = czone_id
        self.sim_id = sim_id
        self.user_id = user_id
        self.auto_print = auto_print
        
        self.started_at = datetime.utcnow()
        self.logs: List[Dict[str, str]] = []
        self.report_id: Optional[int] = None
        self._buffer: List[Dict[str, str]] = []
        self._buffer_size = 10  # Flush every N logs
        
        self._create_report()
    
    def _create_report(self):
        """Create the report in the DB API."""
        try:
            resp = requests.post(f"{DB_API_URL}/reports", json={
                "run_type": self.run_type,
                "name": self.name,
                "started_at": self.started_at.isoformat() + "Z",
                "czone_id": self.czone_id,
                "sim_id": self.sim_id,
                "user_id": self.user_id,
                "parameters": self.parameters,
            }, timeout=5)
            
            if resp.ok:
                data = resp.json().get("data", {})
                self.report_id = data.get("id")
                self.info(f"Run report started (ID: {self.report_id})")
            else:
                print(f"[RunReport] Warning: Could not create report: {resp.status_code}")
        except Exception as e:
            print(f"[RunReport] Warning: Could not connect to DB API: {e}")
    
    def _log(self, level: str, message: str):
        """Add a log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": str(message),
        }
        self.logs.append(entry)
        self._buffer.append(entry)
        
        if self.auto_print:
            prefix = {"info": "INFO", "warn": "WARN", "error": "ERROR", "debug": "DEBUG"}.get(level, level.upper())
            print(f"[{prefix}] {message}")
        
        # Flush buffer periodically
        if len(self._buffer) >= self._buffer_size:
            self._flush_logs()
    
    def _flush_logs(self):
        """Send buffered logs to DB API."""
        if not self._buffer or not self.report_id:
            return
        
        try:
            requests.post(
                f"{DB_API_URL}/reports/{self.report_id}/logs",
                json={"logs": self._buffer},
                timeout=5
            )
            self._buffer = []
        except Exception:
            pass  # Silently fail, logs are still stored locally
    
    def info(self, message: str):
        """Log an info message."""
        self._log("info", message)
    
    def warn(self, message: str):
        """Log a warning message."""
        self._log("warn", message)
    
    def error(self, message: str):
        """Log an error message."""
        self._log("error", message)
    
    def debug(self, message: str):
        """Log a debug message."""
        self._log("debug", message)
    
    def complete(self, summary: Optional[Dict[str, Any]] = None):
        """Mark the report as completed with optional summary."""
        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - self.started_at).total_seconds() * 1000)
        
        self.info(f"Run completed in {duration_ms}ms")
        self._flush_logs()
        
        if not self.report_id:
            return
        
        try:
            requests.patch(f"{DB_API_URL}/reports/{self.report_id}", json={
                "status": "completed",
                "completed_at": completed_at.isoformat() + "Z",
                "duration_ms": duration_ms,
                "summary": summary,
                "logs": self.logs,  # Send all logs on complete
            }, timeout=5)
        except Exception as e:
            print(f"[RunReport] Warning: Could not update report: {e}")
    
    def fail(self, error_message: str):
        """Mark the report as failed with error details."""
        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - self.started_at).total_seconds() * 1000)
        
        self.error(f"Run failed: {error_message}")
        self._flush_logs()
        
        if not self.report_id:
            return
        
        try:
            requests.patch(f"{DB_API_URL}/reports/{self.report_id}", json={
                "status": "failed",
                "completed_at": completed_at.isoformat() + "Z",
                "duration_ms": duration_ms,
                "error": error_message,
                "logs": self.logs,
            }, timeout=5)
        except Exception as e:
            print(f"[RunReport] Warning: Could not update report: {e}")
    
    def capture_exception(self):
        """Capture the current exception and mark report as failed."""
        exc_info = sys.exc_info()
        if exc_info[0] is not None:
            tb = "".join(traceback.format_exception(*exc_info))
            self.fail(tb)


# Convenience function for quick logging without creating a report
def log_to_report(report_id: int, level: str, message: str):
    """Append a single log entry to an existing report."""
    try:
        requests.post(f"{DB_API_URL}/reports/{report_id}/logs", json={
            "logs": [{
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": level,
                "message": message,
            }]
        }, timeout=5)
    except Exception:
        pass
