# sistema_rutas_optimizado.py
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
# CLASE CONEXIÓN CON BOT RAILWAY (SIMPLIFICADA)
# =============================================================================
class ConexionBotRailway:
    def __init__(self, url_base):
        self.url_base = url_base
        self.timeout = 30
    
    def enviar_ruta_bot(self, ruta_data):
        try:
            # ENVIAR SOLO DATOS ESENCIALES para ahorrar memoria
            datos_light = {
                'ruta_id': ruta_data.get('ruta_id'),
                'zona': ruta_data.get('zona'),
                'paradas_count': len(ruta_data.get('paradas', [])),
                'timestamp': ruta_data.get('timestamp_creacion')
            }
            
            url = f"{self.url_base}/api/rutas"
            response = requests.post(url, json=datos_light, timeout=self.timeout)
            return response.status_code == 200
                
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
            return False

# =============================================================================
# CLASE MOTOR DE RUTAS OPTIMIZADO
# =============================================================================
class CoreRouteGenerator:
    def __init__(self, df, api_key, origen_coords, origen_name, max_stops_per_route):
        self.df = df.copy()
        self.api_key = api_key
        self.origen_coords = origen_coords
        self.origen_name = origen_name
        self.max_stops_per_route = max_stops_per_route
        self.results = []
        self.CACHE_FILE = "geocode_cache.json"
        self.GEOCODE_CACHE = self._cargar_cache()
        
    def _cargar_cache(self):
        """Carga el cache de forma segura"""
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _log(self, message):
        """Log optimizado para memoria"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def _normalizar_direccion(self, direccion):
        """Normalización SUPER ligera"""
        if pd.isna(direccion):
            return ""
        
        direccion_str = str(direccion).upper().strip()
        
        # Solo eliminar espacios extras
        direccion_str = re.sub(r'\s+', ' ', direccion_str)
        
        # Eliminar palabras muy comunes
        palabras_comunes = ['CDMX', 'CIUDAD', 'MÉXICO', 'MEXICO', 'COLONIA', 'COL']
        palabras = direccion_str.split()
        palabras_filtradas = [p for p in palabras if p not in palabras_comunes]
        
        return ' '.join(palabras_filtradas[:10])  # Limitar longitud

    def _agrupar_direcciones_rapido(self, df):
        """Agrupación RÁPIDA y eficiente en memoria"""
        self._log("🔍 Agrupando direcciones (modo rápido)...")
        
        # Crear columna normalizada (mínimo procesamiento)
        df['DIR_NORM'] = df['DIRECCIÓN'].apply(self._normalizar_direccion)
        
        # Agrupar eficientemente
        grupos = df.groupby('DIR_NORM')
        
        datos_agrupados = []
        for direccion_norm, grupo in grupos:
            cantidad = len(grupo)
            
            if cantidad > 1:
                # Agrupación rápida - tomar primera fila
                fila_base = grupo.iloc[0].copy()
                fila_base['NOMBRE'] = f"ENTREGA MÚLTIPLE ({cantidad})"
                fila_base['PERSONAS_AGRUPADAS'] = cantidad
                datos_agrupados.append(fila_base)
            else:
                # Una sola persona
                fila_unica = grupo.iloc[0].copy()
                fila_unica['PERSONAS_AGRUPADAS'] = 1
                datos_agrupados.append(fila_unica)
        
        df_agrupado = pd.DataFrame(datos_agrupados)
        self._log(f"✅ Agrupación: {len(df)} → {len(df_agrupado)} puntos")
        
        # LIMPIAR MEMORIA
        del df
        del grupos
        
        return df_agrupado

    def _geocode_rapido(self, direccion):
        """Geocoding optimizado"""
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
                time.sleep(0.1)  # Reducir delay
                return coords
                
        except Exception as e:
            self._log(f"Geocode error: {e}")
            
        return None

    def generate_routes_fast(self):
        """Generación de rutas OPTIMIZADA"""
        self._log("🚀 INICIANDO GENERACIÓN RÁPIDA...")
        
        try:
            # 1. FILTRADO BÁSICO
            df_clean = self.df.copy()
            if 'DIRECCIÓN' in df_clean.columns:
                mask = df_clean['DIRECCIÓN'].str.contains(r'CDMX|CIUDAD', case=False, na=False)
                df_clean = df_clean[mask]
                self._log(f"📍 Registros válidos: {len(df_clean)}")
            
            # 2. AGRUPACIÓN RÁPIDA
            df_agrupado = self._agrupar_direcciones_rapido(df_clean)
            
            # 3. ASIGNAR ZONAS SIMPLIFICADO
            def zona_rapida(direccion):
                d = str(direccion).upper()
                if any(p in d for p in ['CUAUHTEMOC', 'CENTRO', 'DOCTORES']):
                    return 'CENTRO'
                elif any(p in d for p in ['COYOACAN', 'TLALPAN', 'BENITO']):
                    return 'SUR'
                elif any(p in d for p in ['IZTAPALAPA', 'GUSTAVO']):
                    return 'ORIENTE'
                else:
                    return 'OTRAS'
            
            df_agrupado['Zona'] = df_agrupado['DIRECCIÓN'].apply(zona_rapida)
            
            # 4. CREAR RUTAS POR ZONA
            for zona in df_agrupado['Zona'].unique():
                zonas_df = df_agrupado[df_agrupado['Zona'] == zona]
                self._log(f"🗺️ Procesando {zona}: {len(zonas_df)} puntos")
                
                # Crear rutas básicas
                puntos = zonas_df.index.tolist()
                rutas_zona = [puntos[i:i+self.max_stops_per_route] for i in range(0, len(puntos), self.max_stops_per_route)]
                
                for i, ruta_indices in enumerate(rutas_zona, 1):
                    self._crear_ruta_simple(zona, ruta_indices, i)
            
            # 5. GUARDAR RESULTADOS
            self._guardar_cache()
            self._log("🎉 GENERACIÓN COMPLETADA")
            
            return self.results
            
        except Exception as e:
            self._log(f"❌ ERROR: {str(e)}")
            return []

    def _crear_ruta_simple(self, zona, indices, ruta_id):
        """Crear ruta simple sin mapas pesados"""
        try:
            filas = self.df.loc[indices]
            
            # Geocoding básico
            coords_validas = []
            filas_validas = []
            
            for _, fila in filas.iterrows():
                coord = self._geocode_rapido(fila['DIRECCIÓN'])
                if coord:
                    coords_validas.append(coord)
                    filas_validas.append(fila)
            
            if len(coords_validas) < 2:
                return
            
            # CREAR EXCEL SIMPLE
            excel_data = []
            for i, (fila, coord) in enumerate(zip(filas_validas, coords_validas), 1):
                personas = fila.get('PERSONAS_AGRUPADAS', 1)
                excel_data.append({
                    'Orden': i,
                    'Nombre': str(fila.get('NOMBRE', 'N/A')),
                    'Dirección': str(fila.get('DIRECCIÓN', 'N/A')),
                    'Personas_Agrupadas': personas,
                    'Estado': 'PENDIENTE'
                })
            
            # Guardar Excel
            os.makedirs("rutas_excel", exist_ok=True)
            excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
            pd.DataFrame(excel_data).to_excel(excel_file, index=False)
            
            # DATOS PARA TELEGRAM (ligeros)
            ruta_telegram = {
                'ruta_id': ruta_id,
                'zona': zona,
                'paradas_count': len(filas_validas),
                'timestamp': datetime.now().isoformat()
            }
            
            # Enviar al bot
            conexion = ConexionBotRailway("https://monitoring-routes-pjcdmx-production.up.railway.app")
            if conexion.verificar_conexion():
                conexion.enviar_ruta_bot(ruta_telegram)
                self._log(f"✅ Ruta {ruta_id} enviada")
            
            self.results.append({
                'ruta_id': ruta_id,
                'zona': zona,
                'puntos': len(filas_validas)
            })
            
        except Exception as e:
            self._log(f"Error en ruta {ruta_id}: {str(e)}")

    def _guardar_cache(self):
        """Guardar cache de forma segura"""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.GEOCODE_CACHE, f)
        except:
            pass

# =============================================================================
# INTERFAZ GRÁFICA SIMPLIFICADA
# =============================================================================
class SistemaRutasSimpleGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas RÁPIDO")
        self.root.geometry("800x600")
        
        self.api_key = "AIzaSyBeUr2C3SDkwY7zIrYcB6agDni9XDlWrFY"
        self.origen_coords = "19.4283717,-99.1430307"
        self.archivo_excel = None
        
        self.setup_ui_simple()

    def setup_ui_simple(self):
        """Interfaz mínima para ahorrar memoria"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header simple
        ttk.Label(main_frame, text="🚀 SISTEMA RUTAS RÁPIDO", 
                 font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Controles básicos
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(control_frame, text="📂 CARGAR EXCEL", 
                  command=self.cargar_excel_simple).pack(side=tk.LEFT, padx=5)
        
        self.btn_generar = ttk.Button(control_frame, text="🚀 GENERAR RUTAS", 
                                     command=self.generar_rutas_simple, state='disabled')
        self.btn_generar.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🔄 LIMPIAR", 
                  command=self.limpiar_sistema).pack(side=tk.LEFT, padx=5)
        
        # Info archivo
        self.file_label = ttk.Label(main_frame, text="No hay archivo cargado", 
                                   foreground='red')
        self.file_label.pack(pady=5)
        
        # Log simplificado
        log_frame = ttk.LabelFrame(main_frame, text="Progreso", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, mensaje):
        """Log simple"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {mensaje}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def cargar_excel_simple(self):
        """Carga rápida de Excel"""
        archivo = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if archivo:
            try:
                # Carga mínima
                self.df = pd.read_excel(archivo)
                self.archivo_excel = archivo
                self.file_label.config(text=f"✅ {os.path.basename(archivo)} - {len(self.df)} registros")
                self.btn_generar.config(state='normal')
                self.log(f"📊 Excel cargado: {len(self.df)} registros")
            except Exception as e:
                self.log(f"❌ Error: {str(e)}")

    def generar_rutas_simple(self):
        """Generación en hilo separado"""
        if not hasattr(self, 'df'):
            return
            
        self.log("🚀 INICIANDO GENERACIÓN RÁPIDA...")
        self.btn_generar.config(state='disabled')
        
        def proceso():
            try:
                generator = CoreRouteGenerator(
                    df=self.df,
                    api_key=self.api_key,
                    origen_coords=self.origen_coords,
                    origen_name="TSJCDMX",
                    max_stops_per_route=8
                )
                
                # Usar el generador rápido
                resultados = generator.generate_routes_fast()
                
                # Mostrar resultados
                self.root.after(0, lambda: self.mostrar_resultados(resultados))
                
            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ ERROR: {str(e)}"))
                self.root.after(0, lambda: self.btn_generar.config(state='normal'))
        
        threading.Thread(target=proceso, daemon=True).start()

    def mostrar_resultados(self, resultados):
        """Mostrar resultados finales"""
        if resultados:
            total_rutas = len(resultados)
            total_puntos = sum(r['puntos'] for r in resultados)
            self.log(f"🎉 ¡{total_rutas} RUTAS GENERADAS!")
            self.log(f"📍 {total_puntos} puntos de entrega")
            messagebox.showinfo("Éxito", f"¡{total_rutas} rutas generadas!\nRevisa la carpeta 'rutas_excel'")
        else:
            self.log("❌ No se pudieron generar rutas")
            
        self.btn_generar.config(state='normal')

    def limpiar_sistema(self):
        """Limpieza simple"""
        carpetas = ['rutas_excel', 'mapas_pro']
        for carpeta in carpetas:
            if os.path.exists(carpeta):
                shutil.rmtree(carpeta)
                os.makedirs(carpeta)
        self.log("🧹 Sistema limpiado")

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    # Crear carpetas necesarias
    for carpeta in ['rutas_excel', 'mapas_pro']:
        os.makedirs(carpeta, exist_ok=True)
    
    # Iniciar interfaz
    root = tk.Tk()
    app = SistemaRutasSimpleGUI(root)
    root.mainloop()
