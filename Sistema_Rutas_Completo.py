# sistema_rutas_completo_con_vulnerabilidades_y_fotos.py
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
import socket
import platform
import psutil
import urllib.request
import zipfile
import tempfile
from packaging import version

# =============================================================================
# MÓDULO DE VULNERABILIDADES Y SEGURIDAD
# =============================================================================
class SecurityScanner:
    def __init__(self):
        self.vulnerabilities = []
        self.security_issues = []
        
    def scan_system_vulnerabilities(self):
        """Escanea vulnerabilidades del sistema"""
        try:
            self.vulnerabilities = []
            
            # 1. Verificar versión de Python
            python_version = sys.version_info
            if python_version < (3, 7):
                self.vulnerabilities.append({
                    'nivel': 'ALTO',
                    'tipo': 'Python Desactualizado',
                    'descripcion': f'Python versión {python_version} puede tener vulnerabilidades de seguridad',
                    'recomendacion': 'Actualizar a Python 3.9 o superior'
                })
            
            # 2. Verificar librerías con vulnerabilidades conocidas
            vulnerable_libs = self.check_vulnerable_libraries()
            self.vulnerabilities.extend(vulnerable_libs)
            
            # 3. Verificar permisos de archivos
            file_permissions = self.check_file_permissions()
            self.vulnerabilities.extend(file_permissions)
            
            # 4. Verificar conexiones de red
            network_issues = self.check_network_security()
            self.vulnerabilities.extend(network_issues)
            
            # 5. Verificar configuración del sistema
            system_config = self.check_system_configuration()
            self.vulnerabilities.extend(system_config)
            
            return self.vulnerabilities
            
        except Exception as e:
            return [{
                'nivel': 'MEDIO',
                'tipo': 'Error en Escaneo',
                'descripcion': f'Error durante el escaneo: {str(e)}',
                'recomendacion': 'Revisar logs del sistema'
            }]
    
    def check_vulnerable_libraries(self):
        """Verifica librerías con vulnerabilidades conocidas"""
        issues = []
        
        try:
            # Verificar requests
            requests_version = requests.__version__
            if version.parse(requests_version) < version.parse("2.25.0"):
                issues.append({
                    'nivel': 'MEDIO',
                    'tipo': 'Librería Vulnerable',
                    'descripcion': f'Requests versión {requests_version} puede tener vulnerabilidades',
                    'recomendacion': 'Actualizar requests: pip install --upgrade requests'
                })
                
            # Verificar pandas
            pandas_version = pd.__version__
            if version.parse(pandas_version) < version.parse("1.3.0"):
                issues.append({
                    'nivel': 'BAJO',
                    'tipo': 'Pandas Desactualizado',
                    'descripcion': f'Pandas versión {pandas_version} puede tener issues de seguridad',
                    'recomendacion': 'Actualizar pandas: pip install --upgrade pandas'
                })
                
        except Exception as e:
            issues.append({
                'nivel': 'BAJO',
                'tipo': 'Error Verificación Librerías',
                'descripcion': f'No se pudieron verificar las librerías: {str(e)}',
                'recomendacion': 'Verificar manualmente las dependencias'
            })
            
        return issues
    
    def check_file_permissions(self):
        """Verifica permisos de archivos sensibles"""
        issues = []
        
        try:
            sensitive_files = [
                "rutas_excel",
                "rutas_telegram", 
                "avances_ruta",
                "fotos_entregas"
            ]
            
            for file_path in sensitive_files:
                if os.path.exists(file_path):
                    if platform.system() != "Windows":
                        # En sistemas Unix, verificar permisos
                        import stat
                        file_stat = os.stat(file_path)
                        if file_stat.st_mode & stat.S_IROTH:
                            issues.append({
                                'nivel': 'ALTO',
                                'tipo': 'Permisos Inseguros',
                                'descripcion': f'Archivo {file_path} tiene permisos de lectura públicos',
                                'recomendacion': 'Restringir permisos: chmod 600 ' + file_path
                            })
            
        except Exception as e:
            pass
            
        return issues
    
    def check_network_security(self):
        """Verifica configuraciones de red"""
        issues = []
        
        try:
            # Verificar si hay conexiones abiertas
            connections = psutil.net_connections()
            suspicious_ports = [1337, 4444, 31337]  # Puertos comúnmente usados por malware
            
            for conn in connections:
                if conn.status == 'LISTEN' and conn.laddr.port in suspicious_ports:
                    issues.append({
                        'nivel': 'ALTO', 
                        'tipo': 'Puerto Sospechoso',
                        'descripcion': f'Puerto {conn.laddr.port} en estado LISTEN',
                        'recomendacion': 'Investigar proceso que usa este puerto'
                    })
                    
        except Exception as e:
            pass
            
        return issues
    
    def check_system_configuration(self):
        """Verifica configuración del sistema"""
        issues = []
        
        try:
            # Verificar si el sistema tiene antivirus
            if platform.system() == "Windows":
                try:
                    import wmi
                    c = wmi.WMI()
                    antivirus = c.Win32_Product(name="Windows Defender")
                    if not antivirus:
                        issues.append({
                            'nivel': 'MEDIO',
                            'tipo': 'Antivirus No Detectado',
                            'descripcion': 'No se detectó software antivirus activo',
                            'recomendacion': 'Instalar y activar un antivirus'
                        })
                except:
                    issues.append({
                        'nivel': 'BAJO',
                        'tipo': 'Antivirus No Verificado',
                        'descripcion': 'No se pudo verificar el estado del antivirus',
                        'recomendacion': 'Verificar manualmente el antivirus'
                    })
                    
        except Exception as e:
            pass
            
        return issues
    
    def generate_security_report(self):
        """Genera reporte de seguridad completo"""
        vulnerabilities = self.scan_system_vulnerabilities()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'sistema': platform.system() + " " + platform.release(),
            'python_version': platform.python_version(),
            'vulnerabilities_found': len(vulnerabilities),
            'vulnerabilities': vulnerabilities,
            'summary': {
                'alto': len([v for v in vulnerabilities if v['nivel'] == 'ALTO']),
                'medio': len([v for v in vulnerabilities if v['nivel'] == 'MEDIO']),
                'bajo': len([v for v in vulnerabilities if v['nivel'] == 'BAJO'])
            }
        }
        
        return report

# =============================================================================
# CLASE MEJORADA CON GESTIÓN DE FOTOS EN EXCEL
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
# CLASE GESTOR TELEGRAM MEJORADO CON LINKS DE FOTOS
# =============================================================================
class GestorTelegram:
    def __init__(self, gui):
        self.gui = gui
        self.railway_url = "https://monitoring-routes-pjcdmx-production.up.railway.app"
        self.conexion = ConexionBotRailway(self.railway_url)
        self.security_scanner = SecurityScanner()
        
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
            foto_url = avance.get('foto_url', '')  # 🆕 URL de la foto
            foto_local = avance.get('foto_local', '')
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
                    
                    # 🆕 ACTUALIZAR EXCEL CON LINK DE FOTO
                    link_foto = foto_url if foto_url else foto_local
                    
                    df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                    df.at[idx, 'Repartidor'] = repartidor
                    df.at[idx, 'Foto_Acuse'] = link_foto  # 🆕 URL o ruta local
                    df.at[idx, 'Link_Foto'] = f'=HIPERVINCULO("{link_foto}")' if link_foto else ''  # 🆕 FÓRMULA EXCEL
                    df.at[idx, 'Timestamp_Entrega'] = timestamp
                    df.at[idx, 'Estado'] = 'ENTREGADO'
                    
                    persona_encontrada = True
                    self.gui.log(f"✅ Excel actualizado: {persona_entregada} → {nombre_en_excel}")
                    self.gui.log(f"📸 Foto agregada: {link_foto}")
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
                'foto_url': f"https://ejemplo.com/fotos/entrega_{ruta_id}.jpg",  # 🆕 URL simulada
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

    def escanear_vulnerabilidades(self):
        """Escanea vulnerabilidades del sistema"""
        try:
            self.gui.log("🔍 INICIANDO ESCANEO DE VULNERABILIDADES...")
            reporte = self.security_scanner.generate_security_report()
            
            # Mostrar resultados en el log
            self.gui.log(f"📊 VULNERABILIDADES ENCONTRADAS: {reporte['vulnerabilities_found']}")
            self.gui.log(f"   🔴 ALTO: {reporte['summary']['alto']}")
            self.gui.log(f"   🟡 MEDIO: {reporte['summary']['medio']}") 
            self.gui.log(f"   🔵 BAJO: {reporte['summary']['bajo']}")
            
            # Mostrar detalles
            for vuln in reporte['vulnerabilities']:
                self.gui.log(f"   ⚠️ [{vuln['nivel']}] {vuln['tipo']}: {vuln['descripcion']}")
            
            # Guardar reporte completo
            with open("reporte_seguridad.json", "w", encoding="utf-8") as f:
                json.dump(reporte, f, indent=2, ensure_ascii=False)
            
            self.gui.log("💾 Reporte de seguridad guardado: reporte_seguridad.json")
            
            return reporte
            
        except Exception as e:
            self.gui.log(f"❌ Error en escaneo de vulnerabilidades: {str(e)}")
            return None

# =============================================================================
# CLASE PRINCIPAL - MOTOR DE RUTAS (CoreRouteGenerator) - MEJORADO CON FOTOS
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
        
        # 🆕 EXCEL MEJORADO CON COLUMNAS PARA FOTOS Y LINKS
        excel_data = []
        for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1):
            excel_data.append({
                'Orden': i,
                'Nombre': str(fila.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                'Dependencia': str(fila.get('ADSCRIPCIÓN', 'N/A')).strip(),
                'Dirección': str(fila.get('DIRECCIÓN', 'N/A')).strip(),
                'Acuse': '',
                'Repartidor': '',
                'Foto_Acuse': '',  # 🆕 URL o ruta de la foto
                'Link_Foto': '',   # 🆕 Fórmula de hipervínculo Excel
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
        waypoints_param = "|".join([f"{lat},{lng}" for lat, lng in coords_opt])
        google_maps_url = f"https://www.google.com/maps/dir/?api=1&origin={self.origen_coords}&destination={self.origen_coords}&waypoints={waypoints_param}&travelmode=driving"
        
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
                    'foto_acuse': None,
                    'foto_url': None  # 🆕 URL para foto
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
# CLASE INTERFAZ GRÁFICA MEJORADA CON VULNERABILIDADES Y FOTOS
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas PRO Ultra HD - CON FOTOS Y SEGURIDAD")
        self.root.geometry("1200x850")
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
        
        # 🆕 NUEVO: VARIABLES PARA SINCRONIZACIÓN AUTOMÁTICA
        self.sincronizando = False
        self.sincronizacion_thread = None
        
        self.setup_ui()
        
        # 🆕 NUEVO: Solo UNA llamada aquí
        self.root.after(1000, self.cargar_excel_desde_github)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="SISTEMA RUTAS PRO ULTRA HD - CON FOTOS Y SEGURIDAD", font=('Arial', 14, 'bold'), foreground='#2c3e50').pack()
        ttk.Label(header_frame, text="Gestión completa de entregas con evidencias fotográficas y análisis de seguridad", font=('Arial', 9), foreground='#7f8c8d').pack()
        
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

        # 🆕 NUEVO: BOTONES MEJORADOS PARA GESTIÓN DE FOTOS Y SEGURIDAD
        seguridad_frame = ttk.LabelFrame(main_frame, text="Seguridad y Vulnerabilidades", padding="15")
        seguridad_frame.pack(fill=tk.X, pady=(0, 10))
        
        seguridad_btn_frame = ttk.Frame(seguridad_frame)
        seguridad_btn_frame.pack(fill=tk.X)
        
        ttk.Button(seguridad_btn_frame, text="🔍 ESCANEAR VULNERABILIDADES", 
                  command=self.escanear_vulnerabilidades).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(seguridad_btn_frame, text="📊 VER REPORTE SEGURIDAD", 
                  command=self.ver_reporte_seguridad).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(seguridad_btn_frame, text="🛡️ EJECUTAR DIAGNÓSTICO", 
                  command=self.ejecutar_diagnostico_completo).pack(side=tk.LEFT, padx=(0, 10))

        # 🆕 NUEVO: BOTONES PARA GESTIÓN DE FOTOS
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

        # 🆕 NUEVO: BOTÓN DE SINCRONIZACIÓN AUTOMÁTICA
        self.btn_sincronizacion_auto = ttk.Button(fotos_btn_frame, 
                                                text="🔄 INICIAR SINCRONIZACIÓN AUTO",
                                                command=self.toggle_sincronizacion_auto)
        self.btn_sincronizacion_auto.pack(side=tk.LEFT, padx=(0, 10))

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

    # 🆕 NUEVAS FUNCIONES DE SEGURIDAD
    def escanear_vulnerabilidades(self):
        """Escanea vulnerabilidades del sistema"""
        try:
            self.log("🔍 INICIANDO ESCANEO DE VULNERABILIDADES...")
            reporte = self.gestor_telegram.escanear_vulnerabilidades()
            
            if reporte:
                # Mostrar resumen en messagebox
                resumen = f"""
📊 REPORTE DE SEGURIDAD:

🔴 Vulnerabilidades ALTO: {reporte['summary']['alto']}
🟡 Vulnerabilidades MEDIO: {reporte['summary']['medio']}  
🔵 Vulnerabilidades BAJO: {reporte['summary']['bajo']}
📋 Total: {reporte['vulnerabilities_found']}

El reporte completo se guardó en: reporte_seguridad.json
                """
                messagebox.showinfo("Escaneo Completado", resumen)
            else:
                messagebox.showerror("Error", "No se pudo completar el escaneo de seguridad")
                
        except Exception as e:
            self.log(f"❌ Error en escaneo de vulnerabilidades: {str(e)}")
            messagebox.showerror("Error", f"Error durante el escaneo:\n{str(e)}")

    def ver_reporte_seguridad(self):
        """Muestra el reporte de seguridad generado"""
        try:
            if os.path.exists("reporte_seguridad.json"):
                with open("reporte_seguridad.json", "r", encoding="utf-8") as f:
                    reporte = json.load(f)
                
                # Crear ventana para mostrar reporte
                reporte_window = tk.Toplevel(self.root)
                reporte_window.title("Reporte de Seguridad - Vulnerabilidades")
                reporte_window.geometry("800x600")
                
                # Frame principal
                main_frame = ttk.Frame(reporte_window, padding="10")
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                # Encabezado
                header_frame = ttk.Frame(main_frame)
                header_frame.pack(fill=tk.X, pady=(0, 10))
                
                ttk.Label(header_frame, text="REPORTE DE VULNERABILIDADES", 
                         font=('Arial', 14, 'bold')).pack()
                
                ttk.Label(header_frame, 
                         text=f"Sistema: {reporte['sistema']} | Python: {reporte['python_version']}",
                         font=('Arial', 9)).pack()
                
                # Resumen
                resumen_frame = ttk.LabelFrame(main_frame, text="Resumen", padding="10")
                resumen_frame.pack(fill=tk.X, pady=(0, 10))
                
                ttk.Label(resumen_frame, 
                         text=f"🔴 ALTO: {reporte['summary']['alto']} | 🟡 MEDIO: {reporte['summary']['medio']} | 🔵 BAJO: {reporte['summary']['bajo']}",
                         font=('Arial', 11, 'bold')).pack()
                
                # Lista de vulnerabilidades
                vuln_frame = ttk.LabelFrame(main_frame, text="Vulnerabilidades Detectadas", padding="10")
                vuln_frame.pack(fill=tk.BOTH, expand=True)
                
                # Treeview para mostrar vulnerabilidades
                tree = ttk.Treeview(vuln_frame, columns=('Nivel', 'Tipo', 'Descripción'), show='headings')
                tree.heading('Nivel', text='Nivel')
                tree.heading('Tipo', text='Tipo')
                tree.heading('Descripción', text='Descripción')
                
                tree.column('Nivel', width=80)
                tree.column('Tipo', width=150)
                tree.column('Descripción', width=400)
                
                for vuln in reporte['vulnerabilities']:
                    nivel = vuln['nivel']
                    # Colores según nivel
                    if nivel == 'ALTO':
                        nivel = f'🔴 {nivel}'
                    elif nivel == 'MEDIO':
                        nivel = f'🟡 {nivel}'
                    else:
                        nivel = f'🔵 {nivel}'
                    
                    tree.insert('', tk.END, values=(
                        nivel,
                        vuln['tipo'],
                        vuln['descripcion']
                    ))
                
                # Scrollbar
                scrollbar = ttk.Scrollbar(vuln_frame, orient=tk.VERTICAL, command=tree.yview)
                tree.configure(yscroll=scrollbar.set)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                
            else:
                messagebox.showinfo("Info", "Primero ejecuta el escaneo de vulnerabilidades")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el reporte:\n{str(e)}")

    def ejecutar_diagnostico_completo(self):
        """Ejecuta diagnóstico completo del sistema"""
        try:
            self.log("🛡️ INICIANDO DIAGNÓSTICO COMPLETO...")
            
            # 1. Escanear vulnerabilidades
            reporte = self.gestor_telegram.escanear_vulnerabilidades()
            
            # 2. Verificar carpetas necesarias
            carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 'fotos_entregas']
            for carpeta in carpetas:
                if not os.path.exists(carpeta):
                    os.makedirs(carpeta)
                    self.log(f"✅ Carpeta creada: {carpeta}")
            
            # 3. Verificar conexión a internet
            try:
                requests.get("https://www.google.com", timeout=5)
                self.log("✅ Conexión a internet: OK")
            except:
                self.log("⚠️ Conexión a internet: Limitada")
            
            # 4. Verificar API Key
            if hasattr(self, 'api_key') and self.api_key:
                self.log("✅ API Key de Google: Configurada")
            else:
                self.log("❌ API Key de Google: No configurada")
            
            # 5. Resumen final
            if reporte:
                alto = reporte['summary']['alto']
                medio = reporte['summary']['medio']
                
                if alto > 0:
                    mensaje = f"🚨 CRÍTICO: Se encontraron {alto} vulnerabilidades ALTAS"
                    self.log(mensaje)
                    messagebox.showwarning("Diagnóstico Crítico", 
                                         f"Se encontraron {alto} vulnerabilidades de ALTO riesgo.\n\nRevisa el reporte de seguridad completo.")
                elif medio > 0:
                    mensaje = f"⚠️ ADVERTENCIA: Se encontraron {medio} vulnerabilidades MEDIAS"
                    self.log(mensaje)
                    messagebox.showwarning("Diagnóstico", 
                                         f"Se encontraron {medio} vulnerabilidades de riesgo MEDIO.\n\nSe recomienda revisar el reporte.")
                else:
                    mensaje = "✅ SISTEMA EN ESTADO ÓPTIMO"
                    self.log(mensaje)
                    messagebox.showinfo("Diagnóstico Completado", 
                                      "El sistema se encuentra en estado óptimo.\nNo se encontraron vulnerabilidades críticas.")
            
        except Exception as e:
            self.log(f"❌ Error en diagnóstico: {str(e)}")
            messagebox.showerror("Error", f"Error durante el diagnóstico:\n{str(e)}")

    # ... (el resto de las funciones se mantienen igual, solo agregué las nuevas de seguridad)

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

    # ... (las demás funciones se mantienen igual)

# =============================================================================
# SCRIPT PARA CREAR EL .EXE
# =============================================================================
def crear_archivo_setup():
    """Crea un archivo setup.py para compilar a .exe"""
    setup_content = '''
from cx_Freeze import setup, Executable
import sys

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": [
        "tkinter", "pandas", "requests", "folium", "polyline", "os", "time", 
        "hashlib", "json", "datetime", "threading", "webbrowser", "sys", 
        "subprocess", "shutil", "PIL", "io", "socket", "platform", "psutil", 
        "urllib", "zipfile", "tempfile", "packaging"
    ],
    "include_files": [
        # Incluir archivos necesarios
    ],
    "excludes": ["unittest", "email", "html", "http", "urllib", "xml"],
}

# GUI applications require a different base on Windows (the default is for a console application).
base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="SistemaRutasPRO",
    version="2.0",
    description="Sistema de Gestión de Rutas con Fotos y Seguridad",
    options={"build_exe": build_exe_options},
    executables=[Executable("sistema_rutas_completo_con_vulnerabilidades_y_fotos.py", base=base)]
)
'''

    with open("setup.py", "w", encoding="utf-8") as f:
        f.write(setup_content)

    print("✅ Archivo setup.py creado")
    print("💡 Para crear el .exe ejecuta: python setup.py build")

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    # Crear todas las carpetas necesarias
    carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 
                'incidencias_trafico', 'fotos_acuses', 'fotos_entregas', 'fotos_reportes']
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    # Crear archivo setup.py para compilar a .exe
    crear_archivo_setup()
    
    root = tk.Tk()
    app = SistemaRutasGUI(root)
    root.mainloop()
