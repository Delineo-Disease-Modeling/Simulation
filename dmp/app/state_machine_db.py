import sqlite3
import json
from datetime import datetime
import os

class StateMachineDB:
    def __init__(self, db_path="state_machines.db"):
        """Initialize the database connection and create tables if they don't exist."""
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        """Create the necessary tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create state machines table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state_machines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create states table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state_machine_id INTEGER,
                    state_name TEXT NOT NULL,
                    FOREIGN KEY (state_machine_id) REFERENCES state_machines(id)
                )
            ''')
            
            # Create edges table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state_machine_id INTEGER,
                    source_state TEXT NOT NULL,
                    target_state TEXT NOT NULL,
                    transition_prob REAL NOT NULL,
                    mean_time INTEGER NOT NULL,
                    std_dev REAL NOT NULL,
                    distribution_type TEXT NOT NULL,
                    FOREIGN KEY (state_machine_id) REFERENCES state_machines(id)
                )
            ''')
            
            conn.commit()

    def save_state_machine(self, name, description, states, edges):
        """Save a state machine to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert state machine
            cursor.execute('''
                INSERT INTO state_machines (name, description, updated_at)
                VALUES (?, ?, ?)
            ''', (name, description, datetime.now()))
            
            state_machine_id = cursor.lastrowid
            
            # Insert states
            for state in states:
                cursor.execute('''
                    INSERT INTO states (state_machine_id, state_name)
                    VALUES (?, ?)
                ''', (state_machine_id, state))
            
            # Insert edges
            for edge in edges:
                edge_data = edge['data']
                cursor.execute('''
                    INSERT INTO edges (
                        state_machine_id, source_state, target_state,
                        transition_prob, mean_time, std_dev, distribution_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    state_machine_id,
                    edge_data['source'],
                    edge_data['target'],
                    float(edge_data['label'].split('\n')[0].split('=')[1]),
                    int(edge_data['label'].split('\n')[1].split('=')[1]),
                    float(edge_data['label'].split('\n')[2].split('=')[1]),
                    edge_data['label'].split('\n')[3]
                ))
            
            conn.commit()
            return state_machine_id

    def load_state_machine(self, state_machine_id):
        """Load a state machine from the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get state machine details
            cursor.execute('''
                SELECT name, description, created_at, updated_at
                FROM state_machines
                WHERE id = ?
            ''', (state_machine_id,))
            machine_details = cursor.fetchone()
            
            if not machine_details:
                return None
            
            # Get states
            cursor.execute('''
                SELECT state_name
                FROM states
                WHERE state_machine_id = ?
                ORDER BY id
            ''', (state_machine_id,))
            states = [row[0] for row in cursor.fetchall()]
            
            # Get edges
            cursor.execute('''
                SELECT source_state, target_state, transition_prob,
                       mean_time, std_dev, distribution_type
                FROM edges
                WHERE state_machine_id = ?
            ''', (state_machine_id,))
            
            edges = []
            for row in cursor.fetchall():
                source, target, prob, mean, std, dist_type = row
                edges.append({
                    "data": {
                        "source": source,
                        "target": target,
                        "label": f"p={prob:.2f}\nμ={mean}\nσ={std:.1f}\n{dist_type}"
                    }
                })
            
            return {
                "id": state_machine_id,
                "name": machine_details[0],
                "description": machine_details[1],
                "created_at": machine_details[2],
                "updated_at": machine_details[3],
                "states": states,
                "edges": edges
            }

    def list_state_machines(self):
        """List all saved state machines."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, description, created_at, updated_at
                FROM state_machines
                ORDER BY updated_at DESC
            ''')
            return cursor.fetchall()

    def delete_state_machine(self, state_machine_id):
        """Delete a state machine and all its associated data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Delete edges
            cursor.execute('DELETE FROM edges WHERE state_machine_id = ?', (state_machine_id,))
            
            # Delete states
            cursor.execute('DELETE FROM states WHERE state_machine_id = ?', (state_machine_id,))
            
            # Delete state machine
            cursor.execute('DELETE FROM state_machines WHERE id = ?', (state_machine_id,))
            
            conn.commit() 