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
# CLASE PRINCIPAL - MOTOR DE RUTAS (CoreRouteGenerator) - RECONSTRUIDA Y CORREGIDA
# =============================================================================
class CoreRouteGenerator:
    def __init__(self, df, api_key, origen_coords, origen_name, max_stops_per_route=8):
        self.df = df.copy()
        self.api_key = api_key
        self.origen_coords = origen_coords
        self.origen_name = origen_name
        self.MAX_EDIFICIOS_POR_RUTA = 8  # Máximo de edificios por ruta
        self.MIN_EDIFICIOS_POR_RUTA = 6  # Mínimo de edificios por ruta
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
        
        # 🎯 NOMBRES DE COLUMNAS PERSONALIZADOS
        self.COLUMNAS = {
            'NOMBRE': 'NOMBRE',
            'ADSCRIPCION': 'ADSCRIPCIÓN',
            'DIRECCION': 'DIRECCIÓN',
            'ALCALDIA': 'ALCALDÍA',
            'NOTAS': 'NOTAS'
        }
        
        self._log("✅ CoreRouteGenerator inicializado correctamente")
        self._log(f"🏢 Configuración: {self.MIN_EDIFICIOS_POR_RUTA}-{self.MAX_EDIFICIOS_POR_RUTA} edificios por ruta")

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
                if nombre_str.startswith('. '):
                    nombre_str = nombre_str[2:].strip()
                elif nombre_str.startswith('.'):
                    nombre_str = nombre_str[1:].strip()
                break
        
        # Capitalizar nombre
        nombre_str = ' '.join([palabra.capitalize() for palabra in nombre_str.split()])
        
        return nombre_str

    def _extraer_datos_persona(self, fila):
        """Extraer datos de una persona/fila"""
        try:
            nombre_completo = str(fila.get(self.COLUMNAS['NOMBRE'], '')).strip()
            nombre_limpio = self._limpiar_titulo_nombre(nombre_completo)
            
            datos = {
                'nombre_completo': nombre_completo,
                'nombre': nombre_limpio,
                'adscripcion': str(fila.get(self.COLUMNAS['ADSCRIPCION'], '')).strip(),
                'dependencia': str(fila.get(self.COLUMNAS['ADSCRIPCION'], '')).strip(),
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
    # MÉTODOS DE GEOCODIFICACIÓN - COMPLETOS Y CORREGIDOS
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

    def _geocode_cdmx_inteligente(self, direccion, alcaldia):
        """Geocoding especializado para direcciones de CDMX"""
        if not direccion:
            return None
        
        # PRIMERO: Intentar con dirección completa
        coords = self._geocode(direccion)
        if coords:
            return coords
        
        # SEGUNDO: Si tiene alcaldía, agregarla
        if alcaldia and alcaldia not in ['', 'nan']:
            direccion_con_alcaldia = f"{direccion}, Alcaldía {alcaldia}, Ciudad de México"
            coords = self._geocode(direccion_con_alcaldia)
            if coords:
                return coords
        
        # TERCERO: Buscar dirección sin número específico
        direccion_sin_numero = self._extraer_calle_principal(direccion)
        if direccion_sin_numero and direccion_sin_numero != direccion:
            coords = self._geocode(f"{direccion_sin_numero}, Ciudad de México")
            if coords:
                self._log(f"📍 Coordenadas aproximadas para: {direccion[:50]}...")
                return coords
        
        # CUARTO: Intentar solo con colonia si se puede extraer
        colonia = self._extraer_colonia(direccion)
        if colonia and alcaldia:
            coords = self._geocode(f"{colonia}, {alcaldia}, Ciudad de México")
            if coords:
                self._log(f"📍 Coordenadas por colonia para: {direccion[:50]}...")
                return coords
        
        return None

    def _extraer_calle_principal(self, direccion):
        """Extrae solo el nombre de la calle principal"""
        if not direccion:
            return ""
        
        d = str(direccion)
        
        # Eliminar números y lo que venga después
        d = re.sub(r'#\s*\d+.*$', '', d)
        d = re.sub(r'No\.?\s*\d+.*$', '', d)
        d = re.sub(r'Núm\.?\s*\d+.*$', '', d)
        d = re.sub(r'\b\d+\s*[-A-Za-z].*$', '', d)  # Número seguido de letras
        
        # Eliminar referencias a pisos, interiores, etc.
        d = re.sub(r'\bPiso\s*\d+.*$', '', d, flags=re.IGNORECASE)
        d = re.sub(r'\bInt\.?\s*\w+.*$', '', d, flags=re.IGNORECASE)
        d = re.sub(r'\bLocal\s*\w+.*$', '', d, flags=re.IGNORECASE)
        
        return d.strip()

    def _extraer_colonia(self, direccion):
        """Intenta extraer el nombre de la colonia de la dirección"""
        if not direccion:
            return None
        
        d = str(direccion).upper()
        
        # Buscar patrones como "Col. [Nombre]" o "Colonia [Nombre]"
        match = re.search(r'COL\.?\s+([A-ZÁÉÍÓÚÑ\s]+?)(?:,|\.|$)', d)
        if match:
            return match.group(1).strip()
        
        return None

    def _es_geocoding_exacto(self, direccion):
        """Determina si el geocoding fue exacto basado en la dirección"""
        # Verificar si la dirección tiene número específico
        if re.search(r'#\s*\d+|No\.?\s*\d+', direccion):
            return True
        return False

    # =========================================================================
    # MÉTODOS DE NORMALIZACIÓN DE DIRECCIONES
    # =========================================================================
    
    def _normalizar_direccion(self, direccion):
        """Normalizar direcciones - VERSIÓN MEJORADA PARA CDMX"""
        if not direccion or pd.isna(direccion):
            return ""
        
        # Convertir a string y limpiar
        d = str(direccion).strip()
        
        # Eliminar códigos postales y referencias innecesarias
        d = re.sub(r'C\.P\.?\s*\d{5}', '', d)  # C.P. 06720
        d = re.sub(r'C\.?P\.?\s*\d{5}', '', d)  # CP 06720
        d = re.sub(r'CÓDIGO POSTAL\s*\d{5}', '', d)  # Código Postal 06720
        
        # Eliminar "Ciudad de México" y variantes
        d = re.sub(r'Ciudad de México', '', d, flags=re.IGNORECASE)
        d = re.sub(r'CDMX', '', d, flags=re.IGNORECASE)
        d = re.sub(r'Ciudad de Méx\.?', '', d, flags=re.IGNORECASE)
        d = re.sub(r'\.\s*$', '', d)  # Eliminar punto final
        
        # Normalizar puntos cardinales COMPLETAMENTE
        d = re.sub(r'\bS\.?\b', 'Sur', d, flags=re.IGNORECASE)
        d = re.sub(r'\bN\.?\b', 'Norte', d, flags=re.IGNORECASE)
        d = re.sub(r'\bE\.?\b', 'Oriente', d, flags=re.IGNORECASE)
        d = re.sub(r'\bO\.?\b', 'Poniente', d, flags=re.IGNORECASE)
        
        # Normalizar "No.", "Núm.", "#", etc.
        d = re.sub(r'(No\.?\s*|Núm\.?\s*|Número\s*|#\s*)(\d+)', r'#\2', d, flags=re.IGNORECASE)
        
        # Normalizar abreviaturas comunes en CDMX
        normalizaciones = {
            r'\bAv\.?\b': 'Avenida',
            r'\bAvda\.?\b': 'Avenida',
            r'\bBlvd\.?\b': 'Boulevard',
            r'\bC\.?\b': 'Calle',
            r'\bCol\.?\b': 'Colonia',
            r'\bDel\.?\b': 'Delegación',
            r'\bAlc\.?\b': 'Alcaldía',
            r'\bEdif\.?\b': 'Edificio',
            r'\bP\.?\s*iso\b': 'Piso',
            r'\bEsq\.?\b': 'Esquina',
            r'\bInt\.?\b': 'Interior',
            r'\bPriv\.?\b': 'Privada',
            r'\bS\/?N\b': 'S/N',
            r'\bCto\.?\b': 'Circuito',
            r'\bPte\.?\b': 'Poniente',
        }
        
        for patron, reemplazo in normalizaciones.items():
            d = re.sub(patron, reemplazo, d, flags=re.IGNORECASE)
        
        # Limpiar espacios múltiples y trim
        d = re.sub(r'\s+', ' ', d).strip()
        
        # 🔥 CRÍTICO: Extraer el número principal para agrupamiento inteligente
        # Buscar patrones como "Avenida Insurgentes Sur #881" → "Avenida Insurgentes Sur"
        match = re.search(r'(.+?)(?:#\s*(\d+)|No\.?\s*(\d+)|Núm\.?\s*(\d+)|\s+(\d+)\b)', d)
        
        if match:
            # Extraer calle sin número específico
            calle_base = match.group(1).strip()
            numero = match.group(2) or match.group(3) or match.group(4) or match.group(5)
            
            if numero:
                # Agrupar por manzana (primeros dígitos)
                # Ej: 881 → 800, 1234 → 1200, 56 → 00
                if len(numero) >= 3:
                    grupo_numero = numero[:-2] + "00"
                elif len(numero) == 2:
                    grupo_numero = numero[0] + "0"
                else:
                    grupo_numero = "00"
                
                return f"{calle_base} #{grupo_numero}"
        
        return d

    # =========================================================================
    # MÉTODOS DE AGRUPAMIENTO POR EDIFICIO - ÚNICA VERSIÓN CORRECTA
    # =========================================================================
    
    def _agrupar_personas_por_edificio(self):
        """Agrupar todas las personas por edificio/dirección - VERSIÓN MEJORADA"""
        self._log("🏢 Iniciando agrupamiento por edificio para CDMX...")
        
        edificios = {}
        estadisticas = {
            'total': 0,
            'con_direccion': 0,
            'sin_direccion': 0,
            'geocoding_exacto': 0,
            'geocoding_aproximado': 0,
            'sin_coordenadas': 0
        }
        
        for idx, fila in self.df.iterrows():
            datos_persona = self._extraer_datos_persona(fila)
            direccion = datos_persona['direccion']
            alcaldia = datos_persona['alcaldia']
            
            estadisticas['total'] += 1
            
            if not direccion or direccion in ['', 'Sin dirección', 'nan']:
                estadisticas['sin_direccion'] += 1
                continue
            
            estadisticas['con_direccion'] += 1
            
            # 🔥 USAR geocoding inteligente para CDMX
            coords = self._geocode_cdmx_inteligente(direccion, alcaldia)
            
            # Normalizar dirección para agrupamiento inteligente
            direccion_normalizada = self._normalizar_direccion(direccion)
            
            if not direccion_normalizada:
                continue
            
            # Crear clave única para el edificio (usando dirección normalizada y alcaldía)
            clave_edificio = f"{direccion_normalizada}_{alcaldia}"
            
            if clave_edificio not in edificios:
                edificios[clave_edificio] = {
                    'direccion_original': direccion,
                    'direccion_normalizada': direccion_normalizada,
                    'alcaldia': alcaldia,
                    'dependencia_principal': datos_persona['dependencia'],
                    'personas': [],
                    'coordenadas': coords,
                    'total_personas': 0,
                    'geocoding_preciso': coords is not None
                }
            
            edificios[clave_edificio]['personas'].append(datos_persona)
            edificios[clave_edificio]['total_personas'] += 1
            
            if coords:
                # Verificar si fue geocoding exacto o aproximado
                if self._es_geocoding_exacto(direccion):
                    estadisticas['geocoding_exacto'] += 1
                else:
                    estadisticas['geocoding_aproximado'] += 1
            else:
                estadisticas['sin_coordenadas'] += 1
        
        # Estadísticas detalladas
        self._log("📊 ESTADÍSTICAS DE AGRUPAMIENTO:")
        self._log(f"   • Total personas procesadas: {estadisticas['total']}")
        self._log(f"   • Con dirección válida: {estadisticas['con_direccion']}")
        self._log(f"   • Sin dirección: {estadisticas['sin_direccion']}")
        self._log(f"   • Con coordenadas exactas: {estadisticas['geocoding_exacto']}")
        self._log(f"   • Con coordenadas aproximadas: {estadisticas['geocoding_aproximado']}")
        self._log(f"   • Sin coordenadas: {estadisticas['sin_coordenadas']}")
        self._log(f"   • Total edificios únicos: {len(edificios)}")
        
        # Advertencia si hay muchos sin coordenadas
        sin_coords_pct = (estadisticas['sin_coordenadas'] / estadisticas['con_direccion']) * 100
        if sin_coords_pct > 20:
            self._log(f"⚠️ ADVERTENCIA: {sin_coords_pct:.1f}% sin coordenadas")
        
        return edificios

    def _asignar_zona_a_edificio(self, alcaldia):
        """Asignar zona basada en la alcaldía"""
        alcaldia_str = str(alcaldia).upper()
        
        if any(alc in alcaldia_str for alc in ['CUAUHTEMOC', 'MIGUEL HIDALGO', 'BENITO JUAREZ']):
            return 'CENTRO'
        elif any(alc in alcaldia_str for alc in ['ALVARO OBREGON', 'COYOACAN', 'TLALPAN']):
            return 'SUR'
        elif any(alc in alcaldia_str for alc in ['IZTAPALAPA', 'GUSTAVO A. MADERO', 'VENUSTIANO CARRANZA']):
            return 'ORIENTE'
        else:
            return 'OTRAS'

    def _organizar_edificios_por_zona(self, edificios):
        """Organizar edificios por zona geográfica"""
        edificios_por_zona = {}
        
        for clave, edificio in edificios.items():
            zona = self._asignar_zona_a_edificio(edificio['alcaldia'])
            edificio['zona'] = zona
            
            if zona not in edificios_por_zona:
                edificios_por_zona[zona] = []
            
            edificios_por_zona[zona].append(edificio)
        
        # Mostrar distribución
        self._log("📊 Distribución de edificios por zona:")
        for zona, lista_edificios in edificios_por_zona.items():
            total_personas = sum(e['total_personas'] for e in lista_edificios)
            self._log(f"   {zona}: {len(lista_edificios)} edificios, {total_personas} personas")
        
        return edificios_por_zona

    # =========================================================================
    # MÉTODOS DE CREACIÓN DE RUTAS
    # =========================================================================
    
    def _crear_grupos_edificios_por_ruta(self, edificios_por_zona):
        """Crear grupos de 6-8 edificios por ruta"""
        self._log("📦 Creando grupos de edificios para rutas...")
        
        todas_las_rutas = []
        
        for zona, edificios in edificios_por_zona.items():
            if len(edificios) == 0:
                continue
            
            self._log(f"   Zona {zona}: {len(edificios)} edificios")
            
            # Ordenar edificios por proximidad (si tienen coordenadas)
            edificios_con_coords = [e for e in edificios if e['coordenadas']]
            edificios_sin_coords = [e for e in edificios if not e['coordenadas']]
            
            # Si hay suficientes edificios con coordenadas, intentar ordenarlos
            if len(edificios_con_coords) > 1:
                try:
                    # Ordenar por proximidad usando el origen como referencia
                    origen_coords = list(map(float, self.origen_coords.split(',')))
                    edificios_con_coords.sort(key=lambda e: self._calcular_distancia(origen_coords, e['coordenadas']))
                except:
                    pass
            
            # Combinar listas
            edificios_ordenados = edificios_con_coords + edificios_sin_coords
            
            # Dividir en grupos de 6-8 edificios
            grupos = []
            current_group = []
            
            for i, edificio in enumerate(edificios_ordenados):
                current_group.append(edificio)
                
                # Reglas para cerrar grupo:
                # 1. Si alcanza el máximo (8)
                # 2. Si es el último edificio
                # 3. Si tiene al menos el mínimo (6) y quedan menos del mínimo
                if (len(current_group) >= self.MAX_EDIFICIOS_POR_RUTA or 
                    i == len(edificios_ordenados) - 1 or
                    (len(current_group) >= self.MIN_EDIFICIOS_POR_RUTA and 
                     len(edificios_ordenados) - i - 1 < self.MIN_EDIFICIOS_POR_RUTA)):
                    
                    # Solo crear ruta si tiene al menos 2 edificios
                    if len(current_group) >= 2:
                        grupos.append({
                            'zona': zona,
                            'edificios': current_group.copy(),
                            'total_edificios': len(current_group),
                            'total_personas': sum(e['total_personas'] for e in current_group)
                        })
                        current_group = []
            
            self._log(f"   → Se crearán {len(grupos)} rutas para {zona}")
            todas_las_rutas.extend(grupos)
        
        return todas_las_rutas

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
            return 9999

    def _optimizar_ruta_edificios(self, edificios):
        """Optimizar ruta para un grupo de edificios"""
        if len(edificios) < 2:
            return edificios, [], 0, 0, None
        
        # Filtrar edificios con coordenadas
        edificios_con_coords = [e for e in edificios if e['coordenadas']]
        
        if len(edificios_con_coords) < 2:
            return edificios, [], 0, 0, None
        
        try:
            # Preparar waypoints para Google Directions API
            waypoints = "|".join([f"{coord[0]},{coord[1]}" for e in edificios_con_coords for coord in [e['coordenadas']]])
            
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
                
                # Reordenar edificios según optimización
                edificios_opt = [edificios_con_coords[i] for i in orden]
                
                # Calcular distancia y tiempo
                distancia_total = sum(leg['distance']['value'] for leg in route['legs']) / 1000  # km
                tiempo_total = sum(leg['duration']['value'] for leg in route['legs']) / 60  # minutos
                
                # Agregar edificios sin coordenadas al final
                edificios_sin_coords = [e for e in edificios if not e['coordenadas']]
                edificios_opt.extend(edificios_sin_coords)
                
                # Obtener coordenadas ordenadas
                coords_opt = [e['coordenadas'] for e in edificios_opt if e['coordenadas']]
                
                self._log(f"✅ Ruta optimizada: {len(edificios_opt)} edificios, {distancia_total:.1f} km, {tiempo_total:.0f} min")
                return edificios_opt, coords_opt, tiempo_total, distancia_total, poly
            else:
                self._log(f"⚠️ No se pudo optimizar ruta: {data.get('status')}")
                return edificios, [], 0, 0, None
                
        except Exception as e:
            self._log(f"❌ Error optimizando ruta: {e}")
            return edificios, [], 0, 0, None

    # =========================================================================
    # MÉTODOS DE CREACIÓN DE ARCHIVOS
    # =========================================================================
    
    def _crear_excel_ruta(self, zona, edificios_opt, ruta_id):
        """Crear archivo Excel para la ruta"""
        try:
            excel_data = []
            orden_parada = 1
            
            for edificio in edificios_opt:
                for i, persona in enumerate(edificio['personas'], 1):
                    # Crear link para foto
                    link_foto = f"=HIPERVINCULO(\"fotos_entregas/Ruta_{ruta_id}_Edificio_{orden_parada}_Persona_{i}.jpg\", \"📸 VER FOTO\")"
                    
                    excel_data.append({
                        'Orden_Edificio': orden_parada,
                        'Orden_Persona': i,
                        'Edificio': edificio.get('direccion_original', 'Sin dirección'),
                        'Nombre_Completo': persona['nombre_completo'],
                        'Nombre': persona['nombre'],
                        'Dependencia': persona['dependencia'],
                        'Adscripción': persona['adscripcion'],
                        'Dirección': persona['direccion'],
                        'Alcaldía': persona['alcaldia'],
                        'Notas': persona['notas'],
                        'Personas_Mismo_Edificio': edificio['total_personas'],
                        'Acuse': 'PENDIENTE',
                        'Repartidor': '',
                        'Foto_Acuse': link_foto,
                        'Timestamp_Entrega': '',
                        'Estado': 'PENDIENTE',
                        'Coordenadas': f"{edificio['coordenadas'][0]},{edificio['coordenadas'][1]}" if edificio['coordenadas'] else '',
                        'Zona': zona
                    })
                
                orden_parada += 1
            
            # Crear DataFrame y guardar Excel
            excel_df = pd.DataFrame(excel_data)
            excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
            
            os.makedirs("rutas_excel", exist_ok=True)
            excel_df.to_excel(excel_file, index=False)
            
            self._log(f"📊 Excel generado: {excel_file} ({len(excel_data)} registros, {len(edificios_opt)} edificios)")
            return excel_file
            
        except Exception as e:
            self._log(f"❌ Error creando Excel: {e}")
            return None

    def _crear_mapa_ruta(self, zona, edificios_opt, coords_opt, tiempo, dist, poly, ruta_id):
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
            
            # Marcadores para edificios
            for i, (edificio, coord) in enumerate(zip(edificios_opt, coords_opt), 1):
                if not coord:
                    continue
                
                # Crear popup HTML
                popup_html = f"""
                <div style="font-family: Arial; width: 350px;">
                    <h4 style="color: {color}; margin: 0 0 10px;">
                        🏢 Edificio #{i} - {zona}
                    </h4>
                    <b>📍 {edificio.get('direccion_original', 'Sin dirección')[:50]}...</b><br>
                    <small>👥 {edificio['total_personas']} personas</small><hr style="margin: 8px 0;">
                    <small><b>Personas en este edificio:</b></small><br>
                """
                
                for j, persona in enumerate(edificio['personas'][:4], 1):
                    popup_html += f"<small>• {persona['nombre']}</small><br>"
                
                if edificio['total_personas'] > 4:
                    popup_html += f"<small>• ... y {edificio['total_personas']-4} más</small>"
                
                popup_html += "</div>"
                
                folium.Marker(
                    coord,
                    popup=popup_html,
                    tooltip=f"Edificio #{i}: {edificio['total_personas']} personas",
                    icon=folium.Icon(color='red', icon='building', prefix='fa')
                ).add_to(m)
            
            # Panel informativo
            total_personas = sum(e['total_personas'] for e in edificios_opt)
            total_edificios = len(edificios_opt)
            
            info_panel_html = f"""
            <div style="position:fixed; top:10px; left:50px; z-index:1000; background:white; 
                        padding:15px; border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.2);
                        border:2px solid {color}; font-family:Arial; max-width:400px;">
                <h4 style="margin:0 0 10px; color:#2c3e50; border-bottom:2px solid {color}; padding-bottom:5px;">
                    Ruta {ruta_id} - {zona}
                </h4>
                <small>
                    <b>🏢 Edificios:</b> {total_edificios}<br>
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

    def _generar_url_google_maps(self, edificios, ruta_id):
        """Generar URL de Google Maps para la ruta"""
        try:
            if len(edificios) < 2:
                return None
            
            # Filtrar edificios con dirección válida
            direcciones = []
            
            for edificio in edificios:
                direccion = edificio.get('direccion_original', '')
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
            
            self._log(f"🗺️ URL Google Maps generada para Ruta {ruta_id}")
            return url
            
        except Exception as e:
            self._log(f"⚠️ Error generando URL Google Maps: {e}")
            return None

    def _crear_json_telegram(self, zona, edificios_opt, coords_opt, tiempo, dist, ruta_id, excel_file):
        """Crear JSON para Telegram/Bot"""
        try:
            paradas_telegram = []

            for i, edificio in enumerate(edificios_opt, 1):
                primera_persona = edificio['personas'][0] if edificio['personas'] else {'nombre': 'Sin nombre', 'dependencia': ''}
                coordenadas = edificio.get('coordenadas', (0, 0))
                
                parada = {
                    'orden': i,
                    'nombre': f"Edificio {i}",
                    'dependencia': edificio.get('dependencia_principal', ''),
                    'direccion': edificio.get('direccion_original', 'Sin dirección'),
                    'coords': f"{coordenadas[0]},{coordenadas[1]}" if coordenadas else "",
                    'total_personas': edificio['total_personas'],
                    'estado': 'pendiente',
                    'personas': []
                }
                
                for j, persona in enumerate(edificio['personas'], 1):
                    parada['personas'].append({
                        'sub_orden': j,
                        'nombre': persona['nombre'],
                        'nombre_completo': persona['nombre_completo'],
                        'dependencia': persona['dependencia'],
                        'direccion': persona['direccion'],
                        'alcaldia': persona['alcaldia'],
                        'foto_acuse': f"fotos_entregas/Ruta_{ruta_id}_Edificio_{i}_Persona_{j}.jpg",
                        'estado': 'pendiente'
                    })
                
                paradas_telegram.append(parada)
            
            # Generar URL de Google Maps
            google_maps_url = self._generar_url_google_maps(edificios_opt, ruta_id)
            
            # Crear estructura completa
            ruta_telegram = {
                'ruta_id': ruta_id,
                'zona': zona,
                'origen': self.origen_name,
                'repartidor_asignado': None,
                'google_maps_url': google_maps_url,
                'paradas': paradas_telegram,
                'estadisticas': {
                    'total_edificios': len(edificios_opt),
                    'total_personas': sum(e['total_personas'] for e in edificios_opt),
                    'distancia_km': round(dist, 1),
                    'tiempo_min': round(tiempo),
                    'configuracion': 'edificios_agrupados'
                },
                'estado': 'pendiente',
                'timestamp_creacion': datetime.now().isoformat(),
                'excel_original': excel_file
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

    def _procesar_ruta_individual(self, grupo_ruta, ruta_id):
        """Procesar una ruta individual"""
        zona = grupo_ruta['zona']
        edificios = grupo_ruta['edificios']
        
        self._log(f"🚀 Procesando Ruta {ruta_id}: {zona} ({len(edificios)} edificios, {grupo_ruta['total_personas']} personas)")
        
        # Optimizar ruta
        edificios_opt, coords_opt, tiempo, dist, poly = self._optimizar_ruta_edificios(edificios)
        
        if len(edificios_opt) == 0:
            self._log(f"❌ No hay edificios válidos para Ruta {ruta_id}")
            return None
        
        # Crear archivos
        excel_file = self._crear_excel_ruta(zona, edificios_opt, ruta_id)
        mapa_file = self._crear_mapa_ruta(zona, edificios_opt, coords_opt, tiempo, dist, poly, ruta_id)
        ruta_telegram, telegram_file = self._crear_json_telegram(zona, edificios_opt, coords_opt, tiempo, dist, ruta_id, excel_file)
        
        if not excel_file or not ruta_telegram:
            self._log(f"❌ Error creando archivos para Ruta {ruta_id}")
            return None
        
        # Enviar al bot Railway
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
        
        # Resultado final
        resultado = {
            'ruta_id': ruta_id,
            'zona': zona,
            'edificios': len(edificios_opt),
            'personas': sum(e['total_personas'] for e in edificios_opt),
            'distancia': round(dist, 1),
            'tiempo': round(tiempo),
            'excel': excel_file,
            'mapa': mapa_file if mapa_file else '',
            'telegram_file': telegram_file,
            'google_maps_url': ruta_telegram.get('google_maps_url') if ruta_telegram else None
        }
        
        self._log(f"✅ Ruta {ruta_id} creada: {len(edificios_opt)} edificios, {resultado['personas']} personas")
        return resultado

    # =========================================================================
    # MÉTODO PRINCIPAL DE GENERACIÓN
    # =========================================================================
    
    def generate_routes(self):
        """🎯 MÉTODO PRINCIPAL - Generar todas las rutas"""
        self._log("🚀 INICIANDO GENERACIÓN DE RUTAS POR EDIFICIO")
        self._log(f"📊 Total de registros: {len(self.df)}")
        
        if self.df.empty:
            self._log("❌ No hay datos para procesar")
            return []
        
        # 🎯 1. AGRUPAR PERSONAS POR EDIFICIO
        edificios = self._agrupar_personas_por_edificio()
        
        if len(edificios) == 0:
            self._log("❌ No se encontraron edificios válidos")
            return []
        
        # 🎯 2. ORGANIZAR POR ZONA
        edificios_por_zona = self._organizar_edificios_por_zona(edificios)
        
        # 🎯 3. CREAR GRUPOS DE 6-8 EDIFICIOS POR RUTA
        grupos_rutas = self._crear_grupos_edificios_por_ruta(edificios_por_zona)
        
        if len(grupos_rutas) == 0:
            self._log("❌ No se pudieron crear grupos de rutas")
            return []
        
        self._log(f"📦 Total rutas a generar: {len(grupos_rutas)}")
        
        # 🎯 4. GENERAR CADA RUTA
        self.results = []
        ruta_id = 1
        
        for grupo in grupos_rutas:
            if grupo['total_edificios'] >= 2:  # Mínimo 2 edificios
                try:
                    resultado = self._procesar_ruta_individual(grupo, ruta_id)
                    if resultado:
                        self.results.append(resultado)
                        ruta_id += 1
                except Exception as e:
                    self._log(f"❌ Error en Ruta {ruta_id}: {e}")
        
        # 🎯 5. GUARDAR CACHE
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.GEOCODE_CACHE, f)
            self._log("💾 Cache de geocodificación guardado")
        except Exception as e:
            self._log(f"⚠️ Error guardando cache: {e}")
        
        # 🎯 6. GENERAR RESUMEN
        if self.results:
            try:
                resumen_data = []
                for r in self.results:
                    resumen_data.append({
                        'Ruta_ID': r['ruta_id'],
                        'Zona': r['zona'],
                        'Edificios': r['edificios'],
                        'Personas': r['personas'],
                        'Distancia_km': r['distancia'],
                        'Tiempo_min': r['tiempo'],
                        'Excel': os.path.basename(r['excel']),
                        'Google_Maps_URL': r.get('google_maps_url', '')
                    })
                
                resumen_df = pd.DataFrame(resumen_data)
                resumen_df.to_excel("RESUMEN_RUTAS.xlsx", index=False)
                self._log("📋 Resumen 'RESUMEN_RUTAS.xlsx' generado")
                
            except Exception as e:
                self._log(f"⚠️ Error generando resumen: {e}")
        
        # 🎯 7. ESTADÍSTICAS FINALES
        total_rutas = len(self.results)
        total_edificios = sum(r['edificios'] for r in self.results) if self.results else 0
        total_personas = sum(r['personas'] for r in self.results) if self.results else 0
        
        self._log("🎉 GENERACIÓN DE RUTAS COMPLETADA")
        self._log(f"📊 RESUMEN FINAL:")
        self._log(f"   • Total rutas generadas: {total_rutas}")
        self._log(f"   • Total edificios: {total_edificios}")
        self._log(f"   • Total personas: {total_personas}")
        
        if total_rutas > 0:
            self._log(f"   • Edificios por ruta promedio: {total_edificios/total_rutas:.1f}")
            self._log(f"   • Personas por ruta promedio: {total_personas/total_rutas:.1f}")
        
        # Verificar tamaño de rutas
        rutas_pequenas = [r for r in self.results if r['edificios'] < 6]
        if rutas_pequenas:
            self._log(f"⚠️ ADVERTENCIA: {len(rutas_pequenas)} rutas con menos de 6 edificios")
        else:
            self._log("✅ EXCELENTE: Todas las rutas tienen 6+ edificios!")
        
        return self.results

# =============================================================================
# CLASE INTERFAZ GRÁFICA (SistemaRutasGUI) - VERSIÓN FINAL CORREGIDA
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

    # =========================================================================
    # MÉTODOS DE CARGA DE EXCEL - CORREGIDOS
    # =========================================================================
    
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

    def cargar_excel(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo Excel", 
            filetypes=[("Excel files", "*.xlsx")]
        )
        if archivo:
            try:
                self.log("🔄 Cargando Excel...")
                
                # Leer todas las filas manteniendo saltos de línea
                df_completo = pd.read_excel(
                    archivo, 
                    header=None,  # Leer sin encabezado para detectar correctamente
                    dtype=str  # Todo como texto para mantener formato
                )
                
                self.archivo_excel = archivo
                nombre_archivo = os.path.basename(archivo)
                self.file_label.config(text=nombre_archivo, foreground='green')
                self.log(f"✅ Excel cargado: {nombre_archivo}")
                self.log(f"📊 Forma original: {df_completo.shape}")
                
                # 🔥 NUEVO: Procesamiento especial para Excel con secciones
                df_procesado = self._procesar_excel_complejo(df_completo)
                
                if df_procesado is not None and len(df_procesado) > 0:
                    self.df = df_procesado
                    self.log(f"✅ Excel procesado: {len(df_procesado)} registros válidos")
                    
                    # Detección de columnas en el dataframe procesado
                    columna_direccion = self._detectar_columna_direccion(df_procesado)
                    columna_nombre = self._detectar_columna_nombre(df_procesado) 
                    columna_adscripcion = self._detectar_columna_adscripcion(df_procesado)
                    columna_alcaldia = self._detectar_columna_alcaldia(df_procesado)
                    
                    self.columnas_seleccionadas = {
                        'direccion': columna_direccion,
                        'nombre': columna_nombre,
                        'adscripcion': columna_adscripcion,
                        'alcaldia': columna_alcaldia
                    }
                    
                    self.log(f"🎯 Columnas detectadas:")
                    self.log(f"   • Nombre: {columna_nombre}")
                    self.log(f"   • Dirección: {columna_direccion}")
                    self.log(f"   • Adscripción: {columna_adscripcion}")
                    self.log(f"   • Alcaldía: {columna_alcaldia}")
                    
                    # Mostrar vista previa
                    self._mostrar_vista_previa(df_procesado)
                    
                    self.btn_generar.config(state='normal')
                    self.log("🎉 ¡Excel listo para generar rutas!")
                else:
                    self.log("❌ No se pudieron extraer datos válidos del Excel")
                    
            except Exception as e:
                self.log(f"❌ ERROR: {str(e)}")
                import traceback
                self.log(traceback.format_exc())
                messagebox.showerror("Error", f"No se pudo cargar el Excel:\n{str(e)}")

    def _procesar_excel_complejo(self, df_raw):
        """Procesa Excel complejo como el ejemplo (con secciones y celdas combinadas)"""
        try:
            self.log("🔍 Procesando estructura compleja del Excel...")
            
            # 1. Encontrar filas con encabezados de columnas
            filas_encabezados = []
            for idx, fila in df_raw.iterrows():
                # Buscar filas que tengan "NOMBRE" en alguna celda
                for celda in fila:
                    if isinstance(celda, str) and "NOMBRE" in celda.upper():
                        filas_encabezados.append(idx)
                        break
            
            self.log(f"📋 Se encontraron {len(filas_encabezados)} secciones en el Excel")
            
            # 2. Procesar cada sección
            todos_datos = []
            
            for i, idx_encabezado in enumerate(filas_encabezados):
                self.log(f"   📄 Procesando sección {i+1}...")
                
                # Tomar filas después del encabezado hasta encontrar el siguiente encabezado o fila vacía
                inicio = idx_encabezado + 1
                if i + 1 < len(filas_encabezados):
                    fin = filas_encabezados[i + 1]
                else:
                    fin = len(df_raw)
                
                # Extraer datos de esta sección
                datos_seccion = self._extraer_datos_seccion(df_raw, inicio, fin)
                todos_datos.extend(datos_seccion)
            
            # 3. Crear DataFrame final
            if todos_datos:
                df_final = pd.DataFrame(todos_datos)
                self.log(f"✅ Total registros extraídos: {len(df_final)}")
                return df_final
            else:
                self.log("⚠️ No se extrajeron datos válidos")
                return None
                
        except Exception as e:
            self.log(f"❌ Error procesando Excel complejo: {str(e)}")
            return None

    def _extraer_datos_seccion(self, df_raw, inicio, fin):
        """Extrae datos de una sección específica del Excel"""
        datos = []
        
        for idx in range(inicio, fin):
            fila = df_raw.iloc[idx]
            
            # Saltar filas vacías o que contengan títulos de sección
            if fila.isnull().all() or self._es_fila_titulo(fila):
                continue
            
            # Convertir fila a dict considerando la estructura del ejemplo
            # En el ejemplo: #, NOMBRE, ADSCRIPCIÓN, DIRECCIÓN, ALCALDÍA, ACUSE
            dato = {
                'NUMERO': self._limpiar_valor(fila.iloc[1]) if len(fila) > 1 else '',
                'NOMBRE': self._limpiar_valor(fila.iloc[2]) if len(fila) > 2 else '',
                'ADSCRIPCION': self._limpiar_valor(fila.iloc[3]) if len(fila) > 3 else '',
                'DIRECCION': self._limpiar_valor(fila.iloc[4]) if len(fila) > 4 else '',
                'ALCALDIA': self._limpiar_valor(fila.iloc[5]) if len(fila) > 5 else '',
                'ACUSE': self._limpiar_valor(fila.iloc[6]) if len(fila) > 6 else ''
            }
            
            # Filtrar filas sin nombre o dirección
            if dato['NOMBRE'] and dato['NOMBRE'] not in ['', 'nan', 'NaN']:
                # Procesar dirección con saltos de línea
                if dato['DIRECCION']:
                    dato['DIRECCION'] = self._procesar_direccion_multilinea(dato['DIRECCION'])
                
                datos.append(dato)
        
        return datos

    def _procesar_direccion_multilinea(self, direccion):
        """Procesa direcciones con saltos de línea o tags HTML <br>"""
        if not direccion or pd.isna(direccion):
            return ""
        
        # Convertir a string
        dir_str = str(direccion)
        
        # Reemplazar tags HTML <br> por espacios
        dir_str = dir_str.replace('<br>', ' ')
        dir_str = dir_str.replace('<br/>', ' ')
        dir_str = dir_str.replace('<br />', ' ')
        
        # Reemplar saltos de línea reales
        dir_str = dir_str.replace('\n', ' ')
        dir_str = dir_str.replace('\r', ' ')
        
        # Limpiar espacios múltiples
        dir_str = re.sub(r'\s+', ' ', dir_str).strip()
        
        return dir_str

    def _es_fila_titulo(self, fila):
        """Determina si una fila es un título de sección"""
        for celda in fila:
            if isinstance(celda, str):
                celda_upper = celda.upper()
                # Buscar palabras que indiquen títulos de sección
                if any(palabra in celda_upper for palabra in [
                    'GOBIERNO FEDERAL', 'ALCALDÍAS', 'SUPREMA CORTE',
                    'CDMX', 'CONGRESO', 'UNIVERSIDADES', 'COLEGIOS',
                    'CÁMARA DE DIPUTADOS', 'FAMILIA', 'SINDICATOS',
                    'SENADO', 'FISCALÍA', 'ESPECIALES'
                ]):
                    return True
        return False

    def _limpiar_valor(self, valor):
        """Limpia un valor del Excel"""
        if pd.isna(valor) or valor is None:
            return ""
        return str(valor).strip()

def _detectar_columna_direccion(self, df):
    """Detección más robusta de columnas de dirección"""
    columnas_posibles = []
    
    for col in df.columns:
        col_str = str(col).lower()
        # Buscar coincidencias más amplias
        if any(p in col_str for p in ['dirección', 'direccion', 'dir', 'address', 
                                     'ubicación', 'ubicacion', 'domicilio', 'calle', 'direc']):
            return col
        
        # Si no encuentra exacto, guardar para fallback
        if 'dir' in col_str:
            columnas_posibles.append(col)
    
    # Si hay opciones, usar la primera
    if columnas_posibles:
        return columnas_posibles[0]
    
    # Último recurso: usar la primera columna que no sea nombre
    for col in df.columns:
        col_str = str(col).lower()
        if 'nombre' not in col_str and 'name' not in col_str:
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

    def _detectar_columna_alcaldia(self, df):
        """Detectar columna de alcaldía"""
        for col in df.columns:
            col_str = str(col).upper()
            if any(palabra in col_str for palabra in ['ALCALDÍA', 'ALCALDIA', 'MUNICIPIO', 'DELEGACIÓN']):
                return col
        return None

    def _mostrar_vista_previa(self, df, n=10):
        """Muestra vista previa de los datos"""
        self.log("👁️ VISTA PREVIA de datos cargados:")
        for i, (_, fila) in enumerate(df.head(n).iterrows()):
            nombre = fila.get(self.columnas_seleccionadas.get('nombre', ''), 'Sin nombre')[:30]
            direccion = fila.get(self.columnas_seleccionadas.get('direccion', ''), 'Sin dirección')[:50]
            self.log(f"   {i+1}. {nombre}... → {direccion}...")

    def log(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {mensaje}\n")
        self.log_text.see(tk.END)
        self.root.update()

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
        self.log(f"📋 Columnas disponibles: {list(df_completo.columns)}")
        
        # Mostrar las primeras filas para depuración
        self.log("👁️ Vista previa de las primeras filas:")
        for i, row in df_completo.head(3).iterrows():
            self.log(f"   Fila {i}: {row.to_dict()}")
        
        # Usar todos los registros
        df_filtrado = df_completo
        self.log(f"✅ Procesando TODOS los registros: {len(df_filtrado)}")
        
        if len(df_filtrado) == 0:
            self.log("❌ No hay datos")
            return
        
        # 🔥 CORRECCIÓN: Verificar y usar las columnas correctamente
        columna_direccion = None
        columna_nombre = None
        columna_adscripcion = None
        
        # Verificar si tenemos columnas_seleccionadas
        if hasattr(self, 'columnas_seleccionadas') and self.columnas_seleccionadas:
            columna_direccion = self.columnas_seleccionadas.get('direccion')
            columna_nombre = self.columnas_seleccionadas.get('nombre')
            columna_adscripcion = self.columnas_seleccionadas.get('adscripcion')
            
            self.log(f"🎯 Columnas seleccionadas previamente:")
            self.log(f"   • Dirección: '{columna_direccion}'")
            self.log(f"   • Nombre: '{columna_nombre}'")
            self.log(f"   • Adscripción: '{columna_adscripcion}'")
        
        # Si no hay columnas seleccionadas o son None, detectar automáticamente
        if not columna_direccion:
            columna_direccion = self._detectar_columna_direccion(df_filtrado)
        if not columna_nombre:
            columna_nombre = self._detectar_columna_nombre(df_filtrado)
        if not columna_adscripcion:
            columna_adscripcion = self._detectar_columna_adscripcion(df_filtrado)
        
        self.log(f"🎯 Columnas finales a usar:")
        self.log(f"   • Dirección: '{columna_direccion}'")
        self.log(f"   • Nombre: '{columna_nombre}'")
        self.log(f"   • Adscripción: '{columna_adscripcion}'")
        
        # 🔥 VERIFICACIÓN CRÍTICA: Comprobar que las columnas existen
        if columna_direccion not in df_filtrado.columns:
            self.log(f"❌ ERROR: La columna '{columna_direccion}' no existe en el DataFrame")
            self.log(f"   Columnas disponibles: {list(df_filtrado.columns)}")
            
            # Buscar la columna de dirección con diferentes nombres
            posibles_nombres = ['DIRECCION', 'Direccion', 'DIRECCIÓN', 'Dirección', 'DOMICILIO', 'Domicilio', 'DIR']
            for nombre in posibles_nombres:
                if nombre in df_filtrado.columns:
                    columna_direccion = nombre
                    self.log(f"   🔍 Se encontró columna alternativa: '{nombre}'")
                    break
            
            if columna_direccion not in df_filtrado.columns:
                messagebox.showerror("Error", f"No se encontró la columna de dirección.\n\nColumnas disponibles:\n{', '.join(df_filtrado.columns)}")
                return
        
        # Verificar que tenemos nombre
        if not columna_nombre:
            # Buscar cualquier columna que pueda contener nombres
            for col in df_filtrado.columns:
                if any(p in str(col).lower() for p in ['nombre', 'name', 'persona', 'destinatario']):
                    columna_nombre = col
                    break
        
        if not columna_nombre:
            columna_nombre = df_filtrado.columns[0]  # Usar primera columna como fallback
        
        # 🔥 CORRECCIÓN PRINCIPAL: Crear df_estandar con nombres fijos
        df_estandar = df_filtrado.copy()
        
        # Usar la columna correcta para dirección
        if columna_direccion in df_estandar.columns:
            df_estandar['DIRECCIÓN'] = df_estandar[columna_direccion].astype(str)
        else:
            # Crear columna vacía si no existe
            df_estandar['DIRECCIÓN'] = ''
            self.log("⚠️ ADVERTENCIA: No se pudo encontrar columna de dirección")
        
        # Usar la columna correcta para nombre
        if columna_nombre in df_estandar.columns:
            df_estandar['NOMBRE'] = df_estandar[columna_nombre].astype(str)
        else:
            df_estandar['NOMBRE'] = 'Sin nombre'
        
        # Usar la columna correcta para adscripción
        if columna_adscripcion and columna_adscripcion in df_estandar.columns:
            df_estandar['ADSCRIPCIÓN'] = df_estandar[columna_adscripcion].astype(str)
        else:
            df_estandar['ADSCRIPCIÓN'] = 'Sin adscripción'
        
        # Agregar columna de alcaldía si existe
        if hasattr(self, 'columnas_seleccionadas') and 'alcaldia' in self.columnas_seleccionadas:
            columna_alcaldia = self.columnas_seleccionadas['alcaldia']
            if columna_alcaldia and columna_alcaldia in df_estandar.columns:
                df_estandar['ALCALDÍA'] = df_estandar[columna_alcaldia].astype(str)
            else:
                df_estandar['ALCALDÍA'] = ''
        
        self.log(f"🎯 DataFrame estandarizado: {len(df_estandar)} registros")
        self.log(f"📋 Columnas finales: {list(df_estandar.columns)}")
        
        # Mostrar algunas filas para verificar
        self.log("🔍 Ejemplo de datos procesados:")
        for i, row in df_estandar.head(3).iterrows():
            self.log(f"   • {row.get('NOMBRE', '')[:30]}... → {row.get('DIRECCIÓN', '')[:40]}...")
        
        # Generar rutas
        generator = CoreRouteGenerator(
            df=df_estandar,
            api_key=self.api_key,
            origen_coords=self.origen_coords,
            origen_name=self.origen_name,
            max_stops_per_route=self.max_stops
        )
        
        # Conectar el logging
        generator._log = self.log
        resultados = generator.generate_routes()
        
        if resultados:
            self.log(f"🎉 ¡{len(resultados)} RUTAS GENERADAS CON PARADAS POR EDIFICIO!")
            self.log("🏢 Cada edificio con múltiples personas = 1 sola parada de ruta")
            self.log("📱 Las rutas están listas para asignar a repartidores via Telegram")
            
            resumen = f"""
            🎉 ¡{len(resultados)} RUTAS GENERADAS!
            
            Características:
            • Cada edificio con múltiples personas = 1 sola parada de ruta
            • Rutas optimizadas para eficiencia
            • Mapas interactivos generados
            • Archivos Excel individuales para cada ruta
            • Listo para asignar a repartidores via Telegram
            
            Las rutas están en las carpetas:
            • mapas_pro/ - Mapas interactivos
            • rutas_excel/ - Excels con detalles
            • rutas_telegram/ - Archivos para el bot
            """
            messagebox.showinfo("Éxito", resumen)
        else:
            self.log("❌ No se pudieron generar rutas")
            messagebox.showwarning("Advertencia", "No se pudieron generar rutas. Revisa el log para más detalles.")
            
    except Exception as e:
        self.log(f"❌ ERROR: {str(e)}")
        import traceback
        self.log(traceback.format_exc())
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
