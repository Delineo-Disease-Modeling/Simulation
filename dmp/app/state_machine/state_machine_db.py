import sqlite3
import json
from datetime import datetime
import os

class StateMachineDB:
    def __init__(self, db_path=None):
        """Initialize the database connection and create tables if they don't exist."""
        if db_path is None:
            # Get the directory of the current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(current_dir, "state_machines.db")
        self.db_path = db_path
            
        self._create_tables()

    def _create_tables(self):
        """Create the necessary tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create state machines table with demographics as JSON
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state_machines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    disease_name TEXT DEFAULT 'Unknown',
                    variant_name TEXT DEFAULT NULL,
                    model_category TEXT DEFAULT 'default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    demographics TEXT NOT NULL DEFAULT '{}'
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
                    min_cutoff REAL NOT NULL,
                    max_cutoff REAL NOT NULL,
                    FOREIGN KEY (state_machine_id) REFERENCES state_machines(id)
                )
            ''')
            
            # Migrate existing databases to add new columns
            self._migrate_database(cursor)
            
            conn.commit()

    def _migrate_database(self, cursor):
        """Migrate existing database to add new columns if they don't exist."""
        try:
            # Check if columns exist
            cursor.execute("PRAGMA table_info(state_machines)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add disease_name column if it doesn't exist
            if 'disease_name' not in columns:
                cursor.execute('''
                    ALTER TABLE state_machines 
                    ADD COLUMN disease_name TEXT DEFAULT 'Unknown'
                ''')
                print("Database migrated: Added disease_name column")
            
            # Add variant_name column if it doesn't exist
            if 'variant_name' not in columns:
                cursor.execute('''
                    ALTER TABLE state_machines 
                    ADD COLUMN variant_name TEXT DEFAULT NULL
                ''')
                print("Database migrated: Added variant_name column")
            
            # Add model_category column if it doesn't exist
            if 'model_category' not in columns:
                cursor.execute('''
                    ALTER TABLE state_machines 
                    ADD COLUMN model_category TEXT DEFAULT 'default'
                ''')
                print("Database migrated: Added model_category column")
                
        except Exception as e:
            print(f"Migration error: {e}")
            # If migration fails, the table might not exist yet, which is fine

    def get_state_machine_by_name(self, name):
        """Get a state machine by its name."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, created_at, updated_at, demographics
                FROM state_machines
                WHERE name = ?
            ''', (name,))
            return cursor.fetchone()

    def save_state_machine(self, name, states, edges, demographics=None, disease_name="Unknown", variant_name=None, model_category="default", update_existing=True):
        """Save a state machine to the database.
        
        Args:
            name: Name of the state machine
            states: List of states
            edges: List of edges
            demographics: Optional demographics data as a dictionary
            disease_name: Name of the disease (default: "Unknown")
            variant_name: Name of the variant (default: None for default models)
            model_category: Category of the model ("default" or "variant")
            update_existing: If True, will update an existing state machine with the same name
                           If False, will raise an error if a state machine with the same name exists
        
        Returns:
            state_machine_id: ID of the saved state machine
        
        Raises:
            ValueError: If a state machine with the same name exists and update_existing is False
        """
        # Check if state machine with same name exists
        existing = self.get_state_machine_by_name(name)
        if existing and not update_existing:
            raise ValueError(f"A state machine named '{name}' already exists. Use update_existing=True to update it.")
        
        # Ensure demographics is a valid JSON string
        demographics_json = json.dumps(demographics or {})
        
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if existing and update_existing:
                # Update existing state machine
                state_machine_id = existing[0]
                cursor.execute(
                    """
                    UPDATE state_machines 
                    SET demographics = ?, disease_name = ?, variant_name = ?, model_category = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (demographics_json, disease_name, variant_name, model_category, state_machine_id)
                )
                
                # Delete existing states and edges
                cursor.execute('DELETE FROM edges WHERE state_machine_id = ?', (state_machine_id,))
                cursor.execute('DELETE FROM states WHERE state_machine_id = ?', (state_machine_id,))
            else:
                # Insert new state machine
                cursor.execute(
                    """
                    INSERT INTO state_machines (name, disease_name, variant_name, model_category, demographics)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, disease_name, variant_name, model_category, demographics_json)
                )
                state_machine_id = cursor.lastrowid
            
            # Insert states
            for state in states:
                cursor.execute(
                    """
                    INSERT INTO states (state_machine_id, state_name)
                    VALUES (?, ?)
                    """,
                    (state_machine_id, state)
                )
            
            # Insert edges
            for edge in edges:
                cursor.execute(
                    """
                    INSERT INTO edges (
                        state_machine_id, 
                        source_state, 
                        target_state, 
                        transition_prob,
                        mean_time,
                        std_dev,
                        distribution_type,
                        min_cutoff,
                        max_cutoff
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state_machine_id,
                        edge['data']['source'],
                        edge['data']['target'],
                        edge['data'].get('transition_prob', 1.0),
                        edge['data'].get('mean_time', 0),
                        edge['data'].get('std_dev', 0.0),
                        edge['data'].get('distribution_type', 'normal'),
                        edge['data'].get('min_cutoff', 0.0),
                        edge['data'].get('max_cutoff', float('inf'))
                    )
                )
            
            conn.commit()
            return state_machine_id
        except Exception as e:
            if conn is not None:
                conn.rollback()
            raise e
        finally:
            if conn is not None:
                conn.close()

    def load_state_machine(self, state_machine_id):
        """Load a state machine from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get state machine details
                cursor.execute(
                    """
                    SELECT name, disease_name, variant_name, model_category, demographics
                    FROM state_machines
                    WHERE id = ?
                    """,
                    (state_machine_id,)
                )
                machine_data = cursor.fetchone()
                if not machine_data:
                    return None
                
                # Get states
                cursor.execute(
                    """
                    SELECT state_name
                    FROM states
                    WHERE state_machine_id = ?
                    ORDER BY id
                    """,
                    (state_machine_id,)
                )
                states = [row[0] for row in cursor.fetchall()]
                
                # Get edges
                cursor.execute(
                    """
                    SELECT source_state, target_state, transition_prob, mean_time, 
                           std_dev, distribution_type, min_cutoff, max_cutoff
                    FROM edges
                    WHERE state_machine_id = ?
                    """,
                    (state_machine_id,)
                )
                edges = [
                    {
                        "data": {
                            "source": row[0],
                            "target": row[1],
                            "transition_prob": row[2],
                            "mean_time": row[3],
                            "std_dev": row[4],
                            "distribution_type": row[5],
                            "min_cutoff": row[6],
                            "max_cutoff": row[7],
                            "label": f"p={row[2]:.2f}\nμ={row[3]}\nσ={row[4]:.1f}\n{row[5]}\nmin={row[6]:.1f}\nmax={row[7]:.1f}"
                        }
                    }
                    for row in cursor.fetchall()
                ]
                
                # Parse demographics JSON
                demographics = json.loads(machine_data[4] or "{}")
                
                return {
                    "id": state_machine_id,
                    "name": machine_data[0],
                    "disease_name": machine_data[1],
                    "variant_name": machine_data[2],
                    "model_category": machine_data[3],
                    "demographics": demographics,
                    "states": states,
                    "edges": edges
                }
        except Exception as e:
            raise e

    def list_state_machines(self):
        """List all saved state machines."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, disease_name, variant_name, model_category, created_at, updated_at, demographics
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

    def get_unique_diseases(self):
        """Get list of unique diseases in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT disease_name
                FROM state_machines
                WHERE disease_name IS NOT NULL AND disease_name != 'Unknown'
                ORDER BY disease_name
            ''')
            return [row[0] for row in cursor.fetchall()]
    
    def get_variants_for_disease(self, disease_name):
        """Get list of variants for a specific disease."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT variant_name
                FROM state_machines
                WHERE disease_name = ? AND variant_name IS NOT NULL
                ORDER BY variant_name
            ''', (disease_name,))
            return [row[0] for row in cursor.fetchall()]
    
    def get_models_by_category(self, disease_name, category):
        """Get models for a specific disease and category."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, disease_name, variant_name, model_category, created_at, updated_at, demographics
                FROM state_machines
                WHERE disease_name = ? AND model_category = ?
                ORDER BY updated_at DESC
            ''', (disease_name, category))
            return cursor.fetchall()