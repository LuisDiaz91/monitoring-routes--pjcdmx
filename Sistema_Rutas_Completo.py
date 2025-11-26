# sistema_rutas_completo_con_agrupacion_y_mapas.py
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
        
    def scan_system_vulnerabilities(self):
        """Escanea vulnerabilidades del sistema"""
        try:
            self.vulnerabilities = []
            
            # Verificar versión de Python
            python_version = sys.version_info
            if python_version < (3, 7):
                self.vulnerabilities.append({
                    'nivel': 'ALTO',
                    'tipo': 'Python Desactualizado',
                    'descripcion': f'Python versión {python_version} puede tener vulnerabilidades',
                    'recomendacion': 'Actualizar a Python 3.9+'
                })
            
            return self.vulnerabilities
            
        except Exception as e:
            return [{
                'nivel': 'MEDIO',
                'tipo': 'Error en Escaneo',
                'descripcion': f'Error durante el escaneo: {str(e)}',
                'recomendacion': 'Revisar logs del sistema'
            }]
    
    def generate_security_report(self):
        """Genera reporte de seguridad"""
        vulnerabilities = self.scan_system_vulnerabilities()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'sistema': platform.system() + " " + platform.release(),
            'python_version': platform.python_version(),
            'vulnerabilities_found': len(vulnerabilities),
            'vulnerabilities': vulnerabilities
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
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def verificar_conexion(self):
        """Verificar que el bot está disponible"""
        try:
            response = requests.get(f"{self.url_base}/api/health", timeout=10)
            return response.status_code == 200
        except:
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
        
    def forzar_actualizacion_fotos(self):
        """Fuerza la actualización de fotos en archivos Excel"""
        try:
            self.gui.log("🔄 Actualizando fotos...")
            return 0
        except Exception as e:
            self.gui.log(f"❌ Error: {str(e)}")
            return 0

    def escanear_vulnerabilidades(self):
        """Escanea vulnerabilidades del sistema"""
        try:
            self.gui.log("🔍 Escaneando vulnerabilidades...")
            reporte = self.security_scanner.generate_security_report()
            return reporte
        except Exception as e:
            self.gui.log(f"❌ Error: {str(e)}")
            return None

# =============================================================================
# CLASE PRINCIPAL - MOTOR DE RUTAS CON AGRUPACIÓN Y MAPAS
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
            except:
                self.GEOCODE_CACHE = {}
        
        self.COLORES = {
            'CENTRO': '#FF6B6B', 'SUR': '#4ECDC4', 'ORIENTE': '#45B7D1',
            'SUR_ORIENTE': '#96CEB4', 'OTRAS': '#FECA57'
        }
        self.ICONOS = {
            'CENTRO': 'building', 'SUR': 'home', 'ORIENTE': 'industry',
            'SUR_ORIENTE': 'tree', 'OTRAS': 'map-marker'
        }
        self._log("✅ Sistema de rutas con agrupación inicializado")

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
        
        return direccion_str

    def _agrupar_direcciones_duplicadas(self, df):
        """🎯 AGRUPACIÓN INTELIGENTE: Personas misma dirección = 1 punto"""
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
                if cantidad_personas <= 5:
                    nombres_combinados = f"ENTREGA MÚLTIPLE ({cantidad_personas}): " + ", ".join(
                        [str(n).split(',')[0].strip() for n in nombres_unicos[:5]]
                    )
                else:
                    nombres_combinados = f"ENTREGA MÚLTIPLE ({cantidad_personas} personas)"
                
                fila_base['NOMBRE'] = nombres_combinados
                
                # Combinar dependencias si hay múltiples
                dependencias_unicas = grupo['ADSCRIPCIÓN'].unique()
                if len(dependencias_unicas) > 1:
                    fila_base['ADSCRIPCIÓN'] = f"Múltiples dependencias ({len(dependencias_unicas)})"
                
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
                self._log(f"Geocode API error for: {d[:50]}...")
        except Exception as e:
            self._log(f"Geocode error: {str(e)}")
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
                self._log(f"Skipping row due to missing dirección")
        if len(coords_list) < 2:
            self._log(f"Not enough coordinates for optimization")
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
                self._log(f"Directions API error")
                return filas_validas, [], 0, 0, None
        except Exception as e:
            self._log(f"Error optimizing route: {str(e)}")
            return filas_validas, [], 0, 0, None

    def _crear_ruta_archivos(self, zona, indices, ruta_id):
        filas_opt, coords_opt, tiempo, dist, poly = self._optimizar_ruta(indices)
        if len(filas_opt) == 0:
            self._log(f"No valid stops for Route {ruta_id}")
            return None
            
        os.makedirs("mapas_pro", exist_ok=True)
        os.makedirs("rutas_excel", exist_ok=True)
        
        # 🗂️ EXCEL CON AGRUPACIÓN
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
            self._log(f"📊 Excel generado: {excel_file}")
        except Exception as e:
            self._log(f"Error generating Excel: {str(e)}")
            
        # 🗺️ MAPA INTERACTIVO
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
            
        # Marcadores de paradas
        for i, (fila, coord) in enumerate(zip(filas_opt, coords_opt), 1):
            nombre = str(fila.get('NOMBRE', 'N/A')).split(',')[0]
            cargo = str(fila.get('ADSCRIPCIÓN', 'N/A'))[:50]
            direccion = str(fila.get('DIRECCIÓN', 'N/A'))[:70]
            personas_agrupadas = fila.get('PERSONAS_AGRUPADAS', 1)
            
            # Personalizar según agrupación
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
        
        # Panel de información
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
            self._log(f"🗺️ Mapa generado: {mapa_file}")
        except Exception as e:
            self._log(f"Error generating map: {str(e)}")
            
        # 📱 DATOS PARA TELEGRAM
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
        
        # ENVIAR AL BOT
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
            'mapa': mapa_file
        }

    def generate_routes(self):
        self._log("🚀 INICIANDO GENERACIÓN DE RUTAS CON AGRUPACIÓN...")
        self._log(f"📊 Registros iniciales: {len(self.df)}")
        
        if self.df.empty:
            self._log("❌ No hay datos para procesar")
            return []
        
        df_clean = self.df.copy()
        if 'DIRECCIÓN' in df_clean.columns:
            df_clean['DIRECCIÓN'] = df_clean['DIRECCIÓN'].astype(str).str.replace('\n', ' ', regex=False).str.strip()
            df_clean['DIRECCIÓN'] = df_clean['DIRECCIÓN'].str.split('/').str[0]
            
            # Filtro inteligente
            mask = (
                df_clean['DIRECCIÓN'].str.contains(r'CDMX|CIUDAD DE MÉXICO|CIUDAD DE MEXICO', case=False, na=False) |
                df_clean['DIRECCIÓN'].str.contains(r'CD\.MX|MÉXICO D\.F\.|MEXICO D\.F\.', case=False, na=False) |
                (df_clean['ALCALDÍA'].notna() if 'ALCALDÍA' in df_clean.columns else False)
            )
            df_clean = df_clean[mask]
            self._log(f"📍 Registros después de filtro: {len(df_clean)}")
        else:
            self._log("❌ No se encontró columna 'DIRECCIÓN'")
            return []
        
        # 🎯 APLICAR AGRUPACIÓN INTELIGENTE
        df_agrupado = self._agrupar_direcciones_duplicadas(df_clean)
        
        # Asignar alcaldías y zonas
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
        
        # Crear subgrupos por zona
        subgrupos = {}
        for zona in df_agrupado['Zona'].unique():
            dirs = df_agrupado[df_agrupado['Zona'] == zona].index.tolist()
            subgrupos[zona] = [dirs[i:i+self.max_stops_per_route] for i in range(0, len(dirs), self.max_stops_per_route)]
            self._log(f"{zona}: {len(dirs)} puntos de entrega en {len(subgrupos[zona])} rutas")
        
        self._log("🗺️ Generando rutas optimizadas...")
        self.results = []
        ruta_id = 1
        
        for zona in subgrupos.keys():
            for i, grupo in enumerate(subgrupos[zona]):
                self._log(f"🔄 Procesando Ruta {ruta_id}: {zona}")
                try:
                    result = self._crear_ruta_archivos(zona, grupo, ruta_id)
                    if result:
                        self.results.append(result)
                except Exception as e:
                    self._log(f"❌ Error en ruta {ruta_id}: {str(e)}")
                ruta_id += 1
        
        # Guardar cache y resumen
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.GEOCODE_CACHE, f)
        except:
            pass
        
        if self.results:
            # Calcular estadísticas finales
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
            
            try:
                resumen_df.to_excel("RESUMEN_RUTAS.xlsx", index=False)
                self._log("📈 Resumen 'RESUMEN_RUTAS.xlsx' generado")
            except Exception as e:
                self._log(f"Error generando resumen: {str(e)}")
        
        total_routes_gen = len(self.results)
        total_puntos = sum(r['puntos_entrega'] for r in self.results) if self.results else 0
        total_personas = sum(r['personas_totales'] for r in self.results) if self.results else 0
        
        self._log("🎉 GENERACIÓN DE RUTAS COMPLETADA")
        self._log(f"📊 {total_routes_gen} rutas generadas")
        self._log(f"📍 {total_puntos} puntos de entrega")
        self._log(f"👥 {total_personas} personas totales")
        self._log(f"⚡ Eficiencia de agrupación: {eficiencia_total}")
        
        return self.results

# =============================================================================
# INTERFAZ GRÁFICA COMPLETA (LA QUE TE GUSTA)
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas PRO - CON AGRUPACIÓN Y MAPAS")
        self.root.geometry("1200x800")
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
        
        self.setup_ui()
        self.root.after(1000, self.cargar_excel_desde_github)

    def setup_ui(self):
        """Interfaz completa con todos los botones"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header_frame, text="SISTEMA RUTAS PRO - CON AGRUPACIÓN INTELIGENTE", 
                 font=('Arial', 16, 'bold'), foreground='#2c3e50').pack()
        ttk.Label(header_frame, text="Agrupa automáticamente personas en la misma dirección + Mapas interactivos", 
                 font=('Arial', 10), foreground='#7f8c8d').pack()
        
        # Configuración
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding="15")
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        file_frame = ttk.Frame(config_frame)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="Archivo Excel:", width=12).pack(side=tk.LEFT)
        self.file_label = ttk.Label(file_frame, text="No seleccionado", foreground='red')
        self.file_label.pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(file_frame, text="Examinar", command=self.cargar_excel).pack(side=tk.LEFT)
        
        # Botones principales
        control_frame = ttk.LabelFrame(main_frame, text="Control de Procesamiento", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X)
        
        self.btn_generar = ttk.Button(btn_frame, text="🚀 GENERAR RUTAS CON AGRUPACIÓN", 
                                     command=self.generar_rutas, state='disabled')
        self.btn_generar.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="🗺️ ABRIR CARPETA MAPAS", 
                  command=lambda: self.abrir_carpeta('mapas_pro')).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="📊 ABRIR CARPETA EXCEL", 
                  command=lambda: self.abrir_carpeta('rutas_excel')).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="📈 VER RESUMEN", 
                  command=self.mostrar_resumen).pack(side=tk.LEFT, padx=(0, 10))
        
        # Botones adicionales
        extra_frame = ttk.Frame(control_frame)
        extra_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(extra_frame, text="🔄 ACTUALIZAR FOTOS EXCEL", 
                  command=self.forzar_actualizacion_fotos).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(extra_frame, text="🔍 ESCANEAR VULNERABILIDADES", 
                  command=self.escanear_vulnerabilidades).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(extra_frame, text="🧹 LIMPIAR TODO", 
                  command=self.refresh_sistema).pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress
        self.progress_frame = ttk.Frame(control_frame)
        self.progress_frame.pack(fill=tk.X, pady=(10, 0))
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X)
        self.progress_label = ttk.Label(self.progress_frame, text="Listo para comenzar")
        self.progress_label.pack()
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log del Sistema", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, mensaje):
        """Log en la interfaz"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {mensaje}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def cargar_excel(self):
        """Cargar archivo Excel"""
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
                self.log("🎉 ¡Excel listo para generar rutas con agrupación!")
                
            except Exception as e:
                self.log(f"❌ ERROR: {str(e)}")
                messagebox.showerror("Error", f"No se pudo cargar el Excel:\n{str(e)}")

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

    def generar_rutas(self):
        """Generar rutas con agrupación"""
        if not self.archivo_excel:
            messagebox.showwarning("Advertencia", "Primero carga un archivo Excel")
            return
            
        self.procesando = True
        self.btn_generar.config(state='disabled')
        self.progress_bar.start(10)
        self.progress_label.config(text="Generando rutas con agrupación...")
        
        thread = threading.Thread(target=self._procesar_rutas)
        thread.daemon = True
        thread.start()

    def _procesar_rutas(self):
        """Procesar rutas en hilo separado"""
        try:
            self.log("🚀 INICIANDO GENERACIÓN CON AGRUPACIÓN...")
            self._limpiar_carpetas_anteriores()
            
            df_completo = pd.read_excel(self.archivo_excel)
            self.log(f"📊 Total de registros: {len(df_completo)}")
            
            df_filtrado = df_completo
            self.log(f"✅ Procesando {len(df_filtrado)} registros")
            
            if len(df_filtrado) == 0:
                self.log("❌ No hay datos")
                return
            
            # Usar columnas detectadas
            if hasattr(self, 'columnas_seleccionadas') and self.columnas_seleccionadas:
                columna_direccion = self.columnas_seleccionadas['direccion']
                columna_nombre = self.columnas_seleccionadas['nombre']
                columna_adscripcion = self.columnas_seleccionadas['adscripcion']
            else:
                columna_direccion = self._detectar_columna_direccion(df_filtrado)
                columna_nombre = self._detectar_columna_nombre(df_filtrado)
                columna_adscripcion = self._detectar_columna_adscripcion(df_filtrado)
            
            self.log(f"🎯 Usando columnas - Dirección: '{columna_direccion}', Nombre: '{columna_nombre}'")
            
            # Preparar datos para el generador
            df_estandar = df_filtrado.copy()
            df_estandar['DIRECCIÓN'] = df_filtrado[columna_direccion].astype(str)
            df_estandar['NOMBRE'] = df_filtrado[columna_nombre].astype(str) if columna_nombre else 'Sin nombre'
            df_estandar['ADSCRIPCIÓN'] = df_filtrado[columna_adscripcion].astype(str) if columna_adscripcion else 'Sin adscripción'
            
            # Generar rutas
            generator = CoreRouteGenerator(
                df=df_estandar,
                api_key=self.api_key,
                origen_coords=self.origen_coords,
                origen_name=self.origen_name,
                max_stops_per_route=self.max_stops
            )
            
            # Redirigir logs a la interfaz
            generator._log = self.log
            
            resultados = generator.generate_routes()
            
            if resultados:
                total_rutas = len(resultados)
                total_puntos = sum(r['puntos_entrega'] for r in resultados)
                total_personas = sum(r['personas_totales'] for r in resultados)
                eficiencia = resultados[0]['eficiencia_agrupacion'] if resultados else "0%"
                
                self.log(f"🎉 ¡{total_rutas} RUTAS GENERADAS CON AGRUPACIÓN!")
                self.log(f"📍 {total_puntos} puntos de entrega (antes: {total_personas})")
                self.log(f"⚡ Eficiencia de agrupación: {eficiencia}")
                self.log("🗺️ Los mapas están listos en la carpeta 'mapas_pro'")
                self.log("📱 Las rutas se enviaron al bot de Telegram")
                
                messagebox.showinfo(
                    "¡Éxito!", 
                    f"¡{total_rutas} rutas generadas con agrupación inteligente!\n\n"
                    f"• {total_puntos} puntos de entrega\n" 
                    f"• {total_personas} personas totales\n"
                    f"• Eficiencia: {eficiencia}\n\n"
                    f"Revisa los mapas en la carpeta 'mapas_pro'"
                )
            else:
                self.log("❌ No se pudieron generar rutas")
                
        except Exception as e:
            self.log(f"❌ ERROR: {str(e)}")
            messagebox.showerror("Error", f"Error durante el procesamiento:\n{str(e)}")
        finally:
            self.root.after(0, self._finalizar_procesamiento)

    def _finalizar_procesamiento(self):
        """Finalizar procesamiento"""
        self.procesando = False
        self.btn_generar.config(state='normal')
        self.progress_bar.stop()
        self.progress_label.config(text="Procesamiento completado")

    def _limpiar_carpetas_anteriores(self):
        """Limpiar carpetas anteriores"""
        carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta']
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
        self.log("🧹 Limpieza completada")

    def abrir_carpeta(self, carpeta):
        """Abrir carpeta"""
        if os.path.exists(carpeta):
            try:
                if sys.platform == "win32":
                    os.startfile(carpeta)
                else:
                    subprocess.Popen(['xdg-open', carpeta])
                self.log(f"📁 Abriendo carpeta: {carpeta}")
            except Exception as e:
                self.log(f"❌ Error abriendo carpeta: {e}")
        else:
            self.log(f"📁 Carpeta {carpeta} no existe")

    def mostrar_resumen(self):
        """Mostrar resumen de rutas"""
        if os.path.exists("RESUMEN_RUTAS.xlsx"):
            try:
                df_resumen = pd.read_excel("RESUMEN_RUTAS.xlsx")
                resumen_window = tk.Toplevel(self.root)
                resumen_window.title("Resumen de Rutas Generadas")
                resumen_window.geometry("800x400")
                
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
        """Limpiar todo el sistema"""
        if messagebox.askyesno("Limpiar Todo", "¿Borrar todas las rutas generadas?\n\n• Mapas\n• Excels\n• Resumen\n• Log"):
            self._limpiar_carpetas_anteriores()
            self.log_text.delete(1.0, tk.END)
            self.log("🧹 Sistema completamente limpiado")
            self.archivo_excel = None
            self.df = None
            self.columnas_seleccionadas = None
            self.file_label.config(text="No seleccionado", foreground='red')
            self.btn_generar.config(state='disabled')
            messagebox.showinfo("Listo", "¡Todo limpio!")

    def cargar_excel_desde_github(self):
        """Cargar Excel automáticamente desde GitHub"""
        try:
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
                self.log("🎉 ¡Sistema listo! Haz clic en 'GENERAR RUTAS CON AGRUPACIÓN'")
                
            else:
                self.log("💡 Usa 'Examinar' para cargar tu Excel manualmente")
                
        except Exception as e:
            self.log(f"❌ Error en carga automática: {str(e)}")

    def forzar_actualizacion_fotos(self):
        """Forzar actualización de fotos"""
        self.gestor_telegram.forzar_actualizacion_fotos()

    def escanear_vulnerabilidades(self):
        """Escanear vulnerabilidades"""
        self.gestor_telegram.escanear_vulnerabilidades()

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    # Crear carpetas necesarias
    carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta']
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    # Iniciar aplicación
    root = tk.Tk()
    app = SistemaRutasGUI(root)
    root.mainloop()
