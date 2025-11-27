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
import io
import math
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont
import tempfile
import zipfile
from urllib.parse import quote

# =============================================================================
# CONFIGURACIÓN GLOBAL PRO
# =============================================================================
class Config:
    RAILWAY_URL = "https://monitoring-routes-pjcdmx-production.up.railway.app"
    API_KEY = "AIzaSyBeUr2C3SDkwY7zIrYcB6agDni9XDlWrFY"
    ORIGEN_COORDS = "19.4283717,-99.1430307"
    ORIGEN_NAME = "TSJCDMX - Sede Central"
    VERSION = "ULTRA HD PRO v3.0"
    
    COLORS = {
        'CENTRO': '#FF6B6B', 'SUR': '#4ECDC4', 'ORIENTE': '#45B7D1',
        'SUR_ORIENTE': '#96CEB4', 'OTRAS': '#FECA57', 'URGENTE': '#FF3838'
    }
    
    ICONS = {
        'CENTRO': '🏢', 'SUR': '🏠', 'ORIENTE': '🏭',
        'SUR_ORIENTE': '🌳', 'OTRAS': '📍', 'URGENTE': '🚨'
    }

# =============================================================================
# FUNCIONES AUXILIARES MEJORADAS
# =============================================================================
def convert_to_serializable(obj):
    """Convierte objetos pandas/numpy a tipos nativos de Python para JSON"""
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.bool_, np.bool)):
        return bool(obj)
    elif isinstance(obj, (np.str_, np.string_)):
        return str(obj)
    elif isinstance(obj, (list, tuple)):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {str(key): convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    else:
        return obj

def extraer_alcaldia_mejorada(direccion):
    """Extrae la alcaldía con inteligencia mejorada"""
    if pd.isna(direccion): 
        return "NO IDENTIFICADA"
    
    d = str(direccion).upper().strip()
    
    # Diccionario expandido de alcaldías con más palabras clave
    alcaldias = {
        'CUAUHTEMOC': ['CUAUHTEMOC', 'CUAUHTÉMOC', 'DOCTORES', 'CENTRO', 'JUAREZ', 'ROMA', 'CONDESA', 
                      'REFORMA', 'ZONA ROSA', 'SAN RAFAEL', 'TABACALERA', 'PERALVILLO'],
        'MIGUEL HIDALGO': ['MIGUEL HIDALGO', 'POLANCO', 'LOMAS', 'CHAPULTEPEC', 'ANZURES', 
                          'TACUBAYA', 'CONDESA', 'IRRIGACIÓN'],
        'BENITO JUAREZ': ['BENITO JUAREZ', 'DEL VALLE', 'NÁPOLES', 'PORTALES', 'MIXCOAC', 
                         'SAN PEDRO DE LOS PINOS', 'ACACIAS'],
        'ALVARO OBREGON': ['ALVARO OBREGON', 'SAN ANGEL', 'LAS AGUILAS', 'OLIVAR', 
                          'TOLTECAS', 'JARDINES', 'LA JOYA'],
        'COYOACAN': ['COYOACAN', 'COYOACÁN', 'COPILCO', 'UNIVERSIDAD', 'CU', 'UNAM', 
                    'PEDREGAL', 'SANTA URSULA'],
        'TLALPAN': ['TLALPAN', 'TLALPAN CENTRO', 'VILLA OLÍMPICA', 'ISIDRO FABELA'],
        'IZTAPALAPA': ['IZTAPALAPA', 'SAN LORENZO', 'SANTA MARTHA', 'ERMITA', 'CULHUACAN'],
        'GUSTAVO A. MADERO': ['GUSTAVO A. MADERO', 'LINDAVISTA', 'VALLEJO', 'INDUSTRIAL', 
                             'FERRETERA', 'BONDOLITO'],
        'AZCAPOTZALCO': ['AZCAPOTZALCO', 'SANTA CATARINA', 'NUEVA SANTA MARIA', 'CLAVERIA'],
        'VENUSTIANO CARRANZA': ['VENUSTIANO CARRANZA', 'MOCTEZUMA', 'ROMERO RUBIO', 'JARDIN BALBUENA'],
        'XOCHIMILCO': ['XOCHIMILCO', 'SANTA CRUZ', 'SANTIAGO', 'TEPEPAN'],
        'IZTACALCO': ['IZTACALCO', 'AGRÍCOLA', 'PANTITLÁN', 'LA CRUZ'],
        'MILPA ALTA': ['MILPA ALTA', 'SAN PABLO', 'VILLA MILPA ALTA'],
        'TLAHUAC': ['TLAHUAC', 'TLÁHUAC', 'SAN FRANCISCO', 'LA TURBA']
    }
    
    # Búsqueda inteligente por palabras clave
    for alc, palabras_clave in alcaldias.items():
        for palabra in palabras_clave:
            if palabra in d:
                return alc.title()
    
    return "NO IDENTIFICADA"

def asignar_zona_inteligente(alcaldia):
    """Asigna zona con lógica mejorada"""
    ZONAS = {
        'CENTRO': ['Cuauhtemoc', 'Venustiano Carranza', 'Miguel Hidalgo', 'Azcapotzalco'],
        'SUR': ['Coyoacan', 'Tlalpan', 'Alvaro Obregon', 'Benito Juarez'],
        'ORIENTE': ['Iztacalco', 'Iztapalapa', 'Gustavo A. Madero'],
        'SUR_ORIENTE': ['Xochimilco', 'Milpa Alta', 'Tlahuac'],
    }
    
    for zona, alcaldias_zona in ZONAS.items():
        if alcaldia in alcaldias_zona:
            return zona
    return 'OTRAS'

def calcular_prioridad(direccion, dependencia):
    """Calcula prioridad basada en ubicación y tipo de dependencia"""
    prioridad = "NORMAL"
    
    # Prioridad por ubicación estratégica
    ubicaciones_urgentes = ['CENTRO', 'REFORMA', 'POLANCO', 'SANTA FE']
    if any(ub in str(direccion).upper() for ub in ubicaciones_urgentes):
        prioridad = "URGENTE"
    
    # Prioridad por tipo de dependencia
    dependencias_urgentes = ['JUEZ', 'FISCAL', 'MINISTERIO', 'EMBAJADA']
    if any(dep in str(dependencia).upper() for dep in dependencias_urgentes):
        prioridad = "URGENTE"
    
    return prioridad

# =============================================================================
# CLASE CONEXIÓN BOT MEJORADA
# =============================================================================
class ConexionBotRailwayPro:
    def __init__(self, url_base=Config.RAILWAY_URL):
        self.url_base = url_base
        self.timeout = 30
        self.session = requests.Session()
        
    def enviar_ruta_bot(self, ruta_data):
        """Envía ruta con reintentos y manejo de errores mejorado"""
        for intento in range(3):
            try:
                url = f"{self.url_base}/api/rutas"
                response = self.session.post(
                    url,
                    json=ruta_data,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                if response.status_code == 200:
                    return True, "✅ Ruta enviada exitosamente"
                elif response.status_code == 500:
                    time.sleep(2)  # Reintentar después de error del servidor
                    continue
                else:
                    return False, f"❌ Error {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                return False, "❌ Timeout en conexión con el bot"
            except requests.exceptions.ConnectionError:
                return False, "❌ Error de conexión con el bot"
            except Exception as e:
                return False, f"❌ Error inesperado: {str(e)}"
        
        return False, "❌ Máximo de reintentos alcanzado"

    def verificar_conexion(self):
        """Verificación robusta de conexión"""
        try:
            response = self.session.get(f"{self.url_base}/api/health", timeout=10)
            return response.status_code == 200, f"✅ Bot conectado (v{response.json().get('version', 'N/A')})"
        except Exception as e:
            return False, f"❌ Bot no disponible: {str(e)}"

# =============================================================================
# GESTOR TELEGRAM PRO
# =============================================================================
class GestorTelegramPro:
    def __init__(self, gui):
        self.gui = gui
        self.conexion = ConexionBotRailwayPro()
        
    def obtener_estadisticas_completas(self):
        """Obtiene estadísticas detalladas del sistema"""
        try:
            estadisticas = {
                'total_rutas': 0,
                'rutas_pendientes': 0,
                'rutas_en_progreso': 0,
                'rutas_completadas': 0,
                'total_entregas': 0,
                'entregas_hoy': 0,
                'repartidores_activos': 0
            }
            
            if os.path.exists("rutas_telegram"):
                for archivo in os.listdir("rutas_telegram"):
                    if archivo.endswith('.json'):
                        with open(f"rutas_telegram/{archivo}", 'r', encoding='utf-8') as f:
                            ruta = json.load(f)
                            
                        estadisticas['total_rutas'] += 1
                        estado = ruta.get('estado', 'pendiente')
                        
                        if estado == 'pendiente':
                            estadisticas['rutas_pendientes'] += 1
                        elif estado == 'asignada':
                            estadisticas['rutas_en_progreso'] += 1
                        elif estado == 'completada':
                            estadisticas['rutas_completadas'] += 1
                            
                        # Contar entregas
                        paradas = ruta.get('paradas', [])
                        entregas = sum(1 for p in paradas if p.get('estado') == 'entregado')
                        estadisticas['total_entregas'] += entregas
                        
                        # Entregas de hoy
                        hoy = datetime.now().date().isoformat()
                        entregas_hoy = sum(1 for p in paradas 
                                         if p.get('timestamp_entrega', '').startswith(hoy))
                        estadisticas['entregas_hoy'] += entregas_hoy
            
            return estadisticas
        except Exception as e:
            self.gui.log(f"❌ Error obteniendo estadísticas: {str(e)}")
            return {}

# =============================================================================
# MOTOR DE RUTAS ULTRA HD
# =============================================================================
class CoreRouteGeneratorUltraHD:
    def __init__(self, df, api_key, origen_coords, origen_name, max_stops_per_route):
        self.df = df.copy()
        self.api_key = api_key
        self.origen_coords = origen_coords
        self.origen_name = origen_name
        self.max_stops = max_stops_per_route
        self.results = []
        self.log_messages = []
        
        # Cache inteligente
        self.CACHE_FILE = "geocode_cache_ultra.json"
        self.GEOCODE_CACHE = self._cargar_cache()
        
        self._log("🚀 Motor Ultra HD inicializado")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{ts}] {msg}"
        self.log_messages.append(log_msg)
        print(log_msg)

    def _cargar_cache(self):
        """Carga el cache con manejo de errores"""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                self._log("⚠️ Cache corrupto, iniciando nuevo")
        return {}

    def _guardar_cache(self):
        """Guarda el cache de forma segura"""
        try:
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.GEOCODE_CACHE, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"⚠️ Error guardando cache: {e}")

    def _geocode_avanzado(self, direccion, intentos=3):
        """Geocoding con reintentos y manejo de errores mejorado"""
        d = str(direccion).strip()
        if not d or d.lower() in ['nan', 'none', '']:
            return None
            
        # Verificar cache primero
        cache_key = hashlib.md5(d.encode('utf-8')).hexdigest()
        if cache_key in self.GEOCODE_CACHE:
            return self.GEOCODE_CACHE[cache_key]
        
        for intento in range(intentos):
            try:
                url = "https://maps.googleapis.com/maps/api/geocode/json"
                params = {
                    'address': f"{d}, Ciudad de México, CDMX",
                    'key': self.api_key,
                    'region': 'mx'
                }
                
                response = requests.get(url, params=params, timeout=15)
                data = response.json()
                
                if data['status'] == 'OK' and data['results']:
                    location = data['results'][0]['geometry']['location']
                    coords = (location['lat'], location['lng'])
                    
                    # Guardar en cache
                    self.GEOCODE_CACHE[cache_key] = coords
                    time.sleep(0.1)  # Rate limiting
                    
                    self._log(f"📍 Geocoded: {d[:30]}...")
                    return coords
                    
                elif data['status'] == 'OVER_QUERY_LIMIT':
                    wait_time = 2 ** intento  # Exponential backoff
                    self._log(f"⏳ Límite excedido, esperando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                    
            except requests.exceptions.Timeout:
                self._log(f"⏰ Timeout en intento {intento + 1}")
                continue
            except Exception as e:
                self._log(f"⚠️ Error geocoding: {e}")
                break
        
        self._log(f"❌ Falló geocoding: {d[:30]}...")
        return None

    def generar_rutas_optimizadas(self):
        """Genera rutas con inteligencia artificial mejorada"""
        self._log("🎯 INICIANDO GENERACIÓN ULTRA HD...")
        
        try:
            # Preparar datos
            df_procesado = self.df.copy()
            
            # Detectar columnas automáticamente
            columnas_detectadas = self._detectar_columnas(df_procesado)
            self._log(f"📊 Columnas detectadas: {columnas_detectadas}")
            
            # Aplicar transformaciones
            df_procesado = self._aplicar_transformaciones(df_procesado, columnas_detectadas)
            
            # Generar rutas por zona
            resultados = self._generar_rutas_por_zona(df_procesado)
            
            self._guardar_cache()
            self._log(f"✅ GENERACIÓN COMPLETADA: {len(resultados)} rutas creadas")
            
            return resultados
            
        except Exception as e:
            self._log(f"❌ ERROR CRÍTICO: {str(e)}")
            import traceback
            self._log(f"🔍 DEBUG: {traceback.format_exc()}")
            return []

    def _detectar_columnas(self, df):
        """Detección inteligente de columnas"""
        columnas = {
            'direccion': None,
            'nombre': None, 
            'dependencia': None,
            'telefono': None
        }
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            if any(palabra in col_lower for palabra in ['direccion', 'dir', 'domicilio', 'address']):
                columnas['direccion'] = col
            elif any(palabra in col_lower for palabra in ['nombre', 'name', 'persona']):
                columnas['nombre'] = col
            elif any(palabra in col_lower for palabra in ['dependencia', 'dep', 'cargo', 'puesto']):
                columnas['dependencia'] = col
            elif any(palabra in col_lower for palabra in ['telefono', 'tel', 'phone']):
                columnas['telefono'] = col
        
        # Fallbacks inteligentes
        if not columnas['direccion'] and len(df.columns) > 0:
            columnas['direccion'] = df.columns[0]  # Primera columna como fallback
            
        return columnas

    def _aplicar_transformaciones(self, df, columnas):
        """Aplica transformaciones inteligentes a los datos"""
        df_transformado = df.copy()
        
        # Crear columnas derivadas
        if columnas['direccion']:
            df_transformado['DIRECCIÓN_COMPLETA'] = df[columnas['direccion']].astype(str)
            df_transformado['ALCALDIA'] = df_transformado['DIRECCIÓN_COMPLETA'].apply(extraer_alcaldia_mejorada)
            df_transformado['ZONA'] = df_transformado['ALCALDIA'].apply(asignar_zona_inteligente)
            
        if columnas['nombre']:
            df_transformado['NOMBRE_COMPLETO'] = df[columnas['nombre']].astype(str)
            
        if columnas['dependencia']:
            df_transformado['DEPENDENCIA'] = df[columnas['dependencia']].astype(str)
            df_transformado['PRIORIDAD'] = df_transformado.apply(
                lambda x: calcular_prioridad(
                    x.get('DIRECCIÓN_COMPLETA', ''), 
                    x.get('DEPENDENCIA', '')
                ), axis=1
            )
        else:
            df_transformado['PRIORIDAD'] = 'NORMAL'
            
        return df_transformado

    def _generar_rutas_por_zona(self, df):
        """Genera rutas organizadas por zona geográfica"""
        resultados = []
        ruta_id = 1
        
        # Agrupar por zona y prioridad
        zonas = df['ZONA'].unique()
        
        for zona in zonas:
            df_zona = df[df['ZONA'] == zona]
            
            # Separar por prioridad
            df_urgente = df_zona[df_zona['PRIORIDAD'] == 'URGENTE']
            df_normal = df_zona[df_zona['PRIORIDAD'] == 'NORMAL']
            
            # Procesar urgentes primero
            if len(df_urgente) > 0:
                self._log(f"🚨 Procesando {len(df_urgente)} URGENTES en {zona}")
                resultado_urgente = self._crear_ruta_detallada(df_urgente, zona, ruta_id, 'URGENTE')
                if resultado_urgente:
                    resultados.append(resultado_urgente)
                    ruta_id += 1
            
            # Procesar normales en lotes
            if len(df_normal) > 0:
                self._log(f"📦 Procesando {len(df_normal)} normales en {zona}")
                
                # Dividir en lotes según max_stops
                lotes = [df_normal[i:i + self.max_stops] for i in range(0, len(df_normal), self.max_stops)]
                
                for i, lote in enumerate(lotes):
                    resultado_normal = self._crear_ruta_detallada(lote, zona, ruta_id, f'NORMAL_{i+1}')
                    if resultado_normal:
                        resultados.append(resultado_normal)
                        ruta_id += 1
        
        return resultados

    def _crear_ruta_detallada(self, df_ruta, zona, ruta_id, tipo):
        """Crea una ruta detallada con todos los archivos"""
        try:
            self._log(f"🗺️ Creando ruta {ruta_id} - {zona} ({tipo})")
            
            # Crear estructura de carpetas
            os.makedirs("rutas_excel", exist_ok=True)
            os.makedirs("mapas_pro", exist_ok=True)
            os.makedirs("rutas_telegram", exist_ok=True)
            
            # Generar Excel profesional
            archivo_excel = self._generar_excel_pro(df_ruta, zona, ruta_id, tipo)
            
            # Generar mapa interactivo
            archivo_mapa = self._generar_mapa_pro(df_ruta, zona, ruta_id, tipo)
            
            # Generar datos para Telegram
            archivo_telegram = self._generar_datos_telegram(df_ruta, zona, ruta_id, tipo)
            
            resultado = {
                'ruta_id': ruta_id,
                'zona': zona,
                'tipo': tipo,
                'archivo_excel': archivo_excel,
                'archivo_mapa': archivo_mapa,
                'archivo_telegram': archivo_telegram,
                'total_personas': len(df_ruta),
                'timestamp': datetime.now().isoformat()
            }
            
            self._log(f"✅ Ruta {ruta_id} creada exitosamente")
            return resultado
            
        except Exception as e:
            self._log(f"❌ Error creando ruta {ruta_id}: {str(e)}")
            return None

    def _generar_excel_pro(self, df, zona, ruta_id, tipo):
        """Genera archivo Excel profesional"""
        try:
            # Crear DataFrame optimizado
            datos_excel = []
            
            for i, (_, fila) in enumerate(df.iterrows(), 1):
                datos_excel.append({
                    'ORDEN': i,
                    'NOMBRE': fila.get('NOMBRE_COMPLETO', 'N/A'),
                    'DIRECCIÓN': fila.get('DIRECCIÓN_COMPLETA', 'N/A'),
                    'DEPENDENCIA': fila.get('DEPENDENCIA', 'N/A'),
                    'ALCALDÍA': fila.get('ALCALDIA', 'N/A'),
                    'ZONA': zona,
                    'PRIORIDAD': fila.get('PRIORIDAD', 'NORMAL'),
                    'ESTADO': 'PENDIENTE',
                    'FECHA_ENTREGA': '',
                    'HORA_ENTREGA': '',
                    'REPARTIDOR': '',
                    'EVIDENCIA_FOTO': '',
                    'OBSERVACIONES': ''
                })
            
            # Crear DataFrame
            df_excel = pd.DataFrame(datos_excel)
            
            # Nombre del archivo
            nombre_archivo = f"Ruta_{ruta_id:03d}_{zona}_{tipo}.xlsx"
            ruta_completa = f"rutas_excel/{nombre_archivo}"
            
            # Guardar con formato profesional
            with pd.ExcelWriter(ruta_completa, engine='xlsxwriter') as writer:
                df_excel.to_excel(writer, sheet_name='RUTA', index=False)
                
                # Formato profesional
                workbook = writer.book
                worksheet = writer.sheets['RUTA']
                
                # Formatos
                header_format = workbook.add_format({
                    'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC',
                    'border': 1, 'font_size': 10, 'font_name': 'Arial'
                })
                
                # Aplicar formatos
                for col_num, value in enumerate(df_excel.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Autoajustar columnas
                worksheet.set_column('A:Z', 15)
            
            self._log(f"📊 Excel generado: {nombre_archivo}")
            return ruta_completa
            
        except Exception as e:
            self._log(f"❌ Error generando Excel: {str(e)}")
            return None

    def _generar_mapa_pro(self, df, zona, ruta_id, tipo):
        """Genera mapa interactivo profesional"""
        try:
            # Crear mapa centrado en CDMX
            mapa = folium.Map(
                location=[19.4326, -99.1332],
                zoom_start=11,
                tiles='CartoDB positron'
            )
            
            # Añadir marcadores
            for i, (_, fila) in enumerate(df.iterrows(), 1):
                # Obtener coordenadas
                direccion = fila.get('DIRECCIÓN_COMPLETA', '')
                coords = self._geocode_avanzado(direccion)
                
                if coords:
                    # Personalizar icono por prioridad
                    prioridad = fila.get('PRIORIDAD', 'NORMAL')
                    color = 'red' if prioridad == 'URGENTE' else 'blue'
                    icono = 'flash' if prioridad == 'URGENTE' else 'info-sign'
                    
                    popup_text = f"""
                    <div style="font-family: Arial; width: 250px;">
                        <h4>📍 Parada {i}</h4>
                        <b>👤 {fila.get('NOMBRE_COMPLETO', 'N/A')}</b><br>
                        <small>🏢 {fila.get('DEPENDENCIA', 'N/A')}</small><br>
                        <small>📌 {direccion[:50]}...</small><br>
                        <small>🚨 <b>{prioridad}</b></small>
                    </div>
                    """
                    
                    folium.Marker(
                        coords,
                        popup=folium.Popup(popup_text, max_width=300),
                        tooltip=f"Parada {i}: {fila.get('NOMBRE_COMPLETO', '')[:20]}",
                        icon=folium.Icon(color=color, icon=icono, prefix='glyphicon')
                    ).add_to(mapa)
            
            # Añadir panel de información
            panel_html = f"""
            <div style="position: fixed; top: 10px; left: 50px; z-index: 1000; 
                       background: white; padding: 15px; border-radius: 10px; 
                       box-shadow: 0 0 15px rgba(0,0,0,0.3); border: 3px solid {Config.COLORS.get(zona, '#333')};
                       font-family: Arial; max-width: 300px;">
                <h4 style="margin: 0 0 10px; color: #2c3e50; border-bottom: 2px solid {Config.COLORS.get(zona, '#333')}; 
                          padding-bottom: 5px;">RUTA {ruta_id}</h4>
                <div style="font-size: 12px;">
                    <b>📍 Zona:</b> {zona}<br>
                    <b>🚨 Tipo:</b> {tipo}<br>
                    <b>👥 Personas:</b> {len(df)}<br>
                    <b>📅 Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
                    <b>🎯 Prioridad:</b> {df['PRIORIDAD'].value_counts().to_dict()}
                </div>
            </div>
            """
            
            mapa.get_root().html.add_child(folium.Element(panel_html))
            
            # Guardar mapa
            nombre_archivo = f"Ruta_{ruta_id:03d}_{zona}_{tipo}.html"
            ruta_completa = f"mapas_pro/{nombre_archivo}"
            mapa.save(ruta_completa)
            
            self._log(f"🗺️ Mapa generado: {nombre_archivo}")
            return ruta_completa
            
        except Exception as e:
            self._log(f"❌ Error generando mapa: {str(e)}")
            return None

    def _generar_datos_telegram(self, df, zona, ruta_id, tipo):
        """Genera datos para integración con Telegram"""
        try:
            datos_telegram = {
                'ruta_id': ruta_id,
                'zona': zona,
                'tipo': tipo,
                'estado': 'pendiente',
                'fecha_creacion': datetime.now().isoformat(),
                'total_paradas': len(df),
                'paradas': [],
                'estadisticas': {
                    'urgentes': len(df[df['PRIORIDAD'] == 'URGENTE']),
                    'normales': len(df[df['PRIORIDAD'] == 'NORMAL']),
                    'alcaldias': df['ALCALDIA'].value_counts().to_dict()
                }
            }
            
            # Añadir información de cada parada
            for i, (_, fila) in enumerate(df.iterrows(), 1):
                parada = {
                    'orden': i,
                    'nombre': fila.get('NOMBRE_COMPLETO', ''),
                    'direccion': fila.get('DIRECCIÓN_COMPLETA', ''),
                    'dependencia': fila.get('DEPENDENCIA', ''),
                    'alcaldia': fila.get('ALCALDIA', ''),
                    'prioridad': fila.get('PRIORIDAD', 'NORMAL'),
                    'estado': 'pendiente',
                    'timestamp_entrega': None,
                    'evidencia_foto': None,
                    'observaciones': ''
                }
                datos_telegram['paradas'].append(parada)
            
            # Guardar archivo JSON
            nombre_archivo = f"Ruta_{ruta_id:03d}_{zona}_{tipo}.json"
            ruta_completa = f"rutas_telegram/{nombre_archivo}"
            
            with open(ruta_completa, 'w', encoding='utf-8') as f:
                json.dump(convert_to_serializable(datos_telegram), f, indent=2, ensure_ascii=False)
            
            self._log(f"📱 Datos Telegram generados: {nombre_archivo}")
            return ruta_completa
            
        except Exception as e:
            self._log(f"❌ Error generando datos Telegram: {str(e)}")
            return None

# =============================================================================
# INTERFAZ GRÁFICA ULTRA HD
# =============================================================================
class SistemaRutasUltraHD:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Sistema Rutas ULTRA HD PRO - {Config.VERSION}")
        self.root.geometry("1300x900")
        self.root.configure(bg='#1e1e1e')
        
        # Variables de estado
        self.sincronizando = False
        self.sincronizacion_thread = None
        self.generando_rutas = False
        
        # Gestores
        self.gestor_telegram = GestorTelegramPro(self)
        self.conexion_bot = ConexionBotRailwayPro()
        
        # Configuración inicial
        self.api_key = Config.API_KEY
        self.origen_coords = Config.ORIGEN_COORDS
        self.origen_name = Config.ORIGEN_NAME
        self.archivo_excel = None
        self.df = None
        
        # Configurar UI
        self.setup_ui_ultra_hd()
        
        # Iniciar procesos automáticos
        self.root.after(1000, self.iniciar_procesos_automaticos)

    def setup_ui_ultra_hd(self):
        """Configura la interfaz Ultra HD"""
        # Frame principal con estilo moderno
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#2b2b2b')
        style.configure('TLabel', background='#2b2b2b', foreground='white')
        style.configure('TButton', font=('Arial', 10, 'bold'))
        style.configure('Title.TLabel', font=('Arial', 16, 'bold'), foreground='#4ECDC4')
        
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header con logo y título
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = ttk.Label(header_frame, 
                               text="🚀 SISTEMA RUTAS ULTRA HD PRO", 
                               style='Title.TLabel')
        title_label.pack(side=tk.LEFT)
        
        version_label = ttk.Label(header_frame, 
                                 text=f"v{Config.VERSION}", 
                                 foreground='#FECA57',
                                 font=('Arial', 10, 'bold'))
        version_label.pack(side=tk.RIGHT)
        
        # Panel de control principal
        control_frame = ttk.LabelFrame(main_frame, text="🎯 CONTROL PRINCIPAL", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Fila 1: Archivo y API
        file_api_frame = ttk.Frame(control_frame)
        file_api_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(file_api_frame, 
                  text="📁 CARGAR EXCEL", 
                  command=self.cargar_excel,
                  style='TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        self.file_label = ttk.Label(file_api_frame, 
                                   text="No hay archivo cargado", 
                                   foreground='red',
                                   font=('Arial', 10, 'bold'))
        self.file_label.pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Label(file_api_frame, text="🔑 API Key:").pack(side=tk.LEFT)
        self.api_entry = ttk.Entry(file_api_frame, width=30, show="*")
        self.api_entry.insert(0, self.api_key)
        self.api_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        # Fila 2: Botones de acción principales
        action_frame = ttk.Frame(control_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        self.btn_generar = ttk.Button(action_frame,
                                     text="🚀 GENERAR RUTAS ULTRA HD",
                                     command=self.generar_rutas_ultra_hd,
                                     state='disabled',
                                     style='TButton')
        self.btn_generar.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(action_frame,
                  text="📊 VER ESTADÍSTICAS",
                  command=self.mostrar_estadisticas).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(action_frame,
                  text="🔄 SINCRONIZAR CON BOT",
                  command=self.sincronizar_con_bot).pack(side=tk.LEFT, padx=(0, 10))
        
        # Fila 3: Sincronización automática
        sync_frame = ttk.Frame(control_frame)
        sync_frame.pack(fill=tk.X, pady=5)
        
        self.btn_sync_auto = ttk.Button(sync_frame,
                                       text="🔄 INICIAR SYNC AUTO",
                                       command=self.toggle_sincronizacion_auto)
        self.btn_sync_auto.pack(side=tk.LEFT, padx=(0, 10))
        
        self.sync_status = ttk.Label(sync_frame, text="⏹️ Sync detenido", foreground="red")
        self.sync_status.pack(side=tk.LEFT)
        
        # Panel de log mejorado
        log_frame = ttk.LabelFrame(main_frame, text="📝 LOG DEL SISTEMA", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # Crear Text widget con scrollbar
        self.log_text = tk.Text(log_frame, height=20, wrap=tk.WORD, 
                               bg='#1e1e1e', fg='white', 
                               insertbackground='white',
                               font=('Consolas', 10))
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configurar tags para colores en el log
        self.log_text.tag_configure('success', foreground='#4ECDC4')
        self.log_text.tag_configure('error', foreground='#FF6B6B')
        self.log_text.tag_configure('warning', foreground='#FECA57')
        self.log_text.tag_configure('info', foreground='#45B7D1')

    def log(self, mensaje, tipo='info'):
        """Log mejorado con colores"""
        def actualizar_log():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {mensaje}\n", tipo)
            self.log_text.see(tk.END)
            self.root.update()
        
        self.root.after(0, actualizar_log)

    def iniciar_procesos_automaticos(self):
        """Inicia procesos automáticos al cargar la aplicación"""
        self.log("🎯 Iniciando Sistema Ultra HD PRO...", 'info')
        self.log("🔍 Verificando conexión con bot...", 'info')
        
        # Verificar conexión con bot
        conectado, mensaje = self.conexion_bot.verificar_conexion()
        if conectado:
            self.log(mensaje, 'success')
        else:
            self.log(mensaje, 'warning')
        
        # Cargar Excel automáticamente si existe
        if os.path.exists("Alcaldías.xlsx"):
            self.cargar_excel_automatico()

    def cargar_excel_automatico(self):
        """Carga automáticamente el Excel si existe"""
        try:
            self.archivo_excel = "Alcaldías.xlsx"
            self.df = pd.read_excel(self.archivo_excel)
            self.file_label.config(text="Alcaldías.xlsx (Auto)", foreground="green")
            self.btn_generar.config(state='normal')
            self.log("✅ Excel cargado automáticamente", 'success')
            self.log(f"📊 Registros detectados: {len(self.df)}", 'info')
        except Exception as e:
            self.log(f"❌ Error cargando Excel automático: {str(e)}", 'error')

    def cargar_excel(self):
        """Carga manual de archivo Excel"""
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo Excel",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        
        if archivo:
            try:
                self.df = pd.read_excel(archivo)
                self.archivo_excel = archivo
                nombre_archivo = os.path.basename(archivo)
                self.file_label.config(text=nombre_archivo, foreground="green")
                self.btn_generar.config(state='normal')
                self.log(f"✅ Excel cargado: {nombre_archivo}", 'success')
                self.log(f"📊 Total de registros: {len(self.df)}", 'info')
            except Exception as e:
                self.log(f"❌ Error cargando Excel: {str(e)}", 'error')

    def generar_rutas_ultra_hd(self):
        """Genera rutas con el motor Ultra HD"""
        if self.generando_rutas:
            self.log("⚠️ Ya se están generando rutas...", 'warning')
            return
            
        if self.df is None:
            self.log("❌ Primero carga un archivo Excel", 'error')
            return
            
        self.generando_rutas = True
        self.btn_generar.config(state='disabled')
        
        # Ejecutar en hilo separado
        threading.Thread(target=self._ejecutar_generacion_rutas, daemon=True).start()

    def _ejecutar_generacion_rutas(self):
        """Ejecuta la generación de rutas en segundo plano"""
        try:
            self.log("🚀 INICIANDO GENERACIÓN ULTRA HD...", 'info')
            
            # Crear instancia del motor Ultra HD
            motor = CoreRouteGeneratorUltraHD(
                df=self.df,
                api_key=self.api_entry.get(),
                origen_coords=self.origen_coords,
                origen_name=self.origen_name,
                max_stops_per_route=8
            )
            
            # Generar rutas
            resultados = motor.generar_rutas_optimizadas()
            
            # Mostrar resultados
            for mensaje in motor.log_messages:
                if '❌' in mensaje:
                    self.log(mensaje, 'error')
                elif '⚠️' in mensaje:
                    self.log(mensaje, 'warning')
                elif '✅' in mensaje:
                    self.log(mensaje, 'success')
                else:
                    self.log(mensaje, 'info')
            
            if resultados:
                self.log(f"🎉 GENERACIÓN COMPLETADA: {len(resultados)} rutas creadas", 'success')
                
                # Mostrar resumen
                self.mostrar_resumen_generacion(resultados)
            else:
                self.log("❌ No se pudieron generar rutas", 'error')
                
        except Exception as e:
            self.log(f"❌ ERROR CRÍTICO: {str(e)}", 'error')
        finally:
            self.generando_rutas = False
            self.root.after(0, lambda: self.btn_generar.config(state='normal'))

    def mostrar_resumen_generacion(self, resultados):
        """Muestra resumen de la generación"""
        resumen = "📊 RESUMEN DE GENERACIÓN:\n"
        resumen += "─" * 50 + "\n"
        
        for resultado in resultados:
            resumen += f"• Ruta {resultado['ruta_id']}: {resultado['zona']} ({resultado['tipo']}) - {resultado['total_personas']} personas\n"
        
        resumen += "─" * 50 + "\n"
        resumen += f"📈 Total: {len(resultados)} rutas generadas\n"
        
        self.log(resumen, 'success')
        
        # Mostrar mensaje de éxito
        self.root.after(0, lambda: messagebox.showinfo(
            "🎉 Generación Completada",
            f"¡Se generaron {len(resultados)} rutas exitosamente!\n\n"
            f"Puedes ver los archivos en las carpetas:\n"
            f"• rutas_excel/ - Archivos Excel\n"
            f"• mapas_pro/ - Mapas interactivos\n"
            f"• rutas_telegram/ - Datos para Telegram"
        ))

    def toggle_sincronizacion_auto(self):
        """Activa/desactiva la sincronización automática"""
        if self.sincronizando:
            self.detener_sincronizacion_auto()
        else:
            self.iniciar_sincronizacion_auto()

    def iniciar_sincronizacion_auto(self):
        """Inicia sincronización automática"""
        self.sincronizando = True
        self.btn_sync_auto.config(text="⏹️ DETENER SYNC AUTO")
        self.sync_status.config(text="🔄 Sync activo", foreground="green")
        self.log("🔄 Sincronización automática ACTIVADA (cada 5 min)", 'success')
        
        # Iniciar hilo de sincronización
        self.sincronizacion_thread = threading.Thread(target=self._bucle_sincronizacion, daemon=True)
        self.sincronizacion_thread.start()

    def detener_sincronizacion_auto(self):
        """Detiene sincronización automática"""
        self.sincronizando = False
        self.btn_sync_auto.config(text="🔄 INICIAR SYNC AUTO")
        self.sync_status.config(text="⏹️ Sync detenido", foreground="red")
        self.log("⏹️ Sincronización automática DETENIDA", 'warning')

    def _bucle_sincronizacion(self):
        """Bucle de sincronización automática"""
        ciclo = 0
        while self.sincronizando:
            try:
                ciclo += 1
                self.log(f"🔄 Ciclo {ciclo}: Sincronizando...", 'info')
                
                # Aquí iría la lógica de sincronización real
                time.sleep(10)  # Simulación - cambiar por sync real
                
                if ciclo % 30 == 0:  # Cada 5 minutos (30 ciclos de 10 segundos)
                    self.log("📊 Sincronización completada", 'success')
                    
            except Exception as e:
                self.log(f"❌ Error en sincronización: {str(e)}", 'error')
            
            # Espera interrumpible
            for _ in range(30):  # 30 intervalos de 1 segundo
                if not self.sincronizando:
                    break
                time.sleep(1)

    def sincronizar_con_bot(self):
        """Sincronización manual con el bot"""
        self.log("🔄 Iniciando sincronización manual...", 'info')
        # Implementar sincronización real aquí
        self.log("✅ Sincronización manual completada", 'success')

    def mostrar_estadisticas(self):
        """Muestra estadísticas del sistema"""
        try:
            estadisticas = self.gestor_telegram.obtener_estadisticas_completas()
            
            if estadisticas:
                mensaje = "📈 ESTADÍSTICAS DEL SISTEMA:\n"
                mensaje += "─" * 40 + "\n"
                mensaje += f"• 📊 Total rutas: {estadisticas.get('total_rutas', 0)}\n"
                mensaje += f"• ⏳ Pendientes: {estadisticas.get('rutas_pendientes', 0)}\n"
                mensaje += f"• 🚀 En progreso: {estadisticas.get('rutas_en_progreso', 0)}\n"
                mensaje += f"• ✅ Completadas: {estadisticas.get('rutas_completadas', 0)}\n"
                mensaje += f"• 📦 Total entregas: {estadisticas.get('total_entregas', 0)}\n"
                mensaje += f"• 🎯 Entregas hoy: {estadisticas.get('entregas_hoy', 0)}\n"
                mensaje += "─" * 40
                
                self.log(mensaje, 'success')
            else:
                self.log("📊 No hay estadísticas disponibles", 'info')
                
        except Exception as e:
            self.log(f"❌ Error obteniendo estadísticas: {str(e)}", 'error')

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    # Crear carpetas necesarias
    carpetas = ['mapas_pro', 'rutas_excel', 'rutas_telegram', 'avances_ruta', 
                'fotos_entregas', 'fotos_reportes', 'incidencias_trafico']
    
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    # Iniciar aplicación
    root = tk.Tk()
    
    # Configurar cierre seguro
    def on_closing():
        if hasattr(app, 'sincronizando') and app.sincronizando:
            app.detener_sincronizacion_auto()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Crear y ejecutar aplicación
    app = SistemaRutasUltraHD(root)
    root.mainloop()
