import os
import telebot
import sqlite3
import time
import requests
import json
import pandas as pd
from telebot import types
from datetime import datetime
from flask import Flask, request, jsonify, Response, send_file
import threading
import traceback
from functools import wraps
import re  # 🆕 IMPORTANTE: Para extraer nombres

# =============================================================================
# CONFIGURACIÓN INICIAL
# =============================================================================

print("🚀 INICIANDO BOT COMPLETO PJCDMX - SISTEMA AUTOMÁTICO DE RUTAS...")

# CONFIGURACIÓN SEGURA
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ ERROR: BOT_TOKEN no configurado en Railway")
    exit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# =============================================================================
# VARIABLES GLOBALES DEL SISTEMA
# =============================================================================

RUTAS_DISPONIBLES = []
RUTAS_ASIGNADAS = {}
ADMIN_IDS = [7800992671]  # ⚠️ CAMBIA POR TU USER_ID
AVANCES_PENDIENTES = []  # 🆕 SISTEMA DE AVANCES PENDIENTES

# =============================================================================
# CONFIGURACIÓN BASE DE DATOS
# =============================================================================

conn = sqlite3.connect('/tmp/incidentes.db', check_same_thread=False)
cursor = conn.cursor()

# Tabla de incidentes
cursor.execute('''
CREATE TABLE IF NOT EXISTS incidentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    user_name TEXT,
    tipo TEXT,
    descripcion TEXT,
    foto_id TEXT,
    ubicacion TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

# Tabla de fotos
cursor.execute('''
CREATE TABLE IF NOT EXISTS fotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT UNIQUE,
    datos BLOB,
    user_id INTEGER,
    user_name TEXT,
    caption TEXT,
    tipo TEXT,
    ruta_local TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()
print("✅ Base de datos inicializada")

# =============================================================================
# DECORATOR PARA MANEJO DE ERRORES GLOBAL
# =============================================================================

def manejar_errores_telegram(f):
    """Decorator para manejar errores en handlers de Telegram"""
    @wraps(f)
    def decorated_function(message):
        try:
            return f(message)
        except Exception as e:
            error_msg = f"❌ Error en {f.__name__}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            # Intentar notificar al usuario
            try:
                bot.reply_to(message, "⚠️ Ocurrió un error. Por favor, intenta nuevamente.")
            except:
                pass
    return decorated_function

# =============================================================================
# FUNCIONES AUXILIARES EXISTENTES (MANTENER ESTAS)
# =============================================================================

def limpiar_texto_markdown(texto):
    """Limpia texto para evitar problemas con Markdown"""
    if not texto:
        return ""
    caracteres_problematicos = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in caracteres_problematicos:
        texto = texto.replace(char, f'\\{char}')
    return texto

def descargar_foto_telegram(file_id, tipo_foto="general"):
    """Descarga la foto real desde Telegram y la guarda en carpeta correspondiente"""
    try:
        print(f"🔄 Intentando descargar foto: {file_id} - Tipo: {tipo_foto}")
        
        file_info = bot.get_file(file_id)
        if not file_info or not file_info.file_path:
            print("❌ No se pudo obtener file_path de Telegram")
            return None
            
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
        print(f"📡 Descargando desde: {file_url}")
        
        response = requests.get(file_url, timeout=30)
        if response.status_code == 200:
            carpeta_tipo = f"carpeta_fotos_central/{tipo_foto}"
            os.makedirs(carpeta_tipo, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            nombre_archivo = f"foto_{timestamp}.jpg"
            ruta_final = f"{carpeta_tipo}/{nombre_archivo}"
            
            with open(ruta_final, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Foto descargada: {ruta_final} ({len(response.content)} bytes)")
            return ruta_final
        else:
            print(f"❌ Error HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error descargando foto: {str(e)}")
    
    return None

def guardar_foto_completa(file_id, user_id, user_name, caption, tipo, ruta_foto_local=None):
    """Guardar foto con datos binarios completos - VERSIÓN MEJORADA"""
    try:
        datos_imagen = None
        
        # 1. Intentar leer del archivo local si existe
        if ruta_foto_local and os.path.exists(ruta_foto_local):
            with open(ruta_foto_local, 'rb') as f:
                datos_imagen = f.read()
            print(f"✅ Foto leída desde archivo: {len(datos_imagen)} bytes")
        
        # 2. Si no hay archivo local, descargar de Telegram
        if not datos_imagen:
            print(f"🔄 Descargando foto de Telegram: {file_id}")
            file_info = bot.get_file(file_id)
            if file_info and file_info.file_path:
                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
                response = requests.get(file_url, timeout=30)
                if response.status_code == 200:
                    datos_imagen = response.content
                    print(f"✅ Foto descargada de Telegram: {len(datos_imagen)} bytes")
                    
                    # Guardar localmente también
                    if not ruta_foto_local:
                        carpeta = f"carpeta_fotos_central/{tipo}"
                        os.makedirs(carpeta, exist_ok=True)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        ruta_foto_local = f"{carpeta}/foto_{timestamp}.jpg"
                    
                    with open(ruta_foto_local, 'wb') as f:
                        f.write(datos_imagen)
                    print(f"💾 Foto guardada localmente: {ruta_foto_local}")
        
        # 3. Guardar en base de datos
        cursor.execute('''
            INSERT OR REPLACE INTO fotos 
            (file_id, user_id, user_name, caption, tipo, datos, ruta_local, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (file_id, user_id, user_name, caption, tipo, datos_imagen, ruta_foto_local))
        
        conn.commit()
        
        print(f"✅ Foto guardada en BD: {file_id} - Tipo: {tipo} - Datos: {len(datos_imagen) if datos_imagen else 0} bytes")
        return True
        
    except Exception as e:
        print(f"❌ Error guardando foto completa: {e}")
        return False

def cargar_rutas_disponibles():
    global RUTAS_DISPONIBLES
    RUTAS_DISPONIBLES = []
    
    if os.path.exists('rutas_telegram'):
        for archivo in os.listdir('rutas_telegram'):
            if archivo.endswith('.json'):
                try:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta = json.load(f)
                    
                    # 🆕 ELIMINAR FILTRO DE FECHA - ACEPTAR TODAS LAS RUTAS
                    if ruta.get('estado') == 'pendiente':
                        RUTAS_DISPONIBLES.append(ruta)
                        print(f"✅ Ruta cargada: {ruta['ruta_id']} - {ruta['zona']} ({len(ruta['paradas'])} paradas)")
                        
                except Exception as e:
                    print(f"❌ Error cargando ruta {archivo}: {e}")
    
    print(f"🔄 Todas las rutas cargadas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)
    
def formatear_ruta_para_repartidor(ruta):
    try:
        texto = f"RUTA ASIGNADA - ID {ruta.get('ruta_id', '?')}\n\n"
        texto += f"Zona: {limpiar_texto_markdown(ruta.get('zona', 'Sin zona'))}\n"
        texto += f"Paradas: {len(ruta.get('paradas', []))}\n"
        texto += f"Distancia: {ruta.get('estadisticas', {}).get('distancia_km', '?')} km\n"
        texto += f"Tiempo: {ruta.get('estadisticas', {}).get('tiempo_min', '?')} min\n\n"

        entregadas = len([p for p in ruta.get('paradas', []) if p.get('estado') == 'entregado'])
        texto += f"Progreso: {entregadas}/{len(ruta.get('paradas', []))}\n\n"
        texto += "Primeras 3 paradas:\n"

        for i, parada in enumerate(ruta.get('paradas', [])[:3], 1):
            nombre = parada.get('nombre', f"Persona {i}")
            if not nombre or nombre.strip() == "":
                nombre = f"Persona {i} (sin nombre)"
            estado = "Entregado" if parada.get('estado') == 'entregado' else "Pendiente"
            orden = parada.get('orden', i)
            dep = limpiar_texto_markdown(parada.get('dependencia', '')[:30])

            texto += f"{estado} {orden}. {limpiar_texto_markdown(nombre)}\n"
            if dep:
                texto += f"   {dep}\n"

        if len(ruta.get('paradas', [])) > 3:
            texto += f"\n... y {len(ruta.get('paradas', [])) - 3} más\n"

        texto += "\nUsa los botones para navegar"
        return texto

    except Exception as e:
        return f"Ruta {ruta.get('ruta_id', '?')} - {ruta.get('zona', '?')}"
        
def formatear_lista_completa(ruta):
    """Lista completa - 100% segura aunque falte 'nombre' o cualquier campo"""
    try:
        texto = f"LISTA COMPLETA - RUTA {ruta.get('ruta_id', 'ID?')}\n\n"
        texto += f"Zona: {limpiar_texto_markdown(ruta.get('zona', 'Sin zona'))}\n"
        texto += f"Total: {len(ruta.get('paradas', []))} paradas\n\n"

        entregadas = 0
        for i, parada in enumerate(ruta.get('paradas', []), 1):
            # === PROTECCIÓN TOTAL CONTRA CAMPOS FALTANTES ===
            nombre = parada.get('nombre', f"Persona {i} (sin nombre)")
            if not nombre or nombre.strip() == "":
                nombre = f"Persona {i} (sin nombre en lista)"

            estado = "Entregado" if parada.get('estado') == 'entregado' else "Pendiente"
            orden = parada.get('orden', i)
            dependencia = limpiar_texto_markdown(parada.get('dependencia', '')[:40])
            direccion = limpiar_texto_markdown(parada.get('direccion', '')[:40])

            nombre_limpio = limpiar_texto_markdown(nombre)

            texto += f"{estado} {orden}. {nombre_limpio}\n"
            if dependencia:
                texto += f"   {dependencia}\n"
            if direccion:
                texto += f"   {direccion}...\n"

            if parada.get('estado') == 'entregado':
                entregadas += 1
                ts = parada.get('timestamp_entrega', '')[:16].replace('T', ' ')
                if ts:
                    texto += f"   Entregado: {ts}\n"
            texto += "\n"

        texto += f"Progreso: {entregadas}/{len(ruta.get('paradas', []))} entregadas"
        return texto

    except Exception as e:
        print(f"Error formateando lista completa: {e}")
        return f"LISTA COMPLETA Ruta {ruta.get('ruta_id', '?')} - Error de datos"
        
def registrar_avance_pendiente(datos_avance):
    """🆕 Registrar un nuevo avance pendiente - VERSIÓN MEJORADA"""
    try:
        avance_id = f"avance_{int(time.time())}_{hash(str(datos_avance)) % 10000}"
        datos_avance['_id'] = avance_id
        datos_avance['_timestamp'] = datetime.now().isoformat()
        datos_avance['_procesado'] = False
        
        # 🆕 INFORMACIÓN EXTRA PARA DEBUG
        datos_avance['_debug'] = {
            'ruta_existe': os.path.exists(datos_avance.get('foto_local', '')),
            'timestamp_creacion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Guardar en archivo
        os.makedirs('avances_ruta', exist_ok=True)
        archivo_avance = f"avances_ruta/{avance_id}.json"
        with open(archivo_avance, 'w', encoding='utf-8') as f:
            json.dump(datos_avance, f, indent=2, ensure_ascii=False)
        
        # También guardar en memoria
        global AVANCES_PENDIENTES
        AVANCES_PENDIENTES.append(datos_avance)
        
        # Mantener solo últimos 100 en memoria
        if len(AVANCES_PENDIENTES) > 100:
            AVANCES_PENDIENTES = AVANCES_PENDIENTES[-100:]
        
        print(f"📝 Nuevo avance pendiente registrado: {avance_id}")
        print(f"   👤 {datos_avance.get('persona_entregada', 'N/A')}")
        print(f"   🗺️ Ruta {datos_avance.get('ruta_id', 'N/A')}")
        print(f"   📁 Foto: {datos_avance.get('foto_local', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error registrando avance pendiente: {e}")
        traceback.print_exc()
        return False

def registrar_entrega_sistema(user_id, user_name, persona_entregada, ruta_foto_local, comentarios=""):
    """Registrar entrega en el sistema de archivos - COMPATIBLE CON NUEVO SISTEMA"""
    try:
        if user_id not in RUTAS_ASIGNADAS:
            return False
            
        ruta_id = RUTAS_ASIGNADAS[user_id]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                
                # Buscar persona en paradas
                persona_encontrada = False
                for parada in ruta_data['paradas']:
                    nombre_parada = parada['nombre'].upper()
                    persona_buscar = persona_entregada.upper()
                    
                    # Búsqueda flexible
                    if (persona_buscar in nombre_parada or 
                        nombre_parada in persona_buscar or
                        any(palabra in nombre_parada for palabra in persona_buscar.split())):
                        
                        parada['estado'] = 'entregado'
                        parada['timestamp_entrega'] = timestamp
                        parada['foto_acuse'] = ruta_foto_local
                        parada['comentarios'] = comentarios
                        persona_encontrada = True
                        print(f"✅ Persona encontrada en ruta: {parada['nombre']}")
                        break
                
                if not persona_encontrada:
                    print(f"⚠️ Persona NO encontrada en ruta: {persona_entregada}")
                    # Buscar en todas las paradas por coincidencia parcial
                    for parada in ruta_data['paradas']:
                        if any(palabra in parada['nombre'].upper() for palabra in persona_entregada.upper().split()):
                            parada['estado'] = 'entregado'
                            parada['timestamp_entrega'] = timestamp
                            parada['foto_acuse'] = ruta_foto_local
                            parada['comentarios'] = f"{comentarios} (coincidencia parcial)"
                            persona_encontrada = True
                            print(f"✅ Coincidencia parcial: {persona_entregada} → {parada['nombre']}")
                            break
                
                # Verificar si la ruta está completada
                pendientes = [p for p in ruta_data['paradas'] if p.get('estado') != 'entregado']
                if not pendientes:
                    ruta_data['estado'] = 'completada'
                    ruta_data['timestamp_completada'] = timestamp
                
                # Guardar cambios
                with open(f'rutas_telegram/{archivo}', 'w', encoding='utf-8') as f:
                    json.dump(ruta_data, f, indent=2, ensure_ascii=False)
                
                # 🆕 CREAR AVANCE PENDIENTE para sincronización
                avance = {
                    'ruta_id': ruta_id,
                    'repartidor': user_name,
                    'repartidor_id': user_id,
                    'persona_entregada': persona_entregada,
                    'foto_local': ruta_foto_local,
                    'foto_acuse': ruta_foto_local,
                    'timestamp': timestamp,
                    'comentarios': comentarios,
                    'tipo': 'entrega'
                }
                
                # 🆕 REGISTRAR COMO AVANCE PENDIENTE
                registrar_avance_pendiente(avance)
                
                print(f"✅ Entrega registrada y avance creado: {user_name} → {persona_entregada} (Ruta {ruta_id})")
                return True
                
    except Exception as e:
        print(f"❌ Error registrando entrega: {e}")
    
    return False

def inicializar_sistema_completo():
    """Inicialización completa del sistema"""
    print("🔄 Inicializando sistema completo PJCDMX...")
    
    carpetas_necesarias = [
        'carpeta_fotos_central/entregas',
        'carpeta_fotos_central/incidentes', 
        'carpeta_fotos_central/estatus',
        'carpeta_fotos_central/general',
        'rutas_telegram', 
        'avances_ruta', 
        'incidencias_trafico',
        'avances_procesados',
        'rutas_excel'  # 🆕 CARPETA CRÍTICA QUE FALTABA
    ]
    
    for carpeta in carpetas_necesarias:
        os.makedirs(carpeta, exist_ok=True)
        print(f"📁 Carpeta creada/verificada: {carpeta}")
    
    rutas_cargadas = cargar_rutas_disponibles()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = cursor.fetchall()
        print(f"✅ Base de datos: {len(tablas)} tablas verificadas")
    except Exception as e:
        print(f"❌ Error en base de datos: {e}")
    
    print(f"🎯 Sistema listo. Rutas disponibles: {rutas_cargadas}")
    return True

def set_webhook():
    """Configurar webhook en Railway con manejo robusto de errores"""
    try:
        max_intentos = 3
        for intento in range(max_intentos):
            try:
                railway_url = os.environ.get('RAILWAY_STATIC_URL', 
                                           f"https://{os.environ.get('RAILWAY_SERVICE_NAME', 'monitoring-routes-pjcdmx')}.up.railway.app")
                webhook_url = f"{railway_url}/webhook"
                
                print(f"🔄 Configurando webhook (intento {intento + 1}): {webhook_url}")
                
                bot.remove_webhook()
                time.sleep(2)
                
                resultado = bot.set_webhook(url=webhook_url)
                
                if resultado:
                    print(f"✅ Webhook configurado: {webhook_url}")
                    
                    time.sleep(1)
                    info = bot.get_webhook_info()
                    print(f"📊 Info webhook: {info.url} - Pendientes: {info.pending_update_count}")
                    
                    return True
                else:
                    print(f"❌ Intento {intento + 1} falló")
                    
            except Exception as e:
                print(f"❌ Error en intento {intento + 1}: {e}")
                if intento < max_intentos - 1:
                    time.sleep(5)
        
        print("❌ Todos los intentos de configurar webhook fallaron")
        return False
        
    except Exception as e:
        print(f"❌ Error crítico configurando webhook: {e}")
        return False

# =============================================================================
# 🚨 FUNCIONES CRÍTICAS NUEVAS PARA MANEJO DE FOTOS (AGREGAR SOLO ESTAS)
# =============================================================================

def extraer_nombre_entrega(texto):
    """Extraer nombre de persona del texto de entrega"""
    if not texto:
        return "Persona no identificada"
    
    texto = texto.upper().strip()
    
    # Buscar patrones
    patrones = [
        "ENTREGADO A ",
        "ENTREGADA A ", 
        "PARA ",
        "A ",
        "PARA ENTREGAR A "
    ]
    
    for patron in patrones:
        if patron in texto:
            nombre = texto.split(patron, 1)[1].strip()
            # Limpiar nombre
            nombre = re.sub(r'[^\w\s]', ' ', nombre)
            nombre = ' '.join(nombre.split()[:3])  # Primeras 3 palabras
            return nombre.title()
    
    # Si no encuentra patrón
    texto_sin_entregado = texto.replace("ENTREGADO", "").replace("ENTREGADA", "").strip()
    palabras = texto_sin_entregado.split()[:3]
    return ' '.join(palabras).title() if palabras else "Persona no identificada"

def procesar_entrega_con_foto(user_id, user_name, file_id, caption, ruta_foto_guardada):
    """Procesar una entrega con foto - VERSIÓN SEGURA SIN MARKDOWN"""
    try:
        # Extraer nombre de persona
        persona_entregada = extraer_nombre_entrega(caption)
        
        if user_id not in RUTAS_ASIGNADAS:
            # 🆕 MENSAJE SIMPLE SIN MARKDOWN
            respuesta = (f"📸 FOTO RECIBIDA\n\n"
                       f"👤 {persona_entregada}\n"
                       f"📁 Guardada en sistema\n"
                       f"⚠️ No tienes ruta activa asignada")
            bot.send_message(user_id, respuesta, parse_mode=None)
            return
        
        ruta_id = RUTAS_ASIGNADAS[user_id]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Buscar y actualizar ruta
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                
                # Buscar persona en paradas
                persona_encontrada = False
                persona_actual = ""
                
                for parada in ruta_data['paradas']:
                    nombre_parada = parada['nombre'].upper()
                    persona_buscar = persona_entregada.upper()
                    
                    # Búsqueda flexible
                    if (persona_buscar in nombre_parada or 
                        nombre_parada in persona_buscar or
                        any(palabra in nombre_parada for palabra in persona_buscar.split())):
                        
                        parada['estado'] = 'entregado'
                        parada['timestamp_entrega'] = timestamp
                        parada['foto_acuse'] = ruta_foto_guardada
                        persona_encontrada = True
                        persona_actual = parada['nombre']
                        print(f"✅ Persona encontrada en ruta: {parada['nombre']}")
                        break
                
                if not persona_encontrada:
                    print(f"⚠️ Persona NO encontrada en ruta: {persona_entregada}")
                    # Buscar en todas las paradas por coincidencia parcial
                    for parada in ruta_data['paradas']:
                        if any(palabra in parada['nombre'].upper() for palabra in persona_entregada.upper().split()):
                            parada['estado'] = 'entregado'
                            parada['timestamp_entrega'] = timestamp
                            parada['foto_acuse'] = ruta_foto_guardada
                            parada['comentarios'] = f"{caption} (coincidencia parcial)"
                            persona_encontrada = True
                            persona_actual = parada['nombre']
                            print(f"✅ Coincidencia parcial: {persona_entregada} → {parada['nombre']}")
                            break
                
                # Guardar cambios
                with open(f'rutas_telegram/{archivo}', 'w', encoding='utf-8') as f:
                    json.dump(ruta_data, f, indent=2, ensure_ascii=False)
                
                if persona_encontrada:
                    # Contar entregas
                    entregadas = len([p for p in ruta_data['paradas'] if p.get('estado') == 'entregado'])
                    total = len(ruta_data['paradas'])
                    
                    # 🆕 MENSAJE SIMPLE SIN MARKDOWN
                    respuesta = (f"✅ ENTREGA REGISTRADA\n\n"
                               f"👤 {persona_actual}\n"
                               f"📅 {timestamp}\n"
                               f"📊 Progreso: {entregadas}/{total}")
                    
                    # Si se completó la ruta
                    if entregadas == total:
                        respuesta += "\n\n🎉 ¡RUTA COMPLETADA!"
                        
                    # 🆕 CREAR AVANCE PENDIENTE
                    avance = {
                        'ruta_id': ruta_id,
                        'repartidor': user_name,
                        'repartidor_id': user_id,
                        'persona_entregada': persona_actual,
                        'foto_local': ruta_foto_guardada,
                        'timestamp': timestamp,
                        'comentarios': caption,
                        'tipo': 'entrega'
                    }
                    
                    registrar_avance_pendiente(avance)
                    print(f"📝 Avance pendiente creado para Ruta {ruta_id}")
                        
                else:
                    # 🆕 MENSAJE SIMPLE SIN MARKDOWN
                    respuesta = (f"⚠️ ENTREGA REGISTRADA CON OBSERVACIONES\n\n"
                               f"👤 {persona_entregada}\n"
                               f"📅 {timestamp}\n"
                               f"ℹ️ Persona no encontrada en lista original")
                
                bot.send_message(user_id, respuesta, parse_mode=None)  # 🆕 SIN MARKDOWN
                print(f"✅ Entrega registrada: {persona_entregada} en Ruta {ruta_id}")
                return
        
        bot.send_message(user_id, "❌ No se encontró la ruta asignada", parse_mode=None)
        
    except Exception as e:
        print(f"❌ Error procesando entrega: {e}")
        traceback.print_exc()
        bot.send_message(user_id, "❌ Error al registrar entrega", parse_mode=None)

def procesar_foto_reporte(user_id, user_name, file_id, caption, ruta_foto_guardada):
    """Procesar foto de reporte/incidencia - SIN MARKDOWN PROBLEMÁTICO"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 🆕 MENSAJE SIMPLE SIN MARKDOWN
        respuesta = (f"📸 REPORTE CON FOTO\n\n"
                   f"👤 {user_name}\n"
                   f"📅 {timestamp}\n"
                   f"📝 {caption if caption else 'Sin descripción'}\n"
                   f"✅ Reporte registrado en sistema")
        
        bot.send_message(user_id, respuesta, parse_mode=None)  # 🆕 SIN MARKDOWN
        print(f"✅ Foto de reporte guardada: {ruta_foto_guardada}")
        
    except Exception as e:
        print(f"❌ Error procesando reporte: {e}")

def actualizar_excel_desde_entrega(ruta_id, persona_entregada, ruta_foto, repartidor, timestamp):
    """Actualizar Excel automáticamente cuando se registra una entrega"""
    try:
        print(f"🔄 Actualizando Excel para Ruta {ruta_id}: {persona_entregada}")
        
        # Buscar archivo Excel de la ruta
        archivos_excel = [f for f in os.listdir('rutas_excel') 
                         if f"Ruta_{ruta_id}_" in f and f.endswith('.xlsx')]
        
        if not archivos_excel:
            print(f"❌ No se encontró Excel para Ruta {ruta_id}")
            return False
        
        excel_file = f"rutas_excel/{archivos_excel[0]}"
        df = pd.read_excel(excel_file)
        
        # Buscar persona en Excel
        persona_actualizada = False
        for idx, fila in df.iterrows():
            nombre_excel = str(fila.get('Nombre', '')).strip().upper()
            persona_buscar = persona_entregada.strip().upper()
            
            # Búsqueda flexible
            if (persona_buscar in nombre_excel or 
                nombre_excel in persona_buscar or
                any(palabra in nombre_excel for palabra in persona_buscar.split())):
                
                # Crear link para la foto
                link_foto = f'=HIPERVINCULO("{ruta_foto}", "📸 VER FOTO")' if ruta_foto else "SIN FOTO"
                
                # Actualizar fila
                df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                df.at[idx, 'Repartidor'] = repartidor
                df.at[idx, 'Foto_Acuse'] = link_foto
                df.at[idx, 'Timestamp_Entrega'] = timestamp
                df.at[idx, 'Estado'] = 'ENTREGADO'
                
                persona_actualizada = True
                print(f"✅ Excel actualizado: {persona_entregada} → {fila.get('Nombre')}")
                break
        
        if persona_actualizada:
            # Guardar Excel
            df.to_excel(excel_file, index=False)
            print(f"💾 Excel guardado: {excel_file}")
            return True
        else:
            print(f"⚠️ Persona no encontrada en Excel: {persona_entregada}")
            # Agregar nueva fila
            nueva_fila = {
                'Orden': len(df) + 1,
                'Nombre': persona_entregada,
                'Dependencia': 'NO ENCONTRADO EN LISTA ORIGINAL',
                'Dirección': 'REGISTRO AUTOMÁTICO',
                'Acuse': f"✅ ENTREGADO - {timestamp}",
                'Repartidor': repartidor,
                'Foto_Acuse': f'=HIPERVINCULO("{ruta_foto}", "📸 VER FOTO")' if ruta_foto else "SIN FOTO",
                'Timestamp_Entrega': timestamp,
                'Estado': 'ENTREGADO'
            }
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            df.to_excel(excel_file, index=False)
            print(f"📝 Nueva fila agregada en Excel: {persona_entregada}")
            return True
            
    except Exception as e:
        print(f"❌ Error actualizando Excel: {str(e)}")
        return False

# =============================================================================
# 📍 SISTEMA DE UBICACIÓN EN TIEMPO REAL
# =============================================================================

@manejar_errores_telegram
@bot.message_handler(commands=['ubicacion'])
def solicitar_ubicacion(message):
    """Solicitar al usuario que comparta su ubicación"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"📍 Solicitando ubicación de {user_name} (ID: {user_id})")
        
        markup = types.ReplyKeyboardMarkup(
            row_width=1, 
            resize_keyboard=True, 
            one_time_keyboard=True
        )
        
        btn_ubicacion = types.KeyboardButton("📍 Compartir mi ubicación", request_location=True)
        btn_cancelar = types.KeyboardButton("❌ Cancelar")
        markup.add(btn_ubicacion, btn_cancelar)
        
        mensaje = (
            "📍 **COMPARTIR UBICACIÓN EN TIEMPO REAL**\n\n"
            "Por favor comparte tu ubicación actual para:\n\n"
            "• 🗺️ Seguimiento en tiempo real\n"
            "• 📊 Optimización de rutas\n"
            "• 🚨 Respuesta rápida en emergencias\n\n"
            "⚠️ **Tu ubicación solo será visible para el supervisor**"
        )
        
        bot.send_message(
            user_id, 
            mensaje, 
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        print(f"❌ Error solicitando ubicación: {e}")
        bot.reply_to(message, "❌ Error al solicitar ubicación")

@manejar_errores_telegram
@bot.message_handler(content_types=['location'])
def manejar_ubicacion(message):
    """Manejar ubicación recibida del usuario"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        location = message.location
        
        latitud = location.latitude
        longitud = location.longitude
        
        print(f"📍 Ubicación recibida de {user_name}: {latitud}, {longitud}")
        
        # Guardar ubicación en base de datos
        cursor.execute('''
            INSERT INTO incidentes 
            (user_id, user_name, tipo, descripcion, ubicacion, timestamp)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, user_name, 'ubicacion', 'Ubicación en tiempo real', f"{latitud},{longitud}"))
        
        conn.commit()
        
        # Crear mensaje de respuesta
        mensaje = (
            "✅ **UBICACIÓN REGISTRADA**\n\n"
            f"📍 **Coordenadas:**\n"
            f"• Latitud: `{latitud}`\n"
            f"• Longitud: `{longitud}`\n\n"
            f"🗺️ **Ver en Google Maps:**\n"
            f"https://www.google.com/maps?q={latitud},{longitud}\n\n"
            f"👤 **Usuario:** {user_name}\n"
            f"🕒 **Hora:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            "📊 _Tu ubicación ha sido registrada en el sistema_"
        )
        
        # Crear teclado inline con opciones
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "🗺️ Abrir en Maps", 
                url=f"https://www.google.com/maps?q={latitud},{longitud}"
            ),
            types.InlineKeyboardButton(
                "📱 Compartir ruta", 
                url=f"https://www.google.com/maps/dir/?api=1&destination={latitud},{longitud}"
            )
        )
        markup.row(
            types.InlineKeyboardButton("📍 Nueva ubicación", callback_data="nueva_ubicacion"),
            types.InlineKeyboardButton("❌ Cerrar", callback_data="cerrar_ubicacion")
        )
        
        # Enviar mensaje con teclado
        bot.send_message(
            user_id,
            mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        # 🆕 NOTIFICAR A SUPERVISORES
        notificar_supervisores_ubicacion(user_name, latitud, longitud)
        
        print(f"✅ Ubicación guardada: {user_name} - {latitud}, {longitud}")
        
    except Exception as e:
        print(f"❌ Error manejando ubicación: {e}")
        bot.reply_to(message, "❌ Error al procesar ubicación")

def notificar_supervisores_ubicacion(user_name, latitud, longitud):
    """Notificar a supervisores sobre nueva ubicación"""
    try:
        mensaje_supervisor = (
            "📍 **NUEVA UBICACIÓN REGISTRADA**\n\n"
            f"👤 **Repartidor:** {user_name}\n"
            f"📍 **Coordenadas:** {latitud}, {longitud}\n"
            f"🕒 **Hora:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"🗺️ **Ver en mapa:**\n"
            f"https://www.google.com/maps?q={latitud},{longitud}"
        )
        
        # Notificar a todos los administradores
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(
                    admin_id,
                    mensaje_supervisor,
                    parse_mode='Markdown'
                )
                print(f"✅ Supervisor notificado: {admin_id}")
            except Exception as e:
                print(f"❌ Error notificando supervisor {admin_id}: {e}")
                
    except Exception as e:
        print(f"❌ Error en notificación a supervisores: {e}")

@manejar_errores_telegram
@bot.message_handler(func=lambda message: message.text == "📍 Compartir mi ubicación")
def manejar_boton_ubicacion(message):
    """Manejar clic en el botón de ubicación del teclado"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"📍 Botón de ubicación presionado por {user_name}")
        
        # Eliminar teclado
        markup = types.ReplyKeyboardRemove()
        
        mensaje = (
            "📍 **LISTO PARA RECIBIR UBICACIÓN**\n\n"
            "Por favor usa el botón de 📎 (clip) y selecciona \"Ubicación\" "
            "para compartir tu ubicación actual.\n\n"
            "O presiona el botón de ubicación en la barra de herramientas."
        )
        
        bot.send_message(
            user_id,
            mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        print(f"❌ Error manejando botón ubicación: {e}")

@manejar_errores_telegram
@bot.message_handler(func=lambda message: message.text == "❌ Cancelar")
def manejar_cancelar_ubicacion(message):
    """Manejar cancelación de compartir ubicación"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"❌ Ubicación cancelada por {user_name}")
        
        # Eliminar teclado
        markup = types.ReplyKeyboardRemove()
        
        mensaje = "❌ Compartir ubicación cancelado."
        
        bot.send_message(
            user_id,
            mensaje,
            reply_markup=markup
        )
        
    except Exception as e:
        print(f"❌ Error cancelando ubicación: {e}")

# =============================================================================
# HANDLERS DE TELEGRAM (MANTENER LOS QUE YA TIENES)
# =============================================================================

@bot.message_handler(commands=['start', 'hola'])
def enviar_bienvenida(message):
    print(f"🎯 COMANDO /start RECIBIDO de: {message.from_user.first_name}")
    try:
        welcome_text = f"""
🤖 BOT DE RUTAS AUTOMÁTICO - PJCDMX 🚚

¡Hola {message.from_user.first_name}! Soy tu asistente de rutas automáticas.

🚀 COMANDOS PRINCIPALES:
/solicitar_ruta - 🗺️ Obtener ruta automáticamente
/miruta - 📋 Ver mi ruta asignada  
/entregar - 📦 Registrar entrega completada
/ubicacion - 📍 Compartir ubicación en tiempo real

📊 REPORTES Y SEGUIMIENTO:
/incidente - 🚨 Reportar incidente
/foto - 📸 Enviar foto del incidente
/estatus - 📈 Actualizar estado de entrega
/atencionH - 👨‍💼 Soporte humano

¡El sistema asigna rutas automáticamente!
        """
        bot.reply_to(message, welcome_text, parse_mode=None)
        print("✅ Mensaje de bienvenida ENVIADO")
    except Exception as e:
        print(f"❌ ERROR enviando mensaje: {e}")
        try:
            bot.reply_to(message, "🤖 Bot PJCDMX - Usa /solicitar_ruta para comenzar")
        except:
            print("❌ ERROR CRÍTICO: No se pudo enviar ningún mensaje")

@manejar_errores_telegram
@bot.message_handler(commands=['solicitar_ruta'])
def solicitar_ruta_automatica(message):
    """Asignar ruta automáticamente al repartidor - CON MANEJO DE ERRORES"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"🔄 Solicitud de ruta de {user_name} (ID: {user_id})")
        
        if user_id in RUTAS_ASIGNADAS:
            bot.reply_to(message, "⚠️ Ya tienes una ruta asignada. Usa /miruta para verla.")
            return
        
        rutas_disponibles = cargar_rutas_disponibles()
        
        if rutas_disponibles == 0:
            bot.reply_to(message, 
                        "📭 No hay rutas disponibles en este momento.",
                        parse_mode=None)
            return
        
        ruta_asignada = RUTAS_DISPONIBLES.pop(0)
        ruta_id = ruta_asignada['ruta_id']
        zona = ruta_asignada['zona']
        
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        ruta_asignada['repartidor_asignado'] = f"{user_name} (ID:{user_id})"
        ruta_asignada['estado'] = 'asignada'
        ruta_asignada['timestamp_asignacion'] = datetime.now().isoformat()
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(ruta_asignada, f, indent=2, ensure_ascii=False)
        
        RUTAS_ASIGNADAS[user_id] = ruta_id
        mensaje = formatear_ruta_para_repartidor(ruta_asignada)
        
        # 🎯 BOTONES MEJORADOS - CON LISTA COMPLETA
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ Abrir en Maps", url=ruta_asignada['google_maps_url']),
            types.InlineKeyboardButton("👥 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta_id}")
        )
        markup.row(
            types.InlineKeyboardButton("📦 Registrar Entrega", callback_data=f"entregar_{ruta_id}"),
            types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="nueva_ubicacion")
        )
        markup.row(
            types.InlineKeyboardButton("📊 Progreso", callback_data=f"estatus_{ruta_id}"),
            types.InlineKeyboardButton("🚨 Reportar Problema", callback_data=f"incidencia_{ruta_id}")
        )
        
        try:
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            print(f"✅ Ruta {ruta_id} asignada a {user_name}")
        except Exception as e:
            print(f"❌ Error enviando mensaje formateado: {e}")
            mensaje_simple = f"🗺️ Ruta {ruta_id} - {zona}\n{len(ruta_asignada['paradas'])} paradas\n\nAbre en Maps:"
            bot.reply_to(message, mensaje_simple, parse_mode=None, reply_markup=markup)
        
    except Exception as e:
        error_msg = f"❌ Error asignando ruta: {str(e)}"
        print(error_msg)
        bot.reply_to(message, 
                    "❌ Error al asignar ruta.\n\nPor favor, intenta nuevamente.",
                    parse_mode=None)

@manejar_errores_telegram
@bot.message_handler(commands=['miruta'])
def ver_mi_ruta(message):
    """Ver la ruta asignada actual - CON MANEJO SEGURO"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    if user_id not in RUTAS_ASIGNADAS:
        bot.reply_to(message, "❌ No tienes una ruta asignada. Usa /solicitar_ruta para obtener una.")
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for archivo in os.listdir('rutas_telegram'):
        if f"Ruta_{ruta_id}_" in archivo:
            try:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta = json.load(f)
                
                mensaje = formatear_ruta_para_repartidor(ruta)
                
                # 🎯 BOTONES MEJORADOS - CON LISTA COMPLETA
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("🗺️ Abrir en Maps", url=ruta['google_maps_url']),
                    types.InlineKeyboardButton("👥 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta_id}")
                )
                markup.row(
                    types.InlineKeyboardButton("📦 Registrar Entrega", callback_data=f"entregar_{ruta_id}"),
                    types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="nueva_ubicacion")
                )
                markup.row(
                    types.InlineKeyboardButton("📊 Progreso", callback_data=f"estatus_{ruta_id}"),
                    types.InlineKeyboardButton("🚨 Reportar Problema", callback_data=f"incidencia_{ruta_id}")
                )
                
                try:
                    bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
                except Exception as e:
                    print(f"❌ Error enviando /miruta: {e}")
                    mensaje_simple = f"🗺️ Ruta {ruta_id}\n{ruta['zona']} - {len(ruta['paradas'])} paradas\n\nAbre en Maps:"
                    bot.reply_to(message, mensaje_simple, parse_mode=None, reply_markup=markup)
                return
                
            except Exception as e:
                print(f"❌ Error leyendo ruta {archivo}: {e}")
    
    bot.reply_to(message, 
                "❌ No se pudo encontrar tu ruta.",
                parse_mode=None)

# =============================================================================
# 🚨 HANDLER DE FOTOS CORREGIDO (USAR SOLO ESTE)
# =============================================================================

@manejar_errores_telegram   
@bot.message_handler(content_types=['photo'])
def manejar_fotos(message):
    """Manejar fotos de entregas y reportes - VERSIÓN MEJORADA CON DATOS COMPLETOS"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        
        print(f"📸 Foto recibida de {user_name}: '{caption}'")
        
        # Detección de tipo
        caption_lower = caption.lower()
        
        if any(word in caption_lower for word in ['entregado', 'entregada', '✅', 'recibido', 'acuse']):
            tipo = 'foto_acuse'
            carpeta = 'entregas'
            es_entrega = True
        elif any(word in caption_lower for word in ['retrasado', 'problema', '⏳', 'estatus']):
            tipo = 'foto_estatus' 
            carpeta = 'estatus'
            es_entrega = False
        elif any(word in caption_lower for word in ['incidente', 'tráfico', 'trafico', 'accidente', '🚨']):
            tipo = 'foto_incidente'
            carpeta = 'incidentes'
            es_entrega = False
        else:
            tipo = 'foto_general'
            carpeta = 'general'
            es_entrega = False

        print(f"🎯 CLASIFICACIÓN: '{caption}' → Carpeta: {carpeta}, Entrega: {es_entrega}")
        
        # DESCARGAR Y GUARDAR FOTO COMPLETA
        ruta_foto_local = descargar_foto_telegram(file_id, carpeta)
        
        # 🆕 USAR LA NUEVA FUNCIÓN QUE GUARDA DATOS BINARIOS
        guardar_foto_completa(
            file_id=file_id,
            user_id=user_id,
            user_name=user_name,
            caption=caption,
            tipo=tipo,
            ruta_foto_local=ruta_foto_local
        )

        # PROCESAR SEGÚN TIPO
        if es_entrega:
            print(f"🎯 Detectada entrega, procesando...")
            procesar_entrega_con_foto(user_id, user_name, file_id, caption, ruta_foto_local)
        else:
            print(f"🎯 Foto de reporte, procesando...")
            procesar_foto_reporte(user_id, user_name, file_id, caption, ruta_foto_local)
        
        # 🆕 INFORMAR AL USUARIO CON ENLACE A LA FOTO
        try:
            foto_url = f"https://{os.environ.get('RAILWAY_STATIC_URL', 'tu-url-railway')}/api/fotos/{file_id}"
            mensaje_extra = f"\n\n📎 Enlace permanente: {foto_url}"
            
            if es_entrega:
                bot.send_message(user_id, f"✅ Entrega registrada.{mensaje_extra}", parse_mode=None)
            else:
                bot.send_message(user_id, f"✅ Reporte con foto guardado.{mensaje_extra}", parse_mode=None)
                
        except Exception as e:
            print(f"⚠️ No se pudo enviar enlace de foto: {e}")
        
        print(f"📸 Procesamiento completado: {user_name} - Tipo: {tipo}")
        
    except Exception as e:
        print(f"❌ Error con foto: {e}")
        traceback.print_exc()
        try:
            bot.reply_to(message, "❌ Error procesando foto. Intenta nuevamente.", parse_mode=None)
        except:
            pass

# =============================================================================
# HANDLERS PARA BOTONES INLINE (CALLBACKS) - VERSIÓN MEJORADA
# =============================================================================

def manejar_callback_foto_entrega(call):
    """Manejar clic en botón 'Subir foto ahora' para entrega"""
    try:
        # Extraer ruta_id del callback data (ej: "foto_5")
        partes = call.data.split('_')
        if len(partes) >= 2:
            ruta_id = partes[1]
        else:
            ruta_id = "desconocida"
        
        mensaje = f"📸 **SUBIR FOTO DE ENTREGA - Ruta {ruta_id}**\n\n"
        mensaje += "Por favor toma una foto del acuse firmado y escribe en el pie de foto:\n\n"
        mensaje += "`ENTREGADO A [NOMBRE COMPLETO]`\n\n"
        mensaje += "**Ejemplos:**\n"
        mensaje += "• `ENTREGADO A JUAN PÉREZ LÓPEZ`\n"
        mensaje += "• `ENTREGADO A MARÍA GARCÍA`\n"
        mensaje += "• `PARA CARLOS RODRÍGUEZ`\n\n"
        mensaje += "⚠️ **IMPORTANTE:** El texto debe incluir 'ENTREGADO A' o 'PARA' seguido del nombre."

        # Crear teclado con opción de cancelar
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        bot.answer_callback_query(call.id, "📸 Listo para recibir foto...")
        
    except Exception as e:
        print(f"❌ Error en foto entrega callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al preparar foto")

def manejar_callback_entregar(call):
    """Manejar clic en botón 'Entregar' - VERSIÓN MEJORADA Y SIMPLIFICADA"""
    try:
        # Extraer ruta_id del callback data (ej: "entregar_5")
        partes = call.data.split('_')
        if len(partes) >= 2:
            ruta_id = partes[1]
        else:
            ruta_id = "desconocida"
        
        mensaje = f"📦 **REGISTRAR ENTREGA - Ruta {ruta_id}**\n\n"
        mensaje += "**OPCIÓN 1 - FOTO RÁPIDA:**\n"
        mensaje += "• Usa el botón '📸 Subir foto ahora'\n"
        mensaje += "• Toma foto del acuse firmado\n"
        mensaje += "• Escribe: `ENTREGADO A [NOMBRE]` en el pie de foto\n\n"
        
        mensaje += "**OPCIÓN 2 - MANUAL:**\n"  
        mensaje += "• Simplemente envía una foto normal\n"
        mensaje += "• Escribe el texto de entrega en el pie de foto\n"
        mensaje += "• El sistema detectará automáticamente\n\n"
        
        mensaje += "**📝 FORMATOS ACEPTADOS:**\n"
        mensaje += "• `ENTREGADO A JUAN PÉREZ`\n"
        mensaje += "• `ENTREGADA A MARÍA GARCÍA`\n" 
        mensaje += "• `PARA CARLOS RODRÍGUEZ`\n"
        mensaje += "• `ACUSE DE JUANA LÓPEZ`\n"

        # 🎯 BOTONES SIMPLIFICADOS - SOLO LOS ESENCIALES
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📸 Subir foto ahora", callback_data=f"foto_{ruta_id}"),
        )
        markup.row(
            types.InlineKeyboardButton("🗺️ Volver a la ruta", callback_data=f"volver_resumen_{ruta_id}"),
            types.InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        bot.answer_callback_query(call.id, "📦 Preparando registro de entrega...")
        
    except Exception as e:
        print(f"❌ Error en entregar callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al procesar entrega")

def manejar_callback_estatus(call):
    """Manejar clic en botón 'Estatus' - VERSIÓN SIMPLIFICADA"""
    try:
        user_id = call.from_user.id
        
        if user_id not in RUTAS_ASIGNADAS:
            bot.answer_callback_query(call.id, "❌ No tienes ruta asignada")
            return
        
        ruta_id = RUTAS_ASIGNADAS[user_id]
        
        # Buscar información de la ruta
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta = json.load(f)
                
                entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
                total = len(ruta['paradas'])
                progreso = (entregadas / total) * 100 if total > 0 else 0
                
                mensaje = f"📊 **ESTATUS RUTA {ruta_id}**\n\n"
                mensaje += f"📍 **Zona:** {ruta['zona']}\n"
                mensaje += f"✅ **Entregados:** {entregadas}/{total}\n"
                mensaje += f"📈 **Progreso:** {progreso:.1f}%\n"
                mensaje += f"📏 **Distancia:** {ruta['estadisticas']['distancia_km']} km\n"
                mensaje += f"⏱️ **Tiempo estimado:** {ruta['estadisticas']['tiempo_min']} min\n\n"
                
                if entregadas < total:
                    siguiente_parada = next((p for p in ruta['paradas'] if p.get('estado') != 'entregado'), None)
                    if siguiente_parada:
                        mensaje += f"📍 **Próxima parada:**\n"
                        mensaje += f"👤 {siguiente_parada['nombre']}\n"
                        mensaje += f"🏢 {siguiente_parada.get('dependencia', 'N/A')}\n"
                        mensaje += f"📪 {siguiente_parada['direccion'][:50]}..."
                
                # 🎯 BOTONES SIMPLIFICADOS
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("📦 Registrar entrega", callback_data=f"entregar_{ruta_id}"),
                    types.InlineKeyboardButton("🗺️ Ver en Maps", url=ruta['google_maps_url'])
                )
                markup.row(
                    types.InlineKeyboardButton("🔄 Actualizar", callback_data=f"estatus_{ruta_id}"),
                    types.InlineKeyboardButton("❌ Cerrar", callback_data="cancelar")
                )
                
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=mensaje,
                    parse_mode='Markdown',
                    reply_markup=markup
                )
                break
        
        bot.answer_callback_query(call.id, "📊 Estatus actualizado")
        
    except Exception as e:
        print(f"❌ Error en estatus callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al obtener estatus")

def manejar_callback_incidencia(call):
    """Manejar clic en botón 'Incidencia' - VERSIÓN SIMPLIFICADA"""
    try:
        mensaje = "🚨 **REPORTAR INCIDENCIA**\n\n"
        mensaje += "Selecciona el tipo de incidencia:\n\n"
        
        # 🎯 BOTONES SIMPLIFICADOS - SOLO LOS MÁS IMPORTANTES
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🚗 Tráfico", callback_data="incidencia_trafico"),
            types.InlineKeyboardButton("🛑 Vehicular", callback_data="incidencia_vehicular")
        )
        markup.row(
            types.InlineKeyboardButton("📦 Entrega", callback_data="incidencia_entrega"),
            types.InlineKeyboardButton("📞 Supervisor", callback_data="contactar_supervisor")
        )
        markup.row(
            types.InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        bot.answer_callback_query(call.id, "🚨 Preparando reporte...")
        
    except Exception as e:
        print(f"❌ Error en incidencia callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al procesar incidencia")

def manejar_callback_lista_completa(call):
    """Manejar clic en botón 'Ver Lista Completa' - VERSIÓN CORREGIDA Y MEJORADA"""
    try:
        # 🆕 CORRECCIÓN: Extraer ruta_id correctamente
        # El formato es "lista_completa_5" -> ["lista", "completa", "5"]
        partes = call.data.split('_')
        ruta_id = partes[2] if len(partes) >= 3 else "desconocida"
        
        user_id = call.from_user.id
        
        print(f"📋 Solicitando lista completa de Ruta {ruta_id} por {call.from_user.first_name}")
        
        # Buscar la ruta
        ruta_encontrada = None
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                try:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta_encontrada = json.load(f)
                    break
                except Exception as e:
                    print(f"❌ Error leyendo ruta {archivo}: {e}")
                    continue
        
        if not ruta_encontrada:
            bot.answer_callback_query(call.id, "❌ No se encontró la ruta")
            return
        
        # 🆕 USAR LA FUNCIÓN SEGURA SIN MARKDOWN
        mensaje = formatear_lista_completa(ruta_encontrada)
        
        # 🎯 BOTONES MEJORADOS - MÁS CLAROS Y ORGANIZADOS
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📦 Registrar entrega", callback_data=f"entregar_{ruta_id}"),
            types.InlineKeyboardButton("🗺️ Abrir Maps", url=ruta_encontrada['google_maps_url'])
        )
        markup.row(
            types.InlineKeyboardButton("📊 Volver al resumen", callback_data=f"volver_resumen_{ruta_id}"),
            types.InlineKeyboardButton("❌ Cerrar", callback_data="cancelar")
        )
        
        # 🆕 MANEJO SEGURO DE MARKDOWN
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=mensaje,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except Exception as e:
            print(f"⚠️ Error con Markdown, enviando sin formato: {e}")
            # Enviar sin Markdown como fallback
            mensaje_simple = f"👥 LISTA COMPLETA - Ruta {ruta_id}\n\n"
            mensaje_simple += f"📍 Zona: {ruta_encontrada['zona']}\n"
            mensaje_simple += f"📊 Total: {len(ruta_encontrada['paradas'])} personas\n\n"
            
            for i, parada in enumerate(ruta_encontrada['paradas'][:5], 1):
                estado = "✅" if parada.get('estado') == 'entregado' else "📍"
                mensaje_simple += f"{estado} {parada['orden']}. {parada['nombre']}\n"
            
            if len(ruta_encontrada['paradas']) > 5:
                mensaje_simple += f"\n... y {len(ruta_encontrada['paradas']) - 5} más"
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=mensaje_simple,
                parse_mode=None,
                reply_markup=markup
            )
        
        bot.answer_callback_query(call.id, "👥 Mostrando lista completa...")
        
    except Exception as e:
        print(f"❌ Error en lista completa callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al mostrar lista")

def manejar_callback_volver_resumen(call):
    """Manejar clic en botón 'Volver al resumen' - VERSIÓN CORREGIDA Y MEJORADA"""
    try:
        # 🆕 CORRECCIÓN: Extraer ruta_id correctamente
        partes = call.data.split('_')
        ruta_id = partes[2] if len(partes) >= 3 else "desconocida"
        
        user_id = call.from_user.id
        
        print(f"📋 Volviendo al resumen de Ruta {ruta_id}")
        
        # Buscar la ruta
        ruta_encontrada = None
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                try:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta_encontrada = json.load(f)
                    break
                except Exception as e:
                    print(f"❌ Error leyendo ruta {archivo}: {e}")
                    continue
        
        if not ruta_encontrada:
            bot.answer_callback_query(call.id, "❌ No se encontró la ruta")
            return
        
        mensaje = formatear_ruta_para_repartidor(ruta_encontrada)
        
        # 🎯 BOTONES MEJORADOS - CON LISTA COMPLETA
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ Abrir en Maps", url=ruta_encontrada['google_maps_url']),
            types.InlineKeyboardButton("👥 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta_id}")
        )
        markup.row(
            types.InlineKeyboardButton("📦 Registrar Entrega", callback_data=f"entregar_{ruta_id}"),
            types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="nueva_ubicacion")
        )
        markup.row(
            types.InlineKeyboardButton("📊 Progreso", callback_data=f"estatus_{ruta_id}"),
            types.InlineKeyboardButton("🚨 Reportar Problema", callback_data=f"incidencia_{ruta_id}")
        )
        
        # 🆕 MANEJO SEGURO DE MARKDOWN
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=mensaje,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except Exception as e:
            print(f"⚠️ Error con Markdown, enviando sin formato: {e}")
            mensaje_simple = f"🗺️ RUTA {ruta_id}\n\n"
            mensaje_simple += f"📍 {ruta_encontrada['zona']}\n"
            mensaje_simple += f"📦 {len(ruta_encontrada['paradas'])} paradas\n"
            mensaje_simple += f"📏 {ruta_encontrada['estadisticas']['distancia_km']} km\n"
            mensaje_simple += f"⏱️ {ruta_encontrada['estadisticas']['tiempo_min']} min\n\n"
            mensaje_simple += "🚀 Usa los botones para navegar"
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=mensaje_simple,
                parse_mode=None,
                reply_markup=markup
            )
        
        bot.answer_callback_query(call.id, "📋 Volviendo al resumen...")
        
    except Exception as e:
        print(f"❌ Error en volver resumen callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al volver al resumen")

# 🎯 CALLBACKS SIMPLIFICADOS PARA INCIDENCIAS
def manejar_callback_incidencia_trafico(call):
    """Manejar incidencia de tráfico - VERSIÓN SIMPLE"""
    try:
        mensaje = "🚗 **INCIDENCIA DE TRÁFICO REGISTRADA**\n\n"
        mensaje += "Se ha registrado tu reporte de tráfico.\n"
        mensaje += "El supervisor ha sido notificado.\n\n"
        mensaje += "📝 _Por favor envía un mensaje con los detalles específicos..._"
        
        bot.answer_callback_query(call.id, "🚗 Reporte de tráfico registrado")
        bot.send_message(call.message.chat.id, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Error en incidencia tráfico: {e}")
        bot.answer_callback_query(call.id, "❌ Error al procesar incidencia")

def manejar_callback_incidencia_vehicular(call):
    """Manejar incidencia vehicular - VERSIÓN SIMPLE"""
    try:
        mensaje = "🛑 **INCIDENCIA VEHICULAR REGISTRADA**\n\n"
        mensaje += "Se ha registrado tu reporte vehicular.\n"
        mensaje += "El departamento de transporte ha sido notificado.\n\n"
        mensaje += "📞 _Te contactaremos pronto para asistencia..._"
        
        bot.answer_callback_query(call.id, "🛑 Reporte vehicular registrado")
        bot.send_message(call.message.chat.id, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Error en incidencia vehicular: {e}")
        bot.answer_callback_query(call.id, "❌ Error al procesar incidencia")

def manejar_callback_incidencia_entrega(call):
    """Manejar incidencia de entrega - VERSIÓN SIMPLE"""
    try:
        mensaje = "📦 **PROBLEMA DE ENTREGA REGISTRADO**\n\n"
        mensaje += "Se ha registrado el problema con la entrega.\n"
        mensaje += "El supervisor de rutas ha sido notificado.\n\n"
        mensaje += "📋 _Por favor proporciona detalles del problema..._"
        
        bot.answer_callback_query(call.id, "📦 Problema de entrega registrado")
        bot.send_message(call.message.chat.id, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Error en incidencia entrega: {e}")
        bot.answer_callback_query(call.id, "❌ Error al procesar incidencia")

def manejar_callback_contactar_supervisor(call):
    """Manejar contacto con supervisor - VERSIÓN ACTUALIZADA"""
    try:
        mensaje = "📞 **CONTACTO CON SUPERVISOR**\n\n"
        mensaje += "🔸 **Supervisor:** Lic. Pedro Javier Hernandez Vasquez\n"
        mensaje += "🔸 **Teléfono:** 55 3197 3078\n"
        mensaje += "🔸 **Horario:** 7:00 - 19:00 hrs\n\n"
        mensaje += "📲 _Puedes llamar o enviar mensaje directamente_"
        
        bot.answer_callback_query(call.id, "📞 Información de supervisor")
        bot.send_message(call.message.chat.id, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Error en contacto supervisor: {e}")
        bot.answer_callback_query(call.id, "❌ Error al contactar")

def manejar_callback_nueva_ubicacion(call):
    """Manejar solicitud de nueva ubicación"""
    try:
        user_id = call.from_user.id
        user_name = call.from_user.first_name
        
        print(f"📍 Nueva ubicación solicitada por {user_name}")
        
        # Eliminar mensaje anterior
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # Solicitar ubicación nuevamente
        markup = types.ReplyKeyboardMarkup(
            row_width=1, 
            resize_keyboard=True, 
            one_time_keyboard=True
        )
        
        btn_ubicacion = types.KeyboardButton("📍 Compartir mi ubicación", request_location=True)
        btn_cancelar = types.KeyboardButton("❌ Cancelar")
        markup.add(btn_ubicacion, btn_cancelar)
        
        mensaje = (
            "📍 **COMPARTIR UBICACIÓN EN TIEMPO REAL**\n\n"
            "Por favor comparte tu ubicación actual para:\n\n"
            "• 🗺️ Seguimiento en tiempo real\n"
            "• 📊 Optimización de rutas\n"
            "• 🚨 Respuesta rápida en emergencias\n\n"
            "⚠️ **Tu ubicación solo será visible para el supervisor**"
        )
        
        bot.send_message(
            user_id, 
            mensaje, 
            parse_mode='Markdown',
            reply_markup=markup
        )
        
        bot.answer_callback_query(call.id, "📍 Solicitando nueva ubicación...")
        
    except Exception as e:
        print(f"❌ Error en nueva ubicación callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error al solicitar ubicación")

def manejar_callback_cerrar_ubicacion(call):
    """Manejar cierre de mensaje de ubicación"""
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "✅ Mensaje cerrado")
        
    except Exception as e:
        print(f"❌ Error cerrando ubicación: {e}")
        bot.answer_callback_query(call.id, "❌ Error al cerrar")

@bot.callback_query_handler(func=lambda call: True)
def manejar_todos_los_callbacks(call):
    """Manejar TODOS los clics en botones inline - VERSIÓN SIMPLIFICADA"""
    try:
        user_id = call.from_user.id
        user_name = call.from_user.first_name
        data = call.data
        
        print(f"🖱️ CALLBACK RECIBIDO: {user_name} -> {data}")
        
        # Procesar según el tipo de callback
        if data.startswith('entregar_'):
            manejar_callback_entregar(call)
        elif data.startswith('estatus_'):
            manejar_callback_estatus(call)
        elif data.startswith('incidencia_'):
            manejar_callback_incidencia(call)
        elif data.startswith('lista_completa_'): 
            manejar_callback_lista_completa(call)
        elif data.startswith('volver_resumen_'): 
            manejar_callback_volver_resumen(call)
        elif data.startswith('foto_'):
            manejar_callback_foto_entrega(call)
        # 🎯 CALLBACKS SIMPLIFICADOS
        elif data == 'nueva_ubicacion':
            manejar_callback_nueva_ubicacion(call)
        elif data == 'cerrar_ubicacion':
            manejar_callback_cerrar_ubicacion(call)
        elif data == 'incidencia_trafico':
            manejar_callback_incidencia_trafico(call)
        elif data == 'incidencia_vehicular':
            manejar_callback_incidencia_vehicular(call)
        elif data == 'incidencia_entrega':
            manejar_callback_incidencia_entrega(call)
        elif data == 'contactar_supervisor':
            manejar_callback_contactar_supervisor(call)
        elif data == 'cancelar':
            bot.answer_callback_query(call.id, "❌ Acción cancelada")
            # 🎯 MEJORA: No eliminar el mensaje, volver a la ruta
            try:
                user_id = call.from_user.id
                if user_id in RUTAS_ASIGNADAS:
                    ruta_id = RUTAS_ASIGNADAS[user_id]
                    # Buscar y mostrar la ruta nuevamente
                    for archivo in os.listdir('rutas_telegram'):
                        if f"Ruta_{ruta_id}_" in archivo:
                            with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                                ruta = json.load(f)
                            
                            mensaje = formatear_ruta_para_repartidor(ruta)
                            markup = types.InlineKeyboardMarkup()
                            markup.row(
                                types.InlineKeyboardButton("🗺️ Abrir en Maps", url=ruta['google_maps_url']),
                                types.InlineKeyboardButton("👥 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta_id}")
                            )
                            markup.row(
                                types.InlineKeyboardButton("📦 Registrar Entrega", callback_data=f"entregar_{ruta_id}"),
                                types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="nueva_ubicacion")
                            )
                            markup.row(
                                types.InlineKeyboardButton("📊 Progreso", callback_data=f"estatus_{ruta_id}"),
                                types.InlineKeyboardButton("🚨 Reportar Problema", callback_data=f"incidencia_{ruta_id}")
                            )
                            
                            bot.edit_message_text(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=mensaje,
                                parse_mode='Markdown',
                                reply_markup=markup
                            )
                            break
                else:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception as e:
                print(f"❌ Error en cancelar: {e}")
                bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ Comando no reconocido")
            
    except Exception as e:
        print(f"❌ Error en callback handler: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Error procesando comando")
        except:
            pass

# =============================================================================
# 🆕 SISTEMA DE VISUALIZACIÓN DE FOTOS REALES
# =============================================================================

@app.route('/api/fotos/<file_id>')
def servir_foto_por_id(file_id):
    """Servir foto real por file_id de Telegram"""
    try:
        print(f"🖼️ Solicitando foto con file_id: {file_id}")
        
        # Buscar en la base de datos
        cursor.execute('''
            SELECT file_id, datos, ruta_local, caption, user_name, timestamp 
            FROM fotos WHERE file_id = ?
        ''', (file_id,))
        
        foto = cursor.fetchone()
        
        if not foto:
            return jsonify({"error": "Foto no encontrada"}), 404
            
        file_id, datos_imagen, ruta_local, caption, user_name, timestamp = foto
        
        # Prioridad 1: Datos binarios directos de la BD
        if datos_imagen:
            print(f"✅ Sirviendo foto desde BD: {file_id} - {len(datos_imagen)} bytes")
            return Response(datos_imagen, mimetype='image/jpeg')
        
        # Prioridad 2: Archivo local en disco
        if ruta_local and os.path.exists(ruta_local):
            print(f"✅ Sirviendo foto desde archivo: {ruta_local}")
            return send_file(ruta_local, mimetype='image/jpeg')
        
        # Prioridad 3: Descargar de Telegram nuevamente
        try:
            print(f"🔄 Intentando descargar foto desde Telegram: {file_id}")
            file_info = bot.get_file(file_id)
            if file_info and file_info.file_path:
                file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
                response = requests.get(file_url, timeout=30)
                if response.status_code == 200:
                    print(f"✅ Foto descargada de Telegram: {len(response.content)} bytes")
                    return Response(response.content, mimetype='image/jpeg')
        except Exception as e:
            print(f"❌ Error descargando de Telegram: {e}")
        
        return jsonify({"error": "No se pudo obtener la foto"}), 404
        
    except Exception as e:
        print(f"❌ Error sirviendo foto: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/fotos_usuario/<int:user_id>')
def listar_fotos_usuario(user_id):
    """Listar todas las fotos de un usuario específico"""
    try:
        cursor.execute('''
            SELECT file_id, caption, tipo, ruta_local, timestamp, LENGTH(datos) as tamaño
            FROM fotos 
            WHERE user_id = ? 
            ORDER BY timestamp DESC
        ''', (user_id,))
        
        fotos = cursor.fetchall()
        
        resultado = {
            "status": "success",
            "user_id": user_id,
            "total_fotos": len(fotos),
            "fotos": []
        }
        
        for foto in fotos:
            file_id, caption, tipo, ruta_local, timestamp, tamaño = foto
            
            foto_info = {
                "file_id": file_id,
                "caption": caption,
                "tipo": tipo,
                "timestamp": timestamp,
                "tamaño_bytes": tamaño,
                "url_directa": f"/api/fotos/{file_id}",
                "tiene_datos": tamaño > 0,
                "tiene_archivo": ruta_local and os.path.exists(ruta_local)
            }
            resultado["fotos"].append(foto_info)
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/galeria_fotos')
def galeria_fotos_interactiva():
    """Galería web interactiva para ver todas las fotos - VERSIÓN CORREGIDA"""
    try:
        cursor.execute('''
            SELECT file_id, user_name, caption, tipo, ruta_local, timestamp, LENGTH(datos) as tamaño 
            FROM fotos 
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        fotos = cursor.fetchall()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>📸 Galería de Fotos - Sistema PJCDMX</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                .header { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
                .foto-container { 
                    background: white; margin: 15px; padding: 15px; border-radius: 10px; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: inline-block; width: 300px; vertical-align: top;
                }
                .foto-img { max-width: 100%; height: auto; border-radius: 5px; }
                .foto-info { margin-top: 10px; font-size: 14px; }
                .foto-caption { font-weight: bold; margin: 5px 0; }
                .foto-meta { color: #666; font-size: 12px; }
                .estado { padding: 2px 8px; border-radius: 3px; font-size: 11px; }
                .estado-datos { background: #27ae60; color: white; }
                .estado-archivo { background: #3498db; color: white; }
                .estado-sin { background: #e74c3c; color: white; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📸 Galería de Fotos - Sistema PJCDMX</h1>
                <p>Total de fotos en sistema: <strong>""" + str(len(fotos)) + """</strong></p>
            </div>
        """
        
        for foto in fotos:
            file_id, user_name, caption, tipo, ruta_local, timestamp, tamaño = foto
            
            # Determinar estados
            tiene_datos = tamaño > 0
            tiene_archivo = ruta_local and os.path.exists(ruta_local)
            
            html += """
            <div class="foto-container">
                <img src="/api/fotos/""" + file_id + """" class="foto-img" 
                     onerror="this.src='https://via.placeholder.com/300x200?text=Foto+no+disponible'">
                
                <div class="foto-info">
                    <div class="foto-caption">""" + (caption if caption else 'Sin descripción') + """</div>
                    <div class="foto-meta">
                        <strong>👤 Usuario:</strong> """ + user_name + """<br>
                        <strong>📁 Tipo:</strong> """ + tipo + """<br>
                        <strong>🕒 Fecha:</strong> """ + str(timestamp) + """<br>
                        <strong>📊 Tamaño:</strong> """ + str(tamaño) + """ bytes
                    </div>
                    <div style="margin-top: 8px;">
                        <span class="estado """ + ("estado-datos" if tiene_datos else "estado-sin") + """">
                            """ + ("✅ BD" if tiene_datos else "❌ BD") + """
                        </span>
                        <span class="estado """ + ("estado-archivo" if tiene_archivo else "estado-sin") + """">
                            """ + ("✅ Archivo" if tiene_archivo else "❌ Archivo") + """
                        </span>
                    </div>
                    <div style="margin-top: 8px;">
                        <a href="/api/fotos/""" + file_id + """" target="_blank" style="color: #3498db; text-decoration: none;">
                            🔗 Ver foto completa
                        </a>
                    </div>
                </div>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>", 500

# =============================================================================
# ENDPOINTS FLASK PARA SINCRONIZACIÓN
# =============================================================================

@app.route('/api/avances_pendientes', methods=['GET'])
def obtener_avances_pendientes():
    """🆕 Endpoint para que el programa obtenga avances de entregas PENDIENTES"""
    try:
        avances = []
        
        # 1. Buscar en avances_ruta (entregas recientes)
        if os.path.exists('avances_ruta'):
            archivos_avance = sorted(os.listdir('avances_ruta'), reverse=True)
            for archivo in archivos_avance[:50]:  # Últimos 50 avances
                if archivo.endswith('.json'):
                    try:
                        with open(f'avances_ruta/{archivo}', 'r', encoding='utf-8') as f:
                            avance = json.load(f)
                            # 🆕 AGREGAR INFORMACIÓN CRÍTICA PARA EXCEL
                            avance['_archivo'] = archivo
                            avance['_procesado'] = False
                            avances.append(avance)
                    except Exception as e:
                        print(f"❌ Error leyendo avance {archivo}: {e}")
        
        # 2. También incluir avances de la lista global
        for avance in AVANCES_PENDIENTES:
            avance['_fuente'] = 'memoria'
            avances.append(avance)
        
        print(f"📊 Enviando {len(avances)} avances pendientes al programa")
        return jsonify({
            "status": "success",
            "avances": avances,
            "total": len(avances),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error en /api/avances_pendientes: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/avances/<avance_id>/procesado', methods=['POST'])
def marcar_avance_procesado(avance_id):
    """🆕 Marcar un avance como procesado en el programa"""
    try:
        print(f"✅ Marcando avance como procesado: {avance_id}")
        
        # Buscar en archivos
        if os.path.exists('avances_ruta'):
            for archivo in os.listdir('avances_ruta'):
                if avance_id in archivo:  # Búsqueda simple
                    # Mover a carpeta de procesados
                    os.makedirs('avances_procesados', exist_ok=True)
                    os.rename(f'avances_ruta/{archivo}', f'avances_procesados/{archivo}')
                    print(f"✅ Avance movido a procesados: {archivo}")
                    return jsonify({"status": "success", "archivo": archivo})
        
        # Buscar en memoria
        global AVANCES_PENDIENTES
        AVANCES_PENDIENTES = [av for av in AVANCES_PENDIENTES if av.get('_id') != avance_id]
        
        return jsonify({"status": "success", "message": "Avance marcado como procesado"})
        
    except Exception as e:
        print(f"❌ Error marcando avance como procesado: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check_detallado():
    """Endpoint de salud completo"""
    try:
        cursor.execute("SELECT COUNT(*) FROM incidentes")
        total_incidentes = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM fotos") 
        total_fotos = cursor.fetchone()[0]
        
        total_rutas_archivo = len([f for f in os.listdir('rutas_telegram') if f.endswith('.json')]) if os.path.exists('rutas_telegram') else 0
        
        return jsonify({
            "status": "healthy",
            "service": "bot_rutas_pjcdmx",
            "timestamp": datetime.now().isoformat(),
            "estadisticas": {
                "incidentes_en_bd": total_incidentes,
                "fotos_en_bd": total_fotos,
                "rutas_en_sistema": total_rutas_archivo,
                "rutas_disponibles": len(RUTAS_DISPONIBLES),
                "repartidores_activos": len(RUTAS_ASIGNADAS),
                "avances_pendientes": len(AVANCES_PENDIENTES)
            },
            "carpetas": {
                "existe_rutas_telegram": os.path.exists('rutas_telegram'),
                "existe_fotos_central": os.path.exists('carpeta_fotos_central'),
                "existe_avances_ruta": os.path.exists('avances_ruta')
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/rutas', methods=['POST'])
def recibir_rutas_desde_programa():
    """Endpoint para que el programa generador envíe rutas reales"""
    try:
        datos_ruta = request.json
        
        if not datos_ruta:
            return jsonify({"error": "Datos vacíos"}), 400
        
        ruta_id = datos_ruta.get('ruta_id', 1)
        zona = datos_ruta.get('zona', 'GENERAL')
        
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(datos_ruta, f, indent=2, ensure_ascii=False)
        
        cargar_rutas_disponibles()
        
        print(f"✅ Ruta {ruta_id} recibida via API y guardada")
        
        return jsonify({
            "status": "success", 
            "ruta_id": ruta_id,
            "archivo": archivo_ruta,
            "rutas_disponibles": len(RUTAS_DISPONIBLES)
        })
        
    except Exception as e:
        print(f"❌ Error en API /api/rutas: {e}")
        return jsonify({"error": str(e)}), 500

# 🆕 DEBUG RUTAS - VERSIÓN CORREGIDA
@app.route('/api/debug_rutas', methods=['GET'])
def debug_rutas():
    """Endpoint para debug de rutas"""
    try:
        rutas_en_sistema = []
        
        if os.path.exists('rutas_telegram'):
            for archivo in os.listdir('rutas_telegram'):
                if archivo.endswith('.json'):
                    try:
                        with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                            ruta = json.load(f)
                        
                        rutas_en_sistema.append({
                            'archivo': archivo,
                            'ruta_id': ruta.get('ruta_id'),
                            'zona': ruta.get('zona'),
                            'estado': ruta.get('estado'),
                            'paradas': len(ruta.get('paradas', [])),
                            'timestamp_creacion': ruta.get('timestamp_creacion')
                        })
                    except Exception as e:
                        rutas_en_sistema.append({
                            'archivo': archivo,
                            'error': str(e)
                        })
        
        return jsonify({
            "status": "success",
            "rutas_en_sistema": rutas_en_sistema,
            "rutas_disponibles": len(RUTAS_DISPONIBLES),
            "rutas_cargadas": len(RUTAS_DISPONIBLES),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# 🆕 RECARGAR RUTAS MANUAL
@app.route('/api/recargar_rutas', methods=['POST'])
def recargar_rutas_manual():
    """Forzar recarga de rutas"""
    try:
        rutas_cargadas = cargar_rutas_disponibles()
        
        return jsonify({
            "status": "success",
            "rutas_cargadas": rutas_cargadas,
            "rutas_disponibles": len(RUTAS_DISPONIBLES),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# 🆕 ENDPOINT PARA VER UBICACIONES RECIENTES
@app.route('/api/ubicaciones_recientes')
def obtener_ubicaciones_recientes():
    """Obtener ubicaciones recientes de todos los usuarios"""
    try:
        cursor.execute('''
            SELECT user_name, ubicacion, timestamp, tipo
            FROM incidentes 
            WHERE tipo = 'ubicacion'
            ORDER BY timestamp DESC
            LIMIT 20
        ''')
        
        ubicaciones = cursor.fetchall()
        
        resultado = {
            "status": "success",
            "total_ubicaciones": len(ubicaciones),
            "ubicaciones": []
        }
        
        for ubicacion in ubicaciones:
            user_name, coords, timestamp, tipo = ubicacion
            lat, lng = coords.split(',') if coords else (0, 0)
            
            ubicacion_info = {
                "usuario": user_name,
                "latitud": float(lat),
                "longitud": float(lng),
                "timestamp": timestamp,
                "mapa_url": f"https://www.google.com/maps?q={lat},{lng}"
            }
            resultado["ubicaciones"].append(ubicacion_info)
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# Y LUEGO SIGUE EL WEBHOOK NORMAL
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'POST':
        print("📨 WEBHOOK RECIBIDO - Procesando mensaje...")
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            
            print(f"📝 Update recibido: {json_string[:200]}...")
            
            bot.process_new_updates([update])
            print("✅ Update procesado")
            return 'OK', 200
    return 'Hello! Bot is running!', 200

@app.route('/')
def index():
    return "🤖 Bot PJCDMX - Sistema de Rutas Automáticas 🚚"

@app.route('/fotos/<path:filename>')
def servir_foto(filename):
    """Servir fotos directamente - PARA DEBUG"""
    try:
        # Buscar en diferentes ubicaciones
        posibles_rutas = [
            f'/tmp/carpeta_fotos_central/{filename}',
            f'carpeta_fotos_central/{filename}',
            f'/tmp/{filename}',
            filename
        ]
        
        for ruta in posibles_rutas:
            if os.path.exists(ruta):
                return send_file(ruta, mimetype='image/jpeg')
        
        return "Foto no encontrada", 404
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/ver_fotos')
def ver_todas_las_fotos():
    """Endpoint para ver todas las fotos guardadas"""
    try:
        cursor.execute('''
            SELECT file_id, user_name, caption, tipo, ruta_local, timestamp, LENGTH(datos) as tamaño 
            FROM fotos 
            ORDER BY timestamp DESC
        ''')
        fotos = cursor.fetchall()
        
        resultado = "<h1>📸 Fotos en Sistema</h1>"
        
        for foto in fotos:
            file_id, user_name, caption, tipo, ruta_local, timestamp, tamaño = foto
            resultado += f"""
            <div style="border: 1px solid #ccc; margin: 10px; padding: 10px;">
                <h3>📷 {caption if caption else 'Sin descripción'}</h3>
                <p><strong>Usuario:</strong> {user_name}</p>
                <p><strong>Tipo:</strong> {tipo}</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
                <p><strong>Ruta local:</strong> {ruta_local}</p>
                <p><strong>Tamaño datos:</strong> {tamaño} bytes</p>
            """
            
            if ruta_local and os.path.exists(ruta_local):
                resultado += f'<img src="/fotos/{os.path.basename(ruta_local)}" style="max-width: 300px;"><br>'
                resultado += f'<a href="/fotos/{os.path.basename(ruta_local)}" target="_blank">🔗 Ver foto completa</a>'
            else:
                resultado += "<p>❌ Archivo no encontrado en disco</p>"
            
            resultado += "</div>"
        
        return resultado
        
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>", 500

# =============================================================================
# INICIALIZACIÓN Y EJECUCIÓN
# =============================================================================

print("\n🎯 SISTEMA AUTOMÁTICO DE RUTAS PJCDMX - 100% OPERATIVO")
print("📱 Comandos: /solicitar_ruta, /miruta, /entregar")
print("📍 Sistema de ubicación: ACTIVADO")
print("📸 Fotos reales: ACTIVADO")
print("🔄 Sistema de avances pendientes: ACTIVADO")

inicializar_sistema_completo()

if __name__ == "__main__":
    print("🤖 BOT PJCDMX INICIADO CORRECTAMENTE")
    
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        set_webhook()
    
    if not os.environ.get('RAILWAY_ENVIRONMENT'):
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("✅ Sistema listo para producción en Railway")
