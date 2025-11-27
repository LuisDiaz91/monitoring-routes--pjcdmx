# sistema_rutas_completo_mejorado_final.py
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
import numpy as np

def convert_to_serializable(obj):
    """Convierte objetos pandas/numpy a tipos nativos de Python para JSON"""
    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.bool_, np.bool)):
        return bool(obj)
    elif isinstance(obj, (np.str_, np.string_)):
        return str(obj)
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(key): convert_to_serializable(value) for key, value in obj.items()}
    elif pd.isna(obj):  # Para valores NaN de pandas
        return None
    else:
        return obj
        
# =============================================================================
# CLASE CONEXIÓN CON BOT RAILWAY - MEJORADA (COMPLETA)
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
                json=ruta_data,  # Ya viene serializado desde _crear_ruta_archivos
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
# CLASE GESTOR TELEGRAM (GestorTelegram) - ACTUALIZADA
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
                            # Calcular progreso
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
            # Primero intentar obtener del bot en Railway
            avances_bot = self.conexion.obtener_avances_pendientes()
            
            # También buscar en archivos locales
            avances_locales = []
            if os.path.exists("avances_ruta"):
                archivos_avance = sorted(os.listdir("avances_ruta"), reverse=True)[:limite]
                
                for archivo in archivos_avance:
                    if archivo.endswith('.json'):
                        with open(f"avances_ruta/{archivo}", 'r', encoding='utf-8') as f:
                            avance_data = json.load(f)
                            avances_locales.append(avance_data)
            
            # Combinar y ordenar por timestamp
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
            
            # Obtener avances del bot
            avances = self.conexion.obtener_avances_pendientes()
            
            for avance in avances:
                if self._procesar_avance_desde_bot(avance):
                    actualizaciones += 1
                    # Marcar como procesado en el bot
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
            
            # Buscar archivo Excel de la ruta
            archivos_encontrados = []
            
            for archivo in os.listdir("rutas_excel"):
                if f"Ruta_{ruta_id}_" in archivo and archivo.endswith('.xlsx'):
                    archivos_encontrados.append(archivo)
            
            if not archivos_encontrados:
                self.gui.log(f"❌ No se encontró Excel para Ruta {ruta_id}")
                return False
            
            excel_file = f"rutas_excel/{archivos_encontrados[0]}"
            
            # Leer y actualizar Excel
            df = pd.read_excel(excel_file)
            persona_encontrada = False
            
            # Búsqueda flexible del nombre
            for idx, fila in df.iterrows():
                nombre_en_excel = str(fila.get('Nombre', '')).strip().lower()
                persona_buscar = persona_entregada.lower()
                
                # Buscar coincidencias (contiene o es similar)
                if (persona_buscar in nombre_en_excel or 
                    nombre_en_excel in persona_buscar or
                    self._coincidencia_flexible_nombres(persona_buscar, nombre_en_excel)):
                    
                    # ACTUALIZAR EXCEL CON LINK DE FOTO
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
                # Guardar cambios en Excel
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
        # Eliminar títulos comunes
        palabras_comunes = ['lic', 'lic.', 'ingeniero', 'ing', 'dr', 'doctor', 'mtro', 'maestro', 'sr', 'sra']
        
        n1_clean = ' '.join([p for p in nombre1.split() if p.lower() not in palabras_comunes])
        n2_clean = ' '.join([p for p in nombre2.split() if p.lower() not in palabras_comunes])
        
        # Coincidencia por palabras clave
        palabras1 = set(n1_clean.lower().split())
        palabras2 = set(n2_clean.lower().split())
        
        return len(palabras1.intersection(palabras2)) >= 2

    def simular_entrega_bot(self, ruta_id, repartidor, persona):
        """Simula una entrega para pruebas del sistema"""
        try:
            # Crear avance simulado
            avance_simulado = {
                'ruta_id': ruta_id,
                'repartidor': repartidor,
                'persona_entregada': persona,
                'timestamp': datetime.now().isoformat(),
                'foto_local': f"fotos_entregas/entrega_simulada_{ruta_id}.jpg",
                'tipo': 'entrega_simulada'
            }
            
            # Guardar avance localmente
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_avance = f"avances_ruta/avance_{timestamp}.json"
            
            with open(archivo_avance, 'w', encoding='utf-8') as f:
                json.dump(avance_simulado, f, indent=2, ensure_ascii=False)
            
            # Actualizar Excel correspondiente
            self._procesar_avance_desde_bot(avance_simulado)
            
            self.gui.log(f"🧪 Entrega simulada: {persona} por {repartidor}")
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error en simulación: {str(e)}")
            return False

# =============================================================================
# CLASE PRINCIPAL - MOTOR DE RUTAS (CoreRouteGenerator) - CORREGIDO
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

    def _agrupar_ubicaciones_similares(self, filas):
        """Agrupa personas en la misma ubicación física - VERSIÓN SUPER SIMPLE"""
        grupos = []
        
        for index, fila in filas.iterrows():
            direccion = str(fila.get('DIRECCIÓN', '')).strip()
            if not direccion or direccion in ['nan', '']:
                continue
                
            coords = self._geocode(direccion)
            if not coords:
                continue
                
            # Búsqueda simple
            encontrado = False
            for coord_exist, grupo_filas in grupos:
                if self._calcular_distancia(coords, coord_exist) < 0.2:
                    grupo_filas.append(fila)
                    encontrado = True
                    self._log(f"📍 Agrupando {fila.get('NOMBRE', '')[:20]}...")
                    break
            
            if not encontrado:
                grupos.append((coords, [fila]))
        
        return grupos
       
    def _calcular_distancia(self, coord1, coord2):
        """Calcula distancia en kilómetros entre dos coordenadas"""
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        
        # Fórmula Haversine
        R = 6371  # Radio de la Tierra en km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def _optimizar_ruta(self, grupos_ubicaciones):
        """Optimiza la ruta considerando grupos de ubicaciones - CORREGIDO"""
        if not grupos_ubicaciones:
            self._log("No hay grupos de ubicaciones para optimizar")
            return [], [], 0, 0, None
            
        coords_list = [grupo[0] for grupo in grupos_ubicaciones]  # coordenadas de cada grupo
        filas_agrupadas = []
        
        for coords, grupo_filas in grupos_ubicaciones:
            filas_agrupadas.append({
                'coordenadas': coords,
                'personas': grupo_filas,
                'cantidad_personas': len(grupo_filas)
            })
        
        if len(coords_list) < 2:
            # 🆕 CORRECCIÓN: Si solo hay una ubicación, igual crear la ruta
            self._log(f"⚠️ Solo una ubicación en esta ruta - Creando ruta con {len(filas_agrupadas[0]['personas'])} personas")
            return filas_agrupadas, coords_list, 30, 5, None  # Valores estimados
            
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
                
                # Reordenar según optimización
                filas_opt = [filas_agrupadas[i] for i in orden]
                coords_opt = [coords_list[i] for i in orden]
                
                return filas_opt, coords_opt, tiempo, dist, poly
            else:
                self._log(f"⚠️ Directions API error: {data.get('status')} - Usando orden original")
                # Fallback: usar orden original
                return filas_agrupadas, coords_list, 45, 8, None
        except Exception as e:
            self._log(f"⚠️ Error optimizing route: {str(e)} - Usando orden original")
            return filas_agrupadas, coords_list, 45, 8, None

def _crear_ruta_archivos(self, zona, indices, ruta_id):
    """Crea archivos de ruta - MEJORADO para manejar ubicaciones únicas"""
    # Primero agrupar las ubicaciones
    filas = self.df.loc[indices]
    grupos_ubicaciones = self._agrupar_ubicaciones_similares(filas)
    
    if len(grupos_ubicaciones) == 0:
        self._log(f"❌ No hay ubicaciones válidas para Ruta {ruta_id} - {zona}")
        return None
        
    # 🆕 CORRECCIÓN: Permitir rutas con una sola ubicación pero múltiples personas
    self._log(f"📍 Ruta {ruta_id}: {len(grupos_ubicaciones)} ubicaciones, {sum(len(g[1]) for g in grupos_ubicaciones)} personas")
        
    # Optimizar ruta (ahora maneja el caso de una sola ubicación)
    filas_opt, coords_opt, tiempo, dist, poly = self._optimizar_ruta(grupos_ubicaciones)
    
    os.makedirs("mapas_pro", exist_ok=True)
    os.makedirs("rutas_excel", exist_ok=True)
    
    # Crear Excel
    excel_data = []
    orden_parada = 1
    
    for grupo in filas_opt:
        coordenadas_grupo = grupo['coordenadas']
        personas_grupo = grupo['personas']
        cantidad_personas = grupo['cantidad_personas']
        
        for i, persona in enumerate(personas_grupo):
            link_foto_base = f"fotos_entregas/Ruta_{ruta_id}_Parada_{orden_parada}"
            if cantidad_personas > 1:
                link_foto_base += f"_Persona_{i+1}"
            
            link_foto = f"=HIPERVINCULO(\"{link_foto_base}.jpg\", \"📸 VER FOTO\")"
            
            excel_data.append({
                'Orden': orden_parada,
                'Sub_Orden': i + 1 if cantidad_personas > 1 else '',
                'Nombre': str(persona.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                'Dependencia': str(persona.get('ADSCRIPCIÓN', 'N/A')).strip(),
                'Dirección': str(persona.get('DIRECCIÓN', 'N/A')).strip(),
                'Personas_Misma_Ubicacion': cantidad_personas if i == 0 else '',
                'Acuse': '',
                'Repartidor': '',
                'Foto_Acuse': link_foto,
                'Timestamp_Entrega': '',
                'Estado': 'PENDIENTE',
                'Coordenadas': f"{coordenadas_grupo[0]},{coordenadas_grupo[1]}",
                'Notas': f"Grupo de {cantidad_personas} personas" if cantidad_personas > 1 and i == 0 else ''
            })
        
        orden_parada += 1
    
    excel_df = pd.DataFrame(excel_data)
    excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
    try:
        excel_df.to_excel(excel_file, index=False)
        self._log(f"✅ Generated Excel: {excel_file}")
    except Exception as e:
        self._log(f"❌ Error generating Excel: {str(e)}")
        
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
    
    # Ruta optimizada (solo si hay polyline)
    if poly:
        folium.PolyLine(polyline.decode(poly), color=color, weight=6, opacity=0.8).add_to(m)
    
    # Marcadores de paradas
    for i, (grupo, coord) in enumerate(zip(filas_opt, coords_opt), 1):
        cantidad_personas = grupo['cantidad_personas']
        primera_persona = grupo['personas'][0]
        nombre = str(primera_persona.get('NOMBRE', 'N/A')).split(',')[0]
        direccion = str(primera_persona.get('DIRECCIÓN', 'N/A'))[:70]
        
        if cantidad_personas > 1:
            popup_html = f"""
            <div style='font-family:Arial; width:300px;'>
                <b>📍 Parada #{i} ({cantidad_personas} personas)</b><br>
                <b>👥 {nombre} y {cantidad_personas-1} más</b><br>
                <small>{direccion}...</small>
            </div>
            """
            icon_color = 'orange'
            icono = 'users'
        else:
            popup_html = f"""
            <div style='font-family:Arial; width:250px;'>
                <b>📍 Parada #{i}</b><br>
                <b>👤 {nombre}</b><br>
                <small>{direccion}...</small>
            </div>
            """
            icon_color = 'red'
            icono = self.ICONOS.get(zona, 'circle')
        
        folium.Marker(
            coord,
            popup=popup_html,
            tooltip=f"Parada #{i} ({cantidad_personas} pers)" if cantidad_personas > 1 else f"Parada #{i}",
            icon=folium.Icon(color=icon_color, icon=icono, prefix='fa')
        ).add_to(m)
    
    # Panel de información
    total_personas = sum(grupo['cantidad_personas'] for grupo in filas_opt)
    total_paradas = len(filas_opt)
    
    info_panel_html = f"""
    <div style="position:fixed;top:10px;left:50px;z-index:1000;background:white;padding:15px;border-radius:10px;
                box-shadow:0 0 15px rgba(0,0,0,0.2);border:2px solid {color};font-family:Arial;max-width:350px;">
        <h4 style="margin:0 0 10px;color:#2c3e50;border-bottom:2px solid {color};padding-bottom:5px;">
            Ruta {ruta_id} - {zona}
        </h4>
        <small>
            <b>📍 Paradas:</b> {total_paradas} | <b>👥 Personas:</b> {total_personas}<br>
            <b>📏 Distancia:</b> {dist:.1f} km | <b>⏱️ Tiempo:</b> {tiempo:.0f} min<br>
            <a href="file://{os.path.abspath(excel_file)}" target="_blank">📊 Descargar Excel</a>
        </small>
    </div>
    """
    m.get_root().html.add_child(folium.Element(info_panel_html))
    
    mapa_file = f"mapas_pro/Ruta_{ruta_id}_{zona}.html"
    try:
        m.save(mapa_file)
        self._log(f"✅ Generated Map: {mapa_file}")
    except Exception as e:
        self._log(f"❌ Error generating map: {str(e)}")
        
    # GENERAR DATOS PARA TELEGRAM
    waypoints_param = "|".join([f"{lat},{lng}" for lat, lng in coords_opt])
    google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={self.origen_coords}&destination={self.origen_coords}&waypoints={waypoints_param}&travelmode=driving"
    
    # Preparar paradas para Telegram
    paradas_telegram = []
    orden_telegram = 1
    
    for grupo in filas_opt:
        coordenadas_grupo = grupo['coordenadas']
        personas_grupo = grupo['personas']
        cantidad_personas = grupo['cantidad_personas']
        
        for j, persona in enumerate(personas_grupo):
            link_foto_base = f"fotos_entregas/Ruta_{ruta_id}_Parada_{orden_telegram}"
            if cantidad_personas > 1:
                link_foto_base += f"_Persona_{j+1}"
            
            paradas_telegram.append({
                'orden': orden_telegram,
                'sub_orden': j + 1 if cantidad_personas > 1 else 1,
                'nombre': str(persona.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                'direccion': str(persona.get('DIRECCIÓN', 'N/A')).strip(),
                'dependencia': str(persona.get('ADSCRIPCIÓN', 'N/A')).strip(),
                'coords': f"{coordenadas_grupo[0]},{coordenadas_grupo[1]}",
                'estado': 'pendiente',
                'timestamp_entrega': None,
                'foto_acuse': link_foto_base + ".jpg",
                'es_grupo': cantidad_personas > 1,
                'total_en_grupo': cantidad_personas if j == 0 else None
            })
        
        orden_telegram += 1
    
    ruta_telegram = {
        'ruta_id': ruta_id,
        'zona': zona,
        'repartidor_asignado': None,
        'google_maps_url': google_maps_url,
        'paradas': paradas_telegram,
        'estadisticas': {
            'total_paradas': total_paradas,
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
        # 🆕 CORRECCIÓN: Convertir a tipos serializables antes de guardar
        ruta_telegram_serializable = convert_to_serializable(ruta_telegram)
        
        with open(telegram_file, 'w', encoding='utf-8') as f:
            json.dump(ruta_telegram_serializable, f, indent=2, ensure_ascii=False)
        self._log(f"📱 Datos para Telegram generados: {telegram_file}")
    except Exception as e:
        self._log(f"❌ Error guardando datos Telegram: {str(e)}")
    
    # ENVIAR RUTA AL BOT EN RAILWAY
    try:
        RAILWAY_URL = "https://monitoring-routes-pjcdmx-production.up.railway.app"
        conexion = ConexionBotRailway(RAILWAY_URL)
        
        if conexion.verificar_conexion():
            # 🆕 CORRECCIÓN: Usar la versión serializable también para el envío
            if conexion.enviar_ruta_bot(ruta_telegram_serializable):
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
        'paradas': total_paradas,
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
            
            # 🎯 FILTRO INTELIGENTE
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
        
        # 🆕 MOVER LA FUNCIÓN extraer_alcaldia FUERA o definirla correctamente
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
        
        # 🆕 CORRECCIÓN: Distribución simplificada de rutas
        subgrupos = {}
        for zona in df_clean['Zona'].unique():
            filas_zona = df_clean[df_clean['Zona'] == zona]
            grupos_ubicaciones = self._agrupar_ubicaciones_similares(filas_zona)
            
            rutas_zona = []
            ruta_actual = []
            
            for coords, grupo_filas in grupos_ubicaciones:
                # Si agregar este grupo excede el límite, crear nueva ruta
                if len(ruta_actual) + len(grupo_filas) > self.max_stops_per_route and ruta_actual:
                    rutas_zona.append(ruta_actual)
                    ruta_actual = []
                
                # Agregar todas las filas del grupo
                for fila in grupo_filas:
                    # Buscar el índice original en el DataFrame
                    mask = (
                        (self.df['NOMBRE'].astype(str) == str(fila.get('NOMBRE', ''))) & 
                        (self.df['DIRECCIÓN'].astype(str) == str(fila.get('DIRECCIÓN', '')))
                    )
                    match = self.df[mask]
                    if not match.empty:
                        ruta_actual.append(match.index[0])
            
            if ruta_actual:
                rutas_zona.append(ruta_actual)
            
            subgrupos[zona] = rutas_zona
            self._log(f"📍 {zona}: {len(grupos_ubicaciones)} ubicaciones → {len(rutas_zona)} rutas")
        
        self._log("Generating Optimized Routes...")
        self.results = []
        ruta_id = 1
        
        for zona in subgrupos.keys():
            for grupo in subgrupos[zona]:
                self._log(f"🔄 Processing Route {ruta_id}: {zona}")
                try:
                    result = self._crear_ruta_archivos(zona, grupo, ruta_id)
                    if result:
                        self.results.append(result)
                except Exception as e:
                    self._log(f"❌ Error in route {ruta_id}: {str(e)}")
                ruta_id += 1
        
        # Guardar cache y generar resumen
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.GEOCODE_CACHE, f)
            self._log("✅ Geocode cache saved.")
        except Exception as e:
            self._log(f"❌ Error saving cache: {str(e)}")
        
        if self.results:
            try:
                resumen_df = pd.DataFrame([{
                    'Ruta': r['ruta_id'],
                    'Zona': r['zona'],
                    'Paradas': r['paradas'],
                    'Personas': r['personas'],
                    'Distancia_km': r['distancia'],
                    'Tiempo_min': r['tiempo'],
                    'Excel': os.path.basename(r['excel']),
                    'Mapa': os.path.basename(r['mapa'])
                } for r in self.results])
                resumen_df.to_excel("RESUMEN_RUTAS.xlsx", index=False)
                self._log("✅ Summary 'RESUMEN_RUTAS.xlsx' generated.")
            except Exception as e:
                self._log(f"❌ Error generating summary: {str(e)}")
        
        total_routes = len(self.results)
        self._log(f"🎉 CORE ROUTE GENERATION COMPLETED: {total_routes} routes")
        return self.results

# =============================================================================
# CLASE INTERFAZ GRÁFICA (SistemaRutasGUI) - VERSIÓN FINAL
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas PRO Ultra HD - CON FOTOS Y AGRUPAMIENTO")
        self.root.geometry("1100x800")
        self.root.configure(bg='#f0f0f0')
        
        # 🆕 API Key automática
        self.api_key = "AIzaSyBeUr2C3SDkwY7zIrYcB6agDni9XDlWrFY"
        
        self.origen_coords = "19.4283717,-99.1430307"
        self.origen_name = "TSJCDMX - Niños Héroes 150"
        self.max_stops = 8
        self.archivo_excel = None
        self.df = None
        self.procesando = False
        self.columnas_seleccionadas = None
        self.gestor_telegram = GestorTelegram(self)
        
        # Variables para sincronización automática
        self.sincronizando = False
        self.sincronizacion_thread = None
        
        self.setup_ui()
        
        # Cargar Excel automáticamente al iniciar
        self.root.after(1000, self.cargar_excel_desde_github)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="SISTEMA RUTAS PRO ULTRA HD - CON FOTOS Y AGRUPAMIENTO", 
                 font=('Arial', 14, 'bold'), foreground='#2c3e50').pack()
        ttk.Label(header_frame, text="Gestión completa de entregas con evidencias fotográficas y agrupamiento inteligente", 
                 font=('Arial', 10), foreground='#7f8c8d').pack()
        
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding="15")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        file_frame = ttk.Frame(config_frame)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="Archivo Excel:", width=12).pack(side=tk.LEFT)
        self.file_label = ttk.Label(file_frame, text="No seleccionado", foreground='red')
        self.file_label.pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(file_frame, text="Examinar", command=self.cargar_excel).pack(side=tk.LEFT)
        
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
        self.btn_generar = ttk.Button(btn_frame, text="GENERAR RUTAS OPTIMIZADAS", command=self.generar_rutas, state='disabled')
        self.btn_generar.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="ABRIR CARPETA MAPAS", command=lambda: self.abrir_carpeta('mapas_pro')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="ABRIR CARPETA EXCEL", command=lambda: self.abrir_carpeta('rutas_excel')).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="VER RESUMEN", command=self.mostrar_resumen).pack(side=tk.LEFT, padx=(0, 10))
        
        self.btn_refresh = ttk.Button(btn_frame, text="REFRESH", command=self.refresh_sistema)
        self.btn_refresh.pack(side=tk.LEFT, padx=(0, 10))

        # Botones para gestión de fotos
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

        # Botón de sincronización automática
        self.btn_sincronizacion_auto = ttk.Button(fotos_btn_frame, 
                                                text="🔄 INICIAR SINCRONIZACIÓN AUTO",
                                                command=self.toggle_sincronizacion_auto)
        self.btn_sincronizacion_auto.pack(side=tk.LEFT, padx=(0, 10))

        # Botones para Telegram
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

    def cargar_excel_desde_github(self):
        """Cargar automáticamente el Excel de GitHub y configurar API"""
        try:
            # Configurar API Key en la interfaz
            self.api_entry.delete(0, tk.END)
            self.api_entry.insert(0, self.api_key)
            self.log("✅ API Key de Google Maps configurada automáticamente")
            
            # Cargar Excel automáticamente
            excel_github = "Alcaldías.xlsx"
            
            if os.path.exists(excel_github):
                self.archivo_excel = excel_github
                df_completo = pd.read_excel(excel_github)
                
                self.file_label.config(text=excel_github, foreground='green')
                self.log(f"✅ Excel cargado automáticamente: {excel_github}")
                self.log(f"📊 Registros totales: {len(df_completo)}")
                
                self.df = df_completo
                
                # Detección automática de columnas
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
                self.log("💡 Haz clic en 'GENERAR RUTAS OPTIMIZADAS'")
                
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
                
                # Detección de columnas
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
        self.progress_label.config(text="Generando rutas...")
        
        thread = threading.Thread(target=self._procesar_rutas)
        thread.daemon = True
        thread.start()

    def _procesar_rutas(self):
        try:
            self.log("🚀 INICIANDO GENERACIÓN DE RUTAS CON AGRUPAMIENTO...")
            
            # Limpiar carpetas
            self._limpiar_carpetas_anteriores()
            
            # Cargar datos
            df_completo = pd.read_excel(self.archivo_excel)
            self.log(f"📊 Total de registros: {len(df_completo)}")
            
            # Usar todos los registros
            df_filtrado = df_completo
            self.log(f"✅ Procesando TODOS los registros: {len(df_filtrado)}")
            
            if len(df_filtrado) == 0:
                self.log("❌ No hay datos")
                return
            
            # Usar columnas guardadas
            if hasattr(self, 'columnas_seleccionadas') and self.columnas_seleccionadas:
                columna_direccion = self.columnas_seleccionadas['direccion']
                columna_nombre = self.columnas_seleccionadas['nombre']
                columna_adscripcion = self.columnas_seleccionadas['adscripcion']
            else:
                # Fallback a detección automática
                columna_direccion = self._detectar_columna_direccion(df_filtrado)
                columna_nombre = self._detectar_columna_nombre(df_filtrado)
                columna_adscripcion = self._detectar_columna_adscripcion(df_filtrado)
            
            self.log(f"🎯 Usando columnas - Dirección: '{columna_direccion}', Nombre: '{columna_nombre}'")
            
            # Estandarizar
            df_estandar = df_filtrado.copy()
            df_estandar['DIRECCIÓN'] = df_filtrado[columna_direccion].astype(str)
            df_estandar['NOMBRE'] = df_filtrado[columna_nombre].astype(str) if columna_nombre else 'Sin nombre'
            df_estandar['ADSCRIPCIÓN'] = df_filtrado[columna_adscripcion].astype(str) if columna_adscripcion else 'Sin adscripción'
            
            self.log(f"🎯 Procesando {len(df_estandar)} registros...")

            # Generar rutas
            generator = CoreRouteGenerator(
                df=df_estandar,
                api_key=self.api_key,
                origen_coords=self.origen_coords,
                origen_name=self.origen_name,
                max_stops_per_route=self.max_stops
            )

            # 🚀 LLAMAR AL MÉTODO generate_routes()
            resultados = generator.generate_routes()
            
            if resultados:
                self.log(f"🎉 ¡{len(resultados)} RUTAS GENERADAS CON AGRUPAMIENTO!")
                self.log("📱 Las rutas están listas para asignar a repartidores via Telegram")
                messagebox.showinfo("Éxito", f"¡{len(resultados)} rutas generadas!\n\nAhora puedes asignarlas a repartidores usando el botón 'ASIGNAR RUTAS'")
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
        """Muestra el resumen de rutas generadas en una ventana"""
        if os.path.exists("RESUMEN_RUTAS.xlsx"):
            try:
                df_resumen = pd.read_excel("RESUMEN_RUTAS.xlsx")
                
                # Crear ventana de resumen
                resumen_window = tk.Toplevel(self.root)
                resumen_window.title("Resumen de Rutas Generadas")
                resumen_window.geometry("900x500")
                
                # Frame principal
                main_frame = ttk.Frame(resumen_window, padding="10")
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                # Título
                ttk.Label(main_frame, text="RESUMEN DE RUTAS GENERADAS", 
                         font=('Arial', 14, 'bold')).pack(pady=10)
                
                # Treeview para mostrar datos
                tree_frame = ttk.Frame(main_frame)
                tree_frame.pack(fill=tk.BOTH, expand=True)
                
                # Scrollbars
                v_scrollbar = ttk.Scrollbar(tree_frame)
                v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
                h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
                
                # Treeview
                tree = ttk.Treeview(tree_frame, 
                                   columns=list(df_resumen.columns),
                                   show='headings',
                                   yscrollcommand=v_scrollbar.set,
                                   xscrollcommand=h_scrollbar.set)
                
                # Configurar columnas
                for col in df_resumen.columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=100, minwidth=80)
                
                # Ajustar anchos específicos
                tree.column('Ruta', width=60)
                tree.column('Zona', width=100)
                tree.column('Paradas', width=70)
                tree.column('Personas', width=70)
                tree.column('Distancia_km', width=90)
                tree.column('Tiempo_min', width=80)
                tree.column('Excel', width=200)
                tree.column('Mapa', width=200)
                
                # Insertar datos
                for i, row in df_resumen.iterrows():
                    tree.insert("", tk.END, values=list(row))
                
                tree.pack(fill=tk.BOTH, expand=True)
                
                # Configurar scrollbars
                v_scrollbar.config(command=tree.yview)
                h_scrollbar.config(command=tree.xview)
                
                # Botón de cerrar
                ttk.Button(main_frame, text="Cerrar", 
                          command=resumen_window.destroy).pack(pady=10)
                
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el resumen:\n{str(e)}")
        else:
            messagebox.showinfo("Resumen", "Primero genera las rutas para ver el resumen")

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

    # Métodos para Telegram (se mantienen igual)
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
                paradas_totales = len(ruta_data.get('paradas', []))
                paradas_entregadas = len([p for p in ruta_data.get('paradas', []) 
                                        if p.get('estado') == 'entregado'])
                
                icono = "🟢" if estado == 'completada' else "🟡" if estado == 'en_progreso' else "🔴"
                
                self.log(f"   {icono} Ruta {ruta_id} ({zona}): {estado.upper()}")
                self.log(f"     👤 {repartidor} | 📦 {paradas_entregadas}/{paradas_totales} entregas")
                
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
    # Crear todas las carpetas necesarias
    carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 
                'incidencias_trafico', 'fotos_acuses', 'fotos_entregas', 'fotos_reportes']
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    root = tk.Tk()
    app = SistemaRutasGUI(root)
    root.mainloop()
