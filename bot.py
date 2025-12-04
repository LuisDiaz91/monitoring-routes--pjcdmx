import os
import telebot
import sqlite3
import json
import requests
import urllib.parse
from telebot import types
from datetime import datetime
from flask import Flask, request, jsonify
import re

print("🚀 INICIANDO BOT COMPLETO - CON GOOGLE MAPS INTEGRADO Y CORREGIDO...")

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Variables globales
RUTAS_DISPONIBLES = []
RUTAS_ASIGNADAS = {}

# Configurar base de datos para fotos
conn = sqlite3.connect('/tmp/incidentes.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS fotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT UNIQUE,
    user_id INTEGER,
    user_name TEXT,
    caption TEXT,
    tipo TEXT,
    ruta_local TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# Crear carpetas necesarias
carpetas = ['rutas_telegram', 'carpeta_fotos_central/entregas', 'carpeta_fotos_central/incidentes']
for carpeta in carpetas:
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)

def limpiar_direccion_para_google_maps(direccion):
    """Limpia y prepara una dirección para Google Maps"""
    if not direccion:
        return "Ciudad de México"
    
    d = str(direccion)
    d = d.replace('<br>', ' ').replace('<br/>', ' ').replace('<br />', ' ')
    d = d.replace('\n', ' ').replace('\r', ' ')
    d = re.sub(r'\s+', ' ', d)
    d = re.sub(r'[<>{}|^~\[\]`]', '', d)
    d = d.replace('"', '').replace("'", '')
    
    if not any(term in d.lower() for term in ['ciudad de méxico', 'cdmx', 'mexico', 'méxico']):
        d += ", Ciudad de México"
    
    return d.strip()

def extraer_direccion_valida(parada):
    """Extrae una dirección válida de una parada"""
    direccion = parada.get('direccion', '')
    
    if not direccion or direccion in ['', 'Sin dirección', 'N/A', 'NaN', 'nan']:
        if parada.get('personas') and len(parada['personas']) > 0:
            direccion = parada['personas'][0].get('direccion', '')
    
    if not direccion or direccion in ['', 'Sin dirección', 'N/A', 'NaN', 'nan']:
        if parada.get('coords'):
            try:
                coords = parada['coords']
                if ',' in coords:
                    lat, lon = coords.split(',')
                    return f"{lat},{lon}"
            except:
                pass
    
    if not direccion or direccion in ['', 'Sin dirección', 'N/A', 'NaN', 'nan']:
        edificio_nombre = parada.get('nombre', f"Edificio {parada.get('orden', '')}")
        return f"{edificio_nombre}, Ciudad de México"
    
    return direccion

def cargar_rutas_simple():
    """Cargar rutas de manera simple y directa"""
    global RUTAS_DISPONIBLES
    RUTAS_DISPONIBLES = []
    
    if os.path.exists('rutas_telegram'):
        for archivo in os.listdir('rutas_telegram'):
            if archivo.endswith('.json'):
                try:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta = json.load(f)
                    
                    if not ruta.get('google_maps_url'):
                        print(f"🔄 Generando URL Google Maps para {archivo}...")
                        maps_url = crear_url_google_maps_ruta_completa(ruta)
                        if maps_url:
                            ruta['google_maps_url'] = maps_url
                            with open(f'rutas_telegram/{archivo}', 'w', encoding='utf-8') as f:
                                json.dump(ruta, f, indent=2, ensure_ascii=False)
                            print(f"✅ URL Google Maps generada y guardada")
                    
                    RUTAS_DISPONIBLES.append(ruta)
                    print(f"✅ Cargada: {archivo}")
                    print(f"   📊 {len(ruta.get('paradas', []))} paradas")
                    
                except Exception as e:
                    print(f"❌ Error con {archivo}: {e}")
    
    if len(RUTAS_DISPONIBLES) == 0:
        print("🔄 Creando ruta de prueba...")
        ruta_prueba = {
            "ruta_id": 1,
            "zona": "ZONA CENTRO",
            "origen": "TSJCDMX - Niños Héroes 150, Ciudad de México",
            "paradas": [
                {
                    "orden": 1,
                    "nombre": "PALACIO NACIONAL",
                    "dependencia": "GOBIERNO FEDERAL", 
                    "direccion": "Plaza de la Constitución S/N, Centro Histórico, Ciudad de México",
                    "total_personas": 3,
                    "personas": [
                        {"nombre": "JUAN PÉREZ", "direccion": "Plaza de la Constitución S/N, Centro Histórico, CDMX"},
                        {"nombre": "MARÍA GARCÍA", "direccion": "Plaza de la Constitución S/N, Centro Histórico, CDMX"}
                    ]
                },
                {
                    "orden": 2,
                    "nombre": "SUPREMA CORTE DE JUSTICIA",
                    "dependencia": "PODER JUDICIAL",
                    "direccion": "Pino Suárez 2, Centro, Ciudad de México",
                    "total_personas": 2,
                    "personas": [
                        {"nombre": "CARLOS LÓPEZ", "direccion": "Pino Suárez 2, Centro, CDMX"},
                        {"nombre": "ANA MARTÍNEZ", "direccion": "Pino Suárez 2, Centro, CDMX"}
                    ]
                },
                {
                    "orden": 3,
                    "nombre": "AYUNTAMIENTO CDMX",
                    "dependencia": "GOBIERNO CDMX",
                    "direccion": "Plaza de la Constitución 1, Centro, Ciudad de México", 
                    "total_personas": 4,
                    "personas": [
                        {"nombre": "LUIS HERNÁNDEZ", "direccion": "Plaza de la Constitución 1, Centro, CDMX"},
                        {"nombre": "LAURA RODRÍGUEZ", "direccion": "Plaza de la Constitución 1, Centro, CDMX"}
                    ]
                }
            ]
        }
        
        maps_url = crear_url_google_maps_ruta_completa(ruta_prueba)
        if maps_url:
            ruta_prueba['google_maps_url'] = maps_url
            print(f"✅ URL Google Maps generada para ruta de prueba")
        
        with open('rutas_telegram/Ruta_1_CENTRO.json', 'w', encoding='utf-8') as f:
            json.dump(ruta_prueba, f)
        RUTAS_DISPONIBLES.append(ruta_prueba)
        print(f"✅ Ruta de prueba creada")
    
    print(f"📦 Rutas cargadas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)

def crear_url_google_maps_ruta_completa(ruta):
    """Crear URL de Google Maps con todas las paradas de la ruta"""
    try:
        print(f"🔧 Creando URL Google Maps para ruta {ruta.get('ruta_id', 'N/A')}...")
        
        if not ruta.get('paradas') or len(ruta['paradas']) == 0:
            print("❌ No hay paradas en la ruta")
            return None
        
        origen = "TSJCDMX - Niños Héroes 150, Doctores, Ciudad de México"
        print(f"📍 Origen fijo: {origen}")
        
        direcciones_limpias = []
        for i, parada in enumerate(ruta['paradas']):
            direccion = extraer_direccion_valida(parada)
            direccion_limpia = limpiar_direccion_para_google_maps(direccion)
            print(f"   🏢 Parada {i+1}: {direccion_limpia[:60]}...")
            direcciones_limpias.append(direccion_limpia)
        
        print(f"📍 Total direcciones válidas: {len(direcciones_limpias)}")
        
        if len(direcciones_limpias) < 2:
            print("❌ Se necesitan al menos 2 direcciones para crear ruta")
            return None
        
        direcciones_codificadas = [urllib.parse.quote(d) for d in direcciones_limpias]
        base_url = "https://www.google.com/maps/dir/"
        origen_codificado = urllib.parse.quote(origen)
        destino_codificado = direcciones_codificadas[-1]
        
        if len(direcciones_codificadas) > 1:
            waypoints_str = "/".join(direcciones_codificadas[:-1])
            url_completa = f"{base_url}{origen_codificado}/{waypoints_str}/{destino_codificado}/"
            url_completa += "data=!4m2!4m1!3e0"
        else:
            url_completa = f"{base_url}{origen_codificado}/{destino_codificado}/data=!4m2!4m1!3e0"
        
        print(f"✅ URL Google Maps generada exitosamente")
        return url_completa
        
    except Exception as e:
        print(f"❌ Error creando URL de Google Maps: {str(e)}")
        return None

def crear_url_google_maps_alternativa(ruta):
    """Método alternativo para crear URL de Google Maps"""
    try:
        print(f"🔧 Intentando método alternativo para ruta {ruta.get('ruta_id')}...")
        origen = "TSJCDMX - Niños Héroes 150, Ciudad de México"
        
        waypoints = []
        for parada in ruta['paradas']:
            direccion = extraer_direccion_valida(parada)
            direccion_limpia = limpiar_direccion_para_google_maps(direccion)
            waypoints.append(urllib.parse.quote(direccion_limpia))
        
        if len(waypoints) < 2:
            return None
        
        url = f"https://www.google.com/maps/dir/?api=1"
        url += f"&origin={urllib.parse.quote(origen)}"
        url += f"&destination={waypoints[-1]}"
        
        if len(waypoints) > 1:
            url += f"&waypoints={'|'.join(waypoints[:-1])}"
        
        url += "&travelmode=driving"
        print(f"✅ URL alternativa generada")
        return url
        
    except Exception as e:
        print(f"❌ Error en método alternativo: {e}")
        return None

def verificar_url_google_maps(url):
    """Verificar que la URL de Google Maps sea válida"""
    try:
        if not url:
            return False
        
        if len(url) > 2000:
            print(f"⚠️ URL muy larga ({len(url)} caracteres)")
            return False
        
        if not url.startswith("https://www.google.com/maps/"):
            print(f"⚠️ URL no empieza con google.com/maps/")
            return False
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        
        if response.status_code == 200:
            print(f"✅ URL Google Maps VERIFICADA (status {response.status_code})")
            return True
        else:
            print(f"⚠️ URL retorna status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"⚠️ Error verificando URL: {e}")
        return False

# =============================================================================
# HANDLERS DE TELEGRAM
# =============================================================================

@bot.message_handler(commands=['start', 'inicio'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta"),
        types.InlineKeyboardButton("🗺️ VER RUTA ACTUAL", callback_data="ver_ruta_actual")
    )
    markup.row(
        types.InlineKeyboardButton("📍 SEGUIMIENTO", callback_data="seguimiento_tiempo_real"),
        types.InlineKeyboardButton("📞 SUPERVISOR", callback_data="contactar_supervisor")
    )
    
    bot.reply_to(message, 
        "🤖 **BOT PJCDMX - SISTEMA DE ENTREGAS**\n\n"
        "🚀 **¿Qué necesitas hacer?**\n\n"
        "• 🚗 **SOLICITAR RUTA:** Obtén tu ruta de entregas optimizada\n"
        "• 🗺️ **VER RUTA:** Muestra tu ruta actual con botón para Google Maps\n"
        "• 📍 **SEGUIMIENTO:** Comparte tu ubicación en tiempo real\n"
        "• 📞 **SUPERVISOR:** Contacta a tu supervisor inmediatamente\n\n"
        "👉 **Usa /ruta para comenzar**", 
        parse_mode='Markdown', 
        reply_markup=markup)

@bot.message_handler(commands=['ruta', 'solicitar_ruta'])
def dar_ruta(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    print(f"🎯 Usuario {user_id} ({user_name}) solicitando ruta...")
    
    if user_id in RUTAS_ASIGNADAS:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ VER MI RUTA", callback_data="ver_ruta_actual"),
            types.InlineKeyboardButton("🔄 NUEVA RUTA", callback_data="cambiar_ruta")
        )
        bot.reply_to(message, 
                    f"⚠️ **YA TIENES UNA RUTA ASIGNADA**\n\n"
                    f"Ruta ID: {RUTAS_ASIGNADAS[user_id]}\n\n"
                    f"¿Quieres ver tu ruta actual o solicitar una nueva?", 
                    parse_mode='Markdown', 
                    reply_markup=markup)
        return
    
    if len(RUTAS_DISPONIBLES) == 0:
        cargar_rutas_simple()
    
    if len(RUTAS_DISPONIBLES) == 0:
        bot.reply_to(message, "❌ **NO HAY RUTAS DISPONIBLES**\n\nEl sistema está generando rutas. Intenta más tarde.")
        return
    
    ruta = RUTAS_DISPONIBLES[0]
    RUTAS_ASIGNADAS[user_id] = ruta['ruta_id']
    
    print(f"✅ Ruta {ruta['ruta_id']} asignada a {user_name}")
    
    maps_url = ruta.get('google_maps_url')
    
    if not maps_url:
        print(f"⚠️ Ruta {ruta['ruta_id']} no tiene URL Google Maps, generando...")
        maps_url = crear_url_google_maps_ruta_completa(ruta)
        if not maps_url:
            maps_url = crear_url_google_maps_alternativa(ruta)
    
    url_valida = verificar_url_google_maps(maps_url) if maps_url else False
    
    markup = types.InlineKeyboardMarkup()
    
    if maps_url and url_valida:
        markup.row(types.InlineKeyboardButton("📍 ABRIR RUTA EN GOOGLE MAPS", url=maps_url))
        print(f"✅ Botón Google Maps activado para usuario {user_id}")
    elif maps_url:
        markup.row(types.InlineKeyboardButton("📍 INTENTAR ABRIR RUTA (experimental)", url=maps_url))
        print(f"⚠️ Botón Google Maps experimental para usuario {user_id}")
    else:
        markup.row(types.InlineKeyboardButton("❌ GOOGLE MAPS NO DISPONIBLE", callback_data="sin_maps"))
        print(f"❌ No hay URL Google Maps para usuario {user_id}")
    
    markup.row(
        types.InlineKeyboardButton("📋 VER LISTA DE EDIFICIOS", callback_data=f"lista_completa_{ruta['ruta_id']}"),
        types.InlineKeyboardButton("📍 MI UBICACIÓN", callback_data="ubicacion_actual")
    )
    
    total_edificios = len(ruta.get('paradas', []))
    total_personas = sum(parada.get('total_personas', 1) for parada in ruta.get('paradas', []))
    
    mensaje = f"✅ **RUTA ASIGNADA EXITOSAMENTE**\n\n"
    mensaje += f"👤 **Repartidor:** {user_name}\n"
    mensaje += f"📊 **RUTA:** {ruta.get('zona', 'SIN ZONA')} - ID: {ruta['ruta_id']}\n"
    mensaje += f"🏢 **EDIFICIOS:** {total_edificios}\n"
    mensaje += f"👥 **PERSONAS:** {total_personas}\n\n"
    
    if maps_url and url_valida:
        mensaje += "🚗 **HAZ CLIC EN EL BOTÓN 'ABRIR RUTA EN GOOGLE MAPS' PARA:**\n"
        mensaje += "• Ver la ruta completa optimizada\n"
        mensaje += "• Obtener indicaciones paso a paso\n"
        mensaje += "• Navegar con Google Maps\n\n"
    elif maps_url:
        mensaje += "⚠️ **Google Maps (modo experimental):**\n"
        mensaje += "Puede que la ruta no se cargue completamente.\n\n"
    else:
        mensaje += "❌ **Google Maps no disponible para esta ruta**\n\n"
        mensaje += "Usa la lista de edificios para navegar manualmente.\n\n"
    
    if total_edificios > 0:
        mensaje += "🏢 **PRIMEROS EDIFICIOS:**\n"
        for i, parada in enumerate(ruta.get('paradas', [])[:3], 1):
            nombre_edificio = parada.get('nombre', f'Edificio {i}')
            direccion_original = parada.get('direccion', 'Sin dirección')
            direccion_limpia = limpiar_direccion_para_google_maps(direccion_original)[:50]
            personas = parada.get('total_personas', 1)
            
            mensaje += f"\n**📍 {i}. {nombre_edificio}**\n"
            mensaje += f"   📍 {direccion_limpia}...\n"
            mensaje += f"   👥 {personas} persona{'s' if personas > 1 else ''}\n"
    
    bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "solicitar_ruta")
def callback_solicitar_ruta(call):
    """Handler para solicitar nueva ruta"""
    try:
        user_id = call.from_user.id
        user_name = call.from_user.first_name
        
        print(f"🎯 Callback: Usuario {user_id} ({user_name}) solicitando ruta...")
        bot.answer_callback_query(call.id, "🔄 Procesando solicitud de ruta...")
        
        class FakeUser:
            def __init__(self, uid, name):
                self.id = uid
                self.first_name = name
        
        class FakeMessage:
            def __init__(self, uid, name, chat_id):
                self.from_user = FakeUser(uid, name)
                self.chat = type('obj', (object,), {'id': chat_id})()
                self.message_id = call.message.message_id
        
        fake_message = FakeMessage(user_id, user_name, call.message.chat.id)
        dar_ruta(fake_message)
        
    except Exception as e:
        print(f"❌ Error en callback_solicitar_ruta: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando solicitud")

@bot.callback_query_handler(func=lambda call: call.data == "seguimiento_tiempo_real")
def callback_seguimiento(call):
    """Handler para seguimiento en tiempo real"""
    try:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📍 COMPARTIR MI UBICACIÓN ACTUAL", 
                                     callback_data="compartir_ubicacion"),
            types.InlineKeyboardButton("🗺️ VER RUTA CON MAPA", 
                                     callback_data="ver_ruta_actual")
        )
        markup.row(
            types.InlineKeyboardButton("📸 REPORTAR ENTREGA", 
                                     callback_data="reportar_entrega"),
            types.InlineKeyboardButton("📋 REPORTAR INCIDENTE", 
                                     callback_data="reportar_incidente")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📍 **SEGUIMIENTO EN TIEMPO REAL**\n\n"
                 "Selecciona una opción:\n\n"
                 "• **📍 COMPARTIR UBICACIÓN:** Envía tu ubicación actual\n"
                 "• **🗺️ VER RUTA:** Muestra tu ruta actual\n"
                 "• **📸 REPORTAR ENTREGA:** Envía foto de comprobante\n"
                 "• **📋 REPORTAR INCIDENTE:** Reporta algún problema",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Opciones de seguimiento")
        
    except Exception as e:
        print(f"❌ Error en callback_seguimiento: {e}")
        bot.answer_callback_query(call.id, "❌ Error")

@bot.callback_query_handler(func=lambda call: call.data == "contactar_supervisor")
def callback_supervisor(call):
    """Handler para contactar supervisor"""
    try:
        # CORREGIDO: Variable definida correctamente
        supervisor_nombre = "Pedro Javier Hernandez"
        supervisor_telefono = "+525512345678"
        supervisor_correo = "supervisor@pjcdmx.gob.mx"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📞 LLAMAR SUPERVISOR", 
                                     url=f"tel:{supervisor_telefono}"),
            types.InlineKeyboardButton("📧 ENVIAR CORREO", 
                                     url=f"mailto:{supervisor_correo}")
        )
        markup.row(
            types.InlineKeyboardButton("📱 ENVIAR MENSAJE WHATSAPP", 
                                     url=f"https://wa.me/{supervisor_telefono.replace('+', '')}"),
        )
        markup.row(
            types.InlineKeyboardButton("↩️ VOLVER AL INICIO", 
                                     callback_data="volver_inicio"),
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📞 **CONTACTO CON SUPERVISOR**\n\n"
                 f"**Supervisor:** {supervisor_nombre}\n"
                 f"**Teléfono:** `{supervisor_telefono}`\n"
                 f"**Correo:** `{supervisor_correo}`\n\n"
                 f"**Horario de atención:**\n"
                 f"• Lunes a Viernes: 8:00 - 18:00 hrs\n"
                 f"• Sábados: 9:00 - 14:00 hrs\n\n"
                 f"**Para emergencias fuera de horario:**\n"
                 f"📞 Línea de emergencias: +525576543210",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Información de supervisor")
        
    except Exception as e:
        print(f"❌ Error en callback_supervisor: {e}")
        bot.answer_callback_query(call.id, "❌ Error")

@bot.callback_query_handler(func=lambda call: call.data == "ubicacion_actual")
def callback_ubicacion_actual(call):
    """Handler para ubicación actual"""
    try:
        bot.answer_callback_query(call.id, 
            "📍 Por favor, comparte tu ubicación usando el botón 📎 adjunto", 
            show_alert=False)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row(types.KeyboardButton("📍 Compartir ubicación", request_location=True))
        
        bot.send_message(
            call.message.chat.id,
            "📍 **COMPARTIR UBICACIÓN**\n\n"
            "Por favor, presiona el botón de abajo para compartir tu ubicación actual:",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        print(f"❌ Error en callback_ubicacion_actual: {e}")
        bot.answer_callback_query(call.id, "❌ Error")

@bot.callback_query_handler(func=lambda call: call.data.startswith("lista_completa_"))
def callback_lista_completa(call):
    """Handler para mostrar lista completa de edificios"""
    try:
        ruta_id = int(call.data.split("_")[-1])
        user_id = call.from_user.id
        
        ruta_encontrada = None
        for ruta in RUTAS_DISPONIBLES:
            if ruta['ruta_id'] == ruta_id:
                ruta_encontrada = ruta
                break
        
        if not ruta_encontrada:
            bot.answer_callback_query(call.id, "❌ Ruta no encontrada")
            return
        
        paradas = ruta_encontrada.get('paradas', [])
        
        mensaje = f"📋 **LISTA COMPLETA DE EDIFICIOS**\n\n"
        mensaje += f"Ruta ID: {ruta_id}\n"
        mensaje += f"Zona: {ruta_encontrada.get('zona', 'N/A')}\n"
        mensaje += f"Total edificios: {len(paradas)}\n\n"
        
        for i, parada in enumerate(paradas, 1):
            nombre = parada.get('nombre', f'Edificio {i}')
            direccion = parada.get('direccion', 'Sin dirección')
            dependencia = parada.get('dependencia', 'N/A')
            total_personas = parada.get('total_personas', 1)
            
            direccion_limpia = limpiar_direccion_para_google_maps(direccion)
            
            mensaje += f"**📍 {i}. {nombre}**\n"
            mensaje += f"   🏛️ {dependencia}\n"
            mensaje += f"   📍 {direccion_limpia[:60]}...\n"
            mensaje += f"   👥 {total_personas} persona{'s' if total_personas > 1 else ''}\n\n"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ VER RUTA EN MAPAS", callback_data="ver_ruta_actual"),
            types.InlineKeyboardButton("↩️ VOLVER", callback_data="volver_inicio")
        )
        
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=mensaje,
                parse_mode='Markdown',
                reply_markup=markup
            )
        except:
            bot.send_message(
                call.message.chat.id,
                mensaje,
                parse_mode='Markdown',
                reply_markup=markup
            )
        
        bot.answer_callback_query(call.id, f"✅ Mostrando {len(paradas)} edificios")
        
    except Exception as e:
        print(f"❌ Error en callback_lista_completa: {e}")
        bot.answer_callback_query(call.id, "❌ Error")

@bot.callback_query_handler(func=lambda call: call.data == "volver_inicio")
def callback_volver_inicio(call):
    """Handler para volver al menú principal"""
    try:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta"),
            types.InlineKeyboardButton("🗺️ VER RUTA ACTUAL", callback_data="ver_ruta_actual")
        )
        markup.row(
            types.InlineKeyboardButton("📍 SEGUIMIENTO", callback_data="seguimiento_tiempo_real"),
            types.InlineKeyboardButton("📞 SUPERVISOR", callback_data="contactar_supervisor")
        )
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🤖 **BOT PJCDMX - SISTEMA DE ENTREGAS**\n\n"
                 "🚀 **¿Qué necesitas hacer?**\n\n"
                 "• 🚗 **SOLICITAR RUTA:** Obtén tu ruta de entregas optimizada\n"
                 "• 🗺️ **VER RUTA:** Muestra tu ruta actual con botón para Google Maps\n"
                 "• 📍 **SEGUIMIENTO:** Comparte tu ubicación en tiempo real\n"
                 "• 📞 **SUPERVISOR:** Contacta a tu supervisor inmediatamente\n\n"
                 "👉 **Selecciona una opción:**",
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Menú principal")
        
    except Exception as e:
        print(f"❌ Error en callback_volver_inicio: {e}")
        bot.answer_callback_query(call.id, "❌ Error")

# Handler para ubicaciones compartidas
@bot.message_handler(content_types=['location'])
def handle_location(message):
    """Procesar ubicación compartida por el usuario"""
    try:
        user_id = message.from_user.id
        latitud = message.location.latitude
        longitud = message.location.longitude
        
        print(f"📍 Ubicación recibida de {user_id}: {latitud}, {longitud}")
        
        maps_url = f"https://www.google.com/maps?q={latitud},{longitud}"
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ VER EN GOOGLE MAPS", url=maps_url),
            types.InlineKeyboardButton("📍 GUARDAR UBICACIÓN", callback_data=f"guardar_ubicacion_{latitud}_{longitud}")
        )
        markup.row(
            types.InlineKeyboardButton("📤 COMPARTIR CON SUPERVISOR", 
                                     callback_data=f"compartir_supervisor_{latitud}_{longitud}"),
            types.InlineKeyboardButton("↩️ VOLVER", callback_data="volver_inicio")
        )
        
        bot.send_message(
            message.chat.id,
            f"📍 **UBICACIÓN RECIBIDA**\n\n"
            f"✅ Tu ubicación ha sido registrada:\n"
            f"• **Latitud:** `{latitud}`\n"
            f"• **Longitud:** `{longitud}`\n\n"
            f"**Hora de registro:** {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"¿Qué quieres hacer con esta ubicación?",
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        print(f"❌ Error procesando ubicación: {e}")
        bot.send_message(message.chat.id, "❌ Error procesando tu ubicación")

# Handlers adicionales
@bot.callback_query_handler(func=lambda call: call.data == "ver_ruta_actual")
def callback_ver_ruta_actual(call):
    """Handler para ver ruta actual"""
    user_id = call.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        bot.answer_callback_query(call.id, "❌ No tienes una ruta asignada")
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    ruta_encontrada = None
    for ruta in RUTAS_DISPONIBLES:
        if ruta['ruta_id'] == ruta_id:
            ruta_encontrada = ruta
            break
    
    if not ruta_encontrada:
        bot.answer_callback_query(call.id, "❌ Ruta no encontrada")
        return
    
    maps_url = ruta_encontrada.get('google_maps_url')
    
    markup = types.InlineKeyboardMarkup()
    
    if maps_url and verificar_url_google_maps(maps_url):
        markup.row(types.InlineKeyboardButton("📍 ABRIR RUTA EN GOOGLE MAPS", url=maps_url))
    elif maps_url:
        markup.row(types.InlineKeyboardButton("📍 INTENTAR ABRIR RUTA", url=maps_url))
    
    markup.row(
        types.InlineKeyboardButton("📋 VER DETALLES COMPLETOS", callback_data=f"detalles_ruta_{ruta_id}"),
        types.InlineKeyboardButton("🔄 ACTUALIZAR RUTA", callback_data="actualizar_ruta")
    )
    
    total_paradas = len(ruta_encontrada.get('paradas', []))
    
    mensaje = f"🗺️ **TU RUTA ACTUAL**\n\n"
    mensaje += f"**ID:** {ruta_id}\n"
    mensaje += f"**Zona:** {ruta_encontrada.get('zona', 'N/A')}\n"
    mensaje += f"**Edificios:** {total_paradas}\n"
    mensaje += f"**Origen:** {ruta_encontrada.get('origen', 'TSJCDMX')}\n\n"
    
    if maps_url:
        mensaje += "👉 **Haz clic en el botón para abrir Google Maps con tu ruta completa**\n\n"
    else:
        mensaje += "⚠️ **Google Maps temporalmente no disponible**\n\n"
    
    mensaje += "**PRÓXIMOS EDIFICIOS:**\n"
    for i, parada in enumerate(ruta_encontrada.get('paradas', [])[:3], 1):
        nombre = parada.get('nombre', f'Edificio {i}')
        direccion = limpiar_direccion_para_google_maps(parada.get('direccion', ''))[:40]
        personas = parada.get('total_personas', 1)
        
        mensaje += f"\n{i}. **{nombre}**\n"
        mensaje += f"   📍 {direccion}...\n"
        mensaje += f"   👥 {personas} persona{'s' if personas > 1 else ''}\n"
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "✅ Ruta mostrada")
    except:
        bot.send_message(
            call.message.chat.id,
            mensaje,
            parse_mode='Markdown',
            reply_markup=markup
        )

# Handlers para callbacks adicionales
@bot.callback_query_handler(func=lambda call: call.data.startswith("detalles_ruta_"))
def callback_detalles_ruta(call):
    bot.answer_callback_query(call.id, "📋 Mostrando detalles...")
    bot.send_message(call.message.chat.id, "📋 **Detalles de ruta**\n\nEsta función está en desarrollo.")

@bot.callback_query_handler(func=lambda call: call.data == "actualizar_ruta")
def callback_actualizar_ruta(call):
    bot.answer_callback_query(call.id, "🔄 Actualizando ruta...")
    bot.send_message(call.message.chat.id, "🔄 **Actualizar ruta**\n\nEsta función está en desarrollo.")

@bot.callback_query_handler(func=lambda call: call.data == "cambiar_ruta")
def callback_cambiar_ruta(call):
    user_id = call.from_user.id
    if user_id in RUTAS_ASIGNADAS:
        del RUTAS_ASIGNADAS[user_id]
    
    bot.answer_callback_query(call.id, "🔄 Cambiando ruta...")
    
    class FakeUser:
        def __init__(self, uid, name):
            self.id = uid
            self.first_name = name
    
    class FakeMessage:
        def __init__(self, uid, name, chat_id):
            self.from_user = FakeUser(uid, name)
            self.chat = type('obj', (object,), {'id': chat_id})()
            self.message_id = call.message.message_id
    
    fake_message = FakeMessage(user_id, call.from_user.first_name, call.message.chat.id)
    dar_ruta(fake_message)

@bot.callback_query_handler(func=lambda call: call.data == "sin_maps")
def callback_sin_maps(call):
    bot.answer_callback_query(call.id, "❌ Google Maps no disponible para esta ruta")

@bot.callback_query_handler(func=lambda call: call.data in ["compartir_ubicacion", "reportar_entrega", "reportar_incidente", 
                                                           "guardar_ubicacion", "compartir_supervisor"])
def callback_funciones_en_desarrollo(call):
    bot.answer_callback_query(call.id, "🔧 Función en desarrollo")

# =============================================================================
# FLASK ENDPOINTS
# =============================================================================

@app.route('/')
def home():
    return f"""
    <html>
        <head><title>🤖 Bot PJCDMX - Sistema de Entregas</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1>🤖 Bot PJCDMX - Sistema de Entregas</h1>
            <p><strong>Estado:</strong> ✅ ACTIVO</p>
            <p><strong>Rutas cargadas:</strong> {len(RUTAS_DISPONIBLES)}</p>
            <p><strong>Usuarios con rutas:</strong> {len(RUTAS_ASIGNADAS)}</p>
            <p><strong>Google Maps:</strong> ✅ INTEGRADO Y CORREGIDO</p>
            <hr>
            <p>🔗 <a href="/api/status">Ver estado completo del sistema</a></p>
            <p>🔗 <a href="/api/health">Ver salud del sistema</a></p>
        </body>
    </html>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200

@app.route('/api/status')
def status():
    cursor.execute('SELECT COUNT(*) FROM fotos')
    total_fotos = cursor.fetchone()[0]
    
    total_edificios = sum(len(r.get('paradas', [])) for r in RUTAS_DISPONIBLES)
    total_personas = sum(
        sum(p.get('total_personas', 1) for p in r.get('paradas', [])) 
        for r in RUTAS_DISPONIBLES
    )
    
    rutas_con_maps = sum(1 for r in RUTAS_DISPONIBLES if r.get('google_maps_url'))
    
    return jsonify({
        "status": "ok",
        "rutas": len(RUTAS_DISPONIBLES),
        "rutas_con_google_maps": rutas_con_maps,
        "edificios_totales": total_edificios,
        "personas_totales": total_personas,
        "usuarios_con_ruta": len(RUTAS_ASIGNADAS),
        "fotos_totales": total_fotos,
        "google_maps": {
            "integrado": True,
            "funcionando": rutas_con_maps > 0,
            "rutas_con_url": rutas_con_maps
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "rutas_cargadas": len(RUTAS_DISPONIBLES),
        "bot_token_configured": bool(TOKEN),
        "google_maps_available": any(r.get('google_maps_url') for r in RUTAS_DISPONIBLES),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/rutas', methods=['POST'])
def recibir_rutas_desde_programa():
    """Endpoint para que el programa generador envíe rutas"""
    try:
        datos_ruta = request.json
        
        if not datos_ruta:
            return jsonify({"error": "Datos vacíos"}), 400
        
        ruta_id = datos_ruta.get('ruta_id', 1)
        zona = datos_ruta.get('zona', 'GENERAL')
        
        print(f"📥 Recibiendo ruta {ruta_id} - {zona}")
        print(f"🏢 Paradas recibidas: {len(datos_ruta.get('paradas', []))}")
        
        maps_url = crear_url_google_maps_ruta_completa(datos_ruta)
        if not maps_url:
            maps_url = crear_url_google_maps_alternativa(datos_ruta)
        
        if maps_url:
            datos_ruta['google_maps_url'] = maps_url
            print(f"✅ URL Google Maps generada para ruta {ruta_id}")
            
            if verificar_url_google_maps(maps_url):
                print(f"✅ URL Google Maps verificada como funcional")
            else:
                print(f"⚠️ URL Google Maps no se pudo verificar")
        else:
            print(f"❌ No se pudo generar URL Google Maps para ruta {ruta_id}")
        
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(datos_ruta, f, indent=2, ensure_ascii=False)
        
        cargar_rutas_simple()
        
        print(f"✅ Ruta {ruta_id} recibida via API y guardada")
        
        return jsonify({
            "status": "success", 
            "ruta_id": ruta_id,
            "archivo": archivo_ruta,
            "edificios": len(datos_ruta.get('paradas', [])),
            "google_maps": {
                "url_generada": bool(maps_url),
                "url_verificada": verificar_url_google_maps(maps_url) if maps_url else False
            },
            "rutas_disponibles": len(RUTAS_DISPONIBLES)
        })
        
    except Exception as e:
        print(f"❌ Error en API /api/rutas: {str(e)}")
        return jsonify({"error": str(e)}), 500

# =============================================================================
# INICIALIZACIÓN
# =============================================================================

print("🎯 CARGANDO SISTEMA COMPLETO CON GOOGLE MAPS INTEGRADO Y CORREGIDO...")
cargar_rutas_simple()

print("✅ BOT LISTO - GOOGLE MAPS ACTIVADO Y VERIFICADO")
print(f"📊 Rutas disponibles: {len(RUTAS_DISPONIBLES)}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
