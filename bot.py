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
# DECORATOR PARA MANEJO DE ERRORES GLOBAL
# =============================================================================

def manejar_errores_telegram(f):
    """Decorator para manejar errores en handlers de Telegram"""
    @wraps(f)
    def decorated_function(update, context):
        try:
            return f(update, context)
        except Exception as e:
            error_msg = f"❌ Error en {f.__name__}: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            
            # Intentar notificar al usuario
            try:
                update.message.reply_text("⚠️ Ocurrió un error. Por favor, intenta nuevamente.")
            except:
                pass
    return decorated_function

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
    ruta_id INTEGER,
    persona_entregada TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()
print("✅ Base de datos inicializada")

# =============================================================================
# VARIABLES GLOBALES DEL SISTEMA
# =============================================================================

RUTAS_DISPONIBLES = []
RUTAS_ASIGNADAS = {}
ADMIN_IDS = [7800992671]  # ⚠️ CAMBIA POR TU USER_ID

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

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

def guardar_foto_en_bd(file_id, user_id, user_name, caption, tipo, datos_imagen=None, ruta_local=None):
    """Guardar foto en base de datos con metadatos"""
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO fotos 
            (file_id, user_id, user_name, caption, tipo, datos, ruta_local, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (file_id, user_id, user_name, caption, tipo, datos_imagen, ruta_local))
        conn.commit()
        print(f"✅ Foto guardada en BD: {file_id} - Tipo: {tipo}")
        return True
    except Exception as e:
        print(f"❌ Error guardando foto en BD: {e}")
        return False

def actualizar_excel_desde_bot(datos_entrega):
    """Actualiza el Excel automáticamente cuando el bot recibe entregas"""
    try:
        print(f"🔄 ACTUALIZANDO EXCEL: {datos_entrega.get('persona_entregada')}")
        
        ruta_id = datos_entrega.get('ruta_id')
        persona_entregada = datos_entrega.get('persona_entregada')
        foto_ruta = datos_entrega.get('foto_local') or datos_entrega.get('foto_acuse', '')
        repartidor = datos_entrega.get('repartidor', '')
        timestamp = datos_entrega.get('timestamp', '')
        
        # Buscar archivo de ruta
        archivos_ruta = [f for f in os.listdir('rutas_telegram') 
                       if f.startswith(f'Ruta_{ruta_id}_')]
        
        if not archivos_ruta:
            print(f"❌ No se encontró archivo para Ruta_{ruta_id}")
            return False
            
        with open(f'rutas_telegram/{archivos_ruta[0]}', 'r', encoding='utf-8') as f:
            ruta_data = json.load(f)
        
        excel_file = ruta_data.get('excel_original')
        if not excel_file or not os.path.exists(excel_file):
            print(f"❌ Excel no encontrado: {excel_file}")
            return False
        
        # Leer y actualizar Excel
        df = pd.read_excel(excel_file)
        persona_encontrada = False
        
        for idx, fila in df.iterrows():
            nombre_celda = str(fila.get('Nombre', '')).strip().lower()
            persona_buscar = persona_entregada.strip().lower()
            
            # Búsqueda flexible
            if (persona_buscar in nombre_celda or 
                nombre_celda in persona_buscar or
                any(palabra in nombre_celda for palabra in persona_buscar.split())):
                
                df.at[idx, 'Acuse'] = f"✅ ENTREGADO - {timestamp}"
                df.at[idx, 'Repartidor'] = repartidor
                df.at[idx, 'Foto_Acuse'] = foto_ruta
                df.at[idx, 'Timestamp_Entrega'] = timestamp
                df.at[idx, 'Estado'] = 'ENTREGADO'
                
                persona_encontrada = True
                print(f"✅ Excel actualizado: {persona_entregada}")
                break
        
        if not persona_encontrada:
            print(f"⚠️ Persona no encontrada: {persona_entregada}")
            nueva_fila = {
                'Nombre': persona_entregada,
                'Acuse': f"✅ ENTREGADO - {timestamp}",
                'Repartidor': repartidor,
                'Foto_Acuse': foto_ruta,
                'Timestamp_Entrega': timestamp,
                'Estado': 'ENTREGADO'
            }
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            print(f"📝 Nueva fila agregada: {persona_entregada}")
        
        df.to_excel(excel_file, index=False)
        print(f"💾 Excel actualizado: {os.path.basename(excel_file)}")
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando Excel: {str(e)}")
        return False

def cargar_rutas_disponibles():
    """Cargar rutas disponibles para asignación automática"""
    global RUTAS_DISPONIBLES
    RUTAS_DISPONIBLES = []
    
    if os.path.exists('rutas_telegram'):
        for archivo in os.listdir('rutas_telegram'):
            if archivo.endswith('.json'):
                try:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta = json.load(f)
                        if ruta.get('estado') == 'pendiente':
                            RUTAS_DISPONIBLES.append(ruta)
                except Exception as e:
                    print(f"❌ Error cargando ruta {archivo}: {e}")
    
    print(f"🔄 Rutas disponibles cargadas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)

def formatear_ruta_para_repartidor(ruta):
    """Formatear ruta para mostrar al repartidor"""
    texto = f"*🗺️ RUTA ASIGNADA - {ruta['zona']}*\n\n"
    texto += f"*ID Ruta:* {ruta['ruta_id']}\n"
    texto += f"*Paradas:* {len(ruta['paradas'])}\n"
    texto += f"*Distancia:* {ruta['estadisticas']['distancia_km']} km\n"
    texto += f"*Tiempo estimado:* {ruta['estadisticas']['tiempo_min']} min\n\n"
    
    entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
    texto += f"*Progreso:* {entregadas}/{len(ruta['paradas'])} entregadas\n\n"
    
    texto += "*📍 PARADAS:*\n"
    for parada in ruta['paradas'][:5]:
        estado = "✅" if parada.get('estado') == 'entregado' else "⏳"
        texto += f"{estado} *{parada['orden']}. {parada['nombre']}*\n"
        texto += f"   🏢 {parada['dependencia']}\n"
        texto += f"   🏠 {parada['direccion'][:35]}...\n\n"
    
    if len(ruta['paradas']) > 5:
        texto += f"... y {len(ruta['paradas']) - 5} paradas más\n\n"
    
    texto += "*🚀 Comandos útiles:*\n"
    texto += "📍 /ubicacion - Enviar ubicación actual\n"
    texto += "📦 /entregar - Registrar entrega completada\n" 
    texto += "🚨 /incidente - Reportar problema\n"
    texto += "📸 Envía foto directo para acuse\n"
    texto += "📊 /estatus - Actualizar estado de entrega\n"
    
    return texto

def registrar_entrega_sistema(user_id, user_name, persona_entregada, foto_id=None, comentarios=""):
    """Registrar entrega en el sistema de archivos"""
    try:
        if user_id not in RUTAS_ASIGNADAS:
            return False
            
        ruta_id = RUTAS_ASIGNADAS[user_id]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                
                for parada in ruta_data['paradas']:
                    if persona_entregada.lower() in parada['nombre'].lower():
                        parada['estado'] = 'entregado'
                        parada['timestamp_entrega'] = timestamp
                        parada['foto_acuse'] = f"fotos_acuses/{foto_id}.jpg" if foto_id else None
                        parada['comentarios'] = comentarios
                        break
                
                pendientes = [p for p in ruta_data['paradas'] if p.get('estado') != 'entregado']
                if not pendientes:
                    ruta_data['estado'] = 'completada'
                    ruta_data['timestamp_completada'] = timestamp
                
                with open(f'rutas_telegram/{archivo}', 'w', encoding='utf-8') as f:
                    json.dump(ruta_data, f, indent=2, ensure_ascii=False)
                
                avance = {
                    'ruta_id': ruta_id,
                    'repartidor': user_name,
                    'repartidor_id': user_id,
                    'persona_entregada': persona_entregada,
                    'foto_acuse': f"fotos_acuses/{foto_id}.jpg" if foto_id else None,
                    'timestamp': timestamp,
                    'comentarios': comentarios
                }
                
                avance_file = f"avances_ruta/entrega_{ruta_id}_{int(time.time())}.json"
                with open(avance_file, 'w', encoding='utf-8') as f:
                    json.dump(avance, f, indent=2, ensure_ascii=False)
                
                print(f"✅ Entrega registrada: {user_name} → {persona_entregada} (Ruta {ruta_id})")
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
        'incidencias_trafico'
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
# HANDLERS DE TELEGRAM CON MANEJO DE ERRORES
# =============================================================================

@manejar_errores_telegram
@bot.message_handler(commands=['start', 'hola'])
def enviar_bienvenida(message):
    print(f"🎯 COMANDO /start RECIBIDO de: {message.from_user.first_name}")
    try:
        welcome_text = f"""
🤖 *BOT DE RUTAS AUTOMÁTICO - PJCDMX* 🚚

¡Hola {message.from_user.first_name}! Soy tu asistente de rutas automáticas.

*🚀 COMANDOS PRINCIPALES:*
/solicitar_ruta - 🗺️ Obtener ruta automáticamente
/miruta - 📋 Ver mi ruta asignada
/entregar - 📦 Registrar entrega completada

*📊 REPORTES Y SEGUIMIENTO:*
/ubicacion - 📍 Enviar ubicación actual  
/incidente - 🚨 Reportar incidente
/foto - 📸 Enviar foto del incidente
/estatus - 📈 Actualizar estado de entrega
/atencionH - 👨‍💼 Soporte humano

*¡El sistema asigna rutas automáticamente!*
        """
        bot.reply_to(message, welcome_text, parse_mode='HTML')
        print("✅ Mensaje de bienvenida ENVIADO")
    except Exception as e:
        print(f"❌ ERROR enviando mensaje: {e}")

@manejar_errores_telegram
@bot.message_handler(commands=['solicitar_ruta'])
def solicitar_ruta_automatica(message):
    """Asignar ruta automáticamente al repartidor"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"🔄 Solicitud de ruta de {user_name} (ID: {user_id})")
        
        if user_id in RUTAS_ASIGNADAS:
            bot.reply_to(message, 
                        "📭 *Ya tienes una ruta asignada.*\n\n"
                        "Usa /miruta para ver tu ruta actual.\n"
                        "Si has completado tu ruta, contacta a soporte.",
                        parse_mode='Markdown')
            return
        
        rutas_disponibles = cargar_rutas_disponibles()
        
        if rutas_disponibles == 0:
            bot.reply_to(message, 
                        "📭 *No hay rutas disponibles en este momento.*\n\n"
                        "Todas las rutas han sido asignadas.\n"
                        "Contacta a tu supervisor o intenta más tarde.",
                        parse_mode='Markdown')
            return
        
        ruta_asignada = RUTAS_DISPONIBLES.pop(0)
        ruta_id = ruta_asignada['ruta_id']
        zona = ruta_asignada['zona']
        
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        ruta_asignada['repartidor_asignado'] = f"user_{user_id}"
        ruta_asignada['estado'] = 'asignada'
        ruta_asignada['timestamp_asignacion'] = datetime.now().isoformat()
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(ruta_asignada, f, indent=2, ensure_ascii=False)
        
        RUTAS_ASIGNADAS[user_id] = ruta_id
        mensaje = formatear_ruta_para_repartidor(ruta_asignada)
        
        markup = types.InlineKeyboardMarkup()
        btn_maps = types.InlineKeyboardButton("🗺️ Abrir en Google Maps", url=ruta_asignada['google_maps_url'])
        markup.add(btn_maps)
        
        bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
        print(f"✅ Ruta {ruta_id} asignada a {user_name}")
        
    except Exception as e:
        error_msg = f"❌ Error asignando ruta: {str(e)}"
        print(error_msg)
        bot.reply_to(message, 
                    "❌ *Error al asignar ruta.*\n\n"
                    "Por favor, intenta nuevamente o contacta a soporte.",
                    parse_mode='Markdown')

@manejar_errores_telegram
@bot.message_handler(commands=['miruta'])
def ver_mi_ruta(message):
    """Ver la ruta asignada actual"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    if user_id not in RUTAS_ASIGNADAS:
        bot.reply_to(message, 
                    "📭 *No tienes una ruta asignada.*\n\n"
                    "Usa /solicitar_ruta para obtener una ruta automáticamente.",
                    parse_mode='Markdown')
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for archivo in os.listdir('rutas_telegram'):
        if f"Ruta_{ruta_id}_" in archivo:
            try:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta = json.load(f)
                
                mensaje = formatear_ruta_para_repartidor(ruta)
                markup = types.InlineKeyboardMarkup()
                btn_maps = types.InlineKeyboardButton("🗺️ Abrir en Google Maps", url=ruta['google_maps_url'])
                markup.add(btn_maps)
                
                bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
                return
                
            except Exception as e:
                print(f"❌ Error leyendo ruta {archivo}: {e}")
    
    bot.reply_to(message, 
                "❌ *No se pudo encontrar tu ruta asignada.*\n\n"
                "Por favor, usa /solicitar_ruta para obtener una nueva ruta.",
                parse_mode='Markdown')

@manejar_errores_telegram
@bot.message_handler(commands=['estado_rutas'])
def estado_rutas(message):
    """Ver estado de todas las rutas (solo admin)"""
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Solo administradores pueden usar este comando")
        return
    
    cargar_rutas_disponibles()
    
    total_rutas = 0
    rutas_pendientes = 0
    rutas_asignadas = 0
    rutas_completadas = 0
    
    if os.path.exists('rutas_telegram'):
        for archivo in os.listdir('rutas_telegram'):
            if archivo.endswith('.json'):
                try:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta = json.load(f)
                    
                    total_rutas += 1
                    estado = ruta.get('estado', 'desconocido')
                    
                    if estado == 'pendiente':
                        rutas_pendientes += 1
                    elif estado == 'asignada':
                        rutas_asignadas += 1
                    elif estado == 'completada':
                        rutas_completadas += 1
                        
                except Exception as e:
                    print(f"❌ Error leyendo {archivo}: {e}")
    
    mensaje = f"*📊 ESTADO DEL SISTEMA - RUTAS AUTOMÁTICAS*\n\n"
    mensaje += f"*• Total rutas generadas:* {total_rutas}\n"
    mensaje += f"*• ✅ Asignadas a repartidores:* {rutas_asignadas}\n"
    mensaje += f"*• ⏳ Disponibles para asignar:* {rutas_pendientes}\n"
    mensaje += f"*• 🏁 Completadas:* {rutas_completadas}\n\n"
    mensaje += f"*• 👥 Repartidores activos:* {len(RUTAS_ASIGNADAS)}\n"
    mensaje += f"*• 📁 Rutas en memoria:* {len(RUTAS_DISPONIBLES)}\n\n"
    mensaje += "*Última actualización:* " + datetime.now().strftime("%H:%M:%S")
    
    bot.reply_to(message, mensaje, parse_mode='Markdown')

@manejar_errores_telegram
@bot.message_handler(commands=['generar_rutas_ejemplo'])
def generar_rutas_ejemplo(message):
    """Generar rutas de ejemplo para pruebas (solo admin)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        bot.reply_to(message, "🔄 Generando rutas de ejemplo...")
        
        rutas_ejemplo = [
            {
                'ruta_id': 1,
                'zona': 'CENTRO',
                'repartidor_asignado': None,
                'google_maps_url': 'https://maps.google.com/maps/dir/19.4283717,-99.1430307/19.4326077,-99.1332081/19.4340000,-99.1350000/19.4355000,-99.1360000',
                'paradas': [
                    {
                        'orden': 1,
                        'nombre': 'LIC. CARLOS RODRÍGUEZ HERNÁNDEZ',
                        'direccion': 'Av. Reforma 123, Edificio A, Piso 3, Cuauhtémoc, CDMX',
                        'dependencia': 'SALA SUPERIOR',
                        'coords': '19.4326077,-99.1332081',
                        'estado': 'pendiente'
                    },
                    {
                        'orden': 2,
                        'nombre': 'DRA. MARÍA GARCÍA LÓPEZ',
                        'direccion': 'Insurgentes Sur 456, Oficina 501, Cuauhtémoc, CDMX',
                        'dependencia': 'SALA REGIONAL',
                        'coords': '19.4340000,-99.1350000', 
                        'estado': 'pendiente'
                    }
                ],
                'estadisticas': {
                    'total_paradas': 2,
                    'distancia_km': 5.2,
                    'tiempo_min': 18,
                    'origen': 'TSJCDMX - Niños Héroes 150'
                },
                'estado': 'pendiente',
                'timestamp_creacion': datetime.now().isoformat()
            }
        ]
        
        for ruta in rutas_ejemplo:
            archivo = f"rutas_telegram/Ruta_{ruta['ruta_id']}_{ruta['zona']}.json"
            with open(archivo, 'w', encoding='utf-8') as f:
                json.dump(ruta, f, indent=2, ensure_ascii=False)
        
        cargar_rutas_disponibles()
        
        bot.reply_to(message, 
                    f"✅ *Rutas de ejemplo generadas!*\n\n"
                    f"Se crearon {len(rutas_ejemplo)} rutas de prueba.\n"
                    f"Ahora los repartidores pueden usar /solicitar_ruta\n\n"
                    f"Usa /estado_rutas para ver el estado.",
                    parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error generando rutas: {str(e)}")

@manejar_errores_telegram
@bot.message_handler(commands=['incidente'])
def reportar_incidente(message):
    texto = """
🚨 *REPORTAR INCIDENTE*

Describe el incidente. Ejemplos:
- "Tráfico pesado en Periférico" 
- "No se encuentra a la persona"
- "Vehículo sobrecalentado"
- "Cliente no se encuentra"

*También puedes:*
- Enviar 📍 ubicación del problema
- Enviar 📸 foto como evidencia

Escribe tu reporte:
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"🚨 Incidente: {message.from_user.first_name}")

@manejar_errores_telegram
@bot.message_handler(commands=['ubicacion'])
def solicitar_ubicacion(message):
    texto = """
📍 *UBICACIÓN EN TIEMPO REAL*

Envía tu ubicación actual:
1. Toca el clip 📎 
2. Selecciona "Ubicación"
3. "Enviar mi ubicación actual"

*Útil para:*
- Reportar tu posición actual
- Indicar ubicación de incidente
- Registrar entrega con ubicación
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📍 Ubicación: {message.from_user.first_name}")

@manejar_errores_telegram
@bot.message_handler(content_types=['location'])
def manejar_ubicacion(message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude
    
    cursor.execute('INSERT INTO incidentes (user_id, user_name, tipo, ubicacion) VALUES (?, ?, ?, ?)',
                  (user_id, user, 'ubicacion', f"{lat},{lon}"))
    conn.commit()
    
    respuesta = (f"📍 *UBICACIÓN RECIBIDA* ¡Gracias {user}!\n\n"
                f"*Coordenadas:* `{lat:.6f}, {lon:.6f}`\n"
                f"*Guardado para:* Reportes y seguimiento de rutas")
    
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📍 Ubicación recibida: {user} - {lat},{lon}")

@manejar_errores_telegram  
@bot.message_handler(content_types=['photo'])
def manejar_foto(message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id
    caption = message.caption if message.caption else "Sin descripción"
    
    print(f"📸 Foto recibida de {user}: {caption}")
    
    if any(word in caption.lower() for word in ['entregado', 'entregada', '✅', 'recibido']):
        tipo = 'foto_acuse'
        carpeta = 'entregas'
    elif any(word in caption.lower() for word in ['retrasado', 'problema', '⏳', '🚨']):
        tipo = 'foto_estatus' 
        carpeta = 'estatus'
    elif any(word in caption.lower() for word in ['incidente', 'tráfico', 'trafico', 'accidente']):
        tipo = 'foto_incidente'
        carpeta = 'incidentes'
    else:
        tipo = 'foto_general'
        carpeta = 'general'

    print(f"🎯 CLASIFICACIÓN: '{caption}' → Carpeta: {carpeta}, Tipo: {tipo}")
    
    ruta_foto_local = descargar_foto_telegram(file_id, tipo_foto=carpeta)
    
    if ruta_foto_local:
        with open(ruta_foto_local, 'rb') as f:
            datos_imagen = f.read()
        
        guardar_foto_en_bd(
            file_id=file_id,
            user_id=user_id,
            user_name=user,
            caption=caption,
            tipo=tipo,
            datos_imagen=datos_imagen,
            ruta_local=ruta_foto_local
        )
        print(f"✅ Foto guardada en BD y carpeta: {carpeta}")
    else:
        print("⚠️ Error descargando foto, guardando solo referencia en BD")
        guardar_foto_en_bd(
            file_id=file_id,
            user_id=user_id,
            user_name=user,
            caption=caption,
            tipo=tipo,
            datos_imagen=None,
            ruta_local=None
        )

    persona_entregada = "Por determinar"
    
    if any(word in caption.lower() for word in ['entregado', 'entregada', '✅', 'recibido']):
        tipo = 'foto_acuse'
        
        palabras = caption.split()
        for i, palabra in enumerate(palabras):
            if palabra.lower() in ['a', 'para', 'entregado', 'entregada'] and i + 1 < len(palabras):
                persona_entregada = " ".join(palabras[i+1:])
                break
        
        print(f"🎯 Detectada entrega a: {persona_entregada}")
        
        if user_id in RUTAS_ASIGNADAS:
            if registrar_entrega_sistema(user_id, user, persona_entregada, ruta_foto_local, caption):
                respuesta = f"📦 *ACUSE CON FOTO REGISTRADO* ¡Gracias {user}!\n\n✅ Entrega a *{persona_entregada}* registrada automáticamente.\n📸 Foto guardada en el sistema."
            else:
                respuesta = f"📸 *FOTO DE ACUSE RECIBIDA* ¡Gracias {user}!\n\n*Persona:* {persona_entregada}\n⚠️ *Error registrando en sistema*"
        else:
            respuesta = f"📸 *FOTO DE ACUSE RECIBIDA* ¡Gracias {user}!\n\n*Persona:* {persona_entregada}\nℹ️ *No tienes ruta activa asignada*"
            
    elif any(word in caption.lower() for word in ['retrasado', 'problema', '⏳', '🚨']):
        tipo = 'foto_estatus'
        respuesta = f"📊 *ESTATUS CON FOTO ACTUALIZADO* ¡Gracias {user}!\n\n📸 Foto de evidencia guardada en el sistema."
    else:
        tipo = 'foto_incidente'
        respuesta = f"📸 *FOTO RECIBIDA* ¡Gracias {user}!\n\n📝 Descripción: {caption}\n📸 Foto guardada en el sistema."
    
    cursor.execute('INSERT INTO incidentes (user_id, user_name, tipo, descripcion, foto_id) VALUES (?, ?, ?, ?, ?)',
                  (user_id, user, tipo, caption, ruta_foto_local))
    conn.commit()
    
    if any(word in caption.lower() for word in ['entregado', 'entregada', '✅', 'recibido']):
        datos_entrega_excel = {
            'ruta_id': RUTAS_ASIGNADAS.get(user_id) if user_id in RUTAS_ASIGNADAS else 'desconocido',
            'repartidor': user,
            'persona_entregada': persona_entregada,
            'foto_local': ruta_foto_local,
            'foto_acuse': file_id,
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id
        }
        
        threading.Thread(target=actualizar_excel_desde_bot, args=(datos_entrega_excel,)).start()
        print(f"🚀 Iniciando actualización automática de Excel para: {persona_entregada}")
    
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📸 Procesamiento completado: {user} - Tipo: {tipo}")

@manejar_errores_telegram
@bot.message_handler(commands=['atencionH', 'humano', 'soporte'])
def solicitar_atencion_humana(message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    
    texto = f"""
👨‍💼 *ATENCIÓN HUMANA* 

¡Hola {user}! Contacta a Lic Pedro Javier Hernandez a :
📧 soporte.rutas@pjcdmx.gob.mx
📱 +52 55 3197 3078
🕐 L-V 8:00 - 18:00

*Tu ID:* `{user_id}`
_Proporciona este ID al contactar_

⏳ Respuesta en 15-30 min
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"🚨 AtenciónH: {user} (ID: {user_id})")

@manejar_errores_telegram
@bot.message_handler(commands=['estatus'])
def actualizar_estatus(message):
    texto = """
📊 *ACTUALIZAR ESTATUS*

Opciones disponibles:
✅ ENTREGADO - Paquete entregado
⏳ RETRASADO - Hay retraso  
🚨 PROBLEMA - Problema con entrega
🏁 TERMINADO - Ruta completada

*Puedes:*
- Escribir el estatus: "entregado", "✅", "retrasado por tráfico"
- O enviar FOTO como evidencia con el estatus en el pie de foto

*Ejemplo con foto:* Envía foto con "✅ entregado a Carlos Rodríguez" en la descripción
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📊 Estatus: {message.from_user.first_name}")

@manejar_errores_telegram
@bot.message_handler(commands=['entregar'])
def iniciar_entrega(message):
    texto = """
📦 *REGISTRAR ENTREGA COMPLETADA*

Para registrar una entrega:

1. *Envía el nombre completo* de la persona que recibió
2. *Opcional:* Envía foto del acuse

*Ejemplos:*
`Carlos Rodríguez Hernández`
`Entregado a María García López`

💡 *Consejo:* Si envías foto, asegúrate de incluir el nombre en el pie de foto.

*La entrega se registrará automáticamente en tu ruta actual.*
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📦 Entregar: {message.from_user.first_name}")

@manejar_errores_telegram
@bot.message_handler(func=lambda message: True, content_types=['text'])
def manejar_texto_general(message):
    if message.text.startswith('/'):
        return
    
    user = message.from_user.first_name
    user_id = message.from_user.id
    texto = message.text
    
    if any(word in texto.lower() for word in ['entregado', 'entregada', 'recibido']) and len(texto.split()) > 2:
        partes = texto.split()
        persona_entregada = texto
        
        for i, palabra in enumerate(partes):
            if palabra.lower() in ['a', 'para', 'entregado', 'entregada'] and i + 1 < len(partes):
                persona_entregada = " ".join(partes[i+1:])
                break
        
        if user_id in RUTAS_ASIGNADAS:
            if registrar_entrega_sistema(user_id, user, persona_entregada, None, texto):
                respuesta = f"📦 *ENTREGA REGISTRADA* ¡Gracias {user}!\nEntrega a *{persona_entregada}* registrada en el sistema."
            else:
                respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}!\nRegistrado: \"{texto}\""
        else:
            respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}!\n*Nota:* No tienes ruta activa asignada."
        
        bot.reply_to(message, respuesta, parse_mode='Markdown')
        print(f"📦 Entrega registrada: {user} - {persona_entregada}")
        return
    
    estatus_keywords = {
        '✅': 'ENTREGADO', 'entregado': 'ENTREGADO',
        '⏳': 'RETRASADO', 'retrasado': 'RETRASADO', 
        '🚨': 'PROBLEMA', 'problema': 'PROBLEMA',
        '🏁': 'TERMINADO', 'terminado': 'TERMINADO'
    }
    
    for keyword, estatus in estatus_keywords.items():
        if keyword in texto.lower():
            respuesta = f"📊 *ESTATUS ACTUALIZADO* ¡{user}! Estatus: *{estatus}*\n\n💡 *Tip:* También puedes enviar FOTO como evidencia con el estatus en el pie de foto"
            bot.reply_to(message, respuesta, parse_mode='Markdown')
            print(f"📊 Estatus actualizado: {user} - {estatus}")
            return
    
    respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}! Registrado: \"{texto}\""
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📝 Reporte: {user} - {texto}")

# =============================================================================
# ENDPOINTS FLASK MEJORADOS
# =============================================================================

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
                "repartidores_activos": len(RUTAS_ASIGNADAS)
            },
            "carpetas": {
                "existe_rutas_telegram": os.path.exists('rutas_telegram'),
                "existe_fotos_central": os.path.exists('carpeta_fotos_central'),
                "existe_avances_ruta": os.path.exists('avances_ruta')
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/status')
def status_detallado():
    """Endpoint de estado detallado para monitoreo"""
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        status_info = {
            "status": "healthy",
            "service": "bot_rutas_pjcdmx",
            "timestamp": datetime.now().isoformat(),
            "system": {
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "cpu_percent": round(process.cpu_percent(), 2),
                "uptime_seconds": round(time.time() - process.create_time(), 2)
            },
            "bot": {
                "rutas_disponibles": len(RUTAS_DISPONIBLES),
                "repartidores_activos": len(RUTAS_ASIGNADAS),
                "webhook_configured": True
            },
            "database": {
                "incidentes": cursor.execute("SELECT COUNT(*) FROM incidentes").fetchone()[0],
                "fotos": cursor.execute("SELECT COUNT(*) FROM fotos").fetchone()[0]
            }
        }
        
        return jsonify(status_info)
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/debug')
def debug_info():
    """Información de debug para troubleshooting"""
    import os
    return jsonify({
        'environment': dict(os.environ),
        'current_directory': os.getcwd(),
        'files': os.listdir('.'),
        'python_version': os.sys.version,
        'bot_token_set': bool(os.environ.get('BOT_TOKEN'))
    })

@app.route('/api/metrics')
def metrics_prometheus():
    """Endpoint de métricas compatible con Prometheus"""
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        metrics = [
            f"# HELP bot_memory_usage Memory usage in MB",
            f"# TYPE bot_memory_usage gauge",
            f"bot_memory_usage {memory_mb}",
            f"",
            f"# HELP bot_rutas_disponibles Number of available routes", 
            f"# TYPE bot_rutas_disponibles gauge",
            f"bot_rutas_disponibles {len(RUTAS_DISPONIBLES)}",
            f"",
            f"# HELP bot_repartidores_activos Number of active delivery people",
            f"# TYPE bot_repartidores_activos gauge", 
            f"bot_repartidores_activos {len(RUTAS_ASIGNADAS)}",
            f"",
            f"# HELP bot_incidentes_total Total number of incidents",
            f"# TYPE bot_incidentes_total counter",
            f"bot_incidentes_total {cursor.execute('SELECT COUNT(*) FROM incidentes').fetchone()[0]}",
            f"",
            f"# HELP bot_fotos_total Total number of photos stored",
            f"# TYPE bot_fotos_total counter",
            f"bot_fotos_total {cursor.execute('SELECT COUNT(*) FROM fotos').fetchone()[0]}"
        ]
        
        return Response('\n'.join(metrics), mimetype='text/plain')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

# =============================================================================
# ENDPOINTS ADICIONALES EXISTENTES (MANTENIDOS)
# =============================================================================

@app.route('/api/verificar_fotos')
def verificar_fotos():
    """Endpoint para verificar fotos en el filesystem actual"""
    import os
    import json
    
    try:
        resultado = {
            'status': 'success',
            'directorio_actual': os.getcwd(),
            'existe_carpeta_fotos': os.path.exists('fotos_acuses'),
            'archivos_en_fotos_acuses': [],
            'todos_los_archivos': [],
            'timestamp': datetime.now().isoformat()
        }
        
        if os.path.exists('fotos_acuses'):
            archivos = os.listdir('fotos_acuses')
            resultado['archivos_en_fotos_acuses'] = archivos
            
            for archivo in archivos:
                ruta = f"fotos_acuses/{archivo}"
                if os.path.exists(ruta):
                    stat = os.stat(ruta)
                    resultado['todos_los_archivos'].append({
                        'nombre': archivo,
                        'tamaño_bytes': stat.st_size,
                        'fecha_creacion': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        'existe': True
                    })
                else:
                    resultado['todos_los_archivos'].append({
                        'nombre': archivo, 
                        'existe': False
                    })
        else:
            resultado['error'] = 'Carpeta fotos_acuses no existe'
        
        print(f"🔍 Verificación fotos: {len(resultado['archivos_en_fotos_acuses'])} archivos encontrados")
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/api/verificar_bd')
def verificar_bd():
    """Verificar que las tablas existen en la base de datos"""
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = cursor.fetchall()
        
        conteos = {}
        for tabla in [t[0] for t in tablas]:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
            conteos[tabla] = cursor.fetchone()[0]
            
        return jsonify({
            "status": "success",
            "tablas": [t[0] for t in tablas],
            "conteos": conteos,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/fotos_en_bd')
def fotos_en_bd():
    """Ver todas las fotos guardadas en la base de datos"""
    try:
        cursor.execute('''
            SELECT file_id, user_name, caption, tipo, timestamp, LENGTH(datos) as tamaño_bytes 
            FROM fotos 
            ORDER BY timestamp DESC
            LIMIT 10
        ''')
        fotos = cursor.fetchall()
        
        resultado = []
        for foto in fotos:
            resultado.append({
                'file_id': foto[0],
                'user_name': foto[1],
                'caption': foto[2],
                'tipo': foto[3],
                'timestamp': foto[4],
                'tamaño_bytes': foto[5]
            })
            
        return jsonify({
            "status": "success",
            "total_fotos": len(resultado),
            "fotos": resultado
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/foto/<file_id>')
def servir_foto_desde_bd(file_id):
    """Servir una foto específica desde la base de datos"""
    try:
        cursor.execute('SELECT datos FROM fotos WHERE file_id = ?', (file_id,))
        resultado = cursor.fetchone()
        
        if resultado:
            datos_imagen = resultado[0]
            print(f"📸 Sirviendo foto desde BD: {file_id} - {len(datos_imagen)} bytes")
            return Response(datos_imagen, mimetype='image/jpeg')
        else:
            return jsonify({"error": f"Foto no encontrada en BD: {file_id}"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/forzar_actualizacion_excel', methods=['POST'])
def forzar_actualizacion_excel():
    """Endpoint para forzar la actualización de todos los Excel con las fotos"""
    try:
        actualizaciones = 0
        
        for archivo in os.listdir('avances_ruta'):
            if archivo.endswith('.json'):
                with open(f'avances_ruta/{archivo}', 'r') as f:
                    datos_entrega = json.load(f)
                
                if actualizar_excel_desde_bot(datos_entrega):
                    actualizaciones += 1
        
        return jsonify({
            "status": "success",
            "actualizaciones": actualizaciones,
            "message": f"Se actualizaron {actualizaciones} archivos Excel"
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# =============================================================================
# ENDPOINTS PARA VISUALIZACIÓN DE FOTOS - CORREGIDOS
# =============================================================================

@app.route('/galeria_carpetas')
def galeria_carpetas():
    """Página para navegar por las carpetas de fotos"""
    try:
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>📸 Galería Organizada - PJCDMX</title>
            <meta charset="utf-8">
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    margin: 20px; 
                    background: #f5f5f5; 
                    line-height: 1.6;
                }
                .header {
                    background: #2c3e50;
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }
                .carpeta { 
                    background: white; 
                    padding: 20px; 
                    margin: 15px 0; 
                    border-radius: 10px; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
                }
                .carpeta h2 { 
                    margin-top: 0; 
                    color: #333; 
                    border-bottom: 2px solid;
                    padding-bottom: 10px;
                }
                .entregas { border-left: 5px solid #28a745; }
                .entregas h2 { color: #28a745; }
                .incidentes { border-left: 5px solid #dc3545; }
                .incidentes h2 { color: #dc3545; }
                .estatus { border-left: 5px solid #ffc107; }
                .estatus h2 { color: #ffc107; }
                .general { border-left: 5px solid #17a2b8; }
                .general h2 { color: #17a2b8; }
                .fotos { 
                    display: flex; 
                    flex-wrap: wrap; 
                    gap: 15px; 
                    margin-top: 15px; 
                }
                .foto-item {
                    text-align: center;
                }
                .fotos img { 
                    max-width: 200px; 
                    max-height: 150px;
                    border-radius: 8px; 
                    border: 2px solid #ddd;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    transition: transform 0.3s ease;
                }
                .fotos img:hover {
                    transform: scale(1.05);
                    border-color: #007bff;
                }
                .foto-nombre {
                    font-size: 12px;
                    color: #666;
                    margin-top: 5px;
                    word-break: break-all;
                    max-width: 200px;
                }
                .vacio { 
                    color: #666; 
                    font-style: italic;
                    padding: 20px;
                    text-align: center;
                }
                .contador {
                    background: #e9ecef;
                    padding: 5px 10px;
                    border-radius: 15px;
                    font-size: 14px;
                    margin-left: 10px;
                }
                .carpeta-info {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📸 Galería Organizada de Fotos</h1>
                <p>Sistema de Rutas PJCDMX - Fotos clasificadas automáticamente</p>
                <small>Actualizado: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</small>
            </div>
        """
        
        carpetas = {
            'entregas': '📦 Entregas y Acuses',
            'incidentes': '🚨 Incidentes y Problemas', 
            'estatus': '📊 Estatus y Actualizaciones',
            'general': '📸 Fotos Generales'
        }
        
        for carpeta, nombre in carpetas.items():
            ruta_carpeta = f'carpeta_fotos_central/{carpeta}'
            html += f'<div class="carpeta {carpeta}">'
            html += f'<div class="carpeta-info">'
            html += f'<h2>{nombre}</h2>'
            
            if os.path.exists(ruta_carpeta):
                fotos = [f for f in os.listdir(ruta_carpeta) 
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                html += f'<span class="contador">{len(fotos)} fotos</span>'
            html += '</div>'
            
            if os.path.exists(ruta_carpeta):
                fotos = [f for f in os.listdir(ruta_carpeta) 
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                
                if fotos:
                    html += '<div class="fotos">'
                    for foto in sorted(fotos)[:12]:  # Mostrar máximo 12 fotos
                        html += f'''
                        <div class="foto-item">
                            <a href="/carpeta_fotos_central/{carpeta}/{foto}" target="_blank">
                                <img src="/carpeta_fotos_central/{carpeta}/{foto}" 
                                     alt="{foto}" 
                                     title="{foto}">
                            </a>
                            <div class="foto-nombre">{foto[:20]}...</div>
                        </div>
                        '''
                    if len(fotos) > 12:
                        html += f'<div class="vacio">... y {len(fotos) - 12} fotos más</div>'
                    html += '</div>'
                else:
                    html += '<div class="vacio">No hay fotos en esta categoría</div>'
            else:
                html += '<div class="vacio">Carpeta no existe</div>'
            
            html += '</div>'
        
        html += """
            <div style="margin-top: 30px; padding: 20px; background: white; border-radius: 10px;">
                <h3>📋 Resumen del Sistema</h3>
                <p><strong>Total de rutas generadas:</strong> """ + str(len([f for f in os.listdir('rutas_telegram') if f.endswith('.json')])) + """</p>
                <p><strong>Total de fotos en sistema:</strong> """ + str(sum(len([f for f in os.listdir(f'carpeta_fotos_central/{carpeta}') 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]) 
                    for carpeta in ['entregas', 'incidentes', 'estatus', 'general'] 
                    if os.path.exists(f'carpeta_fotos_central/{carpeta}'))) + """</p>
            </div>
        </body>
        </html>
        """
        return html
        
    except Exception as e:
        return f"Error generando galería: {str(e)}", 500

@app.route('/carpeta_fotos_central/<path:filename>')
def servir_foto_carpeta(filename):
    """Servir fotos desde la carpeta central"""
    try:
        # Verificar que el archivo existe y es seguro
        safe_path = os.path.join('carpeta_fotos_central', filename)
        if not os.path.exists(safe_path):
            return "Foto no encontrada", 404
        
        # Verificar que es una imagen
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return "Tipo de archivo no permitido", 400
            
        return send_file(safe_path)
    except Exception as e:
        return f"Error cargando foto: {str(e)}", 500

@app.route('/api/estado_fotos')
def estado_fotos():
    """API para ver el estado de las fotos"""
    try:
        resultado = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'carpetas': {}
        }
        
        carpetas = ['entregas', 'incidentes', 'estatus', 'general']
        
        for carpeta in carpetas:
            ruta = f'carpeta_fotos_central/{carpeta}'
            if os.path.exists(ruta):
                fotos = [f for f in os.listdir(ruta) 
                        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                resultado['carpetas'][carpeta] = {
                    'existe': True,
                    'total_fotos': len(fotos),
                    'fotos': fotos[:10]  # Primeras 10 fotos
                }
            else:
                resultado['carpetas'][carpeta] = {
                    'existe': False,
                    'total_fotos': 0,
                    'fotos': []
                }
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# =============================================================================
# INICIALIZACIÓN Y EJECUCIÓN
# =============================================================================

print("\n🎯 SISTEMA AUTOMÁTICO DE RUTAS PJCDMX - 100% OPERATIVO")
print("📱 Comandos: /solicitar_ruta, /miruta, /entregar, /estado_rutas")

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
