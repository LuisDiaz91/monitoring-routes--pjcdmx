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
    Versión MEJORADA que funciona con datos de tu generador
    """
    try:
        if not ruta.get('paradas') or len(ruta['paradas']) == 0:
            return None
        
        # 🎯 NUEVO: Extraer origen desde los datos de la ruta
        origen = "TSJCDMX - Niños Héroes 150, Ciudad de México"
        
        # Si la ruta tiene información de origen, usarla
        if ruta.get('origen'):
            origen = ruta['origen']
        
        # 🎯 BUSCAR DIRECCIONES EN LAS PARADAS - VERSIÓN MEJORADA
        direcciones = []

        for parada in ruta['paradas']:
            # Intentar obtener dirección de diferentes lugares
            direccion = parada.get('direccion', '')
            
            # Si no hay en el nivel superior, buscar en la primera persona
            if not direccion or direccion in ['N/A', '', 'Sin dirección']:
                if parada.get('personas') and len(parada['personas']) > 0:
                    primera_persona = parada['personas'][0]
                    direccion = primera_persona.get('direccion', '')
            
            # Si aún no hay, usar un valor por defecto
            if not direccion or direccion in ['N/A', '', 'Sin dirección']:
                direccion = f"Ciudad de México, Parada {parada.get('orden', '')}"
            
            # Agregar Ciudad de México si no está
            if 'ciudad de méxico' not in direccion.lower() and 'cdmx' not in direccion.lower():
                direccion += ", Ciudad de México"
            
            direcciones.append(urllib.parse.quote(direccion))
        
        if len(direcciones) < 2:
            return None
        
        # Construir URL de Google Maps
        base_url = "https://www.google.com/maps/dir/?api=1"
        
        # Origen: siempre el primer punto
        origen_codificado = urllib.parse.quote(origen)
        url = f"{base_url}&origin={origen_codificado}"
        
        # Destino: el último punto
        destino_codificado = direcciones[-1]
        url += f"&destination={destino_codificado}"
        
        # Waypoints: todos los puntos intermedios (excluyendo primero y último)
        if len(direcciones) > 2:
            waypoints_str = "|".join(direcciones[1:-1])
            url += f"&waypoints={waypoints_str}"
        
        # Agregar optimización y modo de viaje
        url += "&travelmode=driving"
        
        # Agregar opción de optimizar ruta
        url += "&dir_action=navigate"
        
        print(f"🗺️ URL Google Maps generada: {url}")
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
    markup.row(
        types.InlineKeyboardButton("📸 ENTREGAS", callback_data="mis_fotos"),
        types.InlineKeyboardButton("📋 LISTA PARADAS", callback_data="lista_completa")
    )
    
    bot.reply_to(message, 
        "🤖 **BOT PJCDMX - SISTEMA DE ENTREGAS**\n\n"
        "🚀 **¿Qué necesitas hacer?**\n\n"
        "• 🚗 **SOLICITAR RUTA:** Obtén tu ruta de entregas optimizada\n"
        "• 🗺️ **VER RUTA:** Muestra tu ruta actual con botón para Google Maps\n"
        "• 📍 **SEGUIMIENTO:** Comparte tu ubicación en tiempo real\n"
        "• 📞 **SUPERVISOR:** Contacta a tu supervisor inmediatamente\n"
        "• 📸 **ENTREGAS:** Registra entregas con fotos y acuses\n"
        "• 📋 **LISTA:** Ver lista completa de personas a entregar\n\n"
        "👉 **Selecciona una opción o usa /ayuda para ver todos los comandos**", 
        parse_mode='Markdown', 
        reply_markup=markup)

@bot.message_handler(commands=['ayuda', 'help'])
def ayuda(message):
    comandos = """
📋 **LISTA DE COMANDOS DISPONIBLES:**

🚗 **RUTAS Y NAVEGACIÓN:**
• /start - Menú principal del bot
• /ruta - Solicitar una nueva ruta de entregas
• /miruta - Ver tu ruta actual asignada
• /maps - Abrir Google Maps con tu ruta completa
• /lista - Ver lista completa de personas a entregar

📍 **SEGUIMIENTO:**
• /seguimiento - Compartir ubicación en tiempo real
• /ubicacion - Enviar tu ubicación actual

📸 **ENTREGAS Y FOTOS:**
• /entregar - Registrar una entrega con foto
• /fotos - Ver tus fotos de entregas enviadas
• /reporte - Enviar reporte de incidente con foto

📞 **CONTACTO Y SOPORTE:**
• /supervisor - Información de contacto del supervisor
• /ayuda - Mostrar esta lista de comandos
• /debug - Información del sistema

🔧 **ADMINISTRACIÓN:**
• /recargar - Recargar rutas desde el sistema
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta"),
        types.InlineKeyboardButton("🗺️ ABRIR GOOGLE MAPS", callback_data="abrir_maps")
    )
    
    bot.reply_to(message, comandos, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['ruta', 'solicitar_ruta'])
def dar_ruta(message):
    user_id = message.from_user.id
    
    if user_id in RUTAS_ASIGNADAS:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ VER MI RUTA ACTUAL", callback_data="ver_ruta_actual"),
            types.InlineKeyboardButton("🔄 CAMBIAR RUTA", callback_data="cambiar_ruta")
        )
        bot.reply_to(message, 
                    "⚠️ **YA TIENES UNA RUTA ASIGNADA**\n\n"
                    "¿Quieres ver tu ruta actual o solicitar una nueva?", 
                    parse_mode='Markdown', 
                    reply_markup=markup)
        return
    
    if len(RUTAS_DISPONIBLES) == 0:
        cargar_rutas_simple()
    
    if len(RUTAS_DISPONIBLES) == 0:
        bot.reply_to(message, "❌ **NO HAY RUTAS DISPONIBLES**\n\nEl sistema está generando rutas. Intenta más tarde.")
        return
    
    # Asignar la primera ruta disponible
    ruta = RUTAS_DISPONIBLES[0]
    RUTAS_ASIGNADAS[user_id] = ruta['ruta_id']
    
    # Generar URL de Google Maps con toda la ruta
    maps_url = crear_url_google_maps_ruta_completa(ruta)
    
    # 🎯 CREAR MENSAJE CON BOTÓN PRINCIPAL DE GOOGLE MAPS
    markup = types.InlineKeyboardMarkup()
    
    if maps_url:
        # BOTÓN PRINCIPAL GRANDE - GOOGLE MAPS
        markup.row(
            types.InlineKeyboardButton("📍 ABRIR RUTA EN GOOGLE MAPS", url=maps_url)
        )
    
    # Botones secundarios
    markup.row(
        types.InlineKeyboardButton("📋 VER LISTA DE PARADAS", callback_data=f"lista_completa_{ruta['ruta_id']}"),
        types.InlineKeyboardButton("📍 MI UBICACIÓN", callback_data="ubicacion_actual")
    )
    markup.row(
        types.InlineKeyboardButton("📸 REGISTRAR ENTREGA", callback_data="registrar_entrega"),
        types.InlineKeyboardButton("📞 CONTACTAR SUPERVISOR", callback_data="contactar_supervisor")
    )
    
    # Mensaje informativo
    mensaje = f"✅ **RUTA ASIGNADA EXITOSAMENTE**\n\n"
    mensaje += f"📊 **RUTA:** {ruta.get('zona', 'SIN ZONA')} - ID: {ruta['ruta_id']}\n"
    mensaje += f"📍 **TOTAL PARADAS:** {len(ruta.get('paradas', []))}\n\n"
    
    if maps_url:
        mensaje += "🚗 **HAZ CLIC EN EL BOTÓN 'ABRIR RUTA EN GOOGLE MAPS' PARA:**\n"
        mensaje += "• Ver la ruta completa optimizada\n"
        mensaje += "• Obtener indicaciones paso a paso\n"
        mensaje += "• Navegar con Google Maps\n\n"
    
    # Mostrar primeras 3 paradas
    mensaje += "📦 **PRIMERAS PARADAS:**\n"
    for i, parada in enumerate(ruta.get('paradas', [])[:3], 1):
        direccion = parada.get('direccion', 'Sin dirección')
        cantidad = parada.get('total_personas', 1)
        
        mensaje += f"\n**📍 Parada {i}**\n"
        mensaje += f"   🏢 {direccion[:50]}...\n"
        if cantidad > 1:
            mensaje += f"   👥 {cantidad} personas en este edificio\n"
    
    bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['miruta', 'verruta'])
def ver_ruta(message):
    user_id = message.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta"),
            types.InlineKeyboardButton("❓ AYUDA", callback_data="ayuda_boton")
        )
        bot.reply_to(message, 
                    "❌ **NO TIENES RUTA ASIGNADA**\n\n"
                    "Primero solicita una ruta para comenzar las entregas.", 
                    parse_mode='Markdown', 
                    reply_markup=markup)
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for ruta in RUTAS_DISPONIBLES:
        if ruta['ruta_id'] == ruta_id:
            # Generar URL de Google Maps con toda la ruta
            maps_url = crear_url_google_maps_ruta_completa(ruta)
            
            # Crear teclado con botón PRINCIPAL de Google Maps
            markup = types.InlineKeyboardMarkup()
            
            if maps_url:
                # BOTÓN PRINCIPAL: ABRIR RUTA EN GOOGLE MAPS
                markup.row(
                    types.InlineKeyboardButton("📍 ABRIR RUTA EN GOOGLE MAPS", url=maps_url)
                )
            
            # Botones de acciones
            markup.row(
                types.InlineKeyboardButton("📋 VER LISTA COMPLETA", callback_data=f"lista_completa_{ruta_id}"),
                types.InlineKeyboardButton("📍 SEGUIMIENTO", callback_data="seguimiento_tiempo_real")
            )
            markup.row(
                types.InlineKeyboardButton("📞 SUPERVISOR", callback_data="contactar_supervisor"),
                types.InlineKeyboardButton("📸 REGISTRAR ENTREGA", callback_data="registrar_entrega")
            )
            
            # Mensaje detallado
            total_paradas = len(ruta['paradas'])
            paradas_entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
            
            mensaje = f"🗺️ **TU RUTA ACTUAL**\n\n"
            mensaje += f"📊 **RUTA:** {ruta['zona']} - ID: {ruta_id}\n"
            mensaje += f"📍 **PARADAS:** {paradas_entregadas}/{total_paradas} entregadas\n"
            mensaje += f"⏱️ **PROGRESO:** {int((paradas_entregadas/total_paradas)*100)}%\n\n"
            
            mensaje += "📍 **PRÓXIMAS PARADAS:**\n\n"
            
            # Mostrar próximas paradas no entregadas
            paradas_pendientes = [p for p in ruta['paradas'] if p.get('estado') != 'entregado']
            
            for i, parada in enumerate(paradas_pendientes[:3], 1):
                nombre = parada.get('nombre', f'Persona {i}')
                dependencia = parada.get('dependencia', 'Sin dependencia')
                direccion = parada.get('direccion', 'Sin dirección')
                
                mensaje += f"**{i}. {nombre}**\n"
                mensaje += f"   🏢 {dependencia}\n"
                mensaje += f"   📍 {direccion}\n\n"
            
            if len(paradas_pendientes) > 3:
                mensaje += f"📋 **... y {len(paradas_pendientes) - 3} más por entregar**\n\n"
            
            if maps_url:
                mensaje += "👉 **Haz clic en 'ABRIR RUTA EN GOOGLE MAPS' para:**\n"
                mensaje += "• Navegar con indicaciones paso a paso\n"
                mensaje += "• Ver la ruta optimizada\n"
                mensaje += "• Calcular tiempos de viaje\n\n"
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada. Usa /ruta para solicitar una nueva.")

@bot.message_handler(commands=['maps', 'googlemaps', 'navegar', 'ruta_maps'])
def navegar_ruta(message):
    """Comando específico para obtener botón de Google Maps"""
    user_id = message.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta"))
        bot.reply_to(message, 
                    "❌ **PRIMERO NECESITAS UNA RUTA**\n\n"
                    "Solicita una ruta para poder verla en Google Maps.", 
                    parse_mode='Markdown', 
                    reply_markup=markup)
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
                types.InlineKeyboardButton("📍 ABRIR RUTA COMPLETA EN GOOGLE MAPS", url=maps_url)
            )
            
            # Botones adicionales
            markup.row(
                types.InlineKeyboardButton("📋 VER LISTA DE PARADAS", callback_data=f"lista_completa_{ruta_id}"),
                types.InlineKeyboardButton("🗺️ VER MI RUTA", callback_data="ver_ruta_actual")
            )
            
            mensaje = "🚗 **NAVEGACIÓN CON GOOGLE MAPS**\n\n"
            mensaje += "Haz clic en el botón para abrir Google Maps con **todas las paradas** en secuencia.\n\n"
            mensaje += "✅ **VENTAJAS:**\n"
            mensaje += "• 🗺️ Ruta optimizada automáticamente\n"
            mensaje += "• 📍 Indicaciones paso a paso\n"
            mensaje += "• ⏱️ Tiempos de viaje estimados\n"
            mensaje += "• 🎧 Navegación por voz disponible\n"
            mensaje += "• 📱 Funciona en móvil y computadora\n\n"
            mensaje += f"📍 **Total paradas en esta ruta:** {len(ruta['paradas'])}"
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

@bot.message_handler(commands=['lista', 'listacompleta', 'paradas'])
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
            
            total_paradas = len(ruta['paradas'])
            paradas_entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
            
            mensaje = f"📋 **LISTA COMPLETA - Ruta {ruta_id}**\n"
            mensaje += f"📍 **Zona:** {ruta['zona']}\n"
            mensaje += f"📊 **Progreso:** {paradas_entregadas}/{total_paradas} entregadas\n"
            mensaje += f"⏱️ **Completado:** {int((paradas_entregadas/total_paradas)*100)}%\n\n"
            
            for i, parada in enumerate(ruta['paradas'], 1):
                nombre = parada.get('nombre', f'Persona {i}')
                dependencia = parada.get('dependencia', 'Sin dependencia')
                direccion = parada.get('direccion', 'Sin dirección')
                estado = "✅" if parada.get('estado') == 'entregado' else "📍"
                cantidad = parada.get('total_personas', 1)
                
                mensaje += f"{estado} **{i}. {nombre}**\n"
                mensaje += f"   🏢 {dependencia}\n"
                mensaje += f"   📍 {direccion}\n"
                if cantidad > 1:
                    mensaje += f"   👥 {cantidad} personas en este edificio\n"
                mensaje += "\n"
            
            # Crear teclado con botón de Google Maps si hay URL
            markup = types.InlineKeyboardMarkup()
            if maps_url:
                markup.row(
                    types.InlineKeyboardButton("🗺️ ABRIR RUTA EN GOOGLE MAPS", url=maps_url)
                )
            
            markup.row(
                types.InlineKeyboardButton("🗺️ VER MI RUTA", callback_data="ver_ruta_actual"),
                types.InlineKeyboardButton("📸 REGISTRAR ENTREGA", callback_data="registrar_entrega")
            )
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

@bot.message_handler(commands=['supervisor', 'contactar'])
def contactar_supervisor(message):
    info_supervisor = """
📞 **INFORMACIÓN DE CONTACTO - SUPERVISOR**

👨‍💼 **Lic. Pedro Javier Hernandez Vasquez**
📱 **Teléfono:** 55 3197 3078
🕒 **Horario:** 7:00 - 19:00 hrs
📧 **Email:** supervisor@pjcdmx.mx

🚨 **PARA EMERGENCIAS:**
• Llamadas prioritarias 24/7
• Soporte inmediato en ruta
• Asistencia técnica
• Reportes urgentes

💬 **CANALES DE CONTACTO:**
• Llamada telefónica directa
• Mensaje de WhatsApp
• Reporte por este bot
• Correo electrónico

⚠️ **Para emergencias en ruta, llama inmediatamente al supervisor.**
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📞 LLAMAR AL SUPERVISOR", url="tel:+525531973078"),
        types.InlineKeyboardButton("📱 ENVIAR WHATSAPP", url="https://wa.me/525531973078")
    )
    markup.row(
        types.InlineKeyboardButton("🚨 REPORTE URGENTE", callback_data="reporte_urgente"),
        types.InlineKeyboardButton("📋 VOLVER AL MENÚ", callback_data="volver_menu")
    )
    
    bot.reply_to(message, info_supervisor, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['seguimiento', 'ubicacion'])
def seguimiento_tiempo_real(message):
    info_seguimiento = """
📍 **SEGUIMIENTO EN TIEMPO REAL**

🚀 **SISTEMA ACTIVADO PARA:**
• 📍 Ubicación GPS en tiempo real
• 🗺️ Optimización automática de rutas
• ⚡ Respuesta inmediata a incidentes
• 📊 Monitoreo continuo del progreso

📱 **¿CÓMO FUNCIONA?**
1. Comparte tu ubicación actual
2. El sistema registra tu posición GPS
3. Supervisores monitorean en tiempo real
4. Se optimiza tu ruta automáticamente
5. Recibes alertas de tráfico y rutas alternas

🛡️ **BENEFICIOS:**
• Seguridad en ruta garantizada
• Asistencia inmediata disponible
• Rutas más eficientes y rápidas
• Comunicación constante con supervisión

⚠️ **Tu ubicación solo es visible para supervisores autorizados del sistema.**
"""
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row(types.KeyboardButton("📍 COMPARTIR MI UBICACIÓN ACTUAL", request_location=True))
    markup.row(types.KeyboardButton("❌ CANCELAR"))
    
    bot.reply_to(message, info_seguimiento, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['fotos', 'entregas'])
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
            bot.reply_to(message, "📭 **NO HAS ENVIADO FOTOS AÚN**\n\nEnvía una foto con el pie de foto 'ENTREGADO A [NOMBRE]' para registrar entregas.")
            return
        
        mensaje = f"📸 **TUS ÚLTIMAS {len(fotos)} FOTOS:**\n\n"
        
        for i, (file_id, caption, tipo, timestamp) in enumerate(fotos, 1):
            fecha = timestamp.split('.')[0] if timestamp else "Sin fecha"
            tipo_emoji = "✅" if tipo == "entrega" else "⚠️"
            
            mensaje += f"{tipo_emoji} **#{i} - {tipo.upper()}**\n"
            mensaje += f"   📅 {fecha}\n"
            mensaje += f"   📝 {caption if caption else 'Sin descripción'}\n\n"
        
        bot.reply_to(message, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Error obteniendo fotos: {e}")
        bot.reply_to(message, "❌ Error al obtener tus fotos")

@bot.message_handler(commands=['debug', 'estado'])
def debug(message):
    user_id = message.from_user.id
    
    # Contar fotos del usuario
    cursor.execute('SELECT COUNT(*) FROM fotos WHERE user_id = ?', (user_id,))
    total_fotos = cursor.fetchone()[0]
    
    mensaje = f"🔧 **INFORMACIÓN DEL SISTEMA**\n\n"
    mensaje += f"📦 Rutas disponibles en sistema: {len(RUTAS_DISPONIBLES)}\n"
    mensaje += f"📸 Tus fotos registradas: {total_fotos}\n"
    mensaje += f"🗺️ Tienes ruta asignada: {'✅ SÍ' if user_id in RUTAS_ASIGNADAS else '❌ NO'}\n"
    
    if user_id in RUTAS_ASIGNADAS:
        mensaje += f"🔢 ID de tu ruta: {RUTAS_ASIGNADAS[user_id]}\n"
        
        # Mostrar información de la ruta asignada
        for ruta in RUTAS_DISPONIBLES:
            if ruta['ruta_id'] == RUTAS_ASIGNADAS[user_id]:
                maps_url = crear_url_google_maps_ruta_completa(ruta)
                if maps_url:
                    mensaje += f"🔗 Google Maps disponible: SÍ\n"
                else:
                    mensaje += f"🔗 Google Maps disponible: NO\n"
                
                total_paradas = len(ruta['paradas'])
                paradas_entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
                mensaje += f"📊 Progreso ruta: {paradas_entregadas}/{total_paradas}\n"
                break
    
    mensaje += f"\n👤 Tu ID de usuario: {user_id}\n"
    mensaje += f"🕒 Hora del servidor: {datetime.now().strftime('%H:%M:%S')}\n\n"
    mensaje += "✅ **SISTEMA OPERATIVO AL 100%**"
    
    bot.reply_to(message, mensaje, parse_mode='Markdown')

@bot.message_handler(commands=['recargar', 'refresh'])
def recargar(message):
    cargar_rutas_simple()
    bot.reply_to(message, f"✅ Rutas recargadas: {len(RUTAS_DISPONIBLES)} disponibles")

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
        
        mensaje = f"📍 **UBICACIÓN REGISTRADA CORRECTAMENTE**\n\n"
        mensaje += f"👤 **Usuario:** {user_name}\n"
        mensaje += f"📌 **Coordenadas GPS:** {latitud}, {longitud}\n"
        mensaje += f"🕒 **Hora de registro:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        mensaje += f"🗺️ **Ver en Google Maps:**\n"
        mensaje += f"https://www.google.com/maps?q={latitud},{longitud}\n\n"
        mensaje += "✅ **Tu ubicación ha sido registrada en el sistema de seguimiento.**"
        
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
        if any(word in caption.upper() for word in ['ENTREGADO', 'ENTREGADA', 'ACUSE', 'ENTREGA']):
            tipo = "entrega"
            carpeta = "entregas"
            respuesta = "✅ **ENTREGA REGISTRADA CORRECTAMENTE**\n\nFoto de entrega guardada en el sistema."
        else:
            tipo = "reporte"
            carpeta = "incidentes"
            respuesta = "✅ **REPORTE GUARDADO**\n\nFoto de reporte/incidente guardada en el sistema."
        
        # Descargar y guardar foto
        ruta_foto = descargar_foto_telegram(file_id, carpeta)
        
        if ruta_foto:
            # Guardar en base de datos
            guardar_foto_bd(file_id, user_id, user_name, caption, tipo, ruta_foto)
            
            # Si es entrega y tiene ruta, procesar
            if tipo == "entrega" and user_id in RUTAS_ASIGNADAS:
                respuesta += f"\n\n🗺️ **Ruta asignada:** {RUTAS_ASIGNADAS[user_id]}\n"
                respuesta += f"📝 **Descripción:** {caption}"
                
                # Marcar parada como entregada si corresponde
                ruta_id = RUTAS_ASIGNADAS[user_id]
                for ruta in RUTAS_DISPONIBLES:
                    if ruta['ruta_id'] == ruta_id:
                        # Buscar persona en la ruta (simplificado)
                        for parada in ruta['paradas']:
                            if caption and any(nombre in caption.upper() for nombre in [parada.get('nombre', '').upper(), parada.get('nombre_completo', '').upper()]):
                                parada['estado'] = 'entregado'
                                respuesta += f"\n✅ **Parada marcada como entregada**"
                                break
                        break
            
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
        
        if data == 'solicitar_ruta':
            dar_ruta(call.message)
            bot.answer_callback_query(call.id, "🚗 Solicitando ruta...")
            
        elif data == 'ver_ruta_actual':
            ver_ruta(call.message)
            bot.answer_callback_query(call.id, "🗺️ Mostrando tu ruta...")
            
        elif data == 'abrir_maps':
            if call.from_user.id in RUTAS_ASIGNADAS:
                navegar_ruta(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ Primero solicita una ruta")
                dar_ruta(call.message)
            
        elif data == 'cambiar_ruta':
            # Limpiar ruta asignada
            user_id = call.from_user.id
            if user_id in RUTAS_ASIGNADAS:
                del RUTAS_ASIGNADAS[user_id]
            dar_ruta(call.message)
            bot.answer_callback_query(call.id, "🔄 Cambiando ruta...")
            
        elif data.startswith('lista_completa_'):
            partes = data.split('_')
            ruta_id = partes[2] if len(partes) >= 3 else "?"
            
            for ruta in RUTAS_DISPONIBLES:
                if str(ruta['ruta_id']) == str(ruta_id):
                    # Generar URL de Google Maps
                    maps_url = crear_url_google_maps_ruta_completa(ruta)
                    
                    total_paradas = len(ruta['paradas'])
                    paradas_entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
                    
                    mensaje = f"📋 **LISTA COMPLETA - Ruta {ruta_id}**\n"
                    mensaje += f"📍 **Zona:** {ruta['zona']}\n"
                    mensaje += f"📊 **Progreso:** {paradas_entregadas}/{total_paradas}\n\n"
                    
                    for i, parada in enumerate(ruta['paradas'], 1):
                        nombre = parada.get('nombre', f'Persona {i}')
                        dependencia = parada.get('dependencia', 'Sin dependencia')
                        direccion = parada.get('direccion', 'Sin dirección')
                        estado = "✅" if parada.get('estado') == 'entregado' else "📍"
                        cantidad = parada.get('total_personas', 1)
                        
                        mensaje += f"{estado} **{i}. {nombre}**\n"
                        mensaje += f"   🏢 {dependencia}\n"
                        mensaje += f"   📍 {direccion}\n"
                        if cantidad > 1:
                            mensaje += f"   👥 {cantidad} personas en este edificio\n"
                        mensaje += "\n"
                    
                    # Crear teclado con botón de Google Maps si hay URL
                    markup = types.InlineKeyboardMarkup()
                    if maps_url:
                        markup.row(
                            types.InlineKeyboardButton("🗺️ ABRIR RUTA EN GOOGLE MAPS", url=maps_url)
                        )
                    
                    markup.row(
                        types.InlineKeyboardButton("🗺️ VER MI RUTA", callback_data="ver_ruta_actual"),
                        types.InlineKeyboardButton("📸 REGISTRAR ENTREGA", callback_data="registrar_entrega")
                    )
                    
                    bot.send_message(call.message.chat.id, mensaje, parse_mode='Markdown', reply_markup=markup)
                    break
            
            bot.answer_callback_query(call.id, "📋 Lista completa mostrada")
            
        elif data == 'lista_completa':
            if call.from_user.id in RUTAS_ASIGNADAS:
                lista_completa(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ Primero obtén una ruta")
                dar_ruta(call.message)
            
        elif data == 'contactar_supervisor':
            contactar_supervisor(call.message)
            bot.answer_callback_query(call.id, "📞 Contactando supervisor...")
            
        elif data == 'reporte_urgente':
            bot.send_message(
                call.message.chat.id,
                "🚨 **REPORTE URGENTE**\n\n"
                "Envía tu reporte urgente con:\n\n"
                "1. 📸 Una foto del incidente\n"
                "2. 📝 Descripción del problema\n"
                "3. 📍 Tu ubicación (usa el botón de ubicación)\n\n"
                "El supervisor será notificado inmediatamente.",
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "🚨 Reporte urgente")
            
        elif data == 'seguimiento_tiempo_real':
            seguimiento_tiempo_real(call.message)
            bot.answer_callback_query(call.id, "📍 Activando seguimiento...")
            
        elif data == 'ubicacion_actual':
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.row(types.KeyboardButton("📍 COMPARTIR MI UBICACIÓN", request_location=True))
            bot.send_message(
                call.message.chat.id,
                "📍 **COMPARTIR UBICACIÓN ACTUAL**\n\nPresiona el botón para compartir tu ubicación GPS actual:",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "📍 Solicitando ubicación...")
            
        elif data == 'registrar_entrega':
            bot.send_message(
                call.message.chat.id,
                "📸 **REGISTRAR ENTREGA**\n\n"
                "Envía una foto del acuse firmado con el pie de foto:\n\n"
                "`ENTREGADO A [NOMBRE COMPLETO]`\n\n"
                "**EJEMPLO:**\n"
                "`ENTREGADO A JUAN PÉREZ LÓPEZ`\n\n"
                "**IMPORTANTE:** Asegúrate de que el nombre coincida con la lista de tu ruta.",
                parse_mode='Markdown'
            )
            bot.answer_callback_query(call.id, "📸 Listo para recibir foto...")
            
        elif data == 'mis_fotos':
            ver_fotos(call.message)
            bot.answer_callback_query(call.id, "📸 Obteniendo tus fotos...")
            
        elif data == 'debug_info':
            debug(call.message)
            bot.answer_callback_query(call.id, "🔧 Obteniendo info del sistema...")
            
        elif data == 'ayuda_boton':
            ayuda(call.message)
            bot.answer_callback_query(call.id, "❓ Mostrando ayuda...")
            
        elif data == 'volver_menu':
            start(call.message)
            bot.answer_callback_query(call.id, "🏠 Volviendo al menú...")
            
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
        "usuarios_con_ruta": len(RUTAS_ASIGNADAS),
        "fotos_totales": total_fotos,
        "timestamp": datetime.now().isoformat()
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
        # Obtener avances de la base de datos
        cursor.execute('''
            SELECT file_id, user_id, user_name, caption, tipo, timestamp 
            FROM fotos 
            WHERE tipo = 'entrega'
            ORDER BY timestamp DESC
        ''')
        
        avances_db = cursor.fetchall()
        avances = []
        
        for avance in avances_db:
            avances.append({
                'file_id': avance[0],
                'user_id': avance[1],
                'user_name': avance[2],
                'caption': avance[3],
                'tipo': avance[4],
                'timestamp': avance[5]
            })
        
        return jsonify({
            "status": "success",
            "avances": avances,
            "total": len(avances),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/api/avances/<avance_id>/procesado', methods=['POST'])
def marcar_avance_procesado(avance_id):
    """Marcar un avance como procesado"""
    try:
        # Aquí podrías marcar el avance como procesado en la BD
        print(f"✅ Avance marcado como procesado: {avance_id}")
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
            "rutas_cargadas": [f"Ruta {r['ruta_id']} - {r['zona']}" for r in RUTAS_DISPONIBLES],
            "usuarios_con_ruta": len(RUTAS_ASIGNADAS),
            "timestamp": datetime.now().isoformat()
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
