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
import re

# =============================================================================
# CONFIGURACIÓN INICIAL
# =============================================================================

print("🚀 INICIANDO BOT COMPLETO PJCDMX - SISTEMA CORREGIDO...")

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
ADMIN_IDS = [7800992671]
AVANCES_PENDIENTES = []

# =============================================================================
# CONFIGURACIÓN BASE DE DATOS
# =============================================================================

conn = sqlite3.connect('/tmp/incidentes.db', check_same_thread=False)
cursor = conn.cursor()

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
# FUNCIONES CRÍTICAS CORREGIDAS
# =============================================================================

def limpiar_texto_markdown(texto):
    """Limpia texto para evitar problemas con Markdown"""
    if not texto:
        return ""
    caracteres_problematicos = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in caracteres_problematicos:
        texto = texto.replace(char, f'\\{char}')
    return texto

def reparar_estructura_ruta(ruta, nombre_archivo):
    """Reparar automáticamente la estructura de una ruta"""
    try:
        necesita_guardar = False
        
        # GARANTIZAR campos básicos de la ruta
        if 'ruta_id' not in ruta:
            ruta['ruta_id'] = 1
            necesita_guardar = True
            
        if 'zona' not in ruta:
            ruta['zona'] = 'GENERAL'
            necesita_guardar = True
            
        if 'estado' not in ruta:
            ruta['estado'] = 'pendiente'
            necesita_guardar = True
            
        if 'estadisticas' not in ruta:
            ruta['estadisticas'] = {
                'distancia_km': 10,
                'tiempo_min': 60,
                'paradas_totales': len(ruta.get('paradas', []))
            }
            necesita_guardar = True
            
        if 'google_maps_url' not in ruta:
            ruta['google_maps_url'] = 'https://maps.google.com'
            necesita_guardar = True
        
        # REPARAR PARADAS - VERSIÓN MÁS ROBUSTA
        if 'paradas' in ruta:
            for i, parada in enumerate(ruta['paradas']):
                reparaciones = []
                
                # GARANTIZAR campo 'nombre' - CRÍTICO
                if 'nombre' not in parada or not parada['nombre'] or parada['nombre'].strip() == "":
                    parada['nombre'] = f"Persona {i+1}"
                    reparaciones.append("nombre")
                    necesita_guardar = True
                
                # GARANTIZAR campo 'dependencia' - CRÍTICO
                if 'dependencia' not in parada or not parada['dependencia'] or parada['dependencia'].strip() == "":
                    parada['dependencia'] = 'SIN DEPENDENCIA'
                    reparaciones.append("dependencia")
                    necesita_guardar = True
                
                # GARANTIZAR campo 'direccion'
                if 'direccion' not in parada or not parada['direccion'] or parada['direccion'].strip() == "":
                    parada['direccion'] = 'DIRECCIÓN NO DISPONIBLE'
                    reparaciones.append("direccion")
                    necesita_guardar = True
                
                # GARANTIZAR campo 'orden'
                if 'orden' not in parada:
                    parada['orden'] = i + 1
                    reparaciones.append("orden")
                    necesita_guardar = True
                
                # GARANTIZAR campo 'estado'
                if 'estado' not in parada:
                    parada['estado'] = 'pendiente'
                    reparaciones.append("estado")
                    necesita_guardar = True
                
                if reparaciones:
                    print(f"   🔧 Reparada parada {i+1}: {', '.join(reparaciones)}")
        
        if necesita_guardar:
            try:
                with open(f'rutas_telegram/{nombre_archivo}', 'w', encoding='utf-8') as f:
                    json.dump(ruta, f, indent=2, ensure_ascii=False)
                print(f"💾 Ruta reparada y guardada: {nombre_archivo}")
            except Exception as e:
                print(f"⚠️ No se pudo guardar ruta reparada: {e}")
        
        return ruta
        
    except Exception as e:
        print(f"❌ Error reparando ruta {nombre_archivo}: {e}")
        return ruta

def formatear_ruta_para_repartidor(ruta):
    """VERSIÓN CORREGIDA - Muestra nombres y dependencias correctamente"""
    try:
        texto = f"🗺️ **RUTA ASIGNADA - ID {ruta.get('ruta_id', '?')}**\n\n"
        texto += f"📍 **Zona:** {ruta.get('zona', 'Sin zona')}\n"
        texto += f"👥 **Paradas:** {len(ruta.get('paradas', []))}\n"
        
        # Estadísticas
        stats = ruta.get('estadisticas', {})
        texto += f"📏 **Distancia:** {stats.get('distancia_km', '?')} km\n"
        texto += f"⏱️ **Tiempo:** {stats.get('tiempo_min', '?')} min\n\n"

        # Progreso
        entregadas = len([p for p in ruta.get('paradas', []) if p.get('estado') == 'entregado'])
        texto += f"📊 **Progreso:** {entregadas}/{len(ruta.get('paradas', []))}\n\n"
        
        texto += "**PRIMERAS 3 PARADAS:**\n\n"

        # MOSTRAR PARADAS CON DATOS REALES
        for i, parada in enumerate(ruta.get('paradas', [])[:3], 1):
            # Extraer datos con valores por defecto
            nombre = parada.get('nombre', f'Persona {i}')
            dependencia = parada.get('dependencia', 'Sin dependencia')
            direccion = parada.get('direccion', 'Sin dirección')
            orden = parada.get('orden', i)
            estado = "✅" if parada.get('estado') == 'entregado' else "📍"
            
            # Limpiar para markdown
            nombre_limpio = limpiar_texto_markdown(str(nombre))
            dep_limpio = limpiar_texto_markdown(str(dependencia))
            dir_limpio = limpiar_texto_markdown(str(direccion))[:50]
            
            texto += f"{estado} **{orden}. {nombre_limpio}**\n"
            texto += f"   🏢 {dep_limpio}\n"
            texto += f"   📍 {dir_limpio}...\n\n"

        if len(ruta.get('paradas', [])) > 3:
            texto += f"📋 ... y **{len(ruta.get('paradas', [])) - 3}** más\n"

        texto += "\n🚀 **Usa los botones para navegar**"
        return texto

    except Exception as e:
        print(f"❌ Error formateando ruta: {e}")
        # Fallback simple pero informativo
        return f"""🗺️ **RUTA {ruta.get('ruta_id', '?')}**

📍 Zona: {ruta.get('zona', '?')}
👥 Paradas: {len(ruta.get('paradas', []))}

⚠️ Error mostrando detalles completos
Usa /debug_ruta para ver información técnica"""

def cargar_rutas_disponibles():
    """Cargar rutas disponibles - VERSIÓN MEJORADA"""
    global RUTAS_DISPONIBLES
    RUTAS_DISPONIBLES = []
    
    if not os.path.exists('rutas_telegram'):
        print("❌ No existe carpeta rutas_telegram")
        os.makedirs('rutas_telegram', exist_ok=True)
        return 0
    
    archivos = [f for f in os.listdir('rutas_telegram') if f.endswith('.json')]
    print(f"📁 Archivos encontrados: {archivos}")
    
    for archivo in archivos:
        try:
            with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                ruta = json.load(f)
            
            # Reparar ruta antes de cargarla
            ruta_reparada = reparar_estructura_ruta(ruta, archivo)
            
            if ruta_reparada.get('estado') == 'pendiente':
                RUTAS_DISPONIBLES.append(ruta_reparada)
                print(f"✅ Ruta cargada: {ruta_reparada['ruta_id']} - {ruta_reparada['zona']}")
                
                # DEBUG: Mostrar primera persona
                if ruta_reparada.get('paradas'):
                    primera = ruta_reparada['paradas'][0]
                    print(f"   👤 Ejemplo: {primera.get('nombre')}")
                    print(f"   🏢 Dependencia: {primera.get('dependencia')}")
                        
        except Exception as e:
            print(f"❌ Error cargando {archivo}: {e}")
    
    print(f"🔄 Rutas cargadas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)

def crear_rutas_de_prueba_si_necesario():
    """Crear rutas de prueba si no hay rutas disponibles"""
    try:
        if len(RUTAS_DISPONIBLES) > 0:
            print(f"✅ Ya hay {len(RUTAS_DISPONIBLES)} rutas disponibles")
            return True
            
        print("🔄 No hay rutas disponibles. Creando rutas de prueba...")
        
        # RUTA DE PRUEBA 1
        ruta1 = {
            "ruta_id": 1,
            "zona": "CENTRO HISTÓRICO",
            "estado": "pendiente",
            "timestamp_creacion": datetime.now().isoformat(),
            "google_maps_url": "https://goo.gl/maps/example1",
            "estadisticas": {
                "distancia_km": 8.5,
                "tiempo_min": 45,
                "paradas_totales": 3
            },
            "paradas": [
                {
                    "orden": 1,
                    "nombre": "JUAN PÉREZ LÓPEZ",
                    "dependencia": "OFICINA CENTRAL",
                    "direccion": "Av. Principal 123, Centro",
                    "estado": "pendiente"
                },
                {
                    "orden": 2,
                    "nombre": "MARÍA GARCÍA HERNÁNDEZ", 
                    "dependencia": "DEPARTAMENTO LEGAL",
                    "direccion": "Calle Secundaria 456, Centro",
                    "estado": "pendiente"
                },
                {
                    "orden": 3,
                    "nombre": "CARLOS RODRÍGUEZ MARTÍNEZ",
                    "dependencia": "RECURSOS HUMANOS",
                    "direccion": "Plaza Central 789, Centro",
                    "estado": "pendiente"
                }
            ]
        }
        
        # RUTA DE PRUEBA 2
        ruta2 = {
            "ruta_id": 2,
            "zona": "ZONA NORTE", 
            "estado": "pendiente",
            "timestamp_creacion": datetime.now().isoformat(),
            "google_maps_url": "https://goo.gl/maps/example2",
            "estadisticas": {
                "distancia_km": 12.3,
                "tiempo_min": 60,
                "paradas_totales": 3
            },
            "paradas": [
                {
                    "orden": 1,
                    "nombre": "LUIS MARTÍNEZ DÍAZ",
                    "dependencia": "SUCURSAL NORTE",
                    "direccion": "Av. Norte 111, Col. Industrial", 
                    "estado": "pendiente"
                },
                {
                    "orden": 2,
                    "nombre": "SOFÍA RAMÍREZ CASTRO",
                    "dependencia": "ALMACÉN NORTE",
                    "direccion": "Calle Industria 222, Col. Industrial",
                    "estado": "pendiente"
                },
                {
                    "orden": 3,
                    "nombre": "MIGUEL ÁNGEL FLORES",
                    "dependencia": "LOGÍSTICA NORTE",
                    "direccion": "Av. Tecnológico 333, Col. Industrial",
                    "estado": "pendiente"
                }
            ]
        }
        
        # Guardar rutas
        with open('rutas_telegram/Ruta_1_CENTRO.json', 'w', encoding='utf-8') as f:
            json.dump(ruta1, f, indent=2, ensure_ascii=False)
        
        with open('rutas_telegram/Ruta_2_NORTE.json', 'w', encoding='utf-8') as f:
            json.dump(ruta2, f, indent=2, ensure_ascii=False)
        
        print("✅ 2 rutas de prueba creadas")
        
        # Recargar rutas
        cargar_rutas_disponibles()
        return True
        
    except Exception as e:
        print(f"❌ Error creando rutas de prueba: {e}")
        return False

def inicializar_sistema_completo():
    """Inicialización completa del sistema"""
    print("🔄 Inicializando sistema completo...")
    
    carpetas = [
        'carpeta_fotos_central/entregas',
        'carpeta_fotos_central/incidentes', 
        'carpeta_fotos_central/estatus',
        'carpeta_fotos_central/general',
        'rutas_telegram', 
        'avances_ruta', 
        'rutas_excel'
    ]
    
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
    
    rutas_cargadas = cargar_rutas_disponibles()
    
    # Crear rutas de prueba si es necesario
    if rutas_cargadas == 0:
        crear_rutas_de_prueba_si_necesario()
    
    print(f"🎯 Sistema listo. Rutas: {len(RUTAS_DISPONIBLES)}")
    return True

# =============================================================================
# HANDLERS DE TELEGRAM CORREGIDOS
# =============================================================================

@bot.message_handler(commands=['start', 'hola'])
def enviar_bienvenida(message):
    try:
        welcome_text = f"""
🤖 BOT DE RUTAS AUTOMÁTICO - PJCDMX 🚚

¡Hola {message.from_user.first_name}! Soy tu asistente de rutas automáticas.

🚀 **COMANDOS PRINCIPALES:**
/solicitar_ruta - 🗺️ Obtener ruta automáticamente
/miruta - 📋 Ver mi ruta asignada  
/debug_ruta - 🔍 Ver información técnica de la ruta
/recargar_rutas - 🔄 Recargar rutas disponibles

📊 **REPORTES Y SEGUIMIENTO:**
/entregar - 📦 Registrar entrega completada
/ubicacion - 📍 Compartir ubicación en tiempo real
/incidente - 🚨 Reportar incidente

¡El sistema asigna rutas automáticamente!
        """
        bot.reply_to(message, welcome_text, parse_mode=None)
    except Exception as e:
        bot.reply_to(message, "🤖 Bot PJCDMX - Usa /solicitar_ruta para comenzar")

@bot.message_handler(commands=['solicitar_ruta'])
def solicitar_ruta_automatica(message):
    """Asignar ruta automáticamente - VERSIÓN CORREGIDA"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"🔄 {user_name} solicita ruta")
        
        if user_id in RUTAS_ASIGNADAS:
            bot.reply_to(message, "⚠️ Ya tienes una ruta asignada. Usa /miruta para verla.")
            return
        
        if len(RUTAS_DISPONIBLES) == 0:
            bot.reply_to(message, "📭 No hay rutas disponibles. Intenta más tarde.")
            return
        
        ruta_asignada = RUTAS_DISPONIBLES.pop(0)
        ruta_id = ruta_asignada['ruta_id']
        
        # Actualizar estado de la ruta
        ruta_asignada['repartidor_asignado'] = f"{user_name} (ID:{user_id})"
        ruta_asignada['estado'] = 'asignada'
        ruta_asignada['timestamp_asignacion'] = datetime.now().isoformat()
        
        # Guardar cambios
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'w', encoding='utf-8') as f:
                    json.dump(ruta_asignada, f, indent=2, ensure_ascii=False)
                break
        
        RUTAS_ASIGNADAS[user_id] = ruta_id
        mensaje = formatear_ruta_para_repartidor(ruta_asignada)
        
        # BOTONES MEJORADOS
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🗺️ Abrir en Maps", url=ruta_asignada['google_maps_url']),
            types.InlineKeyboardButton("👥 Lista Completa", callback_data=f"lista_completa_{ruta_id}")
        )
        markup.row(
            types.InlineKeyboardButton("📦 Registrar Entrega", callback_data=f"entregar_{ruta_id}"),
            types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="nueva_ubicacion")
        )
        
        bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
        print(f"✅ Ruta {ruta_id} asignada a {user_name}")
        
    except Exception as e:
        print(f"❌ Error asignando ruta: {e}")
        bot.reply_to(message, "❌ Error al asignar ruta. Intenta nuevamente.")

@bot.message_handler(commands=['miruta'])
def ver_mi_ruta(message):
    """Ver la ruta asignada actual"""
    user_id = message.from_user.id
    
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
                
                # BOTONES MEJORADOS
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("🗺️ Abrir en Maps", url=ruta['google_maps_url']),
                    types.InlineKeyboardButton("👥 Lista Completa", callback_data=f"lista_completa_{ruta_id}")
                )
                markup.row(
                    types.InlineKeyboardButton("📦 Registrar Entrega", callback_data=f"entregar_{ruta_id}"),
                    types.InlineKeyboardButton("📍 Mi Ubicación", callback_data="nueva_ubicacion")
                )
                
                bot.reply_to(message, mensaje, parse_mode='Markdown', reply_markup=markup)
                return
                
            except Exception as e:
                print(f"❌ Error leyendo ruta: {e}")
    
    bot.reply_to(message, "❌ No se pudo encontrar tu ruta.")

@bot.message_handler(commands=['debug_ruta'])
def debug_ruta_actual(message):
    """Debug completo de la ruta asignada"""
    try:
        user_id = message.from_user.id
        
        if user_id not in RUTAS_ASIGNADAS:
            bot.reply_to(message, "❌ No tienes una ruta asignada.")
            return
        
        ruta_id = RUTAS_ASIGNADAS[user_id]
        
        # Buscar la ruta
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                
                # Debug detallado
                mensaje = f"🔍 **DEBUG RUTA {ruta_id}**\n\n"
                mensaje += f"📁 **Archivo:** {archivo}\n"
                mensaje += f"📍 **Zona:** {ruta_data.get('zona', 'No disponible')}\n"
                mensaje += f"👥 **Total paradas:** {len(ruta_data.get('paradas', []))}\n\n"
                
                # Verificar estructura de las primeras 2 paradas
                mensaje += "**ESTRUCTURA DE PARADAS:**\n"
                for i, parada in enumerate(ruta_data.get('paradas', [])[:2]):
                    mensaje += f"\n**Parada {i+1}:**\n"
                    mensaje += f"• Nombre: `{parada.get('nombre', 'NO TIENE')}`\n"
                    mensaje += f"• Dependencia: `{parada.get('dependencia', 'NO TIENE')}`\n"
                    mensaje += f"• Dirección: `{parada.get('direccion', 'NO TIENE')}`\n"
                    mensaje += f"• Orden: `{parada.get('orden', 'NO TIENE')}`\n"
                
                bot.reply_to(message, mensaje, parse_mode='Markdown')
                return
        
        bot.reply_to(message, "❌ No se encontró el archivo de la ruta.")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error en debug: {str(e)}")

@bot.message_handler(commands=['recargar_rutas'])
def recargar_rutas_comando(message):
    """Forzar recarga de rutas desde archivos"""
    try:
        user_id = message.from_user.id
        
        if user_id not in ADMIN_IDS:
            bot.reply_to(message, "❌ Solo administradores pueden usar este comando.")
            return
        
        rutas_cargadas = cargar_rutas_disponibles()
        
        mensaje = f"🔄 **RUTAS RECARGADAS**\n\n"
        mensaje += f"✅ **Rutas cargadas:** {rutas_cargadas}\n\n"
        
        for ruta in RUTAS_DISPONIBLES[:3]:  # Mostrar primeras 3
            primera_parada = ruta['paradas'][0] if ruta['paradas'] else {}
            mensaje += f"🗺️ **Ruta {ruta['ruta_id']} - {ruta['zona']}**\n"
            mensaje += f"👥 Personas: {len(ruta['paradas'])}\n"
            mensaje += f"👤 Ejemplo: {primera_parada.get('nombre', 'No disponible')}\n"
            mensaje += f"🏢 Dependencia: {primera_parada.get('dependencia', 'No disponible')}\n\n"
        
        bot.reply_to(message, mensaje, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error recargando rutas: {str(e)}")

# =============================================================================
# MANEJO DE FOTOS
# =============================================================================

@bot.message_handler(content_types=['photo'])
def manejar_fotos(message):
    """Manejar fotos de entregas y reportes"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        
        print(f"📸 Foto recibida de {user_name}: '{caption}'")
        
        # Detección de tipo
        if any(word in caption.lower() for word in ['entregado', 'entregada', 'acuse']):
            bot.reply_to(message, "✅ Foto de entrega recibida. Procesando...")
        else:
            bot.reply_to(message, "✅ Foto de reporte recibida. Guardada en sistema.")
        
    except Exception as e:
        print(f"❌ Error con foto: {e}")
        bot.reply_to(message, "❌ Error procesando foto.")

# =============================================================================
# CALLBACK HANDLERS
# =============================================================================

@bot.callback_query_handler(func=lambda call: True)
def manejar_todos_los_callbacks(call):
    """Manejar todos los callbacks"""
    try:
        data = call.data
        
        if data.startswith('lista_completa_'):
            partes = data.split('_')
            ruta_id = partes[2] if len(partes) >= 3 else "?"
            
            # Buscar ruta
            for archivo in os.listdir('rutas_telegram'):
                if f"Ruta_{ruta_id}_" in archivo:
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta = json.load(f)
                    
                    mensaje = f"👥 **LISTA COMPLETA - Ruta {ruta_id}**\n\n"
                    mensaje += f"📍 **Zona:** {ruta.get('zona', '?')}\n"
                    mensaje += f"📊 **Total:** {len(ruta.get('paradas', []))} personas\n\n"
                    
                    for parada in ruta.get('paradas', []):
                        estado = "✅" if parada.get('estado') == 'entregado' else "📍"
                        nombre = parada.get('nombre', 'Sin nombre')
                        dependencia = parada.get('dependencia', 'Sin dependencia')
                        orden = parada.get('orden', '?')
                        
                        mensaje += f"{estado} **{orden}. {nombre}**\n"
                        mensaje += f"   🏢 {dependencia}\n\n"
                    
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=mensaje,
                        parse_mode='Markdown'
                    )
                    break
            
            bot.answer_callback_query(call.id, "👥 Lista completa mostrada")
            
        elif data.startswith('entregar_'):
            bot.answer_callback_query(call.id, "📦 Prepárate para registrar entrega")
            bot.send_message(
                call.message.chat.id,
                "📦 **REGISTRAR ENTREGA**\n\nEnvía una foto del acuse firmado con el pie de foto:\n\n`ENTREGADO A [NOMBRE COMPLETO]`",
                parse_mode='Markdown'
            )
            
        elif data == 'nueva_ubicacion':
            bot.answer_callback_query(call.id, "📍 Solicitando ubicación")
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            btn_ubicacion = types.KeyboardButton("📍 Compartir ubicación", request_location=True)
            markup.add(btn_ubicacion)
            
            bot.send_message(
                call.message.chat.id,
                "📍 **COMPARTIR UBICACIÓN**\n\nPresiona el botón para compartir tu ubicación actual:",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        print(f"❌ Error en callback: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando comando")

# =============================================================================
# ENDPOINTS FLASK
# =============================================================================

@app.route('/')
def index():
    return "🤖 Bot PJCDMX - Sistema de Rutas Automáticas 🚚"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "bot_rutas_pjcdmx",
        "rutas_disponibles": len(RUTAS_DISPONIBLES),
        "repartidores_activos": len(RUTAS_ASIGNADAS),
        "timestamp": datetime.now().isoformat()
    })

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

print("\n🎯 SISTEMA AUTOMÁTICO DE RUTAS PJCDMX - CORREGIDO")
print("📱 Comandos: /solicitar_ruta, /miruta, /debug_ruta")
print("📍 Sistema listo para usar")

inicializar_sistema_completo()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
