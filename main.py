import os
import requests
import customtkinter as ctk
from tkintermapview import TkinterMapView
import pandas as pd
import re
import itertools
from PIL import Image, ImageTk


# --- Fonctions pour l'API Unwired Labs ---
api_key = os.environ.get('UNWIRED_LABS_API_KEY', '.....')  # Remplacez avec votre clé
request_url = "https://us1.unwiredlabs.com/v2/process.php"

def locate_cell_unwired_api(cell):
    template = {
        "token": api_key,
        "radio": "gsm",
        "cells": [{
            "lac": int(cell['lac'], 16) if isinstance(cell['lac'], str) else cell['lac'],
            "cid": int(cell['cid'], 16) if isinstance(cell['cid'], str) else cell['cid'],
            "mcc": cell['mcc'],
            "mnc": cell['mnc']
        }],
        "address": 1
    }

    r = requests.post(request_url, json=template)
    if r.status_code != 200 or r.json().get("status") != "ok":
        print("Erreur lors de la demande de localisation:", r.text)
        return None, None
    else:
        loc = r.json()["lat"], r.json()["lon"]
        return loc

# --- Fonctions pour le fichier CSV ---
def extract_cell_data(data_string):
    pattern = r"\[(\d{3})\.(\d{2})\.(\w{4})\.(\w{4})@(-\d+)\]"
    matches = re.findall(pattern, data_string)

    cells = []
    for match in matches:
        mcc, mnc, lac, cid, rssi = match
        cells.append({
            'mcc': int(mcc),
            'mnc': int(mnc),
            'lac': lac,
            'cid': cid,
            'rssi': int(rssi)
        })
    return cells

df = pd.read_csv('towers.csv', header=None)

def get_location_from_csv(cell):
    mcc, mnc, lac, cid = cell['mcc'], cell['mnc'], cell['lac'], cell['cid']
    tower = df[(df[1] == mcc) & (df[2] == mnc) & (df[3] == int(lac, 16)) & (df[4] == int(cid, 16))]
    if not tower.empty:
        lat, lon = tower.iloc[0][7], tower.iloc[0][6]
        return lat, lon
    return None, None

def get_location(cell):
    if use_api.get():
        return locate_cell_unwired_api(cell)
    else:
        return get_location_from_csv(cell)




# --- Fonctions pour afficher sur la carte ---
current_markers = []
current_polygons = []

GOOGLE_MAPS_API_KEY = '.....'  # Remplacez avec votre clé

def reverse_geocode_google_maps(lat, lon):
    endpoint_url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(endpoint_url)
    data = response.json()
    if data['status'] == 'OK':
        return data['results'][0]['formatted_address']
    else:
        print(f"Erreur de géocodage: {data['status']}")
        return None


def plot_cells_on_map(cells_data):
    global current_markers, current_polygons

    # Supprimer les marqueurs actuels de la carte
    for marker in current_markers:
        marker.delete()
    current_markers.clear()

    # Supprimer les polygones actuels de la carte
    for polygon in current_polygons:
        polygon.delete()
    current_polygons.clear()

    latitudes = []
    longitudes = []
    positions = []

    # Remettons à zéro le widget d'affichage des adresses
    address_display.delete('1.0', ctk.END)

    # Chargeons l'image de la tour
    current_path = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    tower_image_path = os.path.join(current_path, "antenne.png")
    
    if os.path.exists(tower_image_path):
        tower_image = ImageTk.PhotoImage(Image.open(tower_image_path).resize((40, 40)))
    else:
        print("Image not found:", tower_image_path)
        return

    for index, cell in enumerate(cells_data):
        lat, lon = get_location(cell)
        if lat and lon:
            latitudes.append(lat)
            longitudes.append(lon)
            positions.append((lat, lon))
            
            # Obtenir l'adresse à partir des coordonnées
            address = reverse_geocode_google_maps(lat, lon)

            if address:
                # Ajouter l'adresse au widget `address_display`
                address_display.insert(ctk.END, f"Adresse tour {index + 1}: {address}\n")

            marker = map_widget.set_marker(lat, lon, text=f"Tour: {cell['cid']} RSSI: {cell['rssi']}", icon=tower_image, font=("Helvetica Bold", 10))
            current_markers.append(marker)

    # Si triangulation est activée
    if method_choice.get():
        for combo in itertools.combinations(positions, 3):
            polygon = map_widget.set_polygon(list(combo))
            current_polygons.append(polygon)
    else:
        # Estimation de la position basée sur la moyenne
        if positions:
            estimated_lat = sum(lat for lat, _ in positions) / len(positions)
            estimated_lon = sum(lon for _, lon in positions) / len(positions)
            estimated_marker = map_widget.set_marker(estimated_lat, estimated_lon, text="Position estimée", font=("Helvetica Bold", 12))
            current_markers.append(estimated_marker)

            # Obtenir et afficher l'adresse de la position estimée
            estimated_address = reverse_geocode_google_maps(estimated_lat, estimated_lon)
            if estimated_address:
                address_display.insert(ctk.END, f"\nAdresse position estimée: {estimated_address}")

    # Mettre à jour le centre de la carte pour se centrer sur les positions détectées
    center_lat = (max(latitudes) + min(latitudes)) / 2
    center_lon = (max(longitudes) + min(longitudes)) / 2
    map_widget.set_position(center_lat, center_lon, marker=False)
    map_widget.set_zoom(12)



def change_map(option):
    if option == "OpenStreetMap":
        map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
    elif option == "Google normal":
        map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
    elif option == "Google satellite":
        map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

def generate_map():
    data_string = entry.get()
    cells = extract_cell_data(data_string)
    plot_cells_on_map(cells)

app = ctk.CTk()
app.title("Localisateur de tours cellulaires")
app.geometry("1000x600")
app.rowconfigure(1, weight=1)  # Fait en sorte que la ligne contenant la carte prenne tout l'espace supplémentaire
app.columnconfigure(0, weight=1)  # Fait de même pour la colonne

entry = ctk.CTkEntry(app, placeholder_text="Entrez la chaîne de données")
entry.grid(row=0, column=0, padx=10, pady=10, sticky='ew')  # S'étend horizontalement

button_generate_map = ctk.CTkButton(app, text="Générer la carte", command=generate_map)
button_generate_map.grid(row=0, column=1, padx=10, pady=10)

options = ["OpenStreetMap", "Google normal", "Google satellite"]
dropdown = ctk.CTkOptionMenu(app, values=options, command=change_map)
dropdown.grid(row=0, column=2, padx=10, pady=10)
dropdown.set("OpenStreetMap")

method_choice = ctk.BooleanVar(value=True)
method_label = ctk.CTkLabel(app, text="Méthode de géolocalisation:")
method_label.grid(row=3, column=0, padx=10, pady=10)
method_switch = ctk.CTkSwitch(app, 
                              text="Utiliser la triangulation", 
                              variable=method_choice, 
                              onvalue=True, 
                              offvalue=False)
method_switch.grid(row=3, column=1, padx=10, pady=10)


use_api = ctk.BooleanVar(value=False)
switch_label = ctk.CTkLabel(app, text="Source de données:")
switch_label.grid(row=2, column=0, padx=10, pady=10)
switch_button = ctk.CTkSwitch(app, 
                              text="Utiliser l'API Unwired Labs", 
                              variable=use_api, 
                              onvalue=True, 
                              offvalue=False)
switch_button.grid(row=2, column=1, padx=10, pady=10)

map_widget = TkinterMapView(app, width=900, height=500, corner_radius=0)
map_widget.grid(row=1, column=0, columnspan=4, padx=10, pady=10, sticky='nsew')  # S'étend dans toutes les directions

address_display = ctk.CTkTextbox(app, height=5, width=400) # ajustez les dimensions comme vous le souhaitez
address_display.grid(row=1, column=4, padx=10, pady=10, sticky='nsew')  # ajustez le placement comme vous le souhaitez



def change_appearance_mode_event(mode):
    ctk.set_appearance_mode(mode)

# Ajouter l'option menu pour sélectionner le mode d'apparence
appearance_options = ["Light", "Dark", "System"]
appearance_dropdown = ctk.CTkOptionMenu(app, values=appearance_options, command=change_appearance_mode_event)
appearance_dropdown.grid(row=4, column=0, padx=10, pady=10)  # Vous pouvez ajuster les positions et le padding selon vos préférences
appearance_dropdown.set("System")  # Mode d'apparence par défaut


app.mainloop()
