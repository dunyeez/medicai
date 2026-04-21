from flask import Blueprint, render_template, request
import requests
from functools import lru_cache

map_bp = Blueprint('map', __name__)

# Free APIs
IP_LOCATION_URL = "http://ip-api.com/json/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"

VALID_TYPES = {"doctor", "hospital", "pharmacy"}


def validate_doc_type(doc_type):
    return doc_type if doc_type in VALID_TYPES else "doctor"


def get_user_location_from_ip():
    """Get approximate location using IP address as fallback"""
    try:
        response = requests.get(IP_LOCATION_URL, timeout=5)
        data = response.json()
        if data.get('status') == 'success':
            return data['lat'], data['lon']
    except Exception as e:
        print(f"IP Location error: {str(e)}")
    return None, None


def get_directions_free(lat, lng, dest_lat, dest_lng):
    """Get distance and duration using OSRM"""
    try:
        url = f"{OSRM_URL}{lng},{lat};{dest_lng},{dest_lat}?overview=false"
        response = requests.get(url, timeout=8)
        data = response.json()
        if data.get('code') == 'Ok':
            route = data['routes'][0]
            distance_km = round(route['distance'] / 1000, 1)
            duration_min = round(route['duration'] / 60)
            return f"{distance_km} km", f"{duration_min} mins"
    except Exception as e:
        print(f"OSRM error: {str(e)}")
    return "N/A", "N/A"


@lru_cache(maxsize=32)
def get_nearby_doctors(lat, lng, doc_type):
    """Improved Overpass query"""
    osm_type = "doctors" if doc_type == "doctor" else doc_type

    query = f"""
    [out:json][timeout:30];
    (
      nwr["amenity"="{osm_type}"](around:20000,{lat},{lng});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        response = requests.get(OVERPASS_URL, params={'data': query}, timeout=20)
        response.raise_for_status()
        data = response.json()

        doctors = []
        for element in data.get('elements', []):
            if element['type'] == 'node':
                d_lat = element.get('lat')
                d_lng = element.get('lon')
            else:
                center = element.get('center', {})
                d_lat = element.get('lat') or center.get('lat')
                d_lng = element.get('lon') or center.get('lon')

            if not d_lat or not d_lng:
                continue

            tags = element.get('tags', {})

            distance, duration = get_directions_free(lat, lng, d_lat, d_lng)

            doctors.append({
                'name': tags.get('name', f"Unnamed {doc_type.title()}"),
                'address': tags.get('addr:street', tags.get('addr:full', 'Address not available')),
                'latitude': d_lat,
                'longitude': d_lng,
                'rating': "N/A",
                'distance': distance,
                'duration': duration
            })

        print(f"DEBUG: Found {len(doctors)} {doc_type}(s) near ({lat:.4f}, {lng:.4f})")
        return doctors

    except Exception as e:
        print(f"Overpass error for {doc_type}: {str(e)}")
        return []


@map_bp.route('/find-doctors', methods=['GET', 'POST'])
def find_doctors():
    user_lat = None
    user_lng = None
    doc_type = "doctor"        # ← Default value to prevent UnboundLocalError

    if request.method == 'POST':
        doc_type = request.form.get('type', 'doctor')
        doc_type = validate_doc_type(doc_type)

        # Get coordinates from map selection
        selected_lat = request.form.get('selected_lat')
        selected_lng = request.form.get('selected_lng')

        if selected_lat and selected_lng:
            try:
                user_lat = float(selected_lat)
                user_lng = float(selected_lng)
                print(f"DEBUG: User selected location on map -> {user_lat:.4f}, {user_lng:.4f}")
            except ValueError:
                user_lat = user_lng = None

    # If no location from map → use IP location
    if not user_lat or not user_lng:
        user_lat, user_lng = get_user_location_from_ip()
        if user_lat and user_lng:
            print(f"DEBUG: Using IP-based location -> {user_lat:.4f}, {user_lng:.4f}")

    # Final fallback (Oran, Algeria)
    if not user_lat or not user_lng:
        user_lat, user_lng = 35.6970, -0.6330
        print("DEBUG: Using default location (Oran)")

    # Now safely call the function
    doctors = get_nearby_doctors(user_lat, user_lng, doc_type)

    # Sort by distance
    doctors_sorted = sorted(
        doctors,
        key=lambda x: float(x['distance'].split()[0]) if x['distance'] != "N/A" else 999
    )[:20]

    return render_template('nearest_doctor.html',
                           user_latitude=user_lat,
                           user_longitude=user_lng,
                           doctors=doctors_sorted,
                           selected_type=doc_type)