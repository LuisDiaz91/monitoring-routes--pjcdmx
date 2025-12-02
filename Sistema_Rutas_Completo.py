# sistema_rutas_completo_edificios_paradas.py
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
import urllib.parse

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
# CLASE PRINCIPAL - MOTOR DE RUTAS (CoreRouteGenerator) - VERSIÓN RECONSTRUIDA
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
        
        # Cargar caché si existe
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    self.GEOCODE_CACHE = json.load(f)
            except json.JSONDecodeError:
                self._log(f"❌ Cache de geocodificación corrupto, iniciando vacío")
                self.GEOCODE_CACHE = {}
        
        # Configuración de colores e iconos
        self.COLORES = {
            'CENTRO': '#FF6B6B', 'SUR': '#4ECDC4', 'ORIENTE': '#45B7D1',
            'SUR_ORIENTE': '#96CEB4', 'OTRAS': '#FECA57', 'MIXTA': '#9B59B6'
        }
        self.ICONOS = {
            'CENTRO': 'building', 'SUR': 'home', 'ORIENTE': 'industry',
            'SUR_ORIENTE': 'tree', 'OTRAS': 'map-marker', 'MIXTA': 'star'
        }
        
        # 🎯 NOMBRES DE COLUMNAS PERSONALIZADOS PARA TU EXCEL
        self.COLUMNAS = {
            'NOMBRE': 'NOMBRE',
            'ADSCRIPCION': 'ADSCRIPCIÓN',  # CON TILDE como en tu Excel
            'DIRECCION': 'DIRECCIÓN',      # CON TILDE como en tu Excel
            'ALCALDIA': 'ALCALDÍA',        # CON TILDE como en tu Excel
            'NOTAS': 'NOTAS'
        }
        
        self._log("✅ CoreRouteGenerator inicializado correctamente")
        self._log(f"📊 Columnas configuradas: {self.COLUMNAS}")

    def _log(self, message):
        """Registro de mensajes del sistema"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        self.log_messages.append(log_msg)
        print(log_msg)

    # =========================================================================
    # MÉTODOS DE LIMPIEZA Y NORMALIZACIÓN
    # =========================================================================
    
    def _limpiar_titulo_nombre(self, nombre_completo):
        """Quitar títulos académicos/profesionales del nombre"""
        if not nombre_completo or pd.isna(nombre_completo):
            return "Sin nombre"
        
        nombre_str = str(nombre_completo).strip()
        
        # Lista de títulos a quitar
        titulos = [
            'mtra.', 'mtro.', 'lic.', 'ing.', 'dr.', 'dra.', 'presidente',
            'presidenta', 'secretario', 'secretaria', 'director', 'directora',
            'magistrado', 'magistrada', 'maestro', 'maestra', 'ingeniero',
            'ingeniera', 'doctor', 'doctora', 'licenciado', 'licenciada'
        ]
        
        # Convertir a minúsculas para comparación
        nombre_lower = nombre_str.lower()
        
        # Quitar títulos al inicio
        for titulo in titulos:
            if nombre_lower.startswith(titulo + ' '):
                nombre_str = nombre_str[len(titulo):].strip()
                # También quitar posible punto después del título
                if nombre_str.startswith('. '):
                    nombre_str = nombre_str[2:].strip()
                elif nombre_str.startswith('.'):
                    nombre_str = nombre_str[1:].strip()
                break
        
        # Capitalizar nombre
        nombre_str = ' '.join([palabra.capitalize() for palabra in nombre_str.split()])
        
        return nombre_str

    def _extraer_datos_persona(self, fila):
        """Extraer datos de una persona/fila con los nombres correctos de columnas"""
        try:
            nombre_completo = str(fila.get(self.COLUMNAS['NOMBRE'], '')).strip()
            nombre_limpio = self._limpiar_titulo_nombre(nombre_completo)
            
            datos = {
                'nombre_completo': nombre_completo,
                'nombre': nombre_limpio,
                'adscripcion': str(fila.get(self.COLUMNAS['ADSCRIPCION'], '')).strip(),
                'dependencia': str(fila.get(self.COLUMNAS['ADSCRIPCION'], '')).strip(),  # Mismo que adscripción
                'direccion': str(fila.get(self.COLUMNAS['DIRECCION'], '')).strip(),
                'alcaldia': str(fila.get(self.COLUMNAS['ALCALDIA'], '')).strip(),
                'notas': str(fila.get(self.COLUMNAS['NOTAS'], '')).strip(),
                'fila_original': fila
            }
            
            return datos
            
        except Exception as e:
            self._log(f"❌ Error extrayendo datos: {e}")
            return {
                'nombre_completo': 'Error',
                'nombre': 'Error',
                'adscripcion': 'Sin datos',
                'dependencia': 'Sin datos',
                'direccion': 'Sin dirección',
                'alcaldia': 'Sin alcaldía',
                'notas': '',
                'fila_original': fila
            }

    # =========================================================================
    # MÉTODOS DE GEOCODIFICACIÓN
    # =========================================================================
    
    def _geocode(self, direccion):
        """Geocodificar una dirección usando Google Maps API"""
        if not direccion or pd.isna(direccion) or str(direccion).lower() in ['nan', '']:
            return None
            
        d = str(direccion).strip()
        key = hashlib.md5(d.encode('utf-8')).hexdigest()
        
        # Verificar caché
        if key in self.GEOCODE_CACHE:
            return self.GEOCODE_CACHE[key]
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': d + ", Ciudad de México, México",
                'key': self.api_key,
                'region': 'mx'
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                loc = data['results'][0]['geometry']['location']
                coords = (loc['lat'], loc['lng'])
                self.GEOCODE_CACHE[key] = coords
                
                # Respeta límites de la API
                time.sleep(0.11)
                return coords
            else:
                self._log(f"⚠️ Geocode no encontrado para: {d[:50]}...")
                return None
                
        except Exception as e:
            self._log(f"❌ Error en geocode: {e}")
            return None

    def _normalizar_direccion(self, direccion):
        """Normalizar direcciones para agrupamiento inteligente"""
        if not direccion or pd.isna(direccion):
            return ""
            
        direccion_str = str(direccion).lower().strip()
        
        # Remover caracteres especiales
        direccion_str = re.sub(r'[^\w\s]', ' ', direccion_str)
        direccion_str = re.sub(r'\s+', ' ', direccion_str)
        
        # Normalizar abreviaturas comunes
        normalizaciones = {
            r'\bav\b': 'avenida',
            r'\bav\.': 'avenida',
            r'\bcto\b': 'circuito',
            r'\bblvd\b': 'boulevard',
            r'\bcd\b': 'ciudad',
            r'\bcol\b': 'colonia',
            r'\bdeleg\b': 'delegacion',
            r'\bc\.p\.': 'codigo postal',
            r'\bcp\b': 'codigo postal',
            r'\bedif\b': 'edificio',
            r'\besq\b': 'esquina',
            r'\bint\b': 'interior',
            r'\bno\b': 'numero',
            r'\bnum\b': 'numero',
            r'\bprlv\b': 'privada',
            r'\bs/n\b': 'sin numero',
            r'\bsn\b': 'sin numero',
            r'\bpiso\b': '',
            r'\bp\.iso\b': ''
        }
        
        for patron, reemplazo in normalizaciones.items():
            direccion_str = re.sub(patron, reemplazo, direccion_str)
        
        # Remover palabras que no ayudan en agrupamiento
        palabras_innecesarias = [
            'ciudad de mexico', 'mexico', 'cdmx', 'alcaldia', 
            'delegacion', 'codigo postal', 'cp'
        ]
        
        for palabra in palabras_innecesarias:
            direccion_str = direccion_str.replace(palabra, '')
        
        return direccion_str.strip()

    # =========================================================================
    # MÉTODOS DE AGRUPAMIENTO
    # =========================================================================
    
    def _calcular_distancia(self, coord1, coord2):
        """Calcular distancia en kilómetros entre dos coordenadas"""
        try:
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
        except:
            return 9999  # Valor alto para indicar error

    def _agrupar_ubicaciones_similares(self, filas):
        """Agrupar personas en la misma ubicación física"""
        grupos = []
        direcciones_procesadas = []
        
        # Primero procesar todas las direcciones
        for _, fila in filas.iterrows():
            datos_persona = self._extraer_datos_persona(fila)
            direccion = datos_persona['direccion']
            
            if not direccion or direccion in ['nan', '', 'Sin dirección']:
                continue
            
            # Normalizar dirección para comparación
            direccion_normalizada = self._normalizar_direccion(direccion)
            
            # Buscar si ya tenemos una dirección similar
            agrupado = False
            for i, (dir_existente, grupo_existente) in enumerate(grupos):
                # Comparar direcciones normalizadas
                if direccion_normalizada == dir_existente:
                    grupo_existente.append(datos_persona)
                    agrupado = True
                    break
            
            if not agrupado:
                # Verificar por coordenadas
                coords = self._geocode(direccion)
                if coords:
                    # Buscar si hay coordenadas cercanas
                    for i, (coords_existentes, grupo_existente) in enumerate(grupos):
                        if coords_existentes and self._calcular_distancia(coords, coords_existentes) < 0.05:  # 50 metros
                            grupo_existente.append(datos_persona)
                            agrupado = True
                            break
                    
                    if not agrupado:
                        grupos.append((coords, [datos_persona]))
                else:
                    # Si no hay coordenadas, agrupar por dirección normalizada
                    grupos.append((None, [datos_persona]))
        
        self._log(f"📍 Agrupamiento completado: {len(grupos)} ubicaciones únicas")
        return grupos

    # =========================================================================
    # MÉTODOS DE OPTIMIZACIÓN DE RUTAS
    # =========================================================================
    
    def _optimizar_ruta(self, indices):
        """Optimizar ruta usando Google Directions API"""
        filas = self.df.loc[indices]
        
        # Agrupar ubicaciones similares
        grupos_ubicaciones = self._agrupar_ubicaciones_similares(filas)
        
        if len(grupos_ubicaciones) == 0:
            self._log("⚠️ No hay ubicaciones válidas para optimizar")
            return [], [], 0, 0, None
        
        # Separar coordenadas y datos
        coords_list = []
        filas_agrupadas = []
        
        for coords, grupo in grupos_ubicaciones:
            if coords:  # Solo incluir si tiene coordenadas
                coords_list.append(coords)
                filas_agrupadas.append({
                    'coordenadas': coords,
                    'personas': grupo,
                    'cantidad_personas': len(grupo)
                })
        
        if len(coords_list) < 2:
            self._log(f"⚠️ Solo {len(coords_list)} coordenadas válidas")
            return filas_agrupadas, coords_list, 0, 0, None
        
        # Llamar a Google Directions API
        try:
            waypoints = "|".join([f"{lat},{lng}" for lat, lng in coords_list])
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                'origin': self.origen_coords,
                'destination': self.origen_coords,
                'waypoints': f"optimize:true|{waypoints}",
                'key': self.api_key,
                'language': 'es',
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=20)
            data = response.json()
            
            if data['status'] == 'OK' and data['routes']:
                route = data['routes'][0]
                orden = route['waypoint_order']
                poly = route['overview_polyline']['points']
                
                # Calcular distancia y tiempo total
                distancia_total = sum(leg['distance']['value'] for leg in route['legs']) / 1000  # km
                tiempo_total = sum(leg['duration']['value'] for leg in route['legs']) / 60  # minutos
                
                # Reordenar según optimización
                filas_opt = [filas_agrupadas[i] for i in orden]
                coords_opt = [coords_list[i] for i in orden]
                
                self._log(f"✅ Ruta optimizada: {len(filas_opt)} paradas, {distancia_total:.1f} km, {tiempo_total:.0f} min")
                return filas_opt, coords_opt, tiempo_total, distancia_total, poly
            else:
                self._log(f"❌ Error Directions API: {data.get('status')}")
                return filas_agrupadas, coords_list, 0, 0, None
                
        except Exception as e:
            self._log(f"❌ Error optimizando ruta: {e}")
            return filas_agrupadas, coords_list, 0, 0, None

    # =========================================================================
    # MÉTODOS DE CREACIÓN DE ARCHIVOS
    # =========================================================================
    
    def _crear_excel_ruta(self, zona, filas_opt, ruta_id):
        """Crear archivo Excel para la ruta"""
        try:
            excel_data = []
            orden_parada = 1
            
            for grupo in filas_opt:
                coordenadas_grupo = grupo['coordenadas']
                personas_grupo = grupo['personas']
                cantidad_personas = grupo['cantidad_personas']
                
                for i, persona in enumerate(personas_grupo, 1):
                    # Crear link para foto
                    link_foto_base = f"fotos_entregas/Ruta_{ruta_id}_Parada_{orden_parada}"
                    if cantidad_personas > 1:
                        link_foto_base += f"_Persona_{i}"
                    
                    link_foto = f"=HIPERVINCULO(\"{link_foto_base}.jpg\", \"📸 VER FOTO\")"
                    
                    # 🎯 DATOS CORRECTOS DE TU EXCEL
                    excel_data.append({
                        'Orden_Parada': orden_parada,
                        'Sub_Orden': i if cantidad_personas > 1 else '',
                        'Nombre_Completo': persona['nombre_completo'],
                        'Nombre': persona['nombre'],
                        'Dependencia': persona['dependencia'],  # 🎯 ADSCRIPCIÓN
                        'Adscripción': persona['adscripcion'],   # 🎯 MISMO QUE DEPENDENCIA
                        'Dirección': persona['direccion'],
                        'Alcaldía': persona['alcaldia'],
                        'Notas': persona['notas'],
                        'Personas_Misma_Ubicacion': cantidad_personas,
                        'Acuse': 'PENDIENTE',
                        'Repartidor': '',
                        'Foto_Acuse': link_foto,
                        'Timestamp_Entrega': '',
                        'Estado': 'PENDIENTE',
                        'Coordenadas': f"{coordenadas_grupo[0]},{coordenadas_grupo[1]}",
                        'Es_Misma_Parada': 'SÍ' if cantidad_personas > 1 else 'NO',
                        'Info_Grupo': f"Grupo de {cantidad_personas} personas" if cantidad_personas > 1 else ''
                    })
                
                orden_parada += 1
            
            # Crear DataFrame y guardar Excel
            excel_df = pd.DataFrame(excel_data)
            excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
            
            # Asegurar que exista la carpeta
            os.makedirs("rutas_excel", exist_ok=True)
            
            excel_df.to_excel(excel_file, index=False)
            self._log(f"📊 Excel generado: {excel_file} ({len(excel_data)} registros)")
            
            return excel_file
            
        except Exception as e:
            self._log(f"❌ Error creando Excel: {e}")
            return None

    def _crear_mapa_ruta(self, zona, filas_opt, coords_opt, tiempo, dist, poly, ruta_id):
        """Crear mapa interactivo con Folium"""
        try:
            # Crear mapa
            map_origin_coords = list(map(float, self.origen_coords.split(',')))
            m = folium.Map(location=map_origin_coords, zoom_start=13, tiles='CartoDB positron')
            color = self.COLORES.get(zona, 'gray')
            
            # Marcador de origen
            folium.Marker(
                map_origin_coords,
                popup=f"<b>🏛️ {self.origen_name}</b>",
                tooltip="Punto de inicio",
                icon=folium.Icon(color='green', icon='balance-scale', prefix='fa')
            ).add_to(m)
            
            # Ruta optimizada
            if poly:
                folium.PolyLine(
                    polyline.decode(poly), 
                    color=color, 
                    weight=5, 
                    opacity=0.7,
                    popup=f"Ruta {ruta_id} - {zona}"
                ).add_to(m)
            
            # 🎯 MARCAR PARADAS CON INFORMACIÓN COMPLETA
            for i, (grupo, coord) in enumerate(zip(filas_opt, coords_opt), 1):
                cantidad_personas = grupo['cantidad_personas']
                primera_persona = grupo['personas'][0]
                
                # Crear popup HTML detallado
                popup_html = f"""
                <div style="font-family: Arial; width: 350px;">
                    <h4 style="color: {color}; margin: 0 0 10px;">
                        📍 Parada #{i} - {zona}
                    </h4>
                    <b>🏢 {primera_persona['nombre']}</b><br>
                    <small>{primera_persona['dependencia']}</small><hr style="margin: 8px 0;">
                    <small><b>📌 Dirección:</b><br>{primera_persona['direccion'][:100]}...</small>
                """
                
                if cantidad_personas > 1:
                    popup_html += f"""<hr style="margin: 8px 0;">
                    <small><b>👥 Personas en esta ubicación ({cantidad_personas}):</b></small><br>"""
                    
                    for j, persona in enumerate(grupo['personas'][:4], 1):
                        popup_html += f"<small>• {persona['nombre']}</small><br>"
                    
                    if cantidad_personas > 4:
                        popup_html += f"<small>• ... y {cantidad_personas-4} más</small><br>"
                
                popup_html += "</div>"
                
                # Icono según tipo de parada
                if cantidad_personas > 1:
                    icon_color = 'orange'
                    icon_type = 'building'
                else:
                    icon_color = 'red'
                    icon_type = 'user'
                
                folium.Marker(
                    coord,
                    popup=popup_html,
                    tooltip=f"Parada #{i}: {primera_persona['nombre'][:20]}...",
                    icon=folium.Icon(color=icon_color, icon=icon_type, prefix='fa')
                ).add_to(m)
            
            # Panel informativo
            total_personas = sum(grupo['cantidad_personas'] for grupo in filas_opt)
            total_paradas = len(filas_opt)
            
            info_panel_html = f"""
            <div style="position:fixed; top:10px; left:50px; z-index:1000; background:white; 
                        padding:15px; border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.2);
                        border:2px solid {color}; font-family:Arial; max-width:400px;">
                <h4 style="margin:0 0 10px; color:#2c3e50; border-bottom:2px solid {color}; padding-bottom:5px;">
                    Ruta {ruta_id} - {zona}
                </h4>
                <small>
                    <b>🏢 Paradas (Edificios):</b> {total_paradas}<br>
                    <b>👥 Personas:</b> {total_personas}<br>
                    <b>📏 Distancia:</b> {dist:.1f} km<br>
                    <b>⏱️ Tiempo estimado:</b> {tiempo:.0f} min<br>
                    <b>📍 Origen:</b> {self.origen_name}<br>
                </small>
            </div>
            """
            m.get_root().html.add_child(folium.Element(info_panel_html))
            
            # Guardar mapa
            os.makedirs("mapas_pro", exist_ok=True)
            mapa_file = f"mapas_pro/Ruta_{ruta_id}_{zona}.html"
            m.save(mapa_file)
            self._log(f"🗺️ Mapa generado: {mapa_file}")
            
            return mapa_file
            
        except Exception as e:
            self._log(f"❌ Error creando mapa: {e}")
            return None

    def _crear_json_telegram(self, zona, filas_opt, coords_opt, tiempo, dist, ruta_id, excel_file):
        """Crear JSON para Telegram/Bot con toda la información"""
        try:
            # 🎯 PREPARAR PARADAS CON DATOS COMPLETOS - VERSIÓN CORREGIDA
            paradas_telegram = []

            for i, grupo in enumerate(filas_opt, 1):
                primera_persona = grupo['personas'][0]
                coordenadas = grupo['coordenadas']
                
                # 🎯 CORRECCIÓN: La parada DEBE tener nombre y dependencia en el nivel superior
                parada = {
                    'orden': i,
                    'nombre': primera_persona['nombre'],  # 🎯 AGREGAR ESTO
                    'dependencia': primera_persona['dependencia'],  # 🎯 AGREGAR ESTO
                    'tipo': 'edificio' if grupo['cantidad_personas'] > 1 else 'individual',
                    'coords': f"{coordenadas[0]},{coordenadas[1]}",
                    'direccion': primera_persona['direccion'],
                    'total_personas': grupo['cantidad_personas'],
                    'estado': 'pendiente',
                    'timestamp_entrega': None,
                    'personas': []
                }
                
                # 🎯 AGREGAR TODAS LAS PERSONAS CON DATOS COMPLETOS
                for j, persona in enumerate(grupo['personas'], 1):
                    parada['personas'].append({
                        'sub_orden': j,
                        'nombre': persona['nombre'],
                        'nombre_completo': persona['nombre_completo'],
                        'dependencia': persona['dependencia'],
                        'adscripcion': persona['adscripcion'],
                        'direccion': persona['direccion'],
                        'alcaldia': persona['alcaldia'],
                        'foto_acuse': f"fotos_entregas/Ruta_{ruta_id}_Parada_{i}_Persona_{j}.jpg",
                        'estado': 'pendiente',
                        'timestamp_entrega': None
                    })
                
                paradas_telegram.append(parada)
            
            # 🎯 CREAR URL DE GOOGLE MAPS CON DIRECCIONES
            google_maps_url = self._generar_url_google_maps(paradas_telegram)
            
            # 🎯 ESTRUCTURA COMPLETA PARA EL BOT
            ruta_telegram = {
                'ruta_id': ruta_id,
                'zona': zona,
                'repartidor_asignado': None,
                'google_maps_url': google_maps_url,
                'paradas': paradas_telegram,
                'estadisticas': {
                    'total_paradas': len(filas_opt),
                    'total_personas': sum(g['cantidad_personas'] for g in filas_opt),
                    'distancia_km': round(dist, 1),
                    'tiempo_min': round(tiempo),
                    'origen': self.origen_name,
                    'configuracion': 'paradas_por_edificio'
                },
                'estado': 'pendiente',
                'fotos_acuses': [],
                'timestamp_creacion': datetime.now().isoformat(),
                'excel_original': excel_file,
                'metadata': {
                    'columnas_usadas': self.COLUMNAS,
                    'version': '2.0',
                    'generador': 'CoreRouteGenerator Reconstruido'
                }
            }
            
            # Guardar JSON
            os.makedirs("rutas_telegram", exist_ok=True)
            telegram_file = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
            
            with open(telegram_file, 'w', encoding='utf-8') as f:
                json.dump(ruta_telegram, f, indent=2, ensure_ascii=False)
            
            self._log(f"📱 JSON Telegram generado: {telegram_file}")
            
            return ruta_telegram, telegram_file
            
        except Exception as e:
            self._log(f"❌ Error creando JSON Telegram: {e}")
            return None, None

    def _generar_url_google_maps(self, paradas):
        """Generar URL de Google Maps con todas las paradas"""
        try:
            if not paradas or len(paradas) < 2:
                return None
            
            # Tomar direcciones de las primeras personas de cada parada
            direcciones = []
            
            for parada in paradas:
                direccion = parada.get('direccion', '')
                if direccion and direccion not in ['', 'Sin dirección']:
                    # Agregar Ciudad de México si no está
                    if 'ciudad de méxico' not in direccion.lower() and 'cdmx' not in direccion.lower():
                        direccion += ", Ciudad de México"
                    
                    direcciones.append(urllib.parse.quote(direccion))
            
            if len(direcciones) < 2:
                return None
            
            # Construir URL
            base_url = "https://www.google.com/maps/dir/?api=1"
            origen = urllib.parse.quote(self.origen_name + ", Ciudad de México")
            
            url = f"{base_url}&origin={origen}&destination={direcciones[-1]}"
            
            if len(direcciones) > 2:
                waypoints = "|".join(direcciones[1:-1])
                url += f"&waypoints={waypoints}"
            
            url += "&travelmode=driving&dir_action=navigate"
            
            self._log(f"🗺️ URL Google Maps generada: {url[:80]}...")
            return url
            
        except Exception as e:
            self._log(f"⚠️ Error generando URL Google Maps: {e}")
            return None

    # =========================================================================
    # MÉTODO PRINCIPAL DE CREACIÓN DE RUTA
    # =========================================================================
    
    def _crear_ruta_archivos(self, zona, indices, ruta_id):
        """Método principal para crear todos los archivos de una ruta"""
        self._log(f"🚀 Creando Ruta {ruta_id} - {zona} ({len(indices)} registros)")
        
        # Optimizar ruta
        filas_opt, coords_opt, tiempo, dist, poly = self._optimizar_ruta(indices)
        
        if len(filas_opt) == 0:
            self._log(f"❌ No hay paradas válidas para Ruta {ruta_id}")
            return None
        
        # 🎯 CREAR ARCHIVOS
        excel_file = self._crear_excel_ruta(zona, filas_opt, ruta_id)
        mapa_file = self._crear_mapa_ruta(zona, filas_opt, coords_opt, tiempo, dist, poly, ruta_id)
        ruta_telegram, telegram_file = self._crear_json_telegram(zona, filas_opt, coords_opt, tiempo, dist, ruta_id, excel_file)
        
        if not excel_file or not ruta_telegram:
            self._log(f"❌ Error creando archivos para Ruta {ruta_id}")
            return None
        
        # 🎯 ENVIAR AL BOT RAILWAY
        try:
            RAILWAY_URL = "https://monitoring-routes-pjcdmx-production.up.railway.app"
            conexion = ConexionBotRailway(RAILWAY_URL)
            
            if conexion.verificar_conexion():
                if conexion.enviar_ruta_bot(ruta_telegram):
                    self._log(f"📱 Ruta {ruta_id} enviada al bot exitosamente")
                else:
                    self._log("⚠️ Ruta generada pero no se pudo enviar al bot")
            else:
                self._log("❌ No se pudo conectar con el bot")
                
        except Exception as e:
            self._log(f"⚠️ Error enviando al bot: {e}")
        
        # 🎯 RESULTADO FINAL
        total_personas = sum(g['cantidad_personas'] for g in filas_opt)
        
        resultado = {
            'ruta_id': ruta_id,
            'zona': zona,
            'paradas': len(filas_opt),  # Número de edificios
            'personas': total_personas,  # Número total de personas
            'distancia': round(dist, 1),
            'tiempo': round(tiempo),
            'excel': excel_file,
            'mapa': mapa_file if mapa_file else '',
            'telegram_data': ruta_telegram,
            'telegram_file': telegram_file,
            'google_maps_url': ruta_telegram.get('google_maps_url') if ruta_telegram else None
        }
        
        self._log(f"✅ Ruta {ruta_id} creada: {len(filas_opt)} paradas, {total_personas} personas")
        
        return resultado

    # =========================================================================
    # MÉTODOS PARA EVITAR RUTAS DE 1 PERSONA (se mantienen igual)
    # =========================================================================
    
    def _identificar_personas_sueltas(self, subgrupos):
        """Identificar personas que quedarían solas en rutas"""
        personas_sueltas = []
        subgrupos_filtrados = {}
        
        for zona, grupos in subgrupos.items():
            subgrupos_filtrados[zona] = []
            for grupo in grupos:
                if len(grupo) == 1:
                    personas_sueltas.append({
                        'indice': grupo[0],
                        'zona': zona,
                        'datos': self.df.loc[grupo[0]]
                    })
                else:
                    subgrupos_filtrados[zona].append(grupo)
        
        self._log(f"👤 Identificadas {len(personas_sueltas)} personas sueltas")
        return subgrupos_filtrados, personas_sueltas

    def _redistribuir_personas_sueltas(self, subgrupos_filtrados, personas_sueltas):
        """Redistribuir personas sueltas"""
        personas_redistribuidas = 0
        personas_para_rutas_mixtas = []
        
        for persona in personas_sueltas:
            redistribuida = False
            zona = persona['zona']
            
            if zona in subgrupos_filtrados:
                for grupo in subgrupos_filtrados[zona]:
                    if len(grupo) < self.max_stops_per_route:
                        grupo.append(persona['indice'])
                        redistribuida = True
                        personas_redistribuidas += 1
                        break
            
            if not redistribuida:
                personas_para_rutas_mixtas.append(persona)
        
        self._log(f"🔄 {personas_redistribuidas} personas redistribuidas")
        return subgrupos_filtrados, personas_para_rutas_mixtas

    # =========================================================================
    # MÉTODO PRINCIPAL DE GENERACIÓN
    # =========================================================================
    
    def generate_routes(self):
        """🎯 MÉTODO PRINCIPAL - Generar todas las rutas"""
        self._log("🚀 INICIANDO GENERACIÓN DE RUTAS RECONSTRUIDA")
        self._log(f"📊 Total de registros: {len(self.df)}")
        
        if self.df.empty:
            self._log("❌ No hay datos para procesar")
            return []
        
        # 🎯 LIMPIAR Y FILTRAR DATOS
        df_clean = self.df.copy()
        
        # Verificar que las columnas necesarias existan
        columnas_faltantes = []
        for col_name in self.COLUMNAS.values():
            if col_name not in df_clean.columns:
                columnas_faltantes.append(col_name)
        
        if columnas_faltantes:
            self._log(f"⚠️ Columnas faltantes: {columnas_faltantes}")
            self._log("💡 Buscando columnas similares...")
            
            # Intentar encontrar columnas similares
            for key, expected_col in self.COLUMNAS.items():
                if expected_col not in df_clean.columns:
                    for actual_col in df_clean.columns:
                        if expected_col.lower() in actual_col.lower():
                            self.COLUMNAS[key] = actual_col
                            self._log(f"   Usando '{actual_col}' para '{key}'")
                            break
        
        # 🎯 ASIGNAR ZONAS
        def extraer_alcaldia(direccion):
            direccion_str = str(direccion).upper()
            
            alcaldias = {
                'CUAUHTEMOC': ['CUAUHTEMOC', 'DOCTORES', 'CENTRO', 'ROMA', 'CONDESA'],
                'MIGUEL HIDALGO': ['MIGUEL HIDALGO', 'POLANCO', 'LOMAS', 'CHAPULTEPEC'],
                'BENITO JUAREZ': ['BENITO JUÁREZ', 'DEL VALLE', 'NÁPOLES'],
                'ALVARO OBREGON': ['ÁLVARO OBREGÓN', 'SAN ÁNGEL', 'GUADALUPE INN'],
                'COYOACAN': ['COYOACÁN'],
                'IZTAPALAPA': ['IZTAPALAPA'],
                'GUSTAVO A. MADERO': ['GUSTAVO A. MADERO']
            }
            
            for alc, palabras in alcaldias.items():
                if any(p in direccion_str for p in palabras):
                    return alc.title()
            
            return "OTRAS"
        
        # Extraer alcaldía de la dirección
        df_clean['Alcaldia_Extraida'] = df_clean[self.COLUMNAS['DIRECCION']].apply(extraer_alcaldia)
        
        # Asignar zona
        ZONAS = {
            'CENTRO': ['Cuauhtemoc', 'Miguel Hidalgo'],
            'SUR': ['Alvaro Obregon', 'Benito Juarez', 'Coyoacan'],
            'ORIENTE': ['Iztapalapa', 'Gustavo A. Madero'],
            'OTRAS': ['Otras']
        }
        
        def asignar_zona(alcaldia):
            alcaldia_str = str(alcaldia).title()
            for zona_name, alcaldias_in_zone in ZONAS.items():
                if alcaldia_str in alcaldias_in_zone:
                    return zona_name
            return 'OTRAS'
        
        df_clean['Zona'] = df_clean['Alcaldia_Extraida'].apply(asignar_zona)
        
        # 🎯 CREAR SUBGRUPOS POR ZONA
        subgrupos = {}
        for zona in df_clean['Zona'].unique():
            indices = df_clean[df_clean['Zona'] == zona].index.tolist()
            # Dividir en grupos del tamaño máximo
            grupos = [indices[i:i+self.max_stops_per_route] 
                     for i in range(0, len(indices), self.max_stops_per_route)]
            subgrupos[zona] = grupos
            self._log(f"📦 {zona}: {len(indices)} registros → {len(grupos)} grupos")
        
        # 🎯 IDENTIFICAR Y REDISTRIBUIR PERSONAS SUELTAS
        self._log("🔄 Redistribuyendo personas sueltas...")
        subgrupos_filtrados, personas_sueltas = self._identificar_personas_sueltas(subgrupos)
        subgrupos_optimizados, personas_mixtas = self._redistribuir_personas_sueltas(subgrupos_filtrados, personas_sueltas)
        
        # 🎯 GENERAR RUTAS PRINCIPALES
        self.results = []
        ruta_id = 1
        
        for zona in subgrupos_optimizados.keys():
            for grupo in subgrupos_optimizados[zona]:
                if len(grupo) >= 2:  # Mínimo 2 personas por ruta
                    self._log(f"📋 Procesando Ruta {ruta_id}: {zona} ({len(grupo)} personas)")
                    try:
                        resultado = self._crear_ruta_archivos(zona, grupo, ruta_id)
                        if resultado:
                            self.results.append(resultado)
                            ruta_id += 1
                    except Exception as e:
                        self._log(f"❌ Error en Ruta {ruta_id}: {e}")
        
        # 🎯 GUARDAR CACHE
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.GEOCODE_CACHE, f)
            self._log("💾 Cache de geocodificación guardado")
        except Exception as e:
            self._log(f"⚠️ Error guardando cache: {e}")
        
        # 🎯 GENERAR RESUMEN
        if self.results:
            try:
                resumen_data = []
                for r in self.results:
                    resumen_data.append({
                        'Ruta_ID': r['ruta_id'],
                        'Zona': r['zona'],
                        'Paradas': r['paradas'],
                        'Personas': r['personas'],
                        'Distancia_km': r['distancia'],
                        'Tiempo_min': r['tiempo'],
                        'Excel': os.path.basename(r['excel']),
                        'Mapa': os.path.basename(r['mapa']) if r['mapa'] else '',
                        'Google_Maps_URL': r.get('google_maps_url', '')
                    })
                
                resumen_df = pd.DataFrame(resumen_data)
                resumen_df.to_excel("RESUMEN_RUTAS.xlsx", index=False)
                self._log("📋 Resumen 'RESUMEN_RUTAS.xlsx' generado")
                
            except Exception as e:
                self._log(f"⚠️ Error generando resumen: {e}")
        
        # 🎯 ESTADÍSTICAS FINALES
        total_rutas = len(self.results)
        total_paradas = sum(r['paradas'] for r in self.results) if self.results else 0
        total_personas = sum(r['personas'] for r in self.results) if self.results else 0
        
        self._log("🎉 GENERACIÓN DE RUTAS COMPLETADA")
        self._log(f"📊 RESUMEN FINAL:")
        self._log(f"   • Total rutas generadas: {total_rutas}")
        self._log(f"   • Total paradas (edificios): {total_paradas}")
        self._log(f"   • Total personas: {total_personas}")
        self._log(f"   • Personas por ruta promedio: {total_personas/total_rutas:.1f}" if total_rutas > 0 else "0")
        
        # Verificar rutas de 1 persona
        rutas_una_persona = [r for r in self.results if r['personas'] == 1]
        if rutas_una_persona:
            self._log(f"⚠️ ADVERTENCIA: {len(rutas_una_persona)} rutas con solo 1 persona")
        else:
            self._log("✅ EXCELENTE: ¡Cero rutas con 1 persona!")
        
        return self.results
        
# =============================================================================
# CLASE INTERFAZ GRÁFICA (SistemaRutasGUI) - VERSIÓN FINAL
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas PRO Ultra HD - PARADAS POR EDIFICIO")
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
        ttk.Label(header_frame, text="SISTEMA RUTAS PRO ULTRA HD - PARADAS POR EDIFICIO", 
                 font=('Arial', 14, 'bold'), foreground='#2c3e50').pack()
        ttk.Label(header_frame, text="Cada edificio con múltiples personas = 1 sola parada de ruta", 
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
            # Buscar DIRECCIÓN con o sin tilde
            if any(p in str(col).lower() for p in ['dirección', 'direccion', 'dir', 'address', 'ubicación']):
                return col
        return df.columns[0] if len(df.columns) > 0 else None

    def _detectar_columna_nombre(self, df):
        for col in df.columns:
            if any(p in str(col).lower() for p in ['nombre', 'name', 'nombre completo']):
                return col
        return None

    def _detectar_columna_adscripcion(self, df):
        for col in df.columns:
            if any(p in str(col).lower() for p in ['adscripción', 'adscripcion', 'cargo', 'puesto', 'departamento']):
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
            self.log("🚀 INICIANDO GENERACIÓN DE RUTAS CON PARADAS POR EDIFICIO...")
            
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
            
            generator._log = self.log
            resultados = generator.generate_routes()
            
            if resultados:
                self.log(f"🎉 ¡{len(resultados)} RUTAS GENERADAS CON PARADAS POR EDIFICIO!")
                self.log("🏢 Cada edificio con múltiples personas = 1 sola parada de ruta")
                self.log("📱 Las rutas están listas para asignar a repartidores via Telegram")
                messagebox.showinfo("Éxito", f"¡{len(resultados)} rutas generadas!\n\nCada edificio con múltiples personas es una sola parada de ruta.\n\nAhora puedes asignarlas a repartidores usando el botón 'ASIGNAR RUTAS'")
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
