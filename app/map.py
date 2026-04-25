from flask import Blueprint, render_template, request
import requests

map_bp = Blueprint('map', __name__)

IP_LOCATION_URL = "http://ip-api.com/json/"
OVERPASS_URL    = "https://overpass-api.de/api/interpreter"
OSRM_URL        = "http://router.project-osrm.org/route/v1/driving/"
NOMINATIM_URL   = "https://nominatim.openstreetmap.org"

VALID_TYPES = {"doctor", "hospital", "pharmacy"}


def validate_doc_type(doc_type):
    return doc_type if doc_type in VALID_TYPES else "doctor"


def get_user_location_from_ip():
    try:
        response = requests.get(IP_LOCATION_URL, timeout=5)
        data = response.json()
        if data.get('status') == 'success':
            return data['lat'], data['lon'], f"{data.get('city', '')}, {data.get('country', '')}"
    except Exception as e:
        print(f"IP Location error: {str(e)}")
    return None, None, None


def geocode_address(address):
    if not address or not address.strip():
        return None, None
    try:
        params = {'q': address.strip(), 'format': 'json', 'limit': 1, 'addressdetails': 1}
        headers = {'User-Agent': 'MedicAi-PFE-Project'}
        response = requests.get(f"{NOMINATIM_URL}/search", params=params, headers=headers, timeout=6)
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Geocoding error: {str(e)}")
    return None, None


def reverse_geocode(lat, lng):
    try:
        params = {'lat': lat, 'lon': lng, 'format': 'json', 'zoom': 18, 'addressdetails': 1}
        headers = {'User-Agent': 'MedicAi-PFE-Project'}
        response = requests.get(f"{NOMINATIM_URL}/reverse", params=params, headers=headers, timeout=6)
        data = response.json()
        return data.get('display_name', 'Selected location')
    except Exception:
        return f"Lat: {lat:.4f}, Lng: {lng:.4f}"


def get_directions_free(lat, lng, dest_lat, dest_lng):
    try:
        url = f"{OSRM_URL}{lng},{lat};{dest_lng},{dest_lat}?overview=false"
        response = requests.get(url, timeout=8)
        data = response.json()
        if data.get('code') == 'Ok':
            route = data['routes'][0]
            return f"{round(route['distance'] / 1000, 1)} km", f"{round(route['duration'] / 60)} mins"
    except Exception as e:
        print(f"OSRM error: {str(e)}")
    return "N/A", "N/A"


def get_nearby_doctors(lat, lng, doc_type):
    """Overpass API — POST body (fixes 406), no lru_cache (fixes stale empty results)."""
    osm_amenity = "doctors" if doc_type == "doctor" else doc_type

    # Broader query: amenity tag + healthcare tag, nodes + ways
    query = f"""
[out:json][timeout:30];
(
  node["amenity"="{osm_amenity}"](around:10000,{lat},{lng});
  way["amenity"="{osm_amenity}"](around:10000,{lat},{lng});
  node["healthcare"="{doc_type}"](around:10000,{lat},{lng});
  way["healthcare"="{doc_type}"](around:10000,{lat},{lng});
);
out center;
"""
    print(f"[Overpass] POST type={doc_type} around ({lat:.4f}, {lng:.4f})")
    try:
        # ✅ POST with body — not GET with params
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "MedicAi-PFE-Project"},
            timeout=35,
        )
        response.raise_for_status()
        data = response.json()

        elements = data.get('elements', [])
        print(f"[Overpass] Got {len(elements)} elements")

        doctors = []
        seen = set()
        for element in elements:
            d_lat = element.get('lat') or element.get('center', {}).get('lat')
            d_lng = element.get('lon') or element.get('center', {}).get('lon')
            if d_lat is None or d_lng is None:
                continue

            key = (round(d_lat, 4), round(d_lng, 4))
            if key in seen:
                continue
            seen.add(key)

            tags = element.get('tags', {})
            name = (tags.get('name') or tags.get('name:en') or tags.get('name:fr')
                    or f"Unnamed {doc_type.title()}")
            address = (tags.get('addr:full') or tags.get('addr:street')
                       or 'Address not available')

            distance, duration = get_directions_free(lat, lng, d_lat, d_lng)

            doctors.append({
                'name':      name,
                'address':   address,
                'latitude':  d_lat,
                'longitude': d_lng,
                'rating':    "N/A",
                'distance':  distance,
                'duration':  duration,
            })

        return doctors

    except Exception as e:
        print(f"Overpass error: {str(e)}")
        return []


@map_bp.route('/find-doctors', methods=['GET', 'POST'])
def find_doctors():
    user_lat = None
    user_lng = None
    manual_address = None
    selected_address = None
    address_error = None

    if request.method == 'POST':
        doc_type = validate_doc_type(request.form.get('type', 'doctor'))
        
        # NEW: Get location method and coordinates
        location_method = request.form.get('location_method', 'auto')
        map_lat = request.form.get('map_lat', '').strip()
        map_lng = request.form.get('map_lng', '').strip()
        manual_address = request.form.get('manual_address', '').strip()

        print(f"[POST] Method: {location_method}, Map: ({map_lat}, {map_lng}), Manual: {manual_address}")

        # PRIORITY 1: Map selection (NEW!)
        if location_method == 'map' and map_lat and map_lng:
            try:
                user_lat = float(map_lat)
                user_lng = float(map_lng)
                selected_address = reverse_geocode(user_lat, user_lng)
                print(f"[POST] ✅ MAP SELECTION: ({user_lat:.5f}, {user_lng:.5f})")
            except ValueError:
                address_error = "Invalid map coordinates"
                print("[POST] ❌ Invalid map coordinates")

        # PRIORITY 2: Manual address geocoding
        elif manual_address:
            user_lat, user_lng = geocode_address(manual_address)
            if user_lat and user_lng:
                selected_address = manual_address
                print(f"[POST] ✅ MANUAL GEOCODE: ({user_lat:.5f}, {user_lng:.5f})")
            else:
                address_error = f"Address '{manual_address}' not found"
                print(f"[POST] ❌ Geocoding failed: {manual_address}")

        # PRIORITY 3: IP geolocation (auto)
        if not user_lat or not user_lng:
            user_lat, user_lng, ip_address = get_user_location_from_ip()
            if user_lat:
                selected_address = ip_address
                print(f"[POST] ✅ IP AUTO: ({user_lat:.5f}, {user_lng:.5f})")

    else:  # GET request
        doc_type = "doctor"
        user_lat, user_lng, selected_address = get_user_location_from_ip()

    # FINAL FALLBACK
    if not user_lat or not user_lng:
        user_lat, user_lng = 35.6970, -0.6330  # Oran, Algeria
        selected_address = "Oran, Algeria (default)"
        print("[POST] 🛡️ DEFAULT FALLBACK: Oran")

    # Get doctors using final coordinates
    doctors = get_nearby_doctors(user_lat, user_lng, doc_type)
    
    # Sort by distance and limit results
    doctors_sorted = sorted(
        doctors,
        key=lambda x: float(x['distance'].split()[0]) if x['distance'] != "N/A" else 999
    )[:15]

    print(f"[POST] 📍 Found {len(doctors_sorted)} {doc_type}s near ({user_lat:.4f}, {user_lng:.4f})")

    return render_template('nearest_doctor.html',
                           user_latitude=user_lat,
                           user_longitude=user_lng,
                           doctors=doctors_sorted,
                           selected_type=doc_type,
                           manual_address=manual_address or '',
                           address_error=address_error)


# Keep your other routes if you have them...