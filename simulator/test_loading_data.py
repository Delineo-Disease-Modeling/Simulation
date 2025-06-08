import requests

import requests
import json

def stream_data(url):
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
                    print(line)
                    first = False
                else:
                    print("Timestep update:")
                    print(line)
               
        print(f"Line count: {linecount}")

def main(): 
    stream_data("https://db.delineo.me/patterns/1?stream=true")


if __name__ == "__main__":
    main()


