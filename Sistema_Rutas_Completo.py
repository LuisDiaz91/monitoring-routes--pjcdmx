# sistema_rutas_completo_mejorado.py
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

# =============================================================================
# CLASE CONEXIÓN CON BOT RAILWAY - MEJORADA
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

# =============================================================================
# CLASE GESTOR TELEGRAM - COMPLETAMENTE MEJORADA
# =============================================================================
class GestorTelegram:
    def __init__(self, gui_principal):
        self.gui = gui_principal
        self.carpetas = ['rutas_telegram', 'avances_ruta', 'incidencias_trafico', 'fotos_acuses', 'fotos_entregas', 'fotos_reportes']
        self._inicializar_carpetas()
        
    def _inicializar_carpetas(self):
        for carpeta in self.carpetas:
            os.makedirs(carpeta, exist_ok=True)
    
    def asignar_ruta_repartidor(self, archivo_ruta, repartidor):
        """Asigna una ruta específica a un repartidor"""
        try:
            with open(f"rutas_telegram/{archivo_ruta}", 'r', encoding='utf-8') as f:
                ruta_data = json.load(f)
            
            # Actualizar con info del repartidor
            ruta_data['repartidor_asignado'] = repartidor
            ruta_data['estado'] = 'asignada'
            ruta_data['timestamp_asignacion'] = datetime.now().isoformat()
            
            # Guardar archivo actualizado
            with open(f"rutas_telegram/{archivo_ruta}", 'w', encoding='utf-8') as f:
                json.dump(ruta_data, f, indent=2, ensure_ascii=False)
            
            self.gui.log(f"✅ Ruta {archivo_ruta} asignada a {repartidor}")
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error asignando ruta: {str(e)}")
            return False
    
    def procesar_entrega_repartidor(self, datos_entrega):
        """Procesa una entrega reportada por el bot CON FOTOS MEJORADO"""
        try:
            # 1. GUARDAR AVANCE
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archivo_avance = f"avances_ruta/entrega_{timestamp}.json"
            
            # 🆕 MEJORA: Procesar foto antes de guardar
            datos_entrega = self._procesar_foto_entrega(datos_entrega)
            
            with open(archivo_avance, 'w', encoding='utf-8') as f:
                json.dump(datos_entrega, f, indent=2, ensure_ascii=False)
            
            # 2. ACTUALIZAR EXCEL ORIGINAL CON FOTOS
            self._actualizar_excel_entrega(datos_entrega)
            
            # 3. ACTUALIZAR ESTADO DE RUTA
            self._actualizar_estado_ruta(datos_entrega)
            
            self.gui.log(f"📦 Entrega procesada: {datos_entrega.get('persona_entregada', 'N/A')}")
            if datos_entrega.get('foto_local'):
                self.gui.log(f"📸 Foto guardada: {datos_entrega.get('foto_local')}")
            
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error procesando entrega: {str(e)}")
            return False

    def _procesar_foto_entrega(self, datos_entrega):
        """Procesa y descarga la foto de entrega si viene de Telegram"""
        try:
            foto_url = datos_entrega.get('foto_acuse', '')
            
            if foto_url and foto_url.startswith('http'):
                # Generar nombre único para la foto
                ruta_id = datos_entrega.get('ruta_id', 'unknown')
                persona = datos_entrega.get('persona_entregada', 'unknown').replace(' ', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                nombre_archivo = f"entrega_{ruta_id}_{persona}_{timestamp}.jpg"
                ruta_foto_local = f"fotos_entregas/{nombre_archivo}"
                
                # Descargar foto
                response = requests.get(foto_url, timeout=30)
                if response.status_code == 200:
                    with open(ruta_foto_local, 'wb') as f:
                        f.write(response.content)
                    
                    # Actualizar datos con ruta local
                    datos_entrega['foto_local'] = ruta_foto_local
                    datos_entrega['foto_descargada'] = True
                    self.gui.log(f"✅ Foto descargada: {ruta_foto_local}")
                else:
                    self.gui.log(f"⚠️ No se pudo descargar foto: {foto_url}")
                    datos_entrega['foto_local'] = foto_url  # Mantener URL original
            
            return datos_entrega
            
        except Exception as e:
            self.gui.log(f"⚠️ Error procesando foto: {str(e)}")
            return datos_entrega

    def _actualizar_excel_entrega(self, datos_entrega):
        """Actualiza el Excel original con la entrega Y la foto - MEJORADO"""
        try:
            ruta_id = datos_entrega.get('ruta_id')
            persona_entregada = datos_entrega.get('persona_entregada')
            foto_acuse = datos_entrega.get('foto_local') or datos_entrega.get('foto_acuse', '')
            repartidor = datos_entrega.get('repartidor', '')
            timestamp = datos_entrega.get('timestamp', '')
            
            # Buscar archivo de ruta correspondiente
            archivos_ruta = [f for f in os.listdir('rutas_telegram') 
                           if f.startswith(f'Ruta_{ruta_id}_')]
            
            if not archivos_ruta:
                self.gui.log(f"❌ No se encontró archivo de ruta para Ruta_{ruta_id}")
                return False
                
            with open(f'rutas_telegram/{archivos_ruta[0]}', 'r', encoding='utf-8') as f:
                ruta_data = json.load(f)
            
            excel_file = ruta_data.get('excel_original')
            if not excel_file or not os.path.exists(excel_file):
                self.gui.log(f"❌ Archivo Excel no encontrado: {excel_file}")
                return False
            
            # Leer y actualizar Excel
            df = pd.read_excel(excel_file)
            
            # 🆕 MEJORA: Buscar la fila correspondiente de manera más inteligente
            persona_encontrada = False
            for idx, fila in df.iterrows():
                nombre_celda = str(fila.get('Nombre', '')).strip().lower()
                persona_buscar = persona_entregada.strip().lower()
                
                # Búsqueda flexible: contiene o es similar
                if (persona_buscar in nombre_celda or 
                    nombre_celda in persona_buscar or
                    self._nombres_similares(persona_buscar, nombre_celda)):
                    
                    # 🆕 ACTUALIZACIÓN COMPLETA
                    df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                    df.at[idx, 'Repartidor'] = repartidor
                    df.at[idx, 'Foto_Acuse'] = foto_acuse
                    df.at[idx, 'Timestamp_Entrega'] = timestamp
                    df.at[idx, 'Estado'] = 'ENTREGADO'
                    
                    # 🆕 Si existe columna de coordenadas, actualizar
                    if 'Coordenadas' in df.columns:
                        coords = datos_entrega.get('coords_entrega', '')
                        if coords:
                            df.at[idx, 'Coordenadas'] = coords
                    
                    persona_encontrada = True
                    self.gui.log(f"📊 Excel actualizado para: {persona_entregada}")
                    break
            
            if not persona_encontrada:
                self.gui.log(f"⚠️ Persona no encontrada en Excel: {persona_entregada}")
                # 🆕 Agregar como nueva fila al final
                nueva_fila = {
                    'Nombre': persona_entregada,
                    'Acuse': f"✅ ENTREGADO - {timestamp}",
                    'Repartidor': repartidor,
                    'Foto_Acuse': foto_acuse,
                    'Timestamp_Entrega': timestamp,
                    'Estado': 'ENTREGADO'
                }
                df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
                self.gui.log(f"📝 Nueva fila agregada para: {persona_entregada}")
            
            # Guardar Excel actualizado
            df.to_excel(excel_file, index=False)
            self.gui.log(f"💾 Excel guardado: {os.path.basename(excel_file)}")
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error crítico actualizando Excel: {str(e)}")
            return False

    def _nombres_similares(self, nombre1, nombre2):
        """Verifica si dos nombres son similares (para matching flexible)"""
        # Eliminar títulos y palabras comunes
        palabras_comunes = ['lic', 'lic.', 'ingeniero', 'ing', 'dr', 'doctor', 'mtro', 'maestro']
        n1 = ' '.join([p for p in nombre1.split() if p.lower() not in palabras_comunes])
        n2 = ' '.join([p for p in nombre2.split() if p.lower() not in palabras_comunes])
        
        # Verificar si comparten al menos 2 palabras
        palabras1 = set(n1.lower().split())
        palabras2 = set(n2.lower().split())
        return len(palabras1.intersection(palabras2)) >= 2

    def _actualizar_estado_ruta(self, datos_entrega):
        """Actualiza el estado de la ruta en el archivo JSON"""
        try:
            ruta_id = datos_entrega.get('ruta_id')
            archivos_ruta = [f for f in os.listdir('rutas_telegram') 
                           if f.startswith(f'Ruta_{ruta_id}_')]
            
            if not archivos_ruta:
                return False
                
            with open(f'rutas_telegram/{archivos_ruta[0]}', 'r', encoding='utf-8') as f:
                ruta_data = json.load(f)
            
            # Actualizar parada completada
            persona_entregada = datos_entrega.get('persona_entregada')
            for parada in ruta_data.get('paradas', []):
                if persona_entregada.lower() in parada.get('nombre', '').lower():
                    parada['estado'] = 'entregado'
                    parada['timestamp_entrega'] = datos_entrega.get('timestamp')
                    parada['foto_acuse'] = datos_entrega.get('foto_local') or datos_entrega.get('foto_acuse', '')
                    parada['repartidor'] = datos_entrega.get('repartidor', '')
                    break
            
            # Verificar si todas las paradas están completadas
            paradas_pendientes = [p for p in ruta_data.get('paradas', []) 
                                if p.get('estado') != 'entregado']
            
            if not paradas_pendientes:
                ruta_data['estado'] = 'completada'
                ruta_data['timestamp_completada'] = datetime.now().isoformat()
                self.gui.log(f"🎉 ¡Ruta {ruta_id} COMPLETADA!")
            else:
                ruta_data['estado'] = 'en_progreso'
                progreso = len([p for p in ruta_data.get('paradas', []) if p.get('estado') == 'entregado'])
                total = len(ruta_data.get('paradas', []))
                self.gui.log(f"📊 Progreso Ruta {ruta_id}: {progreso}/{total} entregas")
            
            # Guardar archivo actualizado
            with open(f'rutas_telegram/{archivos_ruta[0]}', 'w', encoding='utf-8') as f:
                json.dump(ruta_data, f, indent=2, ensure_ascii=False)
                
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error actualizando estado de ruta: {str(e)}")
            return False
    
    def procesar_incidencia(self, datos_incidencia):
        """Procesa una incidencia reportada por el bot CON FOTOS SEPARADAS"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            tipo_incidencia = datos_incidencia.get('tipo', 'incidencia')
            
            # 🆕 NUEVO: Procesar fotos de reportes
            datos_incidencia = self._procesar_fotos_reporte(datos_incidencia)
            
            # Guardar metadata de la incidencia
            archivo_incidencia = f"incidencias_trafico/incidencia_{timestamp}.json"
            with open(archivo_incidencia, 'w', encoding='utf-8') as f:
                json.dump(datos_incidencia, f, indent=2, ensure_ascii=False)
            
            self.gui.log(f"🚨 Incidencia reportada: {tipo_incidencia} con {len(datos_incidencia.get('fotos_locales', []))} fotos")
            return True
            
        except Exception as e:
            self.gui.log(f"❌ Error procesando incidencia: {str(e)}")
            return False

    def _procesar_fotos_reporte(self, datos_incidencia):
        """Procesa y descarga fotos de reportes/incidencias"""
        try:
            fotos_urls = datos_incidencia.get('fotos', [])
            fotos_locales = []
            
            for i, foto_url in enumerate(fotos_urls):
                if foto_url.startswith('http'):
                    # Generar nombre único
                    tipo = datos_incidencia.get('tipo', 'reporte').replace(' ', '_')
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_foto = f"reporte_{tipo}_{timestamp}_{i+1}.jpg"
                    ruta_foto_local = f"fotos_reportes/{nombre_foto}"
                    
                    # Descargar foto
                    response = requests.get(foto_url, timeout=30)
                    if response.status_code == 200:
                        with open(ruta_foto_local, 'wb') as f:
                            f.write(response.content)
                        
                        fotos_locales.append(ruta_foto_local)
                        self.gui.log(f"📸 Foto de reporte guardada: {ruta_foto_local}")
                    else:
                        self.gui.log(f"⚠️ No se pudo descargar foto de reporte: {foto_url}")
                        fotos_locales.append(foto_url)  # Mantener URL original
            
            # Actualizar datos con rutas locales
            datos_incidencia['fotos_locales'] = fotos_locales
            return datos_incidencia
            
        except Exception as e:
            self.gui.log(f"⚠️ Error procesando fotos de reporte: {str(e)}")
            return datos_incidencia
    
    def obtener_rutas_pendientes(self):
        """Obtiene lista de rutas disponibles para asignar"""
        rutas = []
        for archivo in os.listdir('rutas_telegram'):
            if archivo.endswith('.json'):
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                    if ruta_data.get('estado') in ['pendiente', 'asignada']:
                        paradas_entregadas = len([p for p in ruta_data.get('paradas', []) 
                                                if p.get('estado') == 'entregado'])
                        rutas.append({
                            'archivo': archivo,
                            'ruta_id': ruta_data.get('ruta_id'),
                            'zona': ruta_data.get('zona'),
                            'paradas_total': len(ruta_data.get('paradas', [])),
                            'paradas_entregadas': paradas_entregadas,
                            'repartidor': ruta_data.get('repartidor_asignado'),
                            'estado': ruta_data.get('estado'),
                            'progreso': f"{paradas_entregadas}/{len(ruta_data.get('paradas', []))}"
                        })
        return rutas
    
    def obtener_avances_recientes(self, limite=10):
        """Obtiene avances recientes para mostrar en GUI"""
        avances = []
        archivos = sorted(os.listdir('avances_ruta'), reverse=True)[:limite]
        
        for archivo in archivos:
            try:
                with open(f'avances_ruta/{archivo}', 'r') as f:
                    datos = json.load(f)
                    avances.append(datos)
            except:
                continue
        return avances

    def simular_entrega_bot(self, ruta_id, repartidor, persona_entregada):
        """Simula una entrega del bot para pruebas CON FOTO"""
        # Crear una foto de prueba (puede ser un archivo vacío o una imagen de prueba)
        os.makedirs('fotos_entregas', exist_ok=True)
        foto_prueba = f"fotos_entregas/entrega_prueba_{ruta_id}.jpg"
        
        # Crear archivo de prueba si no existe
        if not os.path.exists(foto_prueba):
            with open(foto_prueba, 'w') as f:
                f.write("Foto de prueba - Simulación")
        
        datos_entrega = {
            'ruta_id': ruta_id,
            'repartidor': repartidor,
            'persona_entregada': persona_entregada,
            'foto_acuse': foto_prueba,
            'foto_local': foto_prueba,
            'timestamp': datetime.now().isoformat(),
            'coords_entrega': '19.4326077,-99.133208',
            'comentarios': 'Entregado en recepción - SIMULADO'
        }
        return self.procesar_entrega_repartidor(datos_entrega)

    def forzar_actualizacion_fotos(self):
        """Fuerza la actualización de todas las fotos pendientes en Excel"""
        try:
            self.gui.log("🔄 FORZANDO ACTUALIZACIÓN DE FOTOS EN EXCEL...")
            
            # Buscar todas las entregas procesadas
            avances = self.obtener_avances_recientes(limite=100)
            actualizaciones = 0
            
            for avance in avances:
                if self._actualizar_excel_entrega(avance):
                    actualizaciones += 1
            
            self.gui.log(f"✅ {actualizaciones} archivos Excel actualizados con fotos")
            return actualizaciones
            
        except Exception as e:
            self.gui.log(f"❌ Error forzando actualización: {str(e)}")
            return 0

# =============================================================================
# CLASE PRINCIPAL - MOTOR DE RUTAS (CoreRouteGenerator) - MANTENIDO
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

    def _optimizar_ruta(self, indices):
        filas = self.df.loc[indices]
        coords_list = []
        filas_validas = []
        for _, fila in filas.iterrows():
            if 'DIRECCIÓN' in fila and pd.notna(fila['DIRECCIÓN']):
                c = self._geocode(fila['DIRECCIÓN'])
                if c:
                    coords_list.append(c)
                    filas_validas.append(fila)
            else:
                self._log(f"Skipping row {fila.name} due to missing or invalid 'DIRECCIÓN'.")
        if len(coords_list) < 2:
            self._log(f"Not enough valid coordinates (found {len(coords_list)}) for route optimization. Skipping.")
            return filas_validas, [], 0, 0, None
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
                filas_opt = [filas_validas[i] for i in orden]
                coords_opt = [coords_list[i] for i in orden]
                return filas_opt, coords_opt, tiempo, dist, poly
            else:
                self._log(f"Directions API error: {data.get('status')}")
                return filas_validas, [], 0, 0, None
        except Exception as e:
            self._log(f"Error optimizing route: {str(e)}")
            return filas_validas, [], 0, 0, None

    def _crear_ruta_archivos(self, zona, indices, ruta_id):
        filas_opt, coords_opt, tiempo, dist, poly = self._optimizar_ruta(indices)
        if len(filas_opt) == 0:
            self._log(f"No valid stops for Route {ruta_id} - {zona}.")
            return None
        os.makedirs("mapas_pro", exist_ok=True)
        os.makedirs("rutas_excel", exist_ok=True)
        
        # 🆕 EXCEL MEJORADO CON COLUMNAS PARA FOTOS
        excel_data = []
        for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1):
            excel_data.append({
                'Orden': i,
                'Nombre': str(fila.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                'Dependencia': str(fila.get('ADSCRIPCIÓN', 'N/A')).strip(),
                'Dirección': str(fila.get('DIRECCIÓN', 'N/A')).strip(),
                'Acuse': '',
                'Repartidor': '',
                'Foto_Acuse': '',
                'Timestamp_Entrega': '',
                'Estado': 'PENDIENTE',
                'Coordenadas': f"{coord[0]},{coord[1]}"
            })
        excel_df = pd.DataFrame(excel_data)
        excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
        try:
            excel_df.to_excel(excel_file, index=False)
            self._log(f"Generated Excel: {excel_file}")
        except Exception as e:
            self._log(f"Error generating Excel: {str(e)}")
            
        map_origin_coords = list(map(float, self.origen_coords.split(',')))
        m = folium.Map(location=map_origin_coords, zoom_start=12, tiles='CartoDB positron')
        color = self.COLORES.get(zona, 'gray')
        folium.Marker(
            map_origin_coords,
            popup=f"<b>{self.origen_name}</b>",
            icon=folium.Icon(color='green', icon='balance-scale', prefix='fa')
        ).add_to(m)
        if poly:
            folium.PolyLine(polyline.decode(poly), color=color, weight=6, opacity=0.8).add_to(m)
        for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1):
            nombre = str(fila.get('NOMBRE', 'N/A')).split(',')[0]
            cargo = str(fila.get('ADSCRIPCIÓN', 'N/A'))[:50]
            direccion = str(fila.get('DIRECCIÓN', 'N/A'))[:70]
            popup_html = f"<div style='font-family:Arial; width:250px;'><b>#{i} {nombre}</b><br><i>{cargo}</i><br><small>{direccion}...</small></div>"
            folium.Marker(
                coord,
                popup=popup_html,
                tooltip=f"#{i} {nombre}",
                icon=folium.Icon(color='red', icon=self.ICONOS.get(zona, 'circle'), prefix='fa')
            ).add_to(m)
        info_panel_html = f"""
        <div style="position:fixed;top:10px;left:50px;z-index:1000;background:white;padding:15px;border-radius:10px;
                    box-shadow:0 0 15px rgba(0,0,0,0.2);border:2px solid {color};font-family:Arial;max-width:320px;">
            <h4 style="margin:0 0 10px;color:#2c3e50;border-bottom:2px solid {color};padding-bottom:5px;">
                Ruta {ruta_id} - {zona}
            </h4>
            <small>
                <b>Paradas:</b> {len(filas_opt)} | <b>{dist:.1f} km</b> | <b>{tiempo:.0f} min</b><br>
                <a href="file://{os.path.abspath(excel_file)}" target="_blank">Descargar Excel</a>
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
        waypoints = "|".join([f"{lat},{lng}" for lat, lng in coords_opt])
        google_maps_url = f"https://www.google.com/maps/dir/{self.origen_coords}/{waypoints}"
        
        ruta_telegram = {
            'ruta_id': ruta_id,
            'zona': zona,
            'repartidor_asignado': None,
            'google_maps_url': google_maps_url,
            'paradas': [
                {
                    'orden': i,
                    'nombre': str(fila.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                    'direccion': str(fila.get('DIRECCIÓN', 'N/A')).strip(),
                    'dependencia': str(fila.get('ADSCRIPCIÓN', 'N/A')).strip(),
                    'coords': f"{coord[0]},{coord[1]}",
                    'estado': 'pendiente',
                    'timestamp_entrega': None,
                    'foto_acuse': None
                }
                for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1)
            ],
            'estadisticas': {
                'total_paradas': len(filas_opt),
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
            'paradas': len(filas_opt),
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
        
        subgrupos = {}
        for zona in df_clean['Zona'].unique():
            dirs = df_clean[df_clean['Zona'] == zona].index.tolist()
            subgrupos[zona] = [dirs[i:i+self.max_stops_per_route] for i in range(0, len(dirs), self.max_stops_per_route)]
            self._log(f"{zona}: {len(dirs)} addresses to {len(subgrupos[zona])} routes")
        
        self._log("Generating Optimized Routes...")
        self.results = []
        ruta_id = 1
        total_routes_to_process = sum(len(grupos) for grupos in subgrupos.values())
        
        for zona in subgrupos.keys():
            for i, grupo in enumerate(subgrupos[zona]):
                self._log(f"Processing Route {ruta_id} of {total_routes_to_process}: {zona}")
                try:
                    result = self._crear_ruta_archivos(zona, grupo, ruta_id)
                    if result:
                        self.results.append(result)
                except Exception as e:
                    self._log(f"Error in route {ruta_id}: {str(e)}")
                ruta_id += 1
        
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
                'Paradas': r['paradas'],
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
        total_paradas = sum(r['paradas'] for r in self.results) if self.results else 0
        total_distancia = sum(r['distancia'] for r in self.results) if self.results else 0
        total_tiempo = sum(r['tiempo'] for r in self.results) if self.results else 0
        
        self._log("CORE ROUTE GENERATION COMPLETED")
        self._log(f"FINAL SUMMARY: {total_routes_gen} routes, {total_paradas} stops")
        return self.results

# =============================================================================
# CLASE INTERFAZ GRÁFICA (SistemaRutasGUI) - COMPLETAMENTE MEJORADA
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas PRO Ultra HD - CON FOTOS")
        self.root.geometry("1100x800")
        self.root.configure(bg='#f0f0f0')
        
        # 🆕 NUEVO: API Key automática AQUÍ
        self.api_key = "AIzaSyBeUr2C3SDkwY7zIrYcB6agDni9XDlWrFY"
        
        self.origen_coords = "19.4283717,-99.1430307"
        self.origen_name = "TSJCDMX - Niños Héroes 150"
        self.max_stops = 8
        self.archivo_excel = None
        self.df = None
        self.procesando = False
        self.columnas_seleccionadas = None
        self.gestor_telegram = GestorTelegram(self)
        
        self.setup_ui()
        
        # 🆕 NUEVO: Solo UNA llamada aquí
        self.root.after(1000, self.cargar_excel_desde_github)
    
    def cargar_excel_desde_github(self):
        """Cargar automáticamente el Excel de GitHub y configurar API"""
        try:
            # 1. 🆕 CONFIGURAR API KEY EN LA INTERFAZ
            self.api_entry.delete(0, tk.END)
            self.api_entry.insert(0, self.api_key)
            self.log("✅ API Key de Google Maps configurada automáticamente")
            
            # 2. CARGAR EXCEL AUTOMÁTICAMENTE
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

    def _filtrar_filas_formato(self, df):
        """
        FILTRO SUPER RELAJADO - solo elimina filas completamente vacías
        """
        self.log("🔧 Usando filtro mínimo...")
        
        filas_validas = []
        for idx, fila in df.iterrows():
            # Solo eliminar filas completamente vacías o con solo espacios
            contenido = ' '.join([str(x) for x in fila.values if pd.notna(x)]).strip()
            if contenido and len(contenido) > 2:  # Mínimo 3 caracteres
                filas_validas.append(idx)
        
        self.log(f"📊 Después de filtro mínimo: {len(filas_validas)} de {len(df)}")
        return df.loc[filas_validas]

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

    def _seleccionar_columnas_manual(self, df):
        """
        Si la detección automática falla, pregunta al usuario
        """
        self.log("🎯 Detección automática falló, selecciona columnas manualmente:")
        
        # Mostrar primeras filas para referencia
        self.log("📋 Primeras filas del Excel:")
        for i in range(min(3, len(df))):
            self.log(f"   Fila {i}: {dict(df.iloc[i])}")
        
        # Crear ventana de selección
        seleccion_window = tk.Toplevel(self.root)
        seleccion_window.title("Seleccionar Columnas")
        seleccion_window.geometry("500x300")
        
        ttk.Label(seleccion_window, text="Selecciona las columnas correspondientes:", 
                  font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Selector para dirección
        frame_dir = ttk.Frame(seleccion_window)
        frame_dir.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame_dir, text="Columna de DIRECCIÓN:", width=20).pack(side=tk.LEFT)
        dir_var = tk.StringVar(value=df.columns[0])
        dir_combo = ttk.Combobox(frame_dir, textvariable=dir_var, values=list(df.columns), state="readonly")
        dir_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Selector para nombre
        frame_nom = ttk.Frame(seleccion_window)
        frame_nom.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame_nom, text="Columna de NOMBRE:", width=20).pack(side=tk.LEFT)
        nom_var = tk.StringVar(value=df.columns[1] if len(df.columns) > 1 else df.columns[0])
        nom_combo = ttk.Combobox(frame_nom, textvariable=nom_var, values=list(df.columns), state="readonly")
        nom_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Selector para adscripción
        frame_ads = ttk.Frame(seleccion_window)
        frame_ads.pack(fill=tk.X, padx=20, pady=5)
        ttk.Label(frame_ads, text="Columna de ADSCRIPCIÓN:", width=20).pack(side=tk.LEFT)
        ads_var = tk.StringVar(value=df.columns[2] if len(df.columns) > 2 else df.columns[0])
        ads_combo = ttk.Combobox(frame_ads, textvariable=ads_var, values=list(df.columns), state="readonly")
        ads_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        resultado = {}
        
        def confirmar():
            resultado.update({
                'direccion': dir_var.get(),
                'nombre': nom_var.get(),
                'adscripcion': ads_var.get()
            })
            seleccion_window.destroy()
        
        ttk.Button(seleccion_window, text="CONFIRMAR", command=confirmar).pack(pady=20)
        
        # Esperar a que se cierre la ventana
        seleccion_window.transient(self.root)
        seleccion_window.grab_set()
        self.root.wait_window(seleccion_window)
        
        return resultado

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="SISTEMA RUTAS PRO ULTRA HD - CON FOTOS", font=('Arial', 16, 'bold'), foreground='#2c3e50').pack()
        ttk.Label(header_frame, text="Gestión completa de entregas con evidencias fotográficas", font=('Arial', 10), foreground='#7f8c8d').pack()
        
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

        # 🆕 NUEVO: BOTONES MEJORADOS PARA GESTIÓN DE FOTOS
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

        # 🆕 NUEVO: BOTONES PARA TELEGRAM
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

    # 🆕 NUEVAS FUNCIONES PARA GESTIÓN DE FOTOS
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
                
                # Carga RÁPIDA sin procesamiento inicial
                df_completo = pd.read_excel(archivo)
                self.archivo_excel = archivo
                
                nombre_archivo = os.path.basename(archivo)
                self.file_label.config(text=nombre_archivo, foreground='green')
                self.log(f"✅ Excel cargado: {nombre_archivo}")
                self.log(f"📊 Registros totales: {len(df_completo)}")
                self.log(f"📋 Columnas disponibles: {list(df_completo.columns)}")
                
                # 🆕 SIN FILTRADO (CARGA TODO)
                self.df = df_completo
                df_filtrado = df_completo
                
                # DETECCIÓN MEJORADA DE COLUMNAS
                col_direccion = self._detectar_columna_direccion(df_filtrado)
                col_nombre = self._detectar_columna_nombre(df_filtrado) 
                col_adscripcion = self._detectar_columna_adscripcion(df_filtrado)
                
                # 🆕 SI LA DETECCIÓN AUTOMÁTICA FALLA, PREGUNTAR MANUALMENTE
                if col_direccion == df_filtrado.columns[0]:  # Si solo detectó la primera columna
                    self.log("⚠️ Detección automática falló, selección manual...")
                    columnas = self._seleccionar_columnas_manual(df_filtrado)
                    col_direccion = columnas['direccion']
                    col_nombre = columnas['nombre']
                    col_adscripcion = columnas['adscripcion']
                
                self.log(f"📍 Columna dirección: '{col_direccion}'")
                self.log(f"👤 Columna nombre: '{col_nombre}'")
                self.log(f"🏢 Columna adscripción: '{col_adscripcion}'")
                
                # Guardar las columnas seleccionadas para usar después
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
            self.log("🚀 INICIANDO GENERACIÓN DE RUTAS...")
            
            # 1. LIMPIAR CARPETAS
            self._limpiar_carpetas_anteriores()
            
            # 2. CARGAR DATOS
            df_completo = pd.read_excel(self.archivo_excel)
            self.log(f"📊 Total de registros: {len(df_completo)}")
            
            # 3. SIN FILTRADO (USA TODO)
            df_filtrado = df_completo
            self.log(f"✅ Procesando TODOS los registros: {len(df_filtrado)}")
            
            if len(df_filtrado) == 0:
                self.log("❌ No hay datos")
                return
            
            # 4. USAR COLUMNAS GUARDADAS (NO DETECTAR DE NUEVO)
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
            
            # 5. ESTANDARIZAR
            df_estandar = df_filtrado.copy()
            df_estandar['DIRECCIÓN'] = df_filtrado[columna_direccion].astype(str)
            df_estandar['NOMBRE'] = df_filtrado[columna_nombre].astype(str) if columna_nombre else 'Sin nombre'
            df_estandar['ADSCRIPCIÓN'] = df_filtrado[columna_adscripcion].astype(str) if columna_adscripcion else 'Sin adscripción'
            
            self.log(f"🎯 Procesando {len(df_estandar)} registros...")
            
            # 6. GENERAR RUTAS
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
                self.log(f"🎉 ¡{len(resultados)} RUTAS GENERADAS!")
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

    # 🆕 NUEVA FUNCIÓN: ASIGNAR RUTAS A REPARTIDORES
    def asignar_rutas_telegram(self):
        """Interfaz completa para asignar rutas a repartidores"""
        rutas_pendientes = self.gestor_telegram.obtener_rutas_pendientes()
        
        if not rutas_pendientes:
            messagebox.showinfo("Info", "No hay rutas pendientes para asignar")
            return
            
        # Crear ventana de asignación
        asignar_window = tk.Toplevel(self.root)
        asignar_window.title("Asignar Rutas a Repartidores")
        asignar_window.geometry("700x500")
        
        ttk.Label(asignar_window, text="ASIGNAR RUTAS A REPARTIDORES", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        # Lista de repartidores disponibles
        repartidores = ["Juan Pérez", "María García", "Carlos López", "Ana Martínez"]
        
        # Frame principal
        main_frame = ttk.Frame(asignar_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for i, ruta in enumerate(rutas_pendientes):
            frame_ruta = ttk.Frame(main_frame, relief='solid', padding=10)
            frame_ruta.pack(fill=tk.X, pady=5)
            
            ttk.Label(frame_ruta, 
                     text=f"Ruta {ruta['ruta_id']} - {ruta['zona']} ({ruta['progreso']} entregas)",
                     font=('Arial', 10, 'bold')).pack(anchor=tk.W)
            
            # Selector de repartidor
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

    # 🆕 NUEVA FUNCIÓN: VER AVANCES DE RUTAS
    def actualizar_avances(self):
        """Muestra el progreso de las rutas desde Telegram"""
        avances = self.gestor_telegram.obtener_avances_recientes(15)
        
        self.log("📊 ACTUALIZANDO AVANCES DE RUTAS...")
        self.log(f"   Total de entregas registradas: {len(avances)}")
        
        for avance in avances[:8]:  # Mostrar últimos 8
            repartidor = avance.get('repartidor', 'N/A')
            persona = avance.get('persona_entregada', 'N/A')
            timestamp = avance.get('timestamp', '')[:16]
            tiene_foto = "📸" if avance.get('foto_local') or avance.get('foto_acuse') else ""
            self.log(f"   ✅ {repartidor} → {persona} [{timestamp}] {tiene_foto}")

    # 🆕 NUEVA FUNCIÓN: VER ESTADO DE RUTAS
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
                
                # Icono según estado
                icono = "🟢" if estado == 'completada' else "🟡" if estado == 'en_progreso' else "🔴"
                
                self.log(f"   {icono} Ruta {ruta_id} ({zona}): {estado.upper()}")
                self.log(f"     👤 {repartidor} | 📦 {paradas_entregadas}/{paradas_totales} entregas")
                
            except Exception as e:
                self.log(f"   ❌ Error leyendo {archivo}: {str(e)}")

    # 🆕 NUEVA FUNCIÓN: SIMULAR ENTREGA PARA PRUEBAS
    def simular_entrega_prueba(self):
        """Simula una entrega para probar el sistema"""
        if not os.path.exists("rutas_telegram"):
            messagebox.showinfo("Info", "Primero genera rutas")
            return
            
        # Buscar primera ruta disponible
        archivos_rutas = [f for f in os.listdir("rutas_telegram") if f.endswith('.json')]
        if not archivos_rutas:
            messagebox.showinfo("Info", "No hay rutas para simular")
            return
            
        with open(f"rutas_telegram/{archivos_rutas[0]}", 'r', encoding='utf-8') as f:
            ruta_data = json.load(f)
        
        # Tomar primera parada de la ruta
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
