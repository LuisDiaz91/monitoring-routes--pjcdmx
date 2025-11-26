# sistema_rutas_completo_con_agrupacion.py
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
import urllib.request
import zipfile
import tempfile
import psutil
from packaging import version
import re

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
            foto_url = avance.get('foto_url', '')
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
                
                # Buscar coincidencias
                if (persona_buscar in nombre_en_excel or 
                    nombre_en_excel in persona_buscar or
                    self._coincidencia_flexible_nombres(persona_buscar, nombre_en_excel)):
                    
                    # ACTUALIZAR EXCEL CON LINK DE FOTO
                    link_foto = foto_url if foto_url else foto_local
                    
                    df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                    df.at[idx, 'Repartidor'] = repartidor
                    df.at[idx, 'Foto_Acuse'] = link_foto
                    df.at[idx, 'Link_Foto'] = f'=HIPERVINCULO("{link_foto}")' if link_foto else ''
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
            avance_simulado = {
                'ruta_id': ruta_id,
                'repartidor': repartidor,
                'persona_entregada': persona,
                'timestamp': datetime.now().isoformat(),
                'foto_url': f"https://ejemplo.com/fotos/entrega_{ruta_id}.jpg",
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
# CLASE PRINCIPAL - MOTOR DE RUTAS CON AGRUPACIÓN
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

    def _normalizar_direccion(self, direccion):
        """Normaliza una dirección para comparación"""
        if pd.isna(direccion):
            return ""
        
        direccion_str = str(direccion).upper().strip()
        
        # Eliminar caracteres especiales y múltiples espacios
        direccion_str = re.sub(r'[^\w\s]', ' ', direccion_str)
        direccion_str = re.sub(r'\s+', ' ', direccion_str)
        
        # Eliminar palabras comunes que no afectan la ubicación
        palabras_comunes = ['CDMX', 'CIUDAD', 'DE', 'MÉXICO', 'MEXICO', 'COLONIA', 'COL', 
                           'CALLE', 'AVENIDA', 'AVE', 'NÚMERO', 'NUM', 'NO', '#', 'CP']
        
        palabras = direccion_str.split()
        palabras_filtradas = [p for p in palabras if p not in palabras_comunes and len(p) > 2]
        
        return ' '.join(palabras_filtradas)

    def _agrupar_direcciones_duplicadas(self, df):
        """Agrupa personas que comparten la misma dirección"""
        self._log("🔍 Agrupando direcciones duplicadas...")
        
        # Crear una columna normalizada para dirección
        df['DIRECCIÓN_NORMALIZADA'] = df['DIRECCIÓN'].apply(self._normalizar_direccion)
        
        # Contar direcciones únicas
        direcciones_unicas = df['DIRECCIÓN_NORMALIZADA'].nunique()
        total_registros = len(df)
        self._log(f"📍 Direcciones únicas: {direcciones_unicas} de {total_registros} registros")
        
        # Agrupar por dirección normalizada
        grupos = df.groupby('DIRECCIÓN_NORMALIZADA')
        
        datos_agrupados = []
        direcciones_agrupadas = 0
        
        for direccion_norm, grupo in grupos:
            cantidad_personas = len(grupo)
            
            if cantidad_personas > 1:
                direcciones_agrupadas += 1
                self._log(f"👥 Dirección agrupada: {cantidad_personas} personas en '{grupo.iloc[0]['DIRECCIÓN'][:50]}...'")
                
                # Tomar la primera fila como base
                fila_base = grupo.iloc[0].copy()
                
                # Combinar nombres
                nombres_unicos = grupo['NOMBRE'].unique()
                if len(nombres_unicos) > 1:
                    if cantidad_personas <= 5:
                        nombres_combinados = f"ENTREGA MÚLTIPLE ({cantidad_personas}): " + ", ".join(
                            [str(n).split(',')[0].strip() for n in nombres_unicos]
                        )
                    else:
                        nombres_combinados = f"ENTREGA MÚLTIPLE ({cantidad_personas} personas)"
                    
                    fila_base['NOMBRE'] = nombres_combinados
                
                # Combinar dependencias
                dependencias_unicas = grupo['ADSCRIPCIÓN'].unique()
                if len(dependencias_unicas) > 1:
                    if len(dependencias_unicas) <= 3:
                        dependencias_combinadas = "Múltiples: " + ", ".join(
                            [str(d).strip() for d in dependencias_unicas if pd.notna(d)]
                        )
                    else:
                        dependencias_combinadas = f"Múltiples dependencias ({len(dependencias_unicas)})"
                    
                    fila_base['ADSCRIPCIÓN'] = dependencias_combinadas
                
                # Agregar información de agrupación
                fila_base['PERSONAS_AGRUPADAS'] = cantidad_personas
                fila_base['NOMBRES_ORIGINALES'] = " | ".join([str(n).strip() for n in grupo['NOMBRE']])
                
                datos_agrupados.append(fila_base)
                
            else:
                # Solo una persona en esta dirección
                fila_unica = grupo.iloc[0].copy()
                fila_unica['PERSONAS_AGRUPADAS'] = 1
                fila_unica['NOMBRES_ORIGINALES'] = str(fila_unica['NOMBRE'])
                datos_agrupados.append(fila_unica)
        
        # Crear nuevo DataFrame agrupado
        df_agrupado = pd.DataFrame(datos_agrupados)
        
        self._log(f"🎯 Reducción de {total_registros} → {len(df_agrupado)} puntos de entrega")
        self._log(f"👥 {direcciones_agrupadas} direcciones con múltiples personas agrupadas")
        
        return df_agrupado

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
        
        # EXCEL MEJORADO CON INFORMACIÓN DE AGRUPACIÓN
        excel_data = []
        for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1):
            personas_agrupadas = fila.get('PERSONAS_AGRUPADAS', 1)
            
            excel_data.append({
                'Orden': i,
                'Nombre': str(fila.get('NOMBRE', 'N/A')).split(',')[0].strip(),
                'Dependencia': str(fila.get('ADSCRIPCIÓN', 'N/A')).strip(),
                'Dirección': str(fila.get('DIRECCIÓN', 'N/A')).strip(),
                'Personas_Agrupadas': personas_agrupadas,
                'Nombres_Originales': fila.get('NOMBRES_ORIGINALES', ''),
                'Acuse': '',
                'Repartidor': '',
                'Foto_Acuse': '',
                'Link_Foto': '',
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
            personas_agrupadas = fila.get('PERSONAS_AGRUPADAS', 1)
            
            # Personalizar popup según agrupación
            if personas_agrupadas > 1:
                popup_html = f"""
                <div style='font-family:Arial; width:280px;'>
                    <b>#{i} 📦 ENTREGA MÚLTIPLE ({personas_agrupadas} personas)</b><br>
                    <i>{cargo}</i><br>
                    <small>{direccion}...</small><br>
                    <hr style='margin:5px 0;'>
                    <small><b>Personas:</b> {personas_agrupadas} en esta ubicación</small>
                </div>
                """
                icon_color = 'orange'
                icon_type = 'users'
            else:
                popup_html = f"""
                <div style='font-family:Arial; width:250px;'>
                    <b>#{i} {nombre}</b><br>
                    <i>{cargo}</i><br>
                    <small>{direccion}...</small>
                </div>
                """
                icon_color = 'red'
                icon_type = self.ICONOS.get(zona, 'circle')
            
            folium.Marker(
                coord,
                popup=popup_html,
                tooltip=f"#{i} {nombre}",
                icon=folium.Icon(color=icon_color, icon=icon_type, prefix='fa')
            ).add_to(m)
        
        # Calcular estadísticas de agrupación
        total_personas = sum(fila.get('PERSONAS_AGRUPADAS', 1) for fila in filas_opt)
        puntos_entrega = len(filas_opt)
        eficiencia = f"{(1 - (puntos_entrega / total_personas)) * 100:.1f}%" if total_personas > 0 else "0%"
        
        info_panel_html = f"""
        <div style="position:fixed;top:10px;left:50px;z-index:1000;background:white;padding:15px;border-radius:10px;
                    box-shadow:0 0 15px rgba(0,0,0,0.2);border:2px solid {color};font-family:Arial;max-width:350px;">
            <h4 style="margin:0 0 10px;color:#2c3e50;border-bottom:2px solid {color};padding-bottom:5px;">
                Ruta {ruta_id} - {zona}
            </h4>
            <small>
                <b>Puntos de entrega:</b> {puntos_entrega}<br>
                <b>Personas totales:</b> {total_personas}<br>
                <b>Eficiencia agrupación:</b> {eficiencia}<br>
                <b>Distancia:</b> {dist:.1f} km | <b>Tiempo:</b> {tiempo:.0f} min<br>
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
                    'personas_agrupadas': fila.get('PERSONAS_AGRUPADAS', 1),
                    'nombres_originales': fila.get('NOMBRES_ORIGINALES', ''),
                    'estado': 'pendiente',
                    'timestamp_entrega': None,
                    'foto_acuse': None,
                    'foto_url': None
                }
                for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1)
            ],
            'estadisticas': {
                'puntos_entrega': puntos_entrega,
                'personas_totales': total_personas,
                'eficiencia_agrupacion': eficiencia,
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
            'puntos_entrega': puntos_entrega,
            'personas_totales': total_personas,
            'eficiencia_agrupacion': eficiencia,
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
            
            # FILTRO INTELIGENTE
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
        
        # 🆕 AGRUPAR DIRECCIONES DUPLICADAS
        df_agrupado = self._agrupar_direcciones_duplicadas(df_clean)
        
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
        
        df_agrupado['Alcaldia'] = df_agrupado['DIRECCIÓN'].apply(extraer_alcaldia)
        
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
        
        df_agrupado['Zona'] = df_agrupado['Alcaldia'].apply(asignar_zona)
        
        subgrupos = {}
        for zona in df_agrupado['Zona'].unique():
            dirs = df_agrupado[df_agrupado['Zona'] == zona].index.tolist()
            subgrupos[zona] = [dirs[i:i+self.max_stops_per_route] for i in range(0, len(dirs), self.max_stops_per_route)]
            self._log(f"{zona}: {len(dirs)} puntos de entrega en {len(subgrupos[zona])} rutas")
        
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
            # CALCULAR ESTADÍSTICAS FINALES DE AGRUPACIÓN
            total_puntos_entrega = sum(r['puntos_entrega'] for r in self.results)
            total_personas = sum(r['personas_totales'] for r in self.results)
            eficiencia_total = f"{(1 - (total_puntos_entrega / total_personas)) * 100:.1f}%" if total_personas > 0 else "0%"
            
            resumen_df = pd.DataFrame([{
                'Ruta': r['ruta_id'],
                'Zona': r['zona'],
                'Puntos_Entrega': r['puntos_entrega'],
                'Personas_Totales': r['personas_totales'],
                'Eficiencia_Agrupacion': r['eficiencia_agrupacion'],
                'Distancia_km': r['distancia'],
                'Tiempo_min': r['tiempo'],
                'Excel': os.path.basename(r['excel']),
                'Mapa': os.path.basename(r['mapa'])
            } for r in self.results])
            
            # Agregar fila de totales
            total_row = {
                'Ruta': 'TOTAL',
                'Zona': '-',
                'Puntos_Entrega': total_puntos_entrega,
                'Personas_Totales': total_personas,
                'Eficiencia_Agrupacion': eficiencia_total,
                'Distancia_km': sum(r['distancia'] for r in self.results),
                'Tiempo_min': sum(r['tiempo'] for r in self.results),
                'Excel': '-',
                'Mapa': '-'
            }
            resumen_df = pd.concat([resumen_df, pd.DataFrame([total_row])], ignore_index=True)
            
            try:
                resumen_df.to_excel("RESUMEN_RUTAS.xlsx", index=False)
                self._log("Summary 'RESUMEN_RUTAS.xlsx' generated.")
            except Exception as e:
                self._log(f"Error generating summary: {str(e)}")
        
        total_routes_gen = len(self.results)
        total_puntos = sum(r['puntos_entrega'] for r in self.results) if self.results else 0
        total_personas = sum(r['personas_totales'] for r in self.results) if self.results else 0
        total_distancia = sum(r['distancia'] for r in self.results) if self.results else 0
        total_tiempo = sum(r['tiempo'] for r in self.results) if self.results else 0
        
        self._log("CORE ROUTE GENERATION COMPLETED")
        self._log(f"FINAL SUMMARY: {total_routes_gen} rutas, {total_puntos} puntos de entrega, {total_personas} personas")
        self._log(f"EFICIENCIA DE AGRUPACIÓN: {eficiencia_total}")
        
        return self.results

# =============================================================================
# EL RESTO DEL CÓDIGO SE MANTIENE IGUAL (SistemaRutasGUI y ejecución)
# =============================================================================

# [Aquí iría el resto del código de SistemaRutasGUI que ya te pasé...
# Pero con la nueva CoreRouteGenerator que incluye agrupación]

# Para ahorrar espacio, solo incluyo la parte modificada. El resto del código
# de la interfaz gráfica es el mismo que ya tienes funcionando.

def crear_archivo_setup():
    setup_content = '''
from cx_Freeze import setup, Executable
import sys

build_exe_options = {
    "packages": [
        "tkinter", "pandas", "requests", "folium", "polyline", "os", "time", 
        "hashlib", "json", "datetime", "threading", "webbrowser", "sys", 
        "subprocess", "shutil", "PIL", "io", "socket", "platform", "psutil", 
        "urllib", "zipfile", "tempfile", "packaging", "re"
    ],
    "include_files": [],
    "excludes": ["unittest", "email", "html", "http", "urllib", "xml"],
}

base = None
if sys.platform == "win32":
    base = "Win32GUI"

setup(
    name="SistemaRutasPRO",
    version="2.1",
    description="Sistema de Gestión de Rutas con Agrupación Inteligente",
    options={"build_exe": build_exe_options},
    executables=[Executable("sistema_rutas_completo_con_agrupacion.py", base=base)]
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
    carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 
                'incidencias_trafico', 'fotos_acuses', 'fotos_entregas', 'fotos_reportes']
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    crear_archivo_setup()
    
    root = tk.Tk()
    
    # Para ahorrar espacio, aquí iría tu clase SistemaRutasGUI completa
    # que ya tienes funcionando, pero usando la nueva CoreRouteGenerator
    
    # Como ejemplo mínimo:
    from tkinter import messagebox
    messagebox.showinfo("Sistema Actualizado", 
                       "¡Sistema con agrupación inteligente listo!\n\n"
                       "Ahora el sistema agrupará automáticamente a las personas "
                       "que comparten la misma dirección en un solo punto de entrega.")
    
    root.mainloop()
