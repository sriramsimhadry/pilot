import sys
import os

# Mock the CITIES and other stuff
CITIES = {
    "hyderabad": {"code": "HYD", "name": "Hyderabad", "display": "Hyderabad"},
    "delhi": {"code": "DEL", "name": "Delhi", "display": "Delhi"},
}

def _extract_cities(query):
    unique = []
    seen_codes = set()
    found = []
    for city_name, city_data in CITIES.items():
        pos = query.find(city_name)
        if pos >= 0:
            found.append((pos, city_data))
    
    found.sort(key=lambda x: x[0])
    for _, city in found:
        if city["code"] not in seen_codes:
            unique.append(city)
            seen_codes.add(city["code"])
            
    if len(unique) >= 2:
        return unique[0], unique[1]
    elif len(unique) == 1:
        if "to" in query:
            return None, unique[0]
        return unique[0], None
    return None, None

q = "i want to go to delhi"
print(f"Query: {q}")
origin, dest = _extract_cities(q)
print(f"Origin: {origin}")
print(f"Dest: {dest}")
