# sistema_rutas_minimo_flexible.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import requests
import folium
import polyline
import os
import time
import hashlib
import json
from datetime import datetime
import threading
import webbrowser
import sys
import subprocess
import shutil
from PIL import Image, ImageTk
import io
import math
import re

# =============================================================================
# CLASE CONEXIÓN CON BOT RAILWAY
# =============================================================================
class ConexionBotRailway:
    def __init__(self, url_base):
        self.url_base = url_base
        self.timeout = 30
    
    def enviar_ruta_bot(self, ruta_data):
        """Enviar ruta generada al bot en Railway"""
        try:
            url = f"{self.url_base}/api/rutas"
            
            response = requests.post(
                url,
                json=ruta_data,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                resultado = response.json()
                print(f"✅ Ruta {ruta_data['ruta_id']} enviada al bot: {resultado}")
                return True
            else:
                print(f"❌ Error enviando ruta: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error de conexión con bot: {e}")
            return False
    
    def verificar_conexion(self):
        """Verificar que el bot está disponible"""
        try:
            response = requests.get(f"{self.url_base}/api/health", timeout=10)
            return response.status_code == 200
        except:
            return False

    def descargar_foto(self, url_foto, ruta_destino):
        """Descarga una foto desde Telegram y la guarda localmente"""
        try:
            response = requests.get(url_foto, timeout=30)
            if response.status_code == 200:
                with open(ruta_destino, 'wb') as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"❌ Error descargando foto: {e}")
            return False

    def obtener_avances_pendientes(self):
        """Obtiene avances pendientes de sincronización del bot"""
        try:
            url = f"{self.url_base}/api/avances_pendientes"
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                datos = response.json()
                return datos.get('avances', [])
            else:
                print(f"❌ Error obteniendo avances: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error obteniendo avances: {str(e)}")
            return []
    
    def marcar_avance_procesado(self, avance_id):
        """Marca un avance como procesado en el bot"""
        try:
            url = f"{self.url_base}/api/avances/{avance_id}/procesado"
            response = requests.post(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error marcando avance como procesado: {str(e)}")
            return False

# =============================================================================
# CLASE GESTOR TELEGRAM
# =============================================================================
class GestorTelegram:
    def __init__(self, gui):
        self.gui = gui
        self.railway_url = "https://monitoring-routes-pjcdmx-production.up.railway.app"
        self.conexion = ConexionBotRailway(self.railway_url)
        
    def obtener_rutas_pendientes(self):
        """Obtiene lista de rutas pendientes de asignación"""
        try:
            rutas = []
            if os.path.exists("rutas_telegram"):
                for archivo in os.listdir("rutas_telegram"):
                    if archivo.endswith('.json'):
                        with open(f"rutas_telegram/{archivo}", 'r', encoding='utf-8') as f:
                            ruta_data = json.load(f)
                            
                        if ruta_data.get('estado') == 'pendiente':
                            paradas = ruta_data.get('paradas', [])
                            entregadas = sum(1 for p in paradas if p.get('estado') == 'entregado')
                            
                            rutas.append({
                                'ruta_id': ruta_data.get('ruta_id'),
                                'zona': ruta_data.get('zona'),
                                'archivo': archivo,
                                'progreso': f"{entregadas}/{len(paradas)}"
                            })
            
            return rutas
            
        except Exception as e:
            self.gui.log(f"❌ Error obteniendo rutas pendientes: {str(e)}")
            return []

    def asignar_ruta_repartidor(self, archivo_ruta, repartidor):
        """Asigna una ruta a un repartidor específico"""
        try:
            ruta_path = f"rutas_telegram/{archivo_ruta}"
            
            with open(ruta_path, 'r', encoding='utf-8') as f:
                ruta_data = json.load(f)
            
            ruta_data['estado'] = 'asignada'
            ruta_data['repartidor_asignado'] = repartidor
            ruta_data['fecha_asignacion'] = datetime.now().isoformat()
            
            with open(ruta_path, 'w', encoding='utf-8') as f:
                json.dump(ruta_data, f, indent=2, ensure_ascii=False)
            
            self.gui.log(f"✅ Ruta {ruta_data['ruta_id']} asignada a {repartidor}")
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error asignando ruta: {str(e)}")
            return False

    def obtener_avances_recientes(self, limite=10):
        """Obtiene los avances más recientes de las rutas"""
        try:
            avances_bot = self.conexion.obtener_avances_pendientes()
            
            avances_locales = []
            if os.path.exists("avances_ruta"):
                archivos_avance = sorted(os.listdir("avances_ruta"), reverse=True)[:limite]
                
                for archivo in archivos_avance:
                    if archivo.endswith('.json'):
                        with open(f"avances_ruta/{archivo}", 'r', encoding='utf-8') as f:
                            avance_data = json.load(f)
                            avances_locales.append(avance_data)
            
            todos_avances = avances_bot + avances_locales
            todos_avances.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            return todos_avances[:limite]
            
        except Exception as e:
            self.gui.log(f"❌ Error obteniendo avances: {str(e)}")
            return []

    def forzar_actualizacion_fotos(self):
        """Fuerza la actualización de fotos en archivos Excel"""
        try:
            actualizaciones = 0
            
            avances = self.conexion.obtener_avances_pendientes()
            
            for avance in avances:
                if self._procesar_avance_desde_bot(avance):
                    actualizaciones += 1
                    avance_id = avance.get('id')
                    if avance_id:
                        self.conexion.marcar_avance_procesado(avance_id)
            
            self.gui.log(f"📸 Se actualizaron {actualizaciones} archivos Excel con fotos")
            return actualizaciones
            
        except Exception as e:
            self.gui.log(f"❌ Error forzando actualización: {str(e)}")
            return 0

    def _procesar_avance_desde_bot(self, avance):
        """Procesa un avance del bot y actualiza el Excel correspondiente"""
        try:
            ruta_id = avance.get('ruta_id')
            persona_entregada = avance.get('persona_entregada', '').strip()
            foto_ruta = avance.get('foto_local', '')
            repartidor = avance.get('repartidor', '')
            timestamp = avance.get('timestamp', '')
            
            if not persona_entregada or not ruta_id:
                return False
            
            archivos_encontrados = []
            
            for archivo in os.listdir("rutas_excel"):
                if f"Ruta_{ruta_id}_" in archivo and archivo.endswith('.xlsx'):
                    archivos_encontrados.append(archivo)
            
            if not archivos_encontrados:
                self.gui.log(f"❌ No se encontró Excel para Ruta {ruta_id}")
                return False
            
            excel_file = f"rutas_excel/{archivos_encontrados[0]}"
            
            df = pd.read_excel(excel_file)
            persona_encontrada = False
            
            for idx, fila in df.iterrows():
                nombre_en_excel = str(fila.get('Nombre', '')).strip().lower()
                persona_buscar = persona_entregada.lower()
                
                if (persona_buscar in nombre_en_excel or 
                    nombre_en_excel in persona_buscar or
                    self._coincidencia_flexible_nombres(persona_buscar, nombre_en_excel)):
                    
                    link_foto = f"=HIPERVINCULO(\"{foto_ruta}\", \"VER FOTO\")" if foto_ruta else "SIN FOTO"
                    df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                    df.at[idx, 'Repartidor'] = repartidor
                    df.at[idx, 'Foto_Acuse'] = link_foto
                    df.at[idx, 'Timestamp_Entrega'] = timestamp
                    df.at[idx, 'Estado'] = 'ENTREGADO'
                    
                    persona_encontrada = True
                    self.gui.log(f"✅ Excel actualizado: {persona_entregada} → {nombre_en_excel}")
                    break
            
            if persona_encontrada:
                df.to_excel(excel_file, index=False)
                self.gui.log(f"💾 Excel guardado: {os.path.basename(excel_file)}")
                return True
            else:
                self.gui.log(f"⚠️ '{persona_entregada}' no encontrado en Ruta {ruta_id}")
                return False
                
        except Exception as e:
            self.gui.log(f"❌ Error procesando avance: {str(e)}")
            return False

    def _coincidencia_flexible_nombres(self, nombre1, nombre2):
        """Coincidencia inteligente de nombres"""
        palabras_comunes = ['lic', 'lic.', 'ingeniero', 'ing', 'dr', 'doctor', 'mtro', 'maestro', 'sr', 'sra']
        
        n1_clean = ' '.join([p for p in nombre1.split() if p.lower() not in palabras_comunes])
        n2_clean = ' '.join([p for p in nombre2.split() if p.lower() not in palabras_comunes])
        
        palabras1 = set(n1_clean.lower().split())
        palabras2 = set(n2_clean.lower().split())
        
        return len(palabras1.intersection(palabras2)) >= 2

    def simular_entrega_bot(self, ruta_id, repartidor, persona):
        """Simula una entrega para pruebas del sistema"""
        try:
            avance_simulado = {
                'ruta_id': ruta_id,
                'repartidor': repartidor,
                'persona_entregada': persona,
                'timestamp': datetime.now().isoformat(),
                'foto_local': f"fotos_entregas/entrega_simulada_{ruta_id}.jpg",
                'tipo': 'entrega_simulada'
            }
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_avance = f"avances_ruta/avance_{timestamp}.json"
            
            with open(archivo_avance, 'w', encoding='utf-8') as f:
                json.dump(avance_simulado, f, indent=2, ensure_ascii=False)
            
            self._procesar_avance_desde_bot(avance_simulado)
            
            self.gui.log(f"🧪 Entrega simulada: {persona} por {repartidor}")
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error en simulación: {str(e)}")
            return False

# =============================================================================
# CLASE PRINCIPAL - MOTOR DE RUTAS CON MÍNIMO FLEXIBLE
# =============================================================================
class CoreRouteGenerator:
    def __init__(self, df, api_key, origen_coords, origen_name, max_stops_per_route):
        self.df = df.copy()
        self.api_key = api_key
        self.origen_coords = origen_coords
        self.origen_name = origen_name
        self.max_stops_per_route = max_stops_per_route
        self.results = []
        self.log_messages = []
        self.CACHE_FILE = "geocode_cache.json"
        self.GEOCODE_CACHE = {}
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    self.GEOCODE_CACHE = json.load(f)
            except json.JSONDecodeError:
                self._log(f"Corrupted geocode cache file '{self.CACHE_FILE}', starting with empty cache.")
                self.GEOCODE_CACHE = {}
        self.COLORES = {
            'CENTRO': '#FF6B6B', 'SUR': '#4ECDC4', 'ORIENTE': '#45B7D1',
            'SUR_ORIENTE': '#96CEB4', 'OTRAS': '#FECA57'
        }
        self.ICONOS = {
            'CENTRO': 'building', 'SUR': 'home', 'ORIENTE': 'industry',
            'SUR_ORIENTE': 'tree', 'OTRAS': 'map-marker'
        }
        self._log("CoreRouteGenerator initialized successfully.")

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] {message}")
        print(self.log_messages[-1])

    def _geocode(self, direccion):
        d = str(direccion).strip()
        if not d or d in ['nan', '']:
            return None
        key = hashlib.md5(d.encode('utf-8')).hexdigest()
        if key in self.GEOCODE_CACHE:
            return self.GEOCODE_CACHE[key]
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {'address': d + ", CDMX", 'key': self.api_key}
            r = requests.get(url, params=params, timeout=10)
            data = r.json()
            if data['status'] == 'OK' and data['results']:
                loc = data['results'][0]['geometry']['location']
                coords = (loc['lat'], loc['lng'])
                self.GEOCODE_CACHE[key] = coords
                time.sleep(0.11)
                return coords
            else:
                self._log(f"Geocode API returned status '{data.get('status', 'UNKNOWN')}' for: {d[:50]}...")
        except requests.exceptions.RequestException as req_e:
            self._log(f"Network error during geocoding for {d[:50]}...: {str(req_e)}")
        except Exception as e:
            self._log(f"Unexpected error in geocode for {d[:50]}...: {str(e)}")
        return None

    def _normalizar_direccion(self, direccion):
        """Normaliza direcciones para agrupar por edificio"""
        direccion = direccion.lower().strip()
        direccion = re.sub(r'[^\w\s]', ' ', direccion)
        direccion = re.sub(r'\s+', ' ', direccion)
        
        reemplazos = {
            r'\bav\b': 'avenida',
            r'\bav\.': 'avenida',
            r'\bcto\b': 'circuito',
            r'\bblvd\b': 'boulevard',
            r'\bcd\b': 'ciudad',
            r'\bcol\b': 'colonia',
            r'\bdeleg\b': 'delegacion',
            r'\bdf\b': 'ciudad de mexico',
            r'\bcdmx\b': 'ciudad de mexico',
            r'\bedif\b': 'edificio',
            r'\bentre\b': 'y',
            r'\besq\b': 'esquina',
            r'\bint\b': 'interior',
            r'\bjal\b': 'jalapa',
            r'\blt\b': 'lote',
            r'\bmanz\b': 'manzana',
            r'\bmza\b': 'manzana',
            r'\bno\b': 'numero',
            r'\bnum\b': 'numero',
            r'\bprlv\b': 'privada',
            r'\bs\n': 'sin numero',
            r'\bs/n': 'sin numero',
            r'\bsn\b': 'sin numero',
        }
        
        for patron, reemplazo in reemplazos.items():
            direccion = re.sub(patron, reemplazo, direccion)
        
        palabras_comunes = ['ciudad de mexico', 'mexico', 'cdmx', 'alcaldia', 'delegacion']
        for palabra in palabras_comunes:
            direccion = direccion.replace(palabra, '')
        
        return direccion.strip()

def _calcular_distancia(self, coord1, coord2):
    """Calcula distancia en kilómetros entre dos coordenadas"""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2) * math.sin(dlon/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def _agrupar_por_edificio(self, filas):
    """🎯 Agrupa por edificio/institución - CADA EDIFICIO ES UNA PARADA"""
    grupos = {}
    
    for idx, fila in filas.iterrows():
        direccion = str(fila.get('DIRECCIÓN', '')).strip()
        if not direccion or direccion in ['nan', '']:
            continue
            
        # Normalizar dirección para agrupar por edificio
        direccion_normalizada = self._normalizar_direccion(direccion)
        
        # Buscar edificio existente o crear uno nuevo
        edificio_existente = None
        for edificio_key in grupos.keys():
            if self._es_mismo_edificio(direccion_normalizada, edificio_key):
                edificio_existente = edificio_key
                break
        
        if edificio_existente:
            # Agregar persona al edificio existente
            grupos[edificio_existente]['personas'].append(fila)
            grupos[edificio_existente]['indices'].append(idx)
        else:
            # Crear nuevo edificio
            coords = self._geocode(direccion)
            if coords:
                grupos[direccion_normalizada] = {
                    'coordenadas': coords,
                    'personas': [fila],
                    'indices': [idx],
                    'direccion_original': direccion
                }
    
    # Convertir a lista de grupos (coords, personas, indices)
    lista_grupos = []
    for direccion_key, datos in grupos.items():
        lista_grupos.append((
            datos['coordenadas'],
            datos['personas'],
            datos['indices']  # 🆕 Incluir índices originales
        ))
        self._log(f"🏢 Edificio: {direccion_key[:50]}... → {len(datos['personas'])} personas")
    
    self._log(f"🎯 Agrupamiento por edificio: {len(lista_grupos)} edificios de {len(filas)} registros")
    return lista_grupos
    
    def _es_mismo_edificio(self, dir1, dir2):
        """Determina si dos direcciones pertenecen al mismo edificio"""
        # Coincidencia exacta después de normalización
        if dir1 == dir2:
            return True
        
        # Coincidencia por palabras clave (mismo edificio)
        palabras1 = set(dir1.split())
        palabras2 = set(dir2.split())
        
        # Si comparten al menos 3 palabras clave, probablemente mismo edificio
        palabras_comunes = palabras1.intersection(palabras2)
        return len(palabras_comunes) >= 3

    def _optimizar_ruta(self, indices):
        filas = self.df.loc[indices]
        
        # 🎯 USAR AGRUPAMIENTO POR EDIFICIO
        grupos_edificios = self._agrupar_por_edificio(filas)
        
        coords_list = []
        filas_agrupadas = []
        
        for coords, grupo_filas in grupos_edificios:
            coords_list.append(coords)
            filas_agrupadas.append({
                'coordenadas': coords,
                'personas': grupo_filas,
                'cantidad_personas': len(grupo_filas),
                'es_edificio': True
            })
        
        # 🆕 CORRECCIÓN: Si hay menos de 2 edificios, agregar origen como waypoint adicional
        if len(coords_list) < 2:
            self._log("⚠️ Pocos edificios en ruta - agregando origen como waypoint adicional")
            origen_coords = tuple(map(float, self.origen_coords.split(',')))
            coords_list.append(origen_coords)
            # Agregar un grupo ficticio para el origen
            filas_agrupadas.append({
                'coordenadas': origen_coords,
                'personas': [],
                'cantidad_personas': 0,
                'es_edificio': False,
                'es_origen_adicional': True
            })
        
        if len(coords_list) < 2:
            self._log(f"Not enough valid coordinates (found {len(coords_list)}) for route optimization. Skipping.")
            return filas_agrupadas, [], 0, 0, None
            
        waypoints = "|".join([f"{lat},{lng}" for lat, lng in coords_list])
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            'origin': self.origen_coords,
            'destination': self.origen_coords,
            'waypoints': f"optimize:true|{waypoints}",
            'key': self.api_key
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            if data['status'] == 'OK' and data['routes']:
                route = data['routes'][0]
                orden = route['waypoint_order']
                poly = route['overview_polyline']['points']
                dist = sum(leg['distance']['value'] for leg in route['legs']) / 1000
                tiempo = sum(leg['duration']['value'] for leg in route['legs']) / 60
                
                # 🆕 FILTRAR waypoints que son el origen adicional
                filas_finales = []
                coords_finales = []
                
                for i in orden:
                    # Si no es el origen adicional, agregar a la lista final
                    if not filas_agrupadas[i].get('es_origen_adicional', False):
                        filas_finales.append(filas_agrupadas[i])
                        coords_finales.append(coords_list[i])
                
                return filas_finales, coords_finales, tiempo, dist, poly
            else:
                self._log(f"Directions API error: {data.get('status')}")
                return filas_agrupadas, [], 0, 0, None
        except Exception as e:
            self._log(f"Error optimizing route: {str(e)}")
            return filas_agrupadas, [], 0, 0, None

    def _crear_ruta_archivos(self, zona, indices, ruta_id):
        filas_opt, coords_opt, tiempo, dist, poly = self._optimizar_ruta(indices)
        if len(filas_opt) == 0:
            self._log(f"No valid stops for Route {ruta_id} - {zona}.")
            return None
            
        os.makedirs("mapas_pro", exist_ok=True)
        os.makedirs("rutas_excel", exist_ok=True)
        
        # EXCEL CON AGRUPAMIENTO POR EDIFICIO
        excel_data = []
        orden_parada = 1
        
        for grupo in filas_opt:
            coordenadas_grupo = grupo['coordenadas']
            personas_grupo = grupo['personas']
            cantidad_personas = grupo['cantidad_personas']
            
            # 🎯 CADA EDIFICIO ES UNA PARADA, sin importar cuántas personas
            primera_persona = personas_grupo[0]
            direccion_edificio = str(primera_persona.get('DIRECCIÓN', 'N/A')).strip()
            
            # Para cada persona en el edificio, crear una fila en Excel
            for i, persona in enumerate(personas_grupo):
                # Crear link para foto - TODAS las personas del mismo edificio comparten número de parada
                link_foto_base = f"fotos_entregas/Ruta_{ruta_id}_Parada_{orden_parada}"
                if cantidad_personas > 1:
                    link_foto_base += f"_Persona_{i+1}"
                
                link_foto = f"=HIPERVINCULO(\"{link_foto_base}.jpg\", \"📸 VER FOTO\")"
                
                # Información del edificio
                info_edificio = f"Edificio ({cantidad_personas} personas)" if i == 0 else f"Persona {i+1} en edificio"
                
                excel_data.append({
                    'Orden': orden_parada,  # 🎯 MISMO ORDEN PARA TODAS LAS PERSONAS DEL EDIFICIO
                    'Sub_Orden': i + 1 if cantidad_personas > 1 else '',
                    'Nombre': str(persona.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                    'Dependencia': str(persona.get('ADSCRIPCIÓN', 'N/A')).strip(),
                    'Dirección': direccion_edificio,  # 🎯 MISMA DIRECCIÓN PARA TODAS
                    'Personas_En_Edificio': cantidad_personas if i == 0 else '',
                    'Tipo_Entrega': info_edificio,
                    'Acuse': '',
                    'Repartidor': '',
                    'Foto_Acuse': link_foto,
                    'Timestamp_Entrega': '',
                    'Estado': 'PENDIENTE',
                    'Coordenadas': f"{coordenadas_grupo[0]},{coordenadas_grupo[1]}",
                    'Notas': f"Edificio con {cantidad_personas} personas" if cantidad_personas > 1 else ''
                })
            
            # 🎯 SOLO UNA PARADA POR EDIFICIO - incrementar orden
            orden_parada += 1
        
        excel_df = pd.DataFrame(excel_data)
        excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
        try:
            excel_df.to_excel(excel_file, index=False)
            self._log(f"Generated Excel: {excel_file}")
        except Exception as e:
            self._log(f"Error generating Excel: {str(e)}")
            
        # Crear mapa
        map_origin_coords = list(map(float, self.origen_coords.split(',')))
        m = folium.Map(location=map_origin_coords, zoom_start=12, tiles='CartoDB positron')
        color = self.COLORES.get(zona, 'gray')
        
        # Marcador de origen
        folium.Marker(
            map_origin_coords,
            popup=f"<b>{self.origen_name}</b>",
            icon=folium.Icon(color='green', icon='balance-scale', prefix='fa')
        ).add_to(m)
        
        # Ruta optimizada
        if poly:
            folium.PolyLine(polyline.decode(poly), color=color, weight=6, opacity=0.8).add_to(m)
        
        # Marcadores de paradas (EDIFICIOS)
        for i, (grupo, coord) in enumerate(zip(filas_opt, coords_opt), 1):
            cantidad_personas = grupo['cantidad_personas']
            primera_persona = grupo['personas'][0]
            nombre_primero = str(primera_persona.get('NOMBRE', 'N/A')).split(',')[0]
            direccion = str(primera_persona.get('DIRECCIÓN', 'N/A'))[:70]
            
            # 🎯 TODOS LOS EDIFICIOS SON PARADAS ÚNICAS
            popup_html = f"""
            <div style='font-family:Arial; width:300px;'>
                <b>🏢 Parada #{i} - Edificio</b><br>
                <b>👥 {cantidad_personas} personas</b><br>
                <b>📍 {nombre_primero} y {cantidad_personas-1} más</b><br>
                <small>{direccion}...</small>
            </div>
            """
            
            folium.Marker(
                coord,
                popup=popup_html,
                tooltip=f"🏢 Parada #{i} ({cantidad_personas} personas)",
                icon=folium.Icon(color='orange', icon='building', prefix='fa')
            ).add_to(m)
        
        # Panel de información
        total_personas = sum(grupo['cantidad_personas'] for grupo in filas_opt)
        total_paradas = len(filas_opt)  # 🎯 PARADAS = EDIFICIOS
        
        info_panel_html = f"""
        <div style="position:fixed;top:10px;left:50px;z-index:1000;background:white;padding:15px;border-radius:10px;
                    box-shadow:0 0 15px rgba(0,0,0,0.2);border:2px solid {color};font-family:Arial;max-width:350px;">
            <h4 style="margin:0 0 10px;color:#2c3e50;border-bottom:2px solid {color};padding-bottom:5px;">
                Ruta {ruta_id} - {zona}
            </h4>
            <small>
                <b>🏢 Edificios:</b> {total_paradas} | <b>👥 Personas:</b> {total_personas}<br>
                <b>📏 Distancia:</b> {dist:.1f} km | <b>⏱️ Tiempo:</b> {tiempo:.0f} min<br>
                <a href="file://{os.path.abspath(excel_file)}" target="_blank">📊 Descargar Excel</a>
            </small>
        </div>
        """
        m.get_root().html.add_child(folium.Element(info_panel_html))
        
        mapa_file = f"mapas_pro/Ruta_{ruta_id}_{zona}.html"
        try:
            m.save(mapa_file)
            self._log(f"Generated Map: {mapa_file}")
        except Exception as e:
            self._log(f"Error generating map: {str(e)}")
            
        # GENERAR DATOS PARA TELEGRAM
        waypoints_param = "|".join([f"{lat},{lng}" for lat, lng in coords_opt])
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={self.origen_coords}&destination={self.origen_coords}&waypoints={waypoints_param}&travelmode=driving"
        
        # Preparar paradas para Telegram (CADA EDIFICIO ES UNA PARADA)
        paradas_telegram = []
        orden_telegram = 1
        
        for grupo in filas_opt:
            coordenadas_grupo = grupo['coordenadas']
            personas_grupo = grupo['personas']
            cantidad_personas = grupo['cantidad_personas']
            primera_persona = personas_grupo[0]
            direccion_edificio = str(primera_persona.get('DIRECCIÓN', 'N/A')).strip()
            
            # 🎯 UNA SOLA PARADA EN TELEGRAM POR EDIFICIO
            paradas_telegram.append({
                'orden': orden_telegram,
                'nombre_edificio': f"Edificio con {cantidad_personas} personas",
                'direccion': direccion_edificio,
                'coords': f"{coordenadas_grupo[0]},{coordenadas_grupo[1]}",
                'estado': 'pendiente',
                'timestamp_entrega': None,
                'personas_en_edificio': cantidad_personas,
                'lista_personas': [
                    {
                        'nombre': str(p.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                        'dependencia': str(p.get('ADSCRIPCIÓN', 'N/A')).strip(),
                        'foto_acuse': f"fotos_entregas/Ruta_{ruta_id}_Parada_{orden_telegram}_Persona_{j+1}.jpg"
                    }
                    for j, p in enumerate(personas_grupo)
                ]
            })
            
            orden_telegram += 1
        
        ruta_telegram = {
            'ruta_id': ruta_id,
            'zona': zona,
            'repartidor_asignado': None,
            'google_maps_url': google_maps_url,
            'paradas': paradas_telegram,
            'estadisticas': {
                'total_edificios': total_paradas,
                'total_personas': total_personas,
                'distancia_km': round(dist, 1),
                'tiempo_min': round(tiempo),
                'origen': self.origen_name
            },
            'estado': 'pendiente',
            'fotos_acuses': [],
            'timestamp_creacion': datetime.now().isoformat(),
            'excel_original': excel_file,
            'indices_originales': indices
        }
        
        telegram_file = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        try:
            with open(telegram_file, 'w', encoding='utf-8') as f:
                json.dump(ruta_telegram, f, indent=2, ensure_ascii=False)
            self._log(f"📱 Datos para Telegram generados: {telegram_file}")
        except Exception as e:
            self._log(f"❌ Error guardando datos Telegram: {str(e)}")
        
        # ENVIAR RUTA AL BOT EN RAILWAY
        try:
            RAILWAY_URL = "https://monitoring-routes-pjcdmx-production.up.railway.app"
            conexion = ConexionBotRailway(RAILWAY_URL)
            
            if conexion.verificar_conexion():
                if conexion.enviar_ruta_bot(ruta_telegram):
                    self._log(f"📱 Ruta {ruta_id} enviada al bot exitosamente")
                else:
                    self._log("⚠️ Ruta generada pero no se pudo enviar al bot")
            else:
                self._log("❌ No se pudo conectar con el bot en Railway")
                
        except Exception as e:
            self._log(f"❌ Error enviando al bot: {str(e)}")

        return {
            'ruta_id': ruta_id,
            'zona': zona,
            'paradas': total_paradas,  # 🎯 EDIFICIOS
            'personas': total_personas,
            'distancia': round(dist, 1),
            'tiempo': round(tiempo),
            'excel': excel_file,
            'mapa': mapa_file,
            'telegram_data': ruta_telegram,
            'telegram_file': telegram_file
        }

    def generate_routes(self):
    self._log("Starting Core Route Generation Process")
    self._log(f"Initial data records: {len(self.df)}")
    if self.df.empty:
        self._log("No data to process.")
        return []
    
    df_clean = self.df.copy()
    if 'DIRECCIÓN' in df_clean.columns:
        df_clean['DIRECCIÓN'] = df_clean['DIRECCIÓN'].astype(str).str.replace('\n', ' ', regex=False).str.strip()
        df_clean['DIRECCIÓN'] = df_clean['DIRECCIÓN'].str.split('/').str[0]
        
        mask = (
            df_clean['DIRECCIÓN'].str.contains(r'CDMX|CIUDAD DE MÉXICO|CIUDAD DE MEXICO', case=False, na=False) |
            df_clean['DIRECCIÓN'].str.contains(r'CD\.MX|MÉXICO D\.F\.|MEXICO D\.F\.', case=False, na=False) |
            (df_clean['ALCALDÍA'].notna() if 'ALCALDÍA' in df_clean.columns else False)
        )
        df_clean = df_clean[mask]
        self._log(f"📍 Registros después de filtro inteligente: {len(df_clean)}")
    else:
        self._log("'DIRECCIÓN' column not found.")
        return []
    
    def extraer_alcaldia(d):
        d = str(d).upper()
        alcaldias = {
            'CUAUHTEMOC': ['CUAUHTEMOC', 'CUÁUHTEMOC', 'DOCTORES', 'CENTRO', 'JUÁREZ', 'ROMA', 'CONDESA'],
            'MIGUEL HIDALGO': ['MIGUEL HIDALGO', 'POLANCO', 'LOMAS', 'CHAPULTEPEC'],
            'BENITO JUAREZ': ['BENITO JUÁREZ', 'DEL VALLE', 'NÁPOLES'],
            'ALVARO OBREGON': ['ÁLVARO OBREGÓN', 'SAN ÁNGEL', 'LAS ÁGUILAS'],
            'COYOACAN': ['COYOACÁN', 'COYOACAN'],
            'TLALPAN': ['TLALPAN'],
            'IZTAPALAPA': ['IZTAPALAPA'],
            'GUSTAVO A. MADERO': ['GUSTAVO A. MADERO'],
            'AZCAPOTZALCO': ['AZCAPOTZALCO'],
            'VENUSTIANO CARRANZA': ['VENUSTIANO CARRANZA'],
            'XOCHIMILCO': ['XOCHIMILCO'],
            'IZTACALCO': ['IZTACALCO'],
            'MILPA ALTA': ['MILPA ALTA'],
            'TLÁHUAC': ['TLÁHUAC']
        }
        for alc, palabras in alcaldias.items():
            if any(p in d for p in palabras):
                return alc.title()
        return "NO IDENTIFICADA"
    
    df_clean['Alcaldia'] = df_clean['DIRECCIÓN'].apply(extraer_alcaldia)
    
    ZONAS = {
        'CENTRO': ['Cuauhtemoc', 'Venustiano Carranza', 'Miguel Hidalgo'],
        'SUR': ['Coyoacán', 'Tlalpan', 'Álvaro Obregón', 'Benito Juárez'],
        'ORIENTE': ['Iztacalco', 'Iztapalapa', 'Gustavo A. Madero'],
        'SUR_ORIENTE': ['Xochimilco', 'Milpa Alta', 'Tláhuac'],
    }
    
    def asignar_zona(alc):
        for zona_name, alcaldias_in_zone in ZONAS.items():
            if alc in alcaldias_in_zone:
                return zona_name
        return 'OTRAS'
    
    df_clean['Zona'] = df_clean['Alcaldia'].apply(asignar_zona)
    
    # 🎯 ESTRATEGIA SOVIÉTICA: 8 EDIFICIOS EXACTOS POR RUTA
    PARADAS_POR_RUTA = 8  # 🚀 8 PARADAS EXACTAS
    
    self._log(f"🎯 MODO SOVIÉTICO ACTIVADO: {PARADAS_POR_RUTA} edificios por ruta")
    
    # Primero, agrupar todos los registros por edificio
    todos_edificios = []
    
    for zona in df_clean['Zona'].unique():
        registros_zona = df_clean[df_clean['Zona'] == zona]
        self._log(f"🔍 Procesando zona {zona}: {len(registros_zona)} registros")
        
        # Agrupar por edificio en esta zona
        grupos_edificios = self._agrupar_por_edificio(registros_zona)
        
        for coords, personas in grupos_edificios:
            todos_edificios.append({
                'zona': zona,
                'coordenadas': coords,
                'personas': personas,
                'cantidad_personas': len(personas),
                'direccion': str(personas[0].get('DIRECCIÓN', 'N/A')) if personas else 'N/A'
            })
    
    self._log(f"🏗️ Total de edificios únicos encontrados: {len(todos_edificios)}")
    
    # 🎯 CREAR RUTAS DE 8 EDIFICIOS EXACTOS
    rutas_finales = []
    ruta_actual = []
    ruta_id = 1
    
    for edificio in todos_edificios:
        ruta_actual.append(edificio)
        
        # Cuando tenemos 8 edificios, crear la ruta
        if len(ruta_actual) == PARADAS_POR_RUTA:
            # Determinar zona predominante para la ruta
            zonas_en_ruta = [e['zona'] for e in ruta_actual]
            zona_predominante = max(set(zonas_en_ruta), key=zonas_en_ruta.count)
            
            # Crear la ruta
            self._log(f"🛣️ Creando Ruta {ruta_id}: {zona_predominante} ({len(ruta_actual)} edificios)")
            
            # Extraer índices para la ruta
            indices_ruta = []
            for edificio_data in ruta_actual:
                primera_persona = edificio_data['personas'][0]
                # Encontrar el índice original en el DataFrame
                for idx, row in df_clean.iterrows():
                    if str(row.get('DIRECCIÓN', '')).strip() == edificio_data['direccion']:
                        indices_ruta.append(idx)
                        break
            
            # Crear archivos de la ruta
            try:
                result = self._crear_ruta_archivos(zona_predominante, indices_ruta, ruta_id)
                if result:
                    rutas_finales.append(result)
                    self._log(f"✅ Ruta {ruta_id} creada: {result['paradas']} edificios")
                else:
                    self._log(f"❌ Error creando Ruta {ruta_id}")
            except Exception as e:
                self._log(f"❌ Error en Ruta {ruta_id}: {str(e)}")
            
            # Reiniciar para la siguiente ruta
            ruta_actual = []
            ruta_id += 1
    
    # 🎯 MANEJAR EDIFICIOS RESTANTES (si no completan 8)
    if ruta_actual:
        self._log(f"📦 Procesando edificios restantes: {len(ruta_actual)}")
        
        if len(ruta_actual) >= 4:  # Si hay al menos 4, crear ruta
            zonas_en_ruta = [e['zona'] for e in ruta_actual]
            zona_predominante = max(set(zonas_en_ruta), key=zonas_en_ruta.count) if zonas_en_ruta else 'OTRAS'
            
            self._log(f"🛣️ Creando Ruta final {ruta_id}: {zona_predominante} ({len(ruta_actual)} edificios)")
            
            indices_ruta = []
            for edificio_data in ruta_actual:
                primera_persona = edificio_data['personas'][0]
                for idx, row in df_clean.iterrows():
                    if str(row.get('DIRECCIÓN', '')).strip() == edificio_data['direccion']:
                        indices_ruta.append(idx)
                        break
            
            try:
                result = self._crear_ruta_archivos(zona_predominante, indices_ruta, ruta_id)
                if result:
                    rutas_finales.append(result)
                    self._log(f"✅ Ruta final {ruta_id}: {result['paradas']} edificios")
            except Exception as e:
                self._log(f"❌ Error en Ruta final {ruta_id}: {str(e)}")
        else:
            self._log(f"⚠️ Edificios restantes insuficientes: {len(ruta_actual)} (se descartan)")
    
    # GUARDAR RESULTADOS
    self.results = rutas_finales
    
    try:
        with open(self.CACHE_FILE, 'w') as f:
            json.dump(self.GEOCODE_CACHE, f)
        self._log("Geocode cache saved.")
    except Exception as e:
        self._log(f"Error saving cache: {str(e)}")
    
    if self.results:
        resumen_df = pd.DataFrame([{
            'Ruta': r['ruta_id'],
            'Zona': r['zona'],
            'Edificios': r['paradas'],
            'Personas': r['personas'],
            'Distancia_km': r['distancia'],
            'Tiempo_min': r['tiempo'],
            'Excel': os.path.basename(r['excel']),
            'Mapa': os.path.basename(r['mapa'])
        } for r in self.results])
        try:
            resumen_df.to_excel("RESUMEN_RUTAS.xlsx", index=False)
            self._log("Summary 'RESUMEN_RUTAS.xlsx' generated.")
        except Exception as e:
            self._log(f"Error generating summary: {str(e)}")
    
    total_routes_gen = len(self.results)
    total_edificios = sum(r['paradas'] for r in self.results) if self.results else 0
    total_personas = sum(r['personas'] for r in self.results) if self.results else 0
    
    self._log("CORE ROUTE GENERATION COMPLETED")
    self._log(f"FINAL SUMMARY: {total_routes_gen} routes, {total_edificios} edificios, {total_personas} personas")
    
    # 🎯 RESUMEN SOVIÉTICO
    rutas_perfectas = sum(1 for r in self.results if r['paradas'] == PARADAS_POR_RUTA)
    rutas_aceptables = sum(1 for r in self.results if r['paradas'] >= 4 and r['paradas'] < PARADAS_POR_RUTA)
    rutas_insuficientes = sum(1 for r in self.results if r['paradas'] < 4)
    
    self._log(f"📊 RESUMEN SOVIÉTICO: {rutas_perfectas} perfectas ({PARADAS_POR_RUTA} edificios), {rutas_aceptables} aceptables (4-7), {rutas_insuficientes} insuficientes (<4)")
    
    if rutas_perfectas > 0:
        self._log("🎯 OBJETIVO CUMPLIDO: Rutas con 8 edificios exactos creadas")
    
    return self.results
    
# =============================================================================
# CLASE INTERFAZ GRÁFICA (SistemaRutasGUI) - VERSIÓN CORREGIDA
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas PRO - DISTRIBUCIÓN FLEXIBLE")
        self.root.geometry("1100x800")
        self.root.configure(bg='#f0f0f0')
        
        self.api_key = "AIzaSyBeUr2C3SDkwY7zIrYcB6agDni9XDlWrFY"
        
        self.origen_coords = "19.4283717,-99.1430307"
        self.origen_name = "TSJCDMX - Niños Héroes 150"
        self.max_stops = 8
        self.archivo_excel = None
        self.df = None
        self.procesando = False
        self.columnas_seleccionadas = None
        self.gestor_telegram = GestorTelegram(self)
        
        self.sincronizando = False
        self.sincronizacion_thread = None
        
        self.setup_ui()
        
        self.root.after(1000, self.cargar_excel_desde_github)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="SISTEMA RUTAS PRO - DISTRIBUCIÓN FLEXIBLE", 
                 font=('Arial', 14, 'bold'), foreground='#2c3e50').pack()
        ttk.Label(header_frame, text="Mínimo 2 edificios por ruta - Distribución natural según datos disponibles", 
                 font=('Arial', 10), foreground='#7f8c8d').pack()
        
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding="15")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        file_frame = ttk.Frame(config_frame)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="Archivo Excel:", width=12).pack(side=tk.LEFT)
        self.file_label = ttk.Label(file_frame, text="No seleccionado", foreground='red')
        self.file_label.pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(file_frame, text="Examinar", command=self.cargar_excel).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="📊 LISTA COMPLETA", command=self.mostrar_lista_completa).pack(side=tk.LEFT, padx=(10, 0))
        
        api_frame = ttk.Frame(config_frame)
        api_frame.pack(fill=tk.X, pady=5)
        ttk.Label(api_frame, text="API Key Google:", width=12).pack(side=tk.LEFT)
        self.api_entry = ttk.Entry(api_frame, width=40, show="*")
        self.api_entry.pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(api_frame, text="Configurar", command=self.configurar_api).pack(side=tk.LEFT)
        
        params_frame = ttk.Frame(config_frame)
        params_frame.pack(fill=tk.X, pady=5)
        ttk.Label(params_frame, text="Máx por ruta:").pack(side=tk.LEFT)
        self.max_spinbox = ttk.Spinbox(params_frame, from_=1, to=20, width=5)
        self.max_spinbox.set(8)
        self.max_spinbox.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(params_frame, text="Origen:").pack(side=tk.LEFT)
        self.origen_entry = ttk.Entry(params_frame, width=30)
        self.origen_entry.insert(0, self.origen_coords)
        self.origen_entry.pack(side=tk.LEFT, padx=(5, 5))
        
        ttk.Label(params_frame, text="Nombre:").pack(side=tk.LEFT)
        self.nombre_entry = ttk.Entry(params_frame, width=25)
        self.nombre_entry.insert(0, self.origen_name)
        self.nombre_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        control_frame = ttk.LabelFrame(main_frame, text="Control de Procesamiento", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X)
        self.btn_generar = ttk.Button(btn_frame, text="GENERAR RUTAS FLEXIBLES", command=self.generar_rutas, state='disabled')
        self.btn_generar.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="ABRIR CARPETA MAPAS", command=lambda: self.abrir_carpeta('mapas_pro')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="ABRIR CARPETA EXCEL", command=lambda: self.abrir_carpeta('rutas_excel')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="VER RESUMEN", command=self.mostrar_resumen).pack(side=tk.LEFT, padx=(0, 10))
        
        self.btn_refresh = ttk.Button(btn_frame, text="REFRESH", command=self.refresh_sistema)
        self.btn_refresh.pack(side=tk.LEFT, padx=(0, 10))

        fotos_frame = ttk.LabelFrame(main_frame, text="Gestión de Fotos y Evidencias", padding="15")
        fotos_frame.pack(fill=tk.X, pady=(0, 10))
        
        fotos_btn_frame = ttk.Frame(fotos_frame)
        fotos_btn_frame.pack(fill=tk.X)
        
        ttk.Button(fotos_btn_frame, text="📸 VER FOTOS ENTREGAS", 
                  command=self.ver_fotos_entregas).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(fotos_btn_frame, text="🖼️ VER FOTOS REPORTES", 
                  command=self.ver_fotos_reportes).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(fotos_btn_frame, text="🔄 ACTUALIZAR FOTOS EXCEL", 
                  command=self.forzar_actualizacion_fotos).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(fotos_btn_frame, text="📊 VER ESTADO RUTAS", 
                  command=self.ver_estado_rutas).pack(side=tk.LEFT, padx=(0, 10))

        self.btn_sincronizacion_auto = ttk.Button(fotos_btn_frame, 
                                                text="🔄 INICIAR SINCRONIZACIÓN AUTO",
                                                command=self.toggle_sincronizacion_auto)
        self.btn_sincronizacion_auto.pack(side=tk.LEFT, padx=(0, 10))

        telegram_frame = ttk.Frame(control_frame)
        telegram_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(telegram_frame, text="📱 ASIGNAR RUTAS A REPARTIDORES", 
                  command=self.asignar_rutas_telegram).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(telegram_frame, text="🔄 ACTUALIZAR AVANCES", 
                  command=self.actualizar_avances).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(telegram_frame, text="🧪 SIMULAR ENTREGA", 
                  command=self.simular_entrega_prueba).pack(side=tk.LEFT, padx=(0, 10))
        
        self.progress_frame = ttk.Frame(control_frame)
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X)
        self.progress_label = ttk.Label(self.progress_frame, text="Listo para comenzar")
        self.progress_label.pack()
        
        log_frame = ttk.LabelFrame(main_frame, text="Log del Sistema", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def mostrar_lista_completa(self):
        """🎯 BOTÓN CORREGIDO: Muestra la lista completa de datos cargados"""
        try:
            if self.df is None or self.df.empty:
                messagebox.showinfo("Info", "No hay datos cargados")
                return
            
            lista_window = tk.Toplevel(self.root)
            lista_window.title("Lista Completa de Datos")
            lista_window.geometry("900x600")
            
            # Frame para controles
            control_frame = ttk.Frame(lista_window)
            control_frame.pack(fill=tk.X, padx=10, pady=10)
            
            ttk.Label(control_frame, text="Filtrar por zona:").pack(side=tk.LEFT)
            zonas = ['TODAS'] + list(self.df['Zona'].unique()) if 'Zona' in self.df.columns else ['TODAS']
            zona_var = tk.StringVar(value='TODAS')
            zona_combo = ttk.Combobox(control_frame, textvariable=zona_var, values=zonas, state="readonly")
            zona_combo.pack(side=tk.LEFT, padx=10)
            
            ttk.Label(control_frame, text="Buscar:").pack(side=tk.LEFT, padx=(20, 5))
            buscar_var = tk.StringVar()
            buscar_entry = ttk.Entry(control_frame, textvariable=buscar_var, width=20)
            buscar_entry.pack(side=tk.LEFT, padx=5)
            
            def actualizar_tabla():
                df_filtrado = self.df.copy()
                
                # Filtrar por zona
                if zona_var.get() != 'TODAS' and 'Zona' in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado['Zona'] == zona_var.get()]
                
                # Filtrar por búsqueda
                if buscar_var.get():
                    mask = df_filtrado.astype(str).apply(lambda x: x.str.contains(buscar_var.get(), case=False, na=False)).any(axis=1)
                    df_filtrado = df_filtrado[mask]
                
                # Actualizar treeview
                for item in tree.get_children():
                    tree.delete(item)
                
                for _, row in df_filtrado.iterrows():
                    valores = [str(row.get(col, '')) for col in tree['columns']]
                    tree.insert("", tk.END, values=valores)
                
                status_label.config(text=f"Mostrando {len(df_filtrado)} de {len(self.df)} registros")
            
            ttk.Button(control_frame, text="🔍 Aplicar Filtros", command=actualizar_tabla).pack(side=tk.LEFT, padx=10)
            ttk.Button(control_frame, text="📊 Exportar a Excel", command=lambda: self.exportar_lista_completa()).pack(side=tk.LEFT, padx=10)
            
            # Frame para tabla
            table_frame = ttk.Frame(lista_window)
            table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Treeview
            columns = list(self.df.columns)
            tree = ttk.Treeview(table_frame, columns=columns, show='headings')
            
            # Configurar columnas
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)
            
            # Scrollbars
            v_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=tree.yview)
            h_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=tree.xview)
            tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
            
            tree.grid(row=0, column=0, sticky='nsew')
            v_scroll.grid(row=0, column=1, sticky='ns')
            h_scroll.grid(row=1, column=0, sticky='ew')
            
            table_frame.grid_rowconfigure(0, weight=1)
            table_frame.grid_columnconfigure(0, weight=1)
            
            # Status
            status_label = ttk.Label(lista_window, text=f"Cargando {len(self.df)} registros...")
            status_label.pack(pady=5)
            
            # Cargar datos iniciales
            actualizar_tabla()
            
        except Exception as e:
            self.log(f"❌ Error mostrando lista completa: {str(e)}")
            messagebox.showerror("Error", f"No se pudo mostrar la lista:\n{str(e)}")

    def exportar_lista_completa(self):
        """Exporta la lista completa a Excel"""
        try:
            if self.df is None or self.df.empty:
                messagebox.showinfo("Info", "No hay datos para exportar")
                return
            
            archivo = filedialog.asksaveasfilename(
                title="Guardar lista completa",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")]
            )
            
            if archivo:
                self.df.to_excel(archivo, index=False)
                self.log(f"✅ Lista completa exportada: {os.path.basename(archivo)}")
                messagebox.showinfo("Éxito", f"Lista exportada a:\n{archivo}")
                
        except Exception as e:
            self.log(f"❌ Error exportando lista: {str(e)}")
            messagebox.showerror("Error", f"No se pudo exportar:\n{str(e)}")

    def cargar_excel_desde_github(self):
        """Cargar automáticamente el Excel de GitHub y configurar API"""
        try:
            self.api_entry.delete(0, tk.END)
            self.api_entry.insert(0, self.api_key)
            self.log("✅ API Key de Google Maps configurada automáticamente")
            
            excel_github = "Alcaldías.xlsx"
            
            if os.path.exists(excel_github):
                self.archivo_excel = excel_github
                df_completo = pd.read_excel(excel_github)
                
                self.file_label.config(text=excel_github, foreground='green')
                self.log(f"✅ Excel cargado automáticamente: {excel_github}")
                self.log(f"📊 Registros totales: {len(df_completo)}")
                
                self.df = df_completo
                
                col_direccion = self._detectar_columna_direccion(df_completo)
                col_nombre = self._detectar_columna_nombre(df_completo) 
                col_adscripcion = self._detectar_columna_adscripcion(df_completo)
                
                self.columnas_seleccionadas = {
                    'direccion': col_direccion,
                    'nombre': col_nombre,
                    'adscripcion': col_adscripcion
                }
                
                self.btn_generar.config(state='normal')
                self.log("🎉 ¡Sistema completamente listo!")
                self.log("💡 Haz clic en 'GENERAR RUTAS POR EDIFICIO'")
                
            else:
                self.log("📝 Excel no encontrado automáticamente")
                self.log("💡 Usa el botón 'Examinar' para cargar tu Excel manualmente")
                
        except Exception as e:
            self.log(f"❌ ERROR en carga automática: {str(e)}")

    def _detectar_columna_direccion(self, df):
        for col in df.columns:
            if any(p in str(col).lower() for p in ['dirección', 'direccion', 'dir', 'address']):
                return col
        return df.columns[0]

    def _detectar_columna_nombre(self, df):
        for col in df.columns:
            if any(p in str(col).lower() for p in ['nombre', 'name']):
                return col
        return None

    def _detectar_columna_adscripcion(self, df):
        for col in df.columns:
            if any(p in str(col).lower() for p in ['adscripción', 'adscripcion', 'cargo']):
                return col
        return None

    def log(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {mensaje}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def cargar_excel(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo Excel", 
            filetypes=[("Excel files", "*.xlsx")]
        )
        if archivo:
            try:
                self.log("🔄 Cargando Excel...")
                df_completo = pd.read_excel(archivo)
                self.archivo_excel = archivo
                
                nombre_archivo = os.path.basename(archivo)
                self.file_label.config(text=nombre_archivo, foreground='green')
                self.log(f"✅ Excel cargado: {nombre_archivo}")
                self.log(f"📊 Registros totales: {len(df_completo)}")
                
                self.df = df_completo
                
                col_direccion = self._detectar_columna_direccion(df_completo)
                col_nombre = self._detectar_columna_nombre(df_completo) 
                col_adscripcion = self._detectar_columna_adscripcion(df_completo)
                
                self.columnas_seleccionadas = {
                    'direccion': col_direccion,
                    'nombre': col_nombre,
                    'adscripcion': col_adscripcion
                }
                
                self.btn_generar.config(state='normal')
                self.log("🎉 ¡Excel listo para generar rutas!")
                
            except Exception as e:
                self.log(f"❌ ERROR: {str(e)}")
                messagebox.showerror("Error", f"No se pudo cargar el Excel:\n{str(e)}")

    def configurar_api(self):
        self.api_key = self.api_entry.get().strip()
        if self.api_key:
            self.log("✅ API Key configurada")
        else:
            self.log("⚠️ API Key vacía")

    def generar_rutas(self):
        if not self.archivo_excel:
            messagebox.showwarning("Advertencia", "Primero carga un archivo Excel")
            return
        if not self.api_entry.get().strip():
            messagebox.showwarning("API Key", "Configura tu Google Maps API Key")
            return
            
        self.api_key = self.api_entry.get().strip()
        self.origen_coords = self.origen_entry.get().strip()
        self.origen_name = self.nombre_entry.get().strip()
        self.max_stops = int(self.max_spinbox.get())
        
        self.procesando = True
        self.btn_generar.config(state='disabled')
        self.progress_bar.start(10)
        self.progress_label.config(text="Generando rutas por edificio...")
        
        thread = threading.Thread(target=self._procesar_rutas)
        thread.daemon = True
        thread.start()

    def _procesar_rutas(self):
        try:
            self.log("🚀 INICIANDO GENERACIÓN DE RUTAS POR EDIFICIO...")
            
            self._limpiar_carpetas_anteriores()
            
            df_completo = pd.read_excel(self.archivo_excel)
            self.log(f"📊 Total de registros: {len(df_completo)}")
            
            df_filtrado = df_completo
            self.log(f"✅ Procesando TODOS los registros: {len(df_filtrado)}")
            
            if len(df_filtrado) == 0:
                self.log("❌ No hay datos")
                return
            
            if hasattr(self, 'columnas_seleccionadas') and self.columnas_seleccionadas:
                columna_direccion = self.columnas_seleccionadas['direccion']
                columna_nombre = self.columnas_seleccionadas['nombre']
                columna_adscripcion = self.columnas_seleccionadas['adscripcion']
            else:
                columna_direccion = self._detectar_columna_direccion(df_filtrado)
                columna_nombre = self._detectar_columna_nombre(df_filtrado)
                columna_adscripcion = self._detectar_columna_adscripcion(df_filtrado)
            
            self.log(f"🎯 Usando columnas - Dirección: '{columna_direccion}', Nombre: '{columna_nombre}'")
            
            df_estandar = df_filtrado.copy()
            df_estandar['DIRECCIÓN'] = df_filtrado[columna_direccion].astype(str)
            df_estandar['NOMBRE'] = df_filtrado[columna_nombre].astype(str) if columna_nombre else 'Sin nombre'
            df_estandar['ADSCRIPCIÓN'] = df_filtrado[columna_adscripcion].astype(str) if columna_adscripcion else 'Sin adscripción'
            
            self.log(f"🎯 Procesando {len(df_estandar)} registros...")
            
            generator = CoreRouteGenerator(
                df=df_estandar,
                api_key=self.api_key,
                origen_coords=self.origen_coords,
                origen_name=self.origen_name,
                max_stops_per_route=self.max_stops
            )
            
            generator._log = self.log
            resultados = generator.generate_routes()
            
            if resultados:
                self.log(f"🎉 ¡{len(resultados)} RUTAS GENERADAS POR EDIFICIO!")
                self.log("📱 Las rutas están listas para asignar a repartidores via Telegram")
                messagebox.showinfo("Éxito", f"¡{len(resultados)} rutas generadas!\n\nCada edificio es una parada, sin importar cuántas personas tenga.")
            else:
                self.log("❌ No se pudieron generar rutas")
                
        except Exception as e:
            self.log(f"❌ ERROR: {str(e)}")
            messagebox.showerror("Error", f"Error durante el procesamiento:\n{str(e)}")
        finally:
            self.root.after(0, self._finalizar_procesamiento)

    def _finalizar_procesamiento(self):
        self.procesando = False
        self.btn_generar.config(state='normal')
        self.progress_bar.stop()
        self.progress_label.config(text="Procesamiento completado")

    def _limpiar_carpetas_anteriores(self):
        carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 'incidencias_trafico', 'fotos_acuses', 'fotos_entregas', 'fotos_reportes']
        for carpeta in carpetas:
            if os.path.exists(carpeta):
                self.log(f"Limpiando carpeta {carpeta}...")
                for archivo in os.listdir(carpeta):
                    ruta_archivo = os.path.join(carpeta, archivo)
                    try:
                        if os.path.isfile(ruta_archivo):
                            os.unlink(ruta_archivo)
                    except Exception as e:
                        self.log(f"Error eliminando {archivo}: {e}")
            else:
                os.makedirs(carpeta, exist_ok=True)
        if os.path.exists("RESUMEN_RUTAS.xlsx"):
            os.unlink("RESUMEN_RUTAS.xlsx")
        self.log("Limpieza completada")

    def abrir_carpeta(self, carpeta):
        if os.path.exists(carpeta):
            try:
                if sys.platform == "win32":
                    os.startfile(carpeta)
                else:
                    subprocess.Popen(['xdg-open', carpeta])
                self.log(f"Carpeta {carpeta} abierta")
            except Exception as e:
                self.log(f"Error: {e}")
        else:
            self.log(f"Carpeta {carpeta} no existe")

    def mostrar_resumen(self):
        if os.path.exists("RESUMEN_RUTAS.xlsx"):
            try:
                df_resumen = pd.read_excel("RESUMEN_RUTAS.xlsx")
                resumen_window = tk.Toplevel(self.root)
                resumen_window.title("Resumen de Rutas")
                tree = ttk.Treeview(resumen_window)
                tree["columns"] = list(df_resumen.columns)
                for col in df_resumen.columns:
                    tree.column(col, width=100)
                    tree.heading(col, text=col)
                for i, row in df_resumen.iterrows():
                    tree.insert("", tk.END, values=list(row))
                tree.pack(fill=tk.BOTH, expand=True)
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            messagebox.showinfo("Resumen", "Primero genera las rutas")

    def refresh_sistema(self):
        if messagebox.askyesno("REFRESH", "¿Borrar todo?\n\n• Mapas\n• Excels\n• Resumen\n• Log\n• Datos Telegram\n• Fotos"):
            self._limpiar_carpetas_anteriores()
            self.log_text.delete(1.0, tk.END)
            self.log("Sistema REFRESCADO")
            self.archivo_excel = None
            self.df = None
            self.columnas_seleccionadas = None
            self.file_label.config(text="No seleccionado", foreground='red')
            self.btn_generar.config(state='disabled')
            messagebox.showinfo("Listo", "¡Todo limpio!")

    def asignar_rutas_telegram(self):
        """Interfaz para asignar rutas a repartidores"""
        rutas_pendientes = self.gestor_telegram.obtener_rutas_pendientes()
        
        if not rutas_pendientes:
            messagebox.showinfo("Info", "No hay rutas pendientes para asignar")
            return
            
        asignar_window = tk.Toplevel(self.root)
        asignar_window.title("Asignar Rutas a Repartidores")
        asignar_window.geometry("700x500")
        
        ttk.Label(asignar_window, text="ASIGNAR RUTAS A REPARTIDORES", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        repartidores = ["Juan Pérez", "María García", "Carlos López", "Ana Martínez"]
        
        main_frame = ttk.Frame(asignar_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for i, ruta in enumerate(rutas_pendientes):
            frame_ruta = ttk.Frame(main_frame, relief='solid', padding=10)
            frame_ruta.pack(fill=tk.X, pady=5)
            
            ttk.Label(frame_ruta, 
                     text=f"Ruta {ruta['ruta_id']} - {ruta['zona']} ({ruta['progreso']} entregas)",
                     font=('Arial', 10, 'bold')).pack(anchor=tk.W)
            
            selector_frame = ttk.Frame(frame_ruta)
            selector_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(selector_frame, text="Asignar a:").pack(side=tk.LEFT)
            repartidor_var = tk.StringVar(value="Seleccionar repartidor")
            combo_repartidor = ttk.Combobox(selector_frame, textvariable=repartidor_var,
                                          values=repartidores, state="readonly")
            combo_repartidor.pack(side=tk.LEFT, padx=10)
            
            btn_asignar = ttk.Button(selector_frame, text="✅ ASIGNAR",
                                   command=lambda r=ruta, var=repartidor_var: 
                                   self._ejecutar_asignacion(r, var.get()))
            btn_asignar.pack(side=tk.LEFT, padx=10)
    
    def _ejecutar_asignacion(self, ruta, repartidor):
        if repartidor == "Seleccionar repartidor":
            messagebox.showwarning("Advertencia", "Selecciona un repartidor")
            return
            
        if self.gestor_telegram.asignar_ruta_repartidor(ruta['archivo'], repartidor):
            messagebox.showinfo("Éxito", f"Ruta {ruta['ruta_id']} asignada a {repartidor}")
        else:
            messagebox.showerror("Error", "No se pudo asignar la ruta")

    def actualizar_avances(self):
        """Muestra el progreso de las rutas desde Telegram"""
        avances = self.gestor_telegram.obtener_avances_recientes(15)
        
        self.log("📊 ACTUALIZANDO AVANCES DE RUTAS...")
        self.log(f"   Total de entregas registradas: {len(avances)}")
        
        for avance in avances[:8]:
            repartidor = avance.get('repartidor', 'N/A')
            persona = avance.get('persona_entregada', 'N/A')
            timestamp = avance.get('timestamp', '')[:16]
            tiene_foto = "📸" if avance.get('foto_local') or avance.get('foto_acuse') else ""
            self.log(f"   ✅ {repartidor} → {persona} [{timestamp}] {tiene_foto}")

    def ver_estado_rutas(self):
        """Muestra el estado actual de todas las rutas"""
        if not os.path.exists("rutas_telegram"):
            self.log("📋 No hay rutas generadas")
            return
            
        archivos_rutas = [f for f in os.listdir("rutas_telegram") if f.endswith('.json')]
        
        self.log("📋 ESTADO ACTUAL DE RUTAS:")
        for archivo in archivos_rutas:
            try:
                with open(f"rutas_telegram/{archivo}", 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                
                ruta_id = ruta_data.get('ruta_id')
                zona = ruta_data.get('zona')
                estado = ruta_data.get('estado', 'desconocido')
                repartidor = ruta_data.get('repartidor_asignado', 'Sin asignar')
                edificios_totales = len(ruta_data.get('paradas', []))
                edificios_entregados = len([p for p in ruta_data.get('paradas', []) 
                                        if p.get('estado') == 'entregado'])
                
                icono = "🟢" if estado == 'completada' else "🟡" if estado == 'en_progreso' else "🔴"
                
                self.log(f"   {icono} Ruta {ruta_id} ({zona}): {estado.upper()}")
                self.log(f"     👤 {repartidor} | 🏢 {edificios_entregados}/{edificios_totales} edificios")
                
            except Exception as e:
                self.log(f"   ❌ Error leyendo {archivo}: {str(e)}")

    def simular_entrega_prueba(self):
        """Simula una entrega para probar el sistema"""
        if not os.path.exists("rutas_telegram"):
            messagebox.showinfo("Info", "Primero genera rutas")
            return
            
        archivos_rutas = [f for f in os.listdir("rutas_telegram") if f.endswith('.json')]
        if not archivos_rutas:
            messagebox.showinfo("Info", "No hay rutas para simular")
            return
            
        with open(f"rutas_telegram/{archivos_rutas[0]}", 'r', encoding='utf-8') as f:
            ruta_data = json.load(f)
        
        primera_parada = ruta_data.get('paradas', [{}])[0]
        nombre_persona = primera_parada.get('nombre', 'Persona de Prueba')
        
        if self.gestor_telegram.simular_entrega_bot(
            ruta_data.get('ruta_id'), 
            'Repartidor Prueba', 
            nombre_persona
        ):
            self.log("🧪 SIMULACIÓN: Entrega completada exitosamente")
            self.log("💡 Revisa el Excel correspondiente para ver la actualización")
        else:
            self.log("❌ SIMULACIÓN: Error en la entrega")

    def ver_fotos_entregas(self):
        """Abre la carpeta de fotos de entregas"""
        carpeta_entregas = "fotos_entregas"
        if os.path.exists(carpeta_entregas) and os.listdir(carpeta_entregas):
            self.abrir_carpeta(carpeta_entregas)
            self.log(f"📁 Abriendo carpeta de fotos de entregas: {carpeta_entregas}")
        else:
            self.log("📁 No hay fotos de entregas aún")
            messagebox.showinfo("Fotos Entregas", "Aún no hay fotos de entregas descargadas")

    def ver_fotos_reportes(self):
        """Abre la carpeta de fotos de reportes"""
        carpeta_reportes = "fotos_reportes"
        if os.path.exists(carpeta_reportes) and os.listdir(carpeta_reportes):
            self.abrir_carpeta(carpeta_reportes)
            self.log(f"📁 Abriendo carpeta de fotos de reportes: {carpeta_reportes}")
        else:
            self.log("📁 No hay fotos de reportes aún")
            messagebox.showinfo("Fotos Reportes", "Aún no hay fotos de reportes/incidencias")

    def forzar_actualizacion_fotos(self):
        """Fuerza la actualización de todas las fotos pendientes en Excel"""
        try:
            self.log("🔄 FORZANDO ACTUALIZACIÓN DE FOTOS EN EXCEL...")
            
            actualizaciones = self.gestor_telegram.forzar_actualizacion_fotos()
            
            if actualizaciones > 0:
                messagebox.showinfo("Éxito", f"Se actualizaron {actualizaciones} archivos Excel con las fotos")
            else:
                messagebox.showinfo("Info", "No había archivos pendientes de actualizar")
                
        except Exception as e:
            self.log(f"❌ Error forzando actualización: {str(e)}")
            messagebox.showerror("Error", f"No se pudieron actualizar las fotos:\n{str(e)}")

    def toggle_sincronizacion_auto(self):
        """Activar/desactivar sincronización automática"""
        if not self.sincronizando:
            self.iniciar_sincronizacion_auto()
        else:
            self.detener_sincronizacion_auto()

    def iniciar_sincronizacion_auto(self):
        """Iniciar sincronización automática cada 5 minutos"""
        try:
            self.sincronizando = True
            self.btn_sincronizacion_auto.config(text="🔄 DETENER SINCRONIZACIÓN AUTO")
            self.log("🎯 SINCRONIZACIÓN AUTOMÁTICA ACTIVADA - Cada 5 minutos")
            
            self.sincronizacion_thread = threading.Thread(target=self._sincronizacion_background, daemon=True)
            self.sincronizacion_thread.start()
            
        except Exception as e:
            self.log(f"❌ Error iniciando sincronización automática: {str(e)}")

    def detener_sincronizacion_auto(self):
        """Detener sincronización automática"""
        try:
            self.sincronizando = False
            self.btn_sincronizacion_auto.config(text="🔄 INICIAR SINCRONIZACIÓN AUTO")
            self.log("⏹️ SINCRONIZACIÓN AUTOMÁTICA DETENIDA")
            
        except Exception as e:
            self.log(f"❌ Error deteniendo sincronización automática: {str(e)}")

    def _sincronizacion_background(self):
        """Sincronización en segundo plano cada 5 minutos"""
        ciclo = 0
        while self.sincronizando:
            try:
                ciclo += 1
                self.log(f"🔄 CICLO {ciclo}: Sincronizando automáticamente...")
                
                self.sincronizar_con_bot()
                
                for i in range(300):
                    if not self.sincronizando:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.log(f"❌ Error en ciclo {ciclo}: {str(e)}")
                for i in range(60):
                    if not self.sincronizando:
                        break
                    time.sleep(1)

    def sincronizar_con_bot(self):
        """Sincroniza todos los Excel con los datos más recientes del bot"""
        try:
            self.log("🔄 CONECTANDO CON BOT...")
            
            RAILWAY_URL = "https://monitoring-routes-pjcdmx-production.up.railway.app"
            
            health_response = requests.get(f"{RAILWAY_URL}/api/health", timeout=10)
            if health_response.status_code != 200:
                self.log("❌ Bot no responde - Verifica la conexión")
                return False
            
            self.log("📥 DESCARGANDO AVANCES PENDIENTES...")
            avances_response = requests.get(f"{RAILWAY_URL}/api/avances_pendientes", timeout=30)
            
            if avances_response.status_code == 200:
                datos = avances_response.json()
                avances = datos.get('avances', [])
                total_avances = len(avances)
                
                self.log(f"📊 AVANCES ENCONTRADOS: {total_avances}")
                
                if total_avances == 0:
                    self.log("✅ No hay avances pendientes por sincronizar")
                    return True
                
                actualizaciones_exitosas = 0
                
                for i, avance in enumerate(avances, 1):
                    self.log(f"📦 Procesando avance {i}/{total_avances}: {avance.get('persona_entregada', 'N/A')}")
                    
                    if self._procesar_avance_desde_bot(avance):
                        actualizaciones_exitosas += 1
                        
                        try:
                            avance_id = avance.get('_archivo', '').replace('.json', '')
                            requests.post(f"{RAILWAY_URL}/api/avances/{avance_id}/procesado", timeout=5)
                        except:
                            pass
                
                self.log(f"✅ SINCRONIZACIÓN COMPLETADA: {actualizaciones_exitosas} actualizaciones en Excel")
                
                if actualizaciones_exitosas > 0:
                    messagebox.showinfo("Sincronización Exitosa", 
                                      f"Se actualizaron {actualizaciones_exitosas} archivos Excel")
                
                return actualizaciones_exitosas > 0
            else:
                self.log("❌ Error obteniendo avances del bot")
                return False
                
        except Exception as e:
            self.log(f"❌ Error crítico en sincronización: {str(e)}")
            return False
        
    def _procesar_avance_desde_bot(self, avance):
        """Procesa un avance individual del bot y actualiza el Excel correspondiente"""
        try:
            ruta_id = avance.get('ruta_id')
            persona_entregada = avance.get('persona_entregada', '').strip()
            foto_ruta = avance.get('foto_local', '')
            repartidor = avance.get('repartidor', '')
            timestamp = avance.get('timestamp', '')
            
            if not persona_entregada or not ruta_id:
                self.log("⚠️ Avance incompleto - saltando")
                return False
            
            archivos_encontrados = []
            
            for archivo in os.listdir("rutas_excel"):
                if f"Ruta_{ruta_id}_" in archivo and archivo.endswith('.xlsx'):
                    archivos_encontrados.append(archivo)
            
            if not archivos_encontrados:
                self.log(f"❌ No se encontró Excel para Ruta {ruta_id}")
                return False
            
            excel_file = f"rutas_excel/{archivos_encontrados[0]}"
            
            df = pd.read_excel(excel_file)
            persona_encontrada = False
            
            for idx, fila in df.iterrows():
                nombre_en_excel = str(fila.get('Nombre', '')).strip().lower()
                persona_buscar = persona_entregada.lower()
                
                if (persona_buscar in nombre_en_excel or 
                    nombre_en_excel in persona_buscar or
                    self._coincidencia_flexible_nombres(persona_buscar, nombre_en_excel)):
                    
                    link_foto = f"=HIPERVINCULO(\"{foto_ruta}\", \"VER FOTO\")" if foto_ruta else "SIN FOTO"
                    df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                    df.at[idx, 'Repartidor'] = repartidor
                    df.at[idx, 'Foto_Acuse'] = link_foto
                    df.at[idx, 'Timestamp_Entrega'] = timestamp
                    df.at[idx, 'Estado'] = 'ENTREGADO'
                    
                    persona_encontrada = True
                    self.log(f"✅ Excel actualizado: {persona_entregada} → {nombre_en_excel}")
                    break
            
            if persona_encontrada:
                df.to_excel(excel_file, index=False)
                self.log(f"💾 Excel guardado: {os.path.basename(excel_file)}")
                return True
            else:
                self.log(f"⚠️ '{persona_entregada}' no encontrado en Ruta {ruta_id}")
                return False
                
        except Exception as e:
            self.log(f"❌ Error procesando avance: {str(e)}")
            return False

    def _coincidencia_flexible_nombres(self, nombre1, nombre2):
        """Coincidencia inteligente de nombres"""
        palabras_comunes = ['lic', 'lic.', 'ingeniero', 'ing', 'dr', 'doctor', 'mtro', 'maestro', 'sr', 'sra']
        
        n1_clean = ' '.join([p for p in nombre1.split() if p.lower() not in palabras_comunes])
        n2_clean = ' '.join([p for p in nombre2.split() if p.lower() not in palabras_comunes])
        
        palabras1 = set(n1_clean.lower().split())
        palabras2 = set(n2_clean.lower().split())
        
        return len(palabras1.intersection(palabras2)) >= 2

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 
                'incidencias_trafico', 'fotos_acuses', 'fotos_entregas', 'fotos_reportes']
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    root = tk.Tk()
    app = SistemaRutasGUI(root)
    root.mainloop()
