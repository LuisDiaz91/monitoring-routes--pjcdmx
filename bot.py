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
                    print(f"   📊 {len(ruta.get('paradas', []))} paradas")
                    
                    # Debug: mostrar información de la ruta
                    if ruta.get('google_maps_url'):
                        print(f"   🗺️ URL Google Maps disponible")
                        
                except Exception as e:
                    print(f"❌ Error con {archivo}: {e}")
    
    # Si no hay rutas, crear una de prueba con múltiples paradas
    if len(RUTAS_DISPONIBLES) == 0:
        ruta_prueba = {
            "ruta_id": 1,
            "zona": "ZONA CENTRO",
            "origen": "TSJCDMX - Niños Héroes 150, Ciudad de México",
            "google_maps_url": "https://www.google.com/maps/dir/?api=1&origin=TSJCDMX%20-%20Ni%C3%B1os%20H%C3%A9roes%20150%2C%20Ciudad%20de%20M%C3%A9xico&destination=Av%20Principal%20789%2C%20Ciudad%20de%20M%C3%A9xico&waypoints=Av%20Principal%20123%2C%20Ciudad%20de%20M%C3%A9xico%7CCalle%20456%2C%20Ciudad%20de%20M%C3%A9xico&travelmode=driving&dir_action=navigate",
            "paradas": [
                {
                    "orden": 1,
                    "nombre": "EDIFICIO PRINCIPAL",
                    "dependencia": "OFICINA CENTRAL",
                    "direccion": "Av Principal 123, Ciudad de México",
                    "total_personas": 3,
                    "personas": [
                        {"nombre": "JUAN PÉREZ", "direccion": "Av Principal 123, Ciudad de México"},
                        {"nombre": "MARÍA GARCÍA", "direccion": "Av Principal 123, Ciudad de México"},
                        {"nombre": "CARLOS LÓPEZ", "direccion": "Av Principal 123, Ciudad de México"}
                    ]
                },
                {
                    "orden": 2,
                    "nombre": "EDIFICIO LEGAL",
                    "dependencia": "DEPTO LEGAL", 
                    "direccion": "Calle 456, Ciudad de México",
                    "total_personas": 2,
                    "personas": [
                        {"nombre": "ANA MARTÍNEZ", "direccion": "Calle 456, Ciudad de México"},
                        {"nombre": "LUIS HERNÁNDEZ", "direccion": "Calle 456, Ciudad de México"}
                    ]
                },
                {
                    "orden": 3,
                    "nombre": "EDIFICIO ADMINISTRATIVO",
                    "dependencia": "RECURSOS HUMANOS",
                    "direccion": "Av Principal 789, Ciudad de México",
                    "total_personas": 4,
                    "personas": [
                        {"nombre": "PEDRO GÓMEZ", "direccion": "Av Principal 789, Ciudad de México"},
                        {"nombre": "LAURA RODRÍGUEZ", "direccion": "Av Principal 789, Ciudad de México"},
                        {"nombre": "JOSÉ SÁNCHEZ", "direccion": "Av Principal 789, Ciudad de México"},
                        {"nombre": "MÓNICA FLORES", "direccion": "Av Principal 789, Ciudad de México"}
                    ]
                }
            ]
        }
        with open('rutas_telegram/Ruta_1_CENTRO.json', 'w') as f:
            json.dump(ruta_prueba, f)
        RUTAS_DISPONIBLES.append(ruta_prueba)
        print("✅ Ruta de prueba creada (3 edificios, 9 personas)")
    
    print(f"📦 Rutas listas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)

def crear_url_google_maps_ruta_completa(ruta):
    """
    Crear URL de Google Maps con todas las paradas de la ruta
    VERSIÓN SIMPLIFICADA Y CORREGIDA
    """
    try:
        if not ruta.get('paradas') or len(ruta['paradas']) == 0:
            print("❌ No hay paradas en la ruta")
            return None
        
        # Usar el origen de la ruta o uno por defecto
        origen = ruta.get('origen', 'TSJCDMX - Niños Héroes 150, Ciudad de México')
        
        # Obtener todas las direcciones de las paradas
        direcciones = []
        
        for parada in ruta['paradas']:
            # Primero intentar dirección del edificio
            direccion = parada.get('direccion', '')
            
            # Si no hay, buscar en la primera persona
            if not direccion or direccion in ['', 'Sin dirección', 'N/A']:
                if parada.get('personas') and len(parada['personas']) > 0:
                    direccion = parada['personas'][0].get('direccion', '')
            
            # Si aún no hay, usar un valor por defecto
            if not direccion or direccion in ['', 'Sin dirección', 'N/A']:
                direccion = f"Ciudad de México, Edificio {parada.get('orden', '')}"
            
            # Agregar Ciudad de México si no está
            if 'ciudad de méxico' not in direccion.lower() and 'cdmx' not in direccion.lower():
                direccion += ", Ciudad de México"
            
            direcciones.append(urllib.parse.quote(direccion))
        
        print(f"📍 Direcciones encontradas: {len(direcciones)}")
        
        if len(direcciones) < 2:
            print("❌ Se necesitan al menos 2 direcciones para crear ruta")
            return None
        
        # Construir URL de Google Maps
        base_url = "https://www.google.com/maps/dir/?api=1"
        
        # Origen
        origen_codificado = urllib.parse.quote(origen)
        url = f"{base_url}&origin={origen_codificado}"
        
        # Destino (última parada)
        destino_codificado = direcciones[-1]
        url += f"&destination={destino_codificado}"
        
        # Waypoints (todas las paradas excepto la última)
        if len(direcciones) > 1:
            waypoints_str = "|".join(direcciones[:-1])
            url += f"&waypoints={waypoints_str}"
        
        # Agregar optimización
        url += "&travelmode=driving"
        url += "&dir_action=navigate"
        
        print(f"🗺️ URL Google Maps generada (longitud: {len(url)})")
        return url
        
    except Exception as e:
        print(f"❌ Error creando URL de Google Maps: {str(e)}")
        import traceback
        traceback.print_exc()
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
# HANDLERS DE TELEGRAM - MEJORADOS
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
    
    # Buscar ruta disponible (puede implementar lógica de asignación más compleja)
    ruta = RUTAS_DISPONIBLES[0]
    RUTAS_ASIGNADAS[user_id] = ruta['ruta_id']
    
    print(f"✅ Ruta {ruta['ruta_id']} asignada a {user_name}")
    
    # Intentar obtener URL de Google Maps
    maps_url = None
    
    # Primero usar la URL que ya viene en la ruta
    if ruta.get('google_maps_url'):
        maps_url = ruta['google_maps_url']
        print(f"✅ Usando URL existente de Google Maps")
    else:
        # Si no hay, generarla
        maps_url = crear_url_google_maps_ruta_completa(ruta)
        if maps_url:
            print(f"✅ URL Google Maps generada exitosamente")
        else:
            print(f"❌ No se pudo generar URL de Google Maps")
    
    # Crear mensaje
    markup = types.InlineKeyboardMarkup()
    
    if maps_url:
        # BOTÓN PRINCIPAL - GOOGLE MAPS
        markup.row(
            types.InlineKeyboardButton("📍 ABRIR RUTA EN GOOGLE MAPS", url=maps_url)
        )
        print(f"🔗 URL Google Maps: {maps_url[:100]}...")
    
    # Botones secundarios
    markup.row(
        types.InlineKeyboardButton("📋 VER LISTA DE EDIFICIOS", callback_data=f"lista_completa_{ruta['ruta_id']}"),
        types.InlineKeyboardButton("📍 MI UBICACIÓN", callback_data="ubicacion_actual")
    )
    
    # Calcular estadísticas
    total_edificios = len(ruta.get('paradas', []))
    total_personas = sum(parada.get('total_personas', 1) for parada in ruta.get('paradas', []))
    
    mensaje = f"✅ **RUTA ASIGNADA EXITOSAMENTE**\n\n"
    mensaje += f"👤 **Repartidor:** {user_name}\n"
    mensaje += f"📊 **RUTA:** {ruta.get('zona', 'SIN ZONA')} - ID: {ruta['ruta_id']}\n"
    mensaje += f"🏢 **EDIFICIOS:** {total_edificios}\n"
    mensaje += f"👥 **PERSONAS:** {total_personas}\n\n"
    
    if maps_url:
        mensaje += "🚗 **HAZ CLIC EN EL BOTÓN 'ABRIR RUTA EN GOOGLE MAPS' PARA:**\n"
        mensaje += "• Ver la ruta completa optimizada\n"
        mensaje += "• Obtener indicaciones paso a paso\n"
        mensaje += "• Navegar con Google Maps\n\n"
    else:
        mensaje += "⚠️ **Google Maps no disponible para esta ruta**\n\n"
    
    # Mostrar primeros 3 edificios
    if total_edificios > 0:
        mensaje += "🏢 **PRIMEROS EDIFICIOS:**\n"
        for i, parada in enumerate(ruta.get('paradas', [])[:3], 1):
            nombre_edificio = parada.get('nombre', f'Edificio {i}')
            direccion = parada.get('direccion', 'Sin dirección')
            personas = parada.get('total_personas', 1)
            
            mensaje += f"\n**📍 {i}. {nombre_edificio}**\n"
            mensaje += f"   📍 {direccion[:50]}...\n"
            mensaje += f"   👥 {personas} persona{'s' if personas > 1 else ''}\n"
    
    bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)

# ... (el resto del bot se mantiene igual, solo asegúrate de que las funciones ver_ruta, navegar_ruta, etc. usen la misma lógica)

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
            # Intentar obtener URL de Google Maps
            maps_url = None
            
            # Primero usar la URL que ya viene en la ruta
            if ruta.get('google_maps_url'):
                maps_url = ruta['google_maps_url']
            else:
                # Si no hay, generarla
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
                types.InlineKeyboardButton("📋 VER LISTA DE EDIFICIOS", callback_data=f"lista_completa_{ruta_id}"),
                types.InlineKeyboardButton("🗺️ VER MI RUTA", callback_data="ver_ruta_actual")
            )
            
            mensaje = "🚗 **NAVEGACIÓN CON GOOGLE MAPS**\n\n"
            mensaje += "Haz clic en el botón para abrir Google Maps con **todos los edificios** en secuencia.\n\n"
            mensaje += "✅ **VENTAJAS:**\n"
            mensaje += "• 🗺️ Ruta optimizada automáticamente\n"
            mensaje += "• 📍 Indicaciones paso a paso\n"
            mensaje += "• ⏱️ Tiempos de viaje estimados\n"
            mensaje += "• 🎧 Navegación por voz disponible\n"
            mensaje += "• 📱 Funciona en móvil y computadora\n\n"
            mensaje += f"🏢 **Total edificios en esta ruta:** {len(ruta['paradas'])}"
            
            bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

# ... (mantén el resto del código igual)

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
    
    # Contar estadísticas de rutas
    total_edificios = 0
    total_personas = 0
    
    for ruta in RUTAS_DISPONIBLES:
        total_edificios += len(ruta.get('paradas', []))
        for parada in ruta.get('paradas', []):
            total_personas += parada.get('total_personas', 1)
    
    return jsonify({
        "status": "ok",
        "rutas": len(RUTAS_DISPONIBLES),
        "edificios_totales": total_edificios,
        "personas_totales": total_personas,
        "usuarios_con_ruta": len(RUTAS_ASIGNADAS),
        "fotos_totales": total_fotos,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "rutas_cargadas": len(RUTAS_DISPONIBLES),
        "bot_token_configured": bool(TOKEN),
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
        
        # Verificar que sea una ruta con múltiples edificios
        if len(datos_ruta.get('paradas', [])) < 2:
            print(f"⚠️ Ruta {ruta_id} tiene menos de 2 edificios")
        
        # Generar URL de Google Maps para esta ruta
        maps_url = crear_url_google_maps_ruta_completa(datos_ruta)
        if maps_url:
            datos_ruta['google_maps_url'] = maps_url
            print(f"✅ URL Google Maps generada para ruta {ruta_id}")
        else:
            print(f"⚠️ No se pudo generar URL Google Maps para ruta {ruta_id}")
        
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(datos_ruta, f, indent=2, ensure_ascii=False)
        
        # Recargar rutas automáticamente
        cargar_rutas_simple()
        
        print(f"✅ Ruta {ruta_id} recibida via API y guardada")
        
        return jsonify({
            "status": "success", 
            "ruta_id": ruta_id,
            "archivo": archivo_ruta,
            "edificios": len(datos_ruta.get('paradas', [])),
            "google_maps_url": maps_url if maps_url else "No generada",
            "rutas_disponibles": len(RUTAS_DISPONIBLES)
        })
        
    except Exception as e:
        print(f"❌ Error en API /api/rutas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ... (mantén el resto del código igual)

# =============================================================================
# INICIALIZACIÓN
# =============================================================================

print("🎯 CARGANDO SISTEMA COMPLETO CON GOOGLE MAPS INTEGRADO...")
cargar_rutas_simple()
print("✅ BOT LISTO - GOOGLE MAPS ACTIVADO")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
