import requests 
import json
import logging
import sys
import os
from typing import Dict, Any, Generator, Optional

BASE_URL = "https://db.delineo.me/"


def stream_data(url = "https://db.delineo.me/patterns/1?stream=true"):
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        print("Connected to stream!")

        first = True  
        linecount = 0
        for line in response.iter_lines(decode_unicode=True):
            linecount = linecount + 1
            if line:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    print("Warning: Could not parse line:", line)
                    continue

                if first:
                    print("Papdata received:")
                   
                    first = False
                else:
                    print("Timestep update:")
               
        print(f"Line count: {linecount}")

def load_movement_pap_data(cz_id=1): 
    url = "https://db.delineo.me/patterns/2"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors

        data = response.json().get("data", {})

        return {
            "data": {
                "patterns": data.get("patterns", {}),
                "papdata": data.get("papdata", {})
            }
        }

    except requests.RequestException as e:
        return {"error": str(e)}
    




def load_people(): 
    """
    Loads people and their information from central database. 
        
    Returns: 
        people(dict): Dictionary containing people information.
        """
    try:
        response = requests.get(f"{BASE_URL}/people")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error fetching people data:", e)
        return []


def load_places(): 
    try:
        response = requests.get(f"{BASE_URL}/places")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print("Error fetching places data:", e)
        return []
    
class StreamDataLoader:
    @staticmethod
    def stream_data(url: str, timeout: int = 60) -> Generator[Dict[str, Any], None, None]:
        """
        Stream data from the specified URL, yielding data chunks.
        
        :param url: URL to stream data from
        :param timeout: Timeout for the request in seconds
        :yield: Parsed data chunks
        """
        try:
            # Open a streaming connection with explicit headers and timeout
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            
            logging.info(f"Attempting to stream data from: {url}")
            
            # Raw bytes reading approach for more flexible parsing
            with requests.get(url, 
                              stream=True, 
                              headers=headers, 
                              timeout=timeout) as response:
                # Raise an exception for bad responses
                response.raise_for_status()
                
                logging.info("Connection established. Streaming data...")
                
                # Track if we've processed the first chunk (PAP data)
                first_chunk = True
                
                # Buffer to accumulate partial data
                buffer = b''
                decoder = json.JSONDecoder()
                
                # Read the response in chunks
                for chunk in response.iter_content(chunk_size=1024):
                    if not chunk:
                        continue
                    
                    # Accumulate chunk
                    buffer += chunk
                    
                    try:
                        # Try to decode buffer as string
                        buffer_str = buffer.decode('utf-8')
                        
                        # Try to parse JSON objects
                        while True:
                            try:
                                # Attempt to parse a JSON object
                                result, index = decoder.raw_decode(buffer_str)
                                
                                # If successful, process the parsed object
                                yield result
                                
                                # Remove processed part from buffer
                                buffer_str = buffer_str[index:].lstrip()
                                buffer = buffer_str.encode('utf-8')
                            
                            except json.JSONDecodeError:
                                # Not a complete JSON object, wait for more data
                                break
                    
                    except UnicodeDecodeError as ude:
                        logging.error(f"Unicode Decode Error: {ude}")
                        # Reset buffer to avoid continuous errors
                        buffer = b''
                    
                    except Exception as e:
                        logging.error(f"Error processing chunk: {e}")
                        # Reset buffer to avoid continuous errors
                        buffer = b''
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Request Error: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected Error: {e}")
            raise

def load_movement_pap_data_streaming(url: str = 'https://db.delineo.me/patterns/1?stream=true') -> Generator[Dict[str, Any], None, None]:
    """
    Load movement and PAP data via streaming.
    
    :param url: URL to stream data from
    :return: Generator yielding data chunks
    """
    try:
        for data_chunk in StreamDataLoader.stream_data(url):
            yield data_chunk
    except Exception as e:
        logging.error(f"Failed to load streaming data: {e}")
        raise

    
