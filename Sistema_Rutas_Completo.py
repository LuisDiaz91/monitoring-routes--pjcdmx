# sistema_rutas_funcional.py
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
# CLASE CONEXIÓN CON BOT RAILWAY
# =============================================================================
class ConexionBotRailway:
    def __init__(self, url_base):
        self.url_base = url_base
        self.timeout = 30
    
    def verificar_conexion(self):
        """Verificar que el bot está disponible"""
        try:
            response = requests.get(f"{self.url_base}/api/health", timeout=10)
            return response.status_code == 200
        except:
            return False

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
                print(f"✅ Ruta {ruta_data['ruta_id']} enviada al bot")
                return True
            else:
                print(f"❌ Error enviando ruta: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error de conexión con bot: {e}")
            return False

# =============================================================================
# CLASE MOTOR DE RUTAS FUNCIONAL
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
        """Log para la interfaz"""
        print(f"{message}")

    def _normalizar_direccion(self, direccion):
        """Normalización simple"""
        if pd.isna(direccion) or direccion == '':
            return ""
        
        direccion_str = str(direccion).upper().strip()
        
        # Limpiar dirección básicamente
        direccion_str = re.sub(r'\s+', ' ', direccion_str)
        
        return direccion_str

    def _agrupar_direcciones(self, df):
        """Agrupación FUNCIONAL"""
        self._log("🔍 Agrupando direcciones...")
        
        # Crear columna normalizada
        df['DIR_NORM'] = df['DIRECCIÓN'].apply(self._normalizar_direccion)
        
        # Filtrar direcciones vacías
        df = df[df['DIR_NORM'] != '']
        
        # Agrupar
        grupos = df.groupby('DIR_NORM')
        
        datos_agrupados = []
        for direccion_norm, grupo in grupos:
            cantidad = len(grupo)
            
            if cantidad > 1:
                # AGUPAR MÚLTIPLES PERSONAS
                fila_base = grupo.iloc[0].copy()
                
                # Combinar nombres
                nombres = [str(n).split(',')[0].strip() for n in grupo['NOMBRE'] if pd.notna(n)]
                if len(nombres) > 3:
                    nombre_combinado = f"ENTREGA MÚLTIPLE ({cantidad} personas)"
                else:
                    nombre_combinado = f"ENTREGA MÚLTIPLE: {', '.join(nombres)}"
                
                fila_base['NOMBRE'] = nombre_combinado
                fila_base['PERSONAS_AGRUPADAS'] = cantidad
                fila_base['NOMBRES_ORIGINALES'] = " | ".join(nombres)
                
                datos_agrupados.append(fila_base)
            else:
                # UNA SOLA PERSONA
                fila_unica = grupo.iloc[0].copy()
                fila_unica['PERSONAS_AGRUPADAS'] = 1
                fila_unica['NOMBRES_ORIGINALES'] = str(fila_unica['NOMBRE'])
                datos_agrupados.append(fila_unica)
        
        df_agrupado = pd.DataFrame(datos_agrupados)
        self._log(f"✅ De {len(df)} → {len(df_agrupado)} puntos de entrega")
        
        return df_agrupado

    def _geocode(self, direccion):
        """Geocoding con manejo de errores"""
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
                time.sleep(0.1)
                return coords
                
        except Exception as e:
            self._log(f"⚠️ Geocode error para: {d[:30]}...")
            
        return None

    def generate_routes(self):
        """Generación de rutas COMPLETA"""
        self._log("🚀 INICIANDO GENERACIÓN...")
        
        try:
            # 1. PREPARAR DATOS
            df_clean = self.df.copy()
            
            # Verificar columnas necesarias
            if 'DIRECCIÓN' not in df_clean.columns:
                self._log("❌ Error: No hay columna 'DIRECCIÓN'")
                return []
            
            # Limpiar datos
            df_clean['DIRECCIÓN'] = df_clean['DIRECCIÓN'].astype(str).fillna('')
            df_clean = df_clean[df_clean['DIRECCIÓN'].str.strip() != '']
            
            if 'NOMBRE' not in df_clean.columns:
                df_clean['NOMBRE'] = 'Sin nombre'
            else:
                df_clean['NOMBRE'] = df_clean['NOMBRE'].astype(str).fillna('Sin nombre')
            
            self._log(f"📊 Datos limpios: {len(df_clean)} registros")
            
            # 2. AGRUPAR DIRECCIONES
            df_agrupado = self._agrupar_direcciones(df_clean)
            
            if len(df_agrupado) == 0:
                self._log("❌ No hay datos válidos después de agrupar")
                return []
            
            # 3. ASIGNAR ZONAS
            def asignar_zona_simple(direccion):
                d = str(direccion).upper()
                if any(p in d for p in ['CUAUHTEMOC', 'CENTRO', 'DOCTORES', 'ROMA', 'CONDESA']):
                    return 'CENTRO'
                elif any(p in d for p in ['COYOACAN', 'TLALPAN', 'BENITO', 'DEL VALLE', 'NÁPOLES']):
                    return 'SUR'
                elif any(p in d for p in ['IZTAPALAPA', 'GUSTAVO', 'IZTACALCO']):
                    return 'ORIENTE'
                elif any(p in d for p in ['XOCHIMILCO', 'MILPA', 'TLÁHUAC']):
                    return 'SUR_ORIENTE'
                else:
                    return 'OTRAS'
            
            df_agrupado['Zona'] = df_agrupado['DIRECCIÓN'].apply(asignar_zona_simple)
            
            # 4. CREAR RUTAS POR ZONA
            self._log("🗺️ Creando rutas por zona...")
            
            for zona in df_agrupado['Zona'].unique():
                zonas_df = df_agrupado[df_agrupado['Zona'] == zona]
                self._log(f"   📍 {zona}: {len(zonas_df)} puntos")
                
                # Dividir en rutas
                puntos = zonas_df.index.tolist()
                rutas_zona = [puntos[i:i+self.max_stops_per_route] for i in range(0, len(puntos), self.max_stops_per_route)]
                
                for i, ruta_indices in enumerate(rutas_zona, len(self.results) + 1):
                    self._crear_ruta_completa(zona, ruta_indices, i)
            
            # 5. GUARDAR Y TERMINAR
            self._guardar_cache()
            
            if self.results:
                total_rutas = len(self.results)
                total_puntos = sum(r['puntos_entrega'] for r in self.results)
                total_personas = sum(r['personas_totales'] for r in self.results)
                
                self._log(f"🎉 GENERACIÓN COMPLETADA: {total_rutas} rutas")
                self._log(f"📍 {total_puntos} puntos de entrega")
                self._log(f"👥 {total_personas} personas totales")
            else:
                self._log("❌ No se generaron rutas")
            
            return self.results
            
        except Exception as e:
            self._log(f"❌ ERROR CRÍTICO: {str(e)}")
            return []

    def _crear_ruta_completa(self, zona, indices, ruta_id):
        """Crear ruta completa con Excel y envío al bot"""
        try:
            filas = self.df.loc[indices]
            
            # Geocoding
            coords_validas = []
            filas_validas = []
            
            for _, fila in filas.iterrows():
                coord = self._geocode(fila['DIRECCIÓN'])
                if coord:
                    coords_validas.append(coord)
                    filas_validas.append(fila)
            
            if len(coords_validas) < 1:
                self._log(f"⚠️ Ruta {ruta_id}: Sin coordenadas válidas")
                return
            
            # CREAR EXCEL
            excel_data = []
            for i, (fila, coord) in enumerate(zip(filas_validas, coords_validas), 1):
                personas = fila.get('PERSONAS_AGRUPADAS', 1)
                
                excel_data.append({
                    'Orden': i,
                    'Nombre': str(fila.get('NOMBRE', 'N/A')),
                    'Dependencia': str(fila.get('ADSCRIPCIÓN', 'N/A')),
                    'Dirección': str(fila.get('DIRECCIÓN', 'N/A')),
                    'Personas_Agrupadas': personas,
                    'Nombres_Originales': fila.get('NOMBRES_ORIGINALES', ''),
                    'Acuse': '',
                    'Repartidor': '',
                    'Foto_Acuse': '',
                    'Timestamp_Entrega': '',
                    'Estado': 'PENDIENTE',
                    'Coordenadas': f"{coord[0]},{coord[1]}"
                })
            
            # Guardar Excel
            os.makedirs("rutas_excel", exist_ok=True)
            excel_file = f"rutas_excel/Ruta_{ruta_id}_{zona}.xlsx"
            pd.DataFrame(excel_data).to_excel(excel_file, index=False)
            
            # DATOS PARA TELEGRAM
            ruta_telegram = {
                'ruta_id': ruta_id,
                'zona': zona,
                'paradas': [
                    {
                        'orden': i,
                        'nombre': str(fila.get('NOMBRE', 'N/A')),
                        'direccion': str(fila.get('DIRECCIÓN', 'N/A')),
                        'personas_agrupadas': fila.get('PERSONAS_AGRUPADAS', 1),
                        'coords': f"{coord[0]},{coord[1]}"
                    }
                    for i, (fila, coord) in enumerate(zip(filas_validas, coords_validas), 1)
                ],
                'timestamp_creacion': datetime.now().isoformat()
            }
            
            # Enviar al bot
            conexion = ConexionBotRailway("https://monitoring-routes-pjcdmx-production.up.railway.app")
            if conexion.enviar_ruta_bot(ruta_telegram):
                self._log(f"✅ Ruta {ruta_id} enviada al bot")
            else:
                self._log(f"⚠️ Ruta {ruta_id} no se pudo enviar")
            
            self.results.append({
                'ruta_id': ruta_id,
                'zona': zona,
                'puntos_entrega': len(filas_validas),
                'personas_totales': sum(f.get('PERSONAS_AGRUPADAS', 1) for f in filas_validas)
            })
            
        except Exception as e:
            self._log(f"❌ Error en ruta {ruta_id}: {str(e)}")

    def _guardar_cache(self):
        """Guardar cache"""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self.GEOCODE_CACHE, f)
        except:
            pass

# =============================================================================
# INTERFAZ GRÁFICA FUNCIONAL
# =============================================================================
class SistemaRutasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema Rutas CON AGRUPACIÓN")
        self.root.geometry("900x700")
        
        self.api_key = "AIzaSyBeUr2C3SDkwY7zIrYcB6agDni9XDlWrFY"
        self.origen_coords = "19.4283717,-99.1430307"
        self.origen_name = "TSJCDMX - Niños Héroes 150"
        self.archivo_excel = None
        
        self.setup_ui()

    def setup_ui(self):
        """Interfaz completa"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(main_frame, text="🚀 SISTEMA RUTAS CON AGRUPACIÓN INTELIGENTE", 
                 font=('Arial', 14, 'bold')).pack(pady=10)
        
        ttk.Label(main_frame, text="Agrupa automáticamente personas en la misma dirección", 
                 font=('Arial', 10)).pack(pady=5)
        
        # Controles
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(control_frame, text="📂 CARGAR EXCEL", 
                  command=self.cargar_excel).pack(side=tk.LEFT, padx=5)
        
        self.btn_generar = ttk.Button(control_frame, text="🚀 GENERAR RUTAS CON AGRUPACIÓN", 
                                     command=self.generar_rutas, state='disabled')
        self.btn_generar.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🔄 LIMPIAR TODO", 
                  command=self.limpiar_sistema).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="📁 ABRIR CARPETA EXCEL", 
                  command=lambda: self.abrir_carpeta('rutas_excel')).pack(side=tk.LEFT, padx=5)
        
        # Info archivo
        self.file_label = ttk.Label(main_frame, text="No hay archivo cargado", 
                                   foreground='red', font=('Arial', 10))
        self.file_label.pack(pady=5)
        
        # Progress
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(main_frame, text="Listo")
        self.progress_label.pack()
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Progreso de Generación", padding="10")
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
        """Cargar Excel"""
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo Excel", 
            filetypes=[("Excel files", "*.xlsx")]
        )
        if archivo:
            try:
                self.df = pd.read_excel(archivo)
                self.archivo_excel = archivo
                
                nombre_archivo = os.path.basename(archivo)
                self.file_label.config(text=f"✅ {nombre_archivo} - {len(self.df)} registros", foreground='green')
                self.btn_generar.config(state='normal')
                self.log(f"📊 Excel cargado: {nombre_archivo}")
                self.log(f"📈 Registros totales: {len(self.df)}")
                
            except Exception as e:
                self.log(f"❌ ERROR cargando Excel: {str(e)}")

    def generar_rutas(self):
        """Generar rutas en hilo separado"""
        if not hasattr(self, 'df'):
            return
            
        self.log("🚀 INICIANDO GENERACIÓN CON AGRUPACIÓN...")
        self.btn_generar.config(state='disabled')
        self.progress.start()
        self.progress_label.config(text="Generando rutas...")
        
        def proceso():
            try:
                generator = CoreRouteGenerator(
                    df=self.df,
                    api_key=self.api_key,
                    origen_coords=self.origen_coords,
                    origen_name=self.origen_name,
                    max_stops_per_route=8
                )
                
                # Redirigir logs a la interfaz
                generator._log = self.log
                
                resultados = generator.generate_routes()
                
                # Mostrar resultados en el hilo principal
                self.root.after(0, lambda: self.mostrar_resultados(resultados))
                
            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ ERROR CRÍTICO: {str(e)}"))
                self.root.after(0, lambda: self.finalizar_proceso())
        
        threading.Thread(target=proceso, daemon=True).start()

    def mostrar_resultados(self, resultados):
        """Mostrar resultados finales"""
        self.finalizar_proceso()
        
        if resultados:
            total_rutas = len(resultados)
            total_puntos = sum(r['puntos_entrega'] for r in resultados)
            total_personas = sum(r['personas_totales'] for r in resultados)
            
            eficiencia = f"{(1 - (total_puntos / total_personas)) * 100:.1f}%" if total_personas > 0 else "0%"
            
            self.log("🎉 " + "="*50)
            self.log(f"🎯 GENERACIÓN COMPLETADA EXITOSAMENTE")
            self.log(f"📊 {total_rutas} rutas generadas")
            self.log(f"📍 {total_puntos} puntos de entrega")
            self.log(f"👥 {total_personas} personas totales") 
            self.log(f"⚡ Eficiencia de agrupación: {eficiencia}")
            self.log("🎉 " + "="*50)
            
            messagebox.showinfo(
                "¡Éxito!", 
                f"¡{total_rutas} rutas generadas!\n\n"
                f"• {total_puntos} puntos de entrega\n"
                f"• {total_personas} personas\n"
                f"• Eficiencia: {eficiencia}\n\n"
                f"Revisa la carpeta 'rutas_excel'"
            )
        else:
            self.log("❌ No se pudieron generar rutas")
            messagebox.showerror("Error", "No se pudieron generar rutas. Revisa el log.")

    def finalizar_proceso(self):
        """Finalizar proceso"""
        self.progress.stop()
        self.progress_label.config(text="Listo")
        self.btn_generar.config(state='normal')

    def limpiar_sistema(self):
        """Limpiar sistema"""
        if messagebox.askyesno("Limpiar", "¿Borrar todas las rutas generadas?"):
            carpetas = ['rutas_excel', 'mapas_pro']
            for carpeta in carpetas:
                if os.path.exists(carpeta):
                    shutil.rmtree(carpeta)
                    os.makedirs(carpeta)
            self.log("🧹 Sistema limpiado completamente")

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

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    # Crear carpetas necesarias
    for carpeta in ['rutas_excel', 'mapas_pro']:
        os.makedirs(carpeta, exist_ok=True)
    
    # Iniciar aplicación
    root = tk.Tk()
    app = SistemaRutasGUI(root)
    root.mainloop()
