import os
import telebot
import sqlite3
import json
import requests
import urllib.parse
from telebot import types
from datetime import datetime
from flask import Flask, request, jsonify, Response, send_file

print("🚀 INICIANDO BOT COMPLETO - CON GOOGLE MAPS INTEGRADO...")

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
                    RUTAS_DISPONIBLES.append(ruta)
                    print(f"✅ Cargada: {archivo}")
                    
                    # Debug: mostrar primera persona
                    if ruta.get('paradas'):
                        primera = ruta['paradas'][0]
                        print(f"   👤 {primera.get('nombre', 'SIN NOMBRE')}")
                        print(f"   🏢 {primera.get('dependencia', 'SIN DEPENDENCIA')}")
                        
                except Exception as e:
                    print(f"❌ Error con {archivo}: {e}")
    
    # Si no hay rutas, crear una de prueba
    if len(RUTAS_DISPONIBLES) == 0:
        ruta_prueba = {
            "ruta_id": 1,
            "zona": "ZONA CENTRO",
            "paradas": [
                {"nombre": "JUAN PÉREZ", "dependencia": "OFICINA CENTRAL", "direccion": "Av Principal 123, Ciudad de México"},
                {"nombre": "MARÍA GARCÍA", "dependencia": "DEPTO LEGAL", "direccion": "Calle 456, Ciudad de México"},
                {"nombre": "CARLOS LÓPEZ", "dependencia": "RECURSOS HUMANOS", "direccion": "Plaza 789, Ciudad de México"}
            ]
        }
        with open('rutas_telegram/ruta_1.json', 'w') as f:
            json.dump(ruta_prueba, f)
        RUTAS_DISPONIBLES.append(ruta_prueba)
        print("✅ Ruta de prueba creada")
    
    print(f"📦 Rutas listas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)

def crear_url_google_maps_ruta_completa(ruta):
    """
    Crear URL de Google Maps con todas las paradas de la ruta
    Formato: https://www.google.com/maps/dir/?api=1&origin=X&destination=Y&waypoints=A|B|C
    """
    try:
        if not ruta.get('paradas') or len(ruta['paradas']) == 0:
            return None
        
        # Tomar la primera parada como origen
        primera_parada = ruta['paradas'][0]
        origen = urllib.parse.quote(primera_parada.get('direccion', ''))
        
        # Tomar la última parada como destino
        ultima_parada = ruta['paradas'][-1]
        destino = urllib.parse.quote(ultima_parada.get('direccion', ''))
        
        # Las paradas intermedias como waypoints
        waypoints = []
        if len(ruta['paradas']) > 2:
            for parada in ruta['paradas'][1:-1]:  # Excluir primera y última
                direccion = parada.get('direccion', '')
                if direccion:
                    waypoints.append(urllib.parse.quote(direccion))
        
        # Construir la URL
        base_url = "https://www.google.com/maps/dir/?api=1"
        url = f"{base_url}&origin={origen}&destination={destino}"
        
        if waypoints:
            waypoints_str = "|".join(waypoints)
            url += f"&waypoints={waypoints_str}"
        
        # Agregar parámetro para optimizar ruta
        url += "&travelmode=driving"
        
        print(f"🗺️ URL Google Maps generada: {url[:100]}...")
        return url
        
    except Exception as e:
        print(f"❌ Error creando URL de Google Maps: {e}")
        return None

def descargar_foto_telegram(file_id, tipo_foto="entregas"):
    """Descargar foto desde Telegram y guardarla"""
    try:
        print(f"🔄 Descargando foto: {file_id}")
        
        file_info = bot.get_file(file_id)
        if not file_info or not file_info.file_path:
            print("❌ No se pudo obtener file_path")
            return None
            
        file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}"
        
        response = requests.get(file_url, timeout=30)
        if response.status_code == 200:
            carpeta = f"carpeta_fotos_central/{tipo_foto}"
            os.makedirs(carpeta, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            nombre_archivo = f"foto_{timestamp}.jpg"
            ruta_final = f"{carpeta}/{nombre_archivo}"
            
            with open(ruta_final, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Foto guardada: {ruta_final}")
            return ruta_final
        else:
            print(f"❌ Error HTTP: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error descargando foto: {str(e)}")
    
    return None

def guardar_foto_bd(file_id, user_id, user_name, caption, tipo, ruta_foto_local):
    """Guardar información de la foto en la base de datos"""
    try:
        cursor.execute('''
            INSERT INTO fotos 
            (file_id, user_id, user_name, caption, tipo, ruta_local, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (file_id, user_id, user_name, caption, tipo, ruta_foto_local))
        
        conn.commit()
        print(f"✅ Foto guardada en BD: {file_id} - {tipo}")
        return True
        
    except Exception as e:
        print(f"❌ Error guardando foto en BD: {e}")
        return False

# =============================================================================
# HANDLERS DE TELEGRAM - CON BOTÓN DE GOOGLE MAPS COMPLETO
# =============================================================================

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🗺️ Obtener Ruta", callback_data="obtener_ruta"),
        types.InlineKeyboardButton("👥 Ver Lista Completa", callback_data="lista_completa")
    )
    markup.row(
        types.InlineKeyboardButton("📍 Seguimiento Tiempo Real", callback_data="seguimiento_tiempo_real"),
        types.InlineKeyboardButton("📞 Contactar Supervisor", callback_data="contactar_supervisor")
    )
    markup.row(
        types.InlineKeyboardButton("📸 Mis Fotos", callback_data="mis_fotos"),
        types.InlineKeyboardButton("🔧 Debug", callback_data="debug_info")
    )
    
    bot.reply_to(message, 
        "🤖 **Bot PJCDMX - Sistema de Rutas**\n\n"
        "🚀 **Sistema completo activado con:**\n"
        "• 🗺️ Gestión de rutas automáticas\n"
        "• 📸 Sistema de fotos para entregas\n"
        "• 📍 Seguimiento en tiempo real\n"
        "• 👥 Listas completas de destinatarios\n\n"
        "📞 **Soporte inmediato disponible**\n\n"
        "**Selecciona una opción:**", 
        parse_mode='Markdown', 
        reply_markup=markup)

@bot.message_handler(commands=['ruta', 'solicitar_ruta'])
def dar_ruta(message):
    user_id = message.from_user.id
    
    if user_id in RUTAS_ASIGNADAS:
        bot.reply_to(message, "⚠️ Ya tienes una ruta. Usa /miruta")
        return
    
    if len(RUTAS_DISPONIBLES) == 0:
        cargar_rutas_simple()
    
    if len(RUTAS_DISPONIBLES) == 0:
        bot.reply_to(message, "❌ No hay rutas disponibles")
        return
    
    ruta = RUTAS_DISPONIBLES[0]
    RUTAS_ASIGNADAS[user_id] = ruta['ruta_id']
    
    # Generar URL de Google Maps con toda la ruta
    maps_url = crear_url_google_maps_ruta_completa(ruta)
    
    # Crear teclado con botón PRINCIPAL de Google Maps
    markup = types.InlineKeyboardMarkup()
    
    if maps_url:
        # BOTÓN PRINCIPAL: SEGUIR RUTA COMPLETA EN GOOGLE MAPS
        markup.row(
            types.InlineKeyboardButton("🗺️ SEGUIR RUTA EN GOOGLE MAPS", url=maps_url)
        )
    
    markup.row(
        types.InlineKeyboardButton("👥 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta['ruta_id']}"),
        types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="ubicacion_actual")
    )
    markup.row(
        types.InlineKeyboardButton("📞 Contactar Supervisor", callback_data="contactar_supervisor"),
        types.InlineKeyboardButton("📸 Registrar Entrega", callback_data="registrar_entrega")
    )
    
    # Mensaje con información completa de la ruta
    mensaje = f"🗺️ **RUTA ASIGNADA - {ruta['zona']}**\n\n"
    mensaje += f"📊 **Total paradas:** {len(ruta['paradas'])}\n"
    mensaje += f"📍 **Ruta optimizada para:**\n\n"
    
    for i, parada in enumerate(ruta['paradas'][:5], 1):
        nombre = parada.get('nombre', f'Persona {i}')
        dependencia = parada.get('dependencia', 'Sin dependencia')
        direccion = parada.get('direccion', 'Sin dirección')
        
        mensaje += f"**{i}. {nombre}**\n"
        mensaje += f"   🏢 {dependencia}\n"
        mensaje += f"   📍 {direccion}\n\n"
    
    if len(ruta['paradas']) > 5:
        mensaje += f"📋 **... y {len(ruta['paradas']) - 5} más**\n\n"
    
    if maps_url:
        mensaje += "🚗 **Haz clic en el botón 'SEGUIR RUTA EN GOOGLE MAPS' para:**\n"
        mensaje += "• Ver todas las paradas en secuencia\n"
        mensaje += "• Obtener indicaciones paso a paso\n"
        mensaje += "• Calcular tiempos de viaje\n"
        mensaje += "• Navegar con voz\n\n"
    
    mensaje += "📸 **Para registrar entrega:**\nEnvía foto con 'ENTREGADO A [nombre]'"
    
    bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['miruta'])
def ver_ruta(message):
    user_id = message.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🗺️ Obtener Ruta", callback_data="obtener_ruta"))
        bot.reply_to(message, "❌ No tienes ruta asignada", reply_markup=markup)
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for ruta in RUTAS_DISPONIBLES:
        if ruta['ruta_id'] == ruta_id:
            # Generar URL de Google Maps con toda la ruta
            maps_url = crear_url_google_maps_ruta_completa(ruta)
            
            # Crear teclado con botón PRINCIPAL de Google Maps
            markup = types.InlineKeyboardMarkup()
            
            if maps_url:
                # BOTÓN PRINCIPAL: SEGUIR RUTA COMPLETA EN GOOGLE MAPS
                markup.row(
                    types.InlineKeyboardButton("🗺️ SEGUIR RUTA EN GOOGLE MAPS", url=maps_url)
                )
            
            markup.row(
                types.InlineKeyboardButton("👥 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta_id}"),
                types.InlineKeyboardButton("📍 Seguimiento", callback_data="seguimiento_tiempo_real")
            )
            markup.row(
                types.InlineKeyboardButton("📞 Supervisor", callback_data="contactar_supervisor"),
                types.InlineKeyboardButton("📸 Entregar", callback_data="registrar_entrega")
            )
            
            mensaje = f"🗺️ **TU RUTA ACTUAL - {ruta['zona']}**\n\n"
            mensaje += f"📊 **Total paradas:** {len(ruta['paradas'])}\n"
            mensaje += f"📍 **Próximas paradas:**\n\n"
            
            for i, parada in enumerate(ruta['paradas'][:4], 1):
                nombre = parada.get('nombre', f'Persona {i}')
                dependencia = parada.get('dependencia', 'Sin dependencia')
                direccion = parada.get('direccion', 'Sin dirección')
                
                mensaje += f"**{i}. {nombre}**\n"
                mensaje += f"   🏢 {dependencia}\n"
                mensaje += f"   📍 {direccion}\n\n"
            
            if len(ruta['paradas']) > 4:
                mensaje += f"📋 **... y {len(ruta['paradas']) - 4} más**\n\n"
            
            if maps_url:
                mensaje += "🚗 **Haz clic en 'SEGUIR RUTA' para abrir Google Maps con:**\n"
                mensaje += "• Todas las paradas en orden\n"
                mensaje += "• Indicaciones de navegación\n"
                mensaje += "• Tiempos estimados\n\n"
            
            mensaje += "📍 **Usa los botones para acciones rápidas**"
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

@bot.message_handler(commands=['maps', 'googlemaps', 'navegar'])
def navegar_ruta(message):
    """Comando específico para obtener botón de Google Maps"""
    user_id = message.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        bot.reply_to(message, "❌ Primero obtén una ruta con /ruta")
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for ruta in RUTAS_DISPONIBLES:
        if ruta['ruta_id'] == ruta_id:
            # Generar URL de Google Maps
            maps_url = crear_url_google_maps_ruta_completa(ruta)
            
            if not maps_url:
                bot.reply_to(message, "❌ No se pudo generar la ruta en Google Maps")
                return
            
            # Crear mensaje con botón grande de Google Maps
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("🗺️ ABRIR RUTA COMPLETA EN GOOGLE MAPS", url=maps_url)
            )
            
            mensaje = "🚗 **RUTA DE NAVEGACIÓN**\n\n"
            mensaje += "Haz clic en el botón para abrir Google Maps con **todas las paradas** en secuencia.\n\n"
            mensaje += "**Ventajas:**\n"
            mensaje += "• ✅ Ruta optimizada automáticamente\n"
            mensaje += "• 🗺️ Indicaciones paso a paso\n"
            mensaje += "• ⏱️ Tiempos de viaje estimados\n"
            mensaje += "• 🎧 Navegación por voz\n"
            mensaje += "• 📱 Funciona en móvil y desktop\n\n"
            mensaje += "**Total paradas en esta ruta:** " + str(len(ruta['paradas']))
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

@bot.message_handler(commands=['lista_completa'])
def lista_completa(message):
    user_id = message.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        bot.reply_to(message, "❌ No tienes una ruta asignada")
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for ruta in RUTAS_DISPONIBLES:
        if ruta['ruta_id'] == ruta_id:
            # Generar URL de Google Maps
            maps_url = crear_url_google_maps_ruta_completa(ruta)
            
            mensaje = f"👥 **LISTA COMPLETA - Ruta {ruta_id}**\n"
            mensaje += f"📍 **Zona:** {ruta['zona']}\n"
            mensaje += f"📊 **Total personas:** {len(ruta['paradas'])}\n\n"
            
            for i, parada in enumerate(ruta['paradas'], 1):
                nombre = parada.get('nombre', f'Persona {i}')
                dependencia = parada.get('dependencia', 'Sin dependencia')
                direccion = parada.get('direccion', 'Sin dirección')
                estado = "✅" if parada.get('estado') == 'entregado' else "📍"
                
                mensaje += f"{estado} **{i}. {nombre}**\n"
                mensaje += f"   🏢 {dependencia}\n"
                mensaje += f"   📍 {direccion}\n\n"
            
            # Crear teclado con botón de Google Maps si hay URL
            markup = None
            if maps_url:
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("🗺️ SEGUIR ESTA RUTA EN GOOGLE MAPS", url=maps_url)
                )
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

@bot.message_handler(commands=['contactar'])
def contactar_supervisor(message):
    info_supervisor = """
📞 **INFORMACIÓN DE CONTACTO - SUPERVISOR**

👨‍💼 **Lic. Pedro Javier Hernandez Vasquez**
📱 **Teléfono:** 55 3197 3078
🕒 **Horario:** 7:00 - 19:00 hrs
📧 **Email:** (disponible en sistema)

🚨 **Para emergencias:**
• Llamadas prioritarias
• Soporte inmediato en ruta
• Asistencia técnica

💬 **Puedes contactar directamente:**
• Llamada telefónica
• Mensaje de WhatsApp
• Reporte por este bot
"""
    bot.reply_to(message, info_supervisor, parse_mode='Markdown')

@bot.message_handler(commands=['seguimiento'])
def seguimiento_tiempo_real(message):
    info_seguimiento = """
📍 **SEGUIMIENTO EN TIEMPO REAL**

🚀 **Sistema activado para:**
• 📍 Ubicación en tiempo real
• 🗺️ Optimización de rutas
• ⚡ Respuesta rápida
• 📊 Monitoreo continuo

📱 **Cómo funciona:**
1. Comparte tu ubicación actual
2. El sistema registra tu posición
3. Supervisores monitorean en tiempo real
4. Optimizamos tu ruta automáticamente

🛡️ **Beneficios:**
• Seguridad en ruta
• Asistencia inmediata
• Rutas más eficientes
• Comunicación constante

⚠️ **Tu ubicación solo es visible para supervisores autorizados**
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(types.KeyboardButton("📍 Compartir mi ubicación", request_location=True))
    markup.row(types.KeyboardButton("❌ Cancelar"))
    
    bot.reply_to(message, info_seguimiento, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['fotos'])
def ver_fotos(message):
    """Mostrar las fotos que ha enviado el usuario"""
    user_id = message.from_user.id
    
    try:
        cursor.execute('''
            SELECT file_id, caption, tipo, timestamp 
            FROM fotos 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''', (user_id,))
        
        fotos = cursor.fetchall()
        
        if not fotos:
            bot.reply_to(message, "📭 No has enviado fotos aún")
            return
        
        mensaje = f"📸 **Tus últimas {len(fotos)} fotos:**\n\n"
        
        for i, (file_id, caption, tipo, timestamp) in enumerate(fotos, 1):
            fecha = timestamp.split('.')[0] if timestamp else "Sin fecha"
            mensaje += f"{i}. **{tipo.upper()}** - {fecha}\n"
            mensaje += f"   📝 {caption if caption else 'Sin descripción'}\n\n"
        
        bot.reply_to(message, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Error obteniendo fotos: {e}")
        bot.reply_to(message, "❌ Error al obtener tus fotos")

@bot.message_handler(commands=['debug'])
def debug(message):
    user_id = message.from_user.id
    
    # Contar fotos del usuario
    cursor.execute('SELECT COUNT(*) FROM fotos WHERE user_id = ?', (user_id,))
    total_fotos = cursor.fetchone()[0]
    
    mensaje = f"🔧 **INFORMACIÓN DEL SISTEMA**\n\n"
    mensaje += f"📦 Rutas disponibles: {len(RUTAS_DISPONIBLES)}\n"
    mensaje += f"📸 Tus fotos en sistema: {total_fotos}\n"
    mensaje += f"🗺️ Tienes ruta asignada: {'✅ SÍ' if user_id in RUTAS_ASIGNADAS else '❌ NO'}\n"
    
    if user_id in RUTAS_ASIGNADAS:
        mensaje += f"🔢 ID de tu ruta: {RUTAS_ASIGNADAS[user_id]}\n"
        
        # Mostrar información de la ruta asignada
        for ruta in RUTAS_DISPONIBLES:
            if ruta['ruta_id'] == RUTAS_ASIGNADAS[user_id]:
                maps_url = crear_url_google_maps_ruta_completa(ruta)
                if maps_url:
                    mensaje += f"🔗 URL Google Maps: {maps_url[:50]}...\n"
                break
    
    mensaje += f"\n👤 Tu ID: {user_id}\n"
    mensaje += f"🕒 Hora actual: {datetime.now().strftime('%H:%M:%S')}\n\n"
    mensaje += "✅ **Sistema operativo al 100%**"
    
    bot.reply_to(message, mensaje, parse_mode='Markdown')

@bot.message_handler(commands=['recargar'])
def recargar(message):
    cargar_rutas_simple()
    bot.reply_to(message, f"✅ Rutas recargadas: {len(RUTAS_DISPONIBLES)}")

# =============================================================================
# MANEJO DE UBICACIONES
# =============================================================================

@bot.message_handler(content_types=['location'])
def manejar_ubicacion(message):
    """Manejar ubicación en tiempo real"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        location = message.location
        
        latitud = location.latitude
        longitud = location.longitude
        
        # Guardar ubicación en base de datos
        cursor.execute('''
            INSERT INTO fotos 
            (file_id, user_id, user_name, caption, tipo, ruta_local, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (f"location_{user_id}", user_id, user_name, 
              f"Ubicación: {latitud},{longitud}", "ubicacion", None))
        
        conn.commit()
        
        mensaje = f"📍 **UBICACIÓN REGISTRADA**\n\n"
        mensaje += f"👤 **Usuario:** {user_name}\n"
        mensaje += f"📌 **Coordenadas:** {latitud}, {longitud}\n"
        mensaje += f"🕒 **Hora:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        mensaje += f"🗺️ **Ver en mapa:**\n"
        mensaje += f"https://www.google.com/maps?q={latitud},{longitud}\n\n"
        mensaje += "✅ **Tu ubicación ha sido registrada en el sistema**"
        
        # Eliminar teclado de ubicación
        markup = types.ReplyKeyboardRemove()
        
        bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
        print(f"📍 Ubicación guardada: {user_name} - {latitud}, {longitud}")
        
    except Exception as e:
        print(f"❌ Error manejando ubicación: {e}")
        bot.reply_to(message, "❌ Error al procesar ubicación")

# =============================================================================
# MANEJO DE FOTOS
# =============================================================================

@bot.message_handler(content_types=['photo'])
def manejar_foto_completo(message):
    """Manejar fotos con sistema completo"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        
        print(f"📸 Foto recibida de {user_name}: '{caption}'")
        
        # Determinar tipo de foto
        if any(word in caption.upper() for word in ['ENTREGADO', 'ENTREGADA', 'ACUSE']):
            tipo = "entrega"
            carpeta = "entregas"
            respuesta = "✅ **ENTREGA REGISTRADA**\n\nFoto de entrega guardada en el sistema"
        else:
            tipo = "reporte"
            carpeta = "incidentes"
            respuesta = "✅ **REPORTE GUARDADO**\n\nFoto de reporte guardada en el sistema"
        
        # Descargar y guardar foto
        ruta_foto = descargar_foto_telegram(file_id, carpeta)
        
        if ruta_foto:
            # Guardar en base de datos
            guardar_foto_bd(file_id, user_id, user_name, caption, tipo, ruta_foto)
            
            # Si es entrega y tiene ruta, procesar
            if tipo == "entrega" and user_id in RUTAS_ASIGNADAS:
                respuesta += f"\n\n🗺️ **Ruta:** {RUTAS_ASIGNADAS[user_id]}\n"
                respuesta += f"📝 **Texto:** {caption}"
            
            bot.reply_to(message, respuesta, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Error al guardar la foto")
        
    except Exception as e:
        print(f"❌ Error con foto: {e}")
        bot.reply_to(message, "❌ Error procesando foto")

# =============================================================================
# CALLBACK HANDLERS
# =============================================================================

@bot.callback_query_handler(func=lambda call: True)
def manejar_todos_los_callbacks(call):
    """Manejar todos los callbacks de botones"""
    try:
        data = call.data
        
        if data == 'obtener_ruta':
            dar_ruta(call.message)
            bot.answer_callback_query(call.id, "🗺️ Obteniendo ruta...")
            
        elif data.startswith('lista_completa_'):
            partes = data.split('_')
            ruta_id = partes[2] if len(partes) >= 3 else "?"
            
            for ruta in RUTAS_DISPONIBLES:
                if str(ruta['ruta_id']) == str(ruta_id):
                    # Generar URL de Google Maps
                    maps_url = crear_url_google_maps_ruta_completa(ruta)
                    
                    mensaje = f"👥 **LISTA COMPLETA - Ruta {ruta_id}**\n"
                    mensaje += f"📍 **Zona:** {ruta['zona']}\n"
                    mensaje += f"📊 **Total personas:** {len(ruta['paradas'])}\n\n"
                    
                    for i, parada in enumerate(ruta['paradas'], 1):
                        nombre = parada.get('nombre', f'Persona {i}')
                        dependencia = parada.get('dependencia', 'Sin dependencia')
                        direccion = parada.get('direccion', 'Sin dirección')
                        estado = "✅" if parada.get('estado') == 'entregado' else "📍"
                        
                        mensaje += f"{estado} **{i}. {nombre}**\n"
                        mensaje += f"   🏢 {dependencia}\n"
                        mensaje += f"   📍 {direccion}\n\n"
                    
                    # Crear teclado con botón de Google Maps si hay URL
                    markup = None
                    if maps_url:
                        markup = types.InlineKeyboardMarkup()
                        markup.row(
                            types.InlineKeyboardButton("🗺️ SEGUIR RUTA EN GOOGLE MAPS", url=maps_url)
                        )
                    
                    bot.send_message(call.message.chat.id, mensaje, parse_mode='Markdown', reply_markup=markup)
                    break
            
            bot.answer_callback_query(call.id, "👥 Lista completa mostrada")
            
        elif data == 'lista_completa':
            if call.from_user.id in RUTAS_ASIGNADAS:
                lista_completa(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ Primero obtén una ruta")
            
        elif data == 'contactar_supervisor':
            info_supervisor = """
📞 **CONTACTO SUPERVISOR - URGENCIAS**

👨‍💼 **Lic. Pedro Javier Hernandez Vasquez**
📱 **Teléfono:** 55 3197 3078
🕒 **Horario:** 7:00 - 19:00 hrs

🚨 **Para:**
• Emergencias en ruta
• Problemas con entregas
• Asistencia inmediata
• Reportes urgentes

💬 **Contacto directo disponible**
"""
            bot.send_message(call.message.chat.id, info_supervisor, parse_mode='Markdown')
            bot.answer_callback_query(call.id, "📞 Información de contacto")
            
        elif data == 'seguimiento_tiempo_real':
            seguimiento_tiempo_real(call.message)
            bot.answer_callback_query(call.id, "📍 Activando seguimiento...")
            
        elif data == 'ubicacion_actual':
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.row(types.KeyboardButton("📍 Compartir mi ubicación", request_location=True))
            bot.send_message(
                call.message.chat.id,
                "📍 **COMPARTIR UBICACIÓN ACTUAL**\n\nPresiona el botón para compartir tu ubicación:",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "📍 Solicitando ubicación...")
            
        elif data == 'registrar_entrega':
            bot.send_message(
                call.message.chat.id,
                "📸 **REGISTRAR ENTREGA**\n\nEnvía una foto del acuse firmado con el pie de foto:\n\n`ENTREGADO A [NOMBRE COMPLETO]`\n\n**Ejemplo:**\n`ENTREGADO A JUAN PÉREZ LÓPEZ`",
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "📸 Listo para recibir foto...")
            
        elif data == 'mis_fotos':
            ver_fotos(call.message)
            bot.answer_callback_query(call.id, "📸 Obteniendo tus fotos...")
            
        elif data == 'debug_info':
            debug(call.message)
            bot.answer_callback_query(call.id, "🔧 Obteniendo info del sistema...")
            
    except Exception as e:
        print(f"❌ Error en callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando comando")

# =============================================================================
# ENDPOINTS FLASK
# =============================================================================

@app.route('/')
def home():
    return "🤖 Bot ACTIVO - Sistema Completo con Google Maps Integrado"

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
    
    return jsonify({
        "status": "ok",
        "rutas": len(RUTAS_DISPONIBLES),
        "usuarios": len(RUTAS_ASIGNADAS),
        "fotos_totales": total_fotos
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "rutas_cargadas": len(RUTAS_DISPONIBLES),
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
        
        # Verificar que las paradas tengan dirección para Google Maps
        if datos_ruta.get('paradas'):
            for i, parada in enumerate(datos_ruta['paradas']):
                if not parada.get('direccion'):
                    datos_ruta['paradas'][i]['direccion'] = f"Ciudad de México, Parada {i+1}"
        
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(datos_ruta, f, indent=2, ensure_ascii=False)
        
        # Recargar rutas automáticamente
        cargar_rutas_simple()
        
        print(f"✅ Ruta {ruta_id} recibida via API y guardada")
        
        # Generar URL de Google Maps para esta ruta
        maps_url = crear_url_google_maps_ruta_completa(datos_ruta)
        
        return jsonify({
            "status": "success", 
            "ruta_id": ruta_id,
            "archivo": archivo_ruta,
            "rutas_disponibles": len(RUTAS_DISPONIBLES),
            "google_maps_url": maps_url if maps_url else "No generada"
        })
        
    except Exception as e:
        print(f"❌ Error en API /api/rutas: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/avances_pendientes', methods=['GET'])
def obtener_avances_pendientes():
    """Endpoint para que el programa obtenga avances de entregas"""
    try:
        avances = []
        return jsonify({
            "status": "success",
            "avances": avances,
            "total": 0,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/avances/<avance_id>/procesado', methods=['POST'])
def marcar_avance_procesado(avance_id):
    """Marcar un avance como procesado"""
    try:
        print(f"✅ Avance procesado: {avance_id}")
        return jsonify({"status": "success", "message": "Avance marcado como procesado"})
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/diagnostico_rutas', methods=['GET'])
def diagnostico_rutas():
    """Diagnóstico completo de rutas"""
    try:
        archivos_info = []
        if os.path.exists('rutas_telegram'):
            for archivo in os.listdir('rutas_telegram'):
                if archivo.endswith('.json'):
                    try:
                        with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                            ruta = json.load(f)
                        
                        primera_parada = ruta['paradas'][0] if ruta.get('paradas') else {}
                        archivos_info.append({
                            'archivo': archivo,
                            'ruta_id': ruta.get('ruta_id'),
                            'zona': ruta.get('zona'),
                            'paradas': len(ruta.get('paradas', [])),
                            'primera_persona_nombre': primera_parada.get('nombre'),
                            'primera_persona_dependencia': primera_parada.get('dependencia'),
                            'primera_persona_direccion': primera_parada.get('direccion'),
                            'estado': ruta.get('estado')
                        })
                    except Exception as e:
                        archivos_info.append({'archivo': archivo, 'error': str(e)})
        
        return jsonify({
            "status": "success",
            "archivos_en_sistema": archivos_info,
            "rutas_en_memoria": len(RUTAS_DISPONIBLES),
            "rutas_cargadas": [f"Ruta {r['ruta_id']} - {r['zona']}" for r in RUTAS_DISPONIBLES]
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# =============================================================================
# INICIALIZACIÓN
# =============================================================================

print("🎯 CARGANDO SISTEMA COMPLETO CON GOOGLE MAPS INTEGRADO...")
cargar_rutas_simple()
print("✅ BOT LISTO - GOOGLE MAPS ACTIVADO")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
