import os
import telebot
import sqlite3
import time
import requests
import json
import pandas as pd
from telebot import types
from datetime import datetime

print("🚀 INICIANDO BOT COMPLETO PJCDMX - SISTEMA AUTOMÁTICO DE RUTAS...")

# CONFIGURACIÓN SEGURA
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ ERROR: BOT_TOKEN no configurado en Railway")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# BASE DE DATOS
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
conn.commit()
print("🗃️ Base de datos lista")

# SISTEMA DE RUTAS AUTOMÁTICO
RUTAS_DISPONIBLES = []
RUTAS_ASIGNADAS = {}  # user_id -> ruta_id
ADMIN_IDS = [123456789]  # ⚠️ CAMBIA POR TU USER_ID DE TELEGRAM

# CREAR CARPETAS
for carpeta in ['rutas_telegram', 'avances_ruta', 'incidencias_trafico', 'fotos_acuses', 'data']:
    os.makedirs(carpeta, exist_ok=True)
print("📁 Carpetas del sistema creadas")

# =============================================================================
# FUNCIONES DEL SISTEMA DE RUTAS
# =============================================================================

def cargar_rutas_disponibles():
    """Cargar todas las rutas disponibles para asignación automática"""
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
    
    # Mostrar progreso
    entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
    texto += f"*Progreso:* {entregadas}/{len(ruta['paradas'])} entregadas\n\n"
    
    texto += "*📍 PARADAS:*\n"
    for parada in ruta['paradas'][:5]:  # Mostrar máximo 5
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
        
        # Buscar archivo de la ruta
        for archivo in os.listdir('rutas_telegram'):
            if f"Ruta_{ruta_id}_" in archivo:
                with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                    ruta_data = json.load(f)
                
                # Actualizar parada
                for parada in ruta_data['paradas']:
                    if persona_entregada.lower() in parada['nombre'].lower():
                        parada['estado'] = 'entregado'
                        parada['timestamp_entrega'] = timestamp
                        parada['foto_acuse'] = f"fotos_acuses/{foto_id}.jpg" if foto_id else None
                        parada['comentarios'] = comentarios
                        break
                
                # Verificar si todas están entregadas
                pendientes = [p for p in ruta_data['paradas'] if p.get('estado') != 'entregado']
                if not pendientes:
                    ruta_data['estado'] = 'completada'
                    ruta_data['timestamp_completada'] = timestamp
                
                # Guardar cambios
                with open(f'rutas_telegram/{archivo}', 'w', encoding='utf-8') as f:
                    json.dump(ruta_data, f, indent=2, ensure_ascii=False)
                
                # Guardar avance
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

# =============================================================================
# COMANDOS PRINCIPALES - ASIGNACIÓN AUTOMÁTICA
# =============================================================================

@bot.message_handler(commands=['start', 'hola'])
def enviar_bienvenida(message):
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
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    print(f"📨 Start: {message.from_user.first_name}")

@bot.message_handler(commands=['solicitar_ruta'])
def solicitar_ruta_automatica(message):
    """Asignar ruta automáticamente al repartidor"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        print(f"🔄 Solicitud de ruta de {user_name} (ID: {user_id})")
        
        # Verificar si ya tiene ruta asignada
        if user_id in RUTAS_ASIGNADAS:
            bot.reply_to(message, 
                        "📭 *Ya tienes una ruta asignada.*\n\n"
                        "Usa /miruta para ver tu ruta actual.\n"
                        "Si has completado tu ruta, contacta a soporte.",
                        parse_mode='Markdown')
            return
        
        # Recargar rutas disponibles
        rutas_disponibles = cargar_rutas_disponibles()
        
        if rutas_disponibles == 0:
            bot.reply_to(message, 
                        "📭 *No hay rutas disponibles en este momento.*\n\n"
                        "Todas las rutas han sido asignadas.\n"
                        "Contacta a tu supervisor o intenta más tarde.",
                        parse_mode='Markdown')
            return
        
        # Asignar la primera ruta disponible
        ruta_asignada = RUTAS_DISPONIBLES.pop(0)
        ruta_id = ruta_asignada['ruta_id']
        zona = ruta_asignada['zona']
        
        # Actualizar la ruta en archivo
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        ruta_asignada['repartidor_asignado'] = f"user_{user_id}"
        ruta_asignada['estado'] = 'asignada'
        ruta_asignada['timestamp_asignacion'] = datetime.now().isoformat()
        
        # Guardar cambios
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(ruta_asignada, f, indent=2, ensure_ascii=False)
        
        # Registrar asignación en memoria
        RUTAS_ASIGNADAS[user_id] = ruta_id
        
        # Enviar ruta al repartidor
        mensaje = formatear_ruta_para_repartidor(ruta_asignada)
        
        # Botón para Google Maps
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
    
    # Buscar la ruta en archivos
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

# =============================================================================
# COMANDOS DE ADMINISTRADOR
# =============================================================================

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
    
    # Contar rutas por estado
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

@bot.message_handler(commands=['generar_rutas_ejemplo'])
def generar_rutas_ejemplo(message):
    """Generar rutas de ejemplo para pruebas (solo admin)"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        bot.reply_to(message, "🔄 Generando rutas de ejemplo...")
        
        # Datos de ejemplo del Tribunal
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
            },
            {
                'ruta_id': 2,
                'zona': 'SUR',
                'repartidor_asignado': None,
                'google_maps_url': 'https://maps.google.com/maps/dir/19.4283717,-99.1430307/19.3556000,-99.1623000/19.3600000,-99.1650000',
                'paradas': [
                    {
                        'orden': 1,
                        'nombre': 'MTRO. JAVIER DÍAZ MORALES',
                        'direccion': 'Calzada de Tlalpan 789, Torre Judicial, Coyoacán, CDMX',
                        'dependencia': 'UNIDAD DE NOTIFICACIONES',
                        'coords': '19.3556000,-99.1623000',
                        'estado': 'pendiente'
                    },
                    {
                        'orden': 2,
                        'nombre': 'LIC. ANA Martínez Sánchez',
                        'direccion': 'Miguel Ángel de Quevedo 321, Local 2, Coyoacán, CDMX',
                        'dependencia': 'ARCHIVO JUDICIAL',
                        'coords': '19.3600000,-99.1650000',
                        'estado': 'pendiente'
                    }
                ],
                'estadisticas': {
                    'total_paradas': 2,
                    'distancia_km': 8.7,
                    'tiempo_min': 25,
                    'origen': 'TSJCDMX - Niños Héroes 150'
                },
                'estado': 'pendiente',
                'timestamp_creacion': datetime.now().isoformat()
            }
        ]
        
        # Guardar rutas de ejemplo
        for ruta in rutas_ejemplo:
            archivo = f"rutas_telegram/Ruta_{ruta['ruta_id']}_{ruta['zona']}.json"
            with open(archivo, 'w', encoding='utf-8') as f:
                json.dump(ruta, f, indent=2, ensure_ascii=False)
        
        # Recargar disponibles
        cargar_rutas_disponibles()
        
        bot.reply_to(message, 
                    f"✅ *Rutas de ejemplo generadas!*\n\n"
                    f"Se crearon {len(rutas_ejemplo)} rutas de prueba.\n"
                    f"Ahora los repartidores pueden usar /solicitar_ruta\n\n"
                    f"Usa /estado_rutas para ver el estado.",
                    parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error generando rutas: {str(e)}")

# =============================================================================
# TUS COMANDOS ORIGINALES (MANTENIDOS)
# =============================================================================

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

@bot.message_handler(content_types=['location'])
def manejar_ubicacion(message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude
    
    # Guardar en base de datos
    cursor.execute('INSERT INTO incidentes (user_id, user_name, tipo, ubicacion) VALUES (?, ?, ?, ?)',
                  (user_id, user, 'ubicacion', f"{lat},{lon}"))
    conn.commit()
    
    respuesta = (f"📍 *UBICACIÓN RECIBIDA* ¡Gracias {user}!\n\n"
                f"*Coordenadas:* `{lat:.6f}, {lon:.6f}`\n"
                f"*Guardado para:* Reportes y seguimiento de rutas")
    
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📍 Ubicación recibida: {user} - {lat},{lon}")

@bot.message_handler(commands=['foto'])
def solicitar_foto(message):
    texto = """
📸 *ENVIAR FOTO*

Puedes enviar fotos para:
- 📦 Acuse de recibo (entregas)
- 🚨 Evidencia de incidentes  
- 📊 Actualización de estatus

*Cómo enviar:*
1. Toca el clip 📎 
2. "Galería" o "Cámara"
3. Toma/selecciona foto
4. Agrega descripción (opcional pero recomendado)

💡 Para acuses: Incluye "entregado a [nombre]" en la descripción.
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📸 Foto: {message.from_user.first_name}")

@bot.message_handler(content_types=['photo'])
def manejar_foto(message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id
    caption = message.caption if message.caption else "Sin descripción"
    
    # Determinar tipo de foto y procesar
    if any(word in caption.lower() for word in ['entregado', 'entregada', '✅', 'recibido']):
        tipo = 'foto_acuse'
        # Intentar extraer nombre de persona para registro automático
        persona_entregada = "Por determinar"
        palabras = caption.split()
        for i, palabra in enumerate(palabras):
            if palabra.lower() in ['a', 'para', 'entregado', 'entregada'] and i + 1 < len(palabras):
                persona_entregada = " ".join(palabras[i+1:])
                break
        
        # Registrar en sistema automáticamente
        if user_id in RUTAS_ASIGNADAS:
            if registrar_entrega_sistema(user_id, user, persona_entregada, file_id, caption):
                respuesta = f"📦 *ACUSE CON FOTO REGISTRADO* ¡Gracias {user}!\nEntrega a *{persona_entregada}* registrada automáticamente."
            else:
                respuesta = f"📸 *FOTO DE ACUSE RECIBIDA* ¡Gracias {user}!\n*Persona:* {persona_entregada}"
        else:
            respuesta = f"📸 *FOTO DE ACUSE RECIBIDA* ¡Gracias {user}!\n*Nota:* No tienes ruta activa asignada."
            
    elif any(word in caption.lower() for word in ['retrasado', 'problema', '⏳', '🚨']):
        tipo = 'foto_estatus'
        respuesta = f"📊 *ESTATUS CON FOTO ACTUALIZADO* ¡Gracias {user}! Foto de evidencia guardada."
    else:
        tipo = 'foto_incidente'
        respuesta = f"📸 *FOTO RECIBIDA* ¡Gracias {user}! Foto guardada: {caption}"
    
    # Guardar en base de datos
    cursor.execute('INSERT INTO incidentes (user_id, user_name, tipo, descripcion, foto_id) VALUES (?, ?, ?, ?, ?)',
                  (user_id, user, tipo, caption, file_id))
    conn.commit()
    
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📸 Foto recibida: {user} - {caption} - Tipo: {tipo}")

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

@bot.message_handler(func=lambda message: True, content_types=['text'])
def manejar_texto_general(message):
    if message.text.startswith('/'):
        return
    
    user = message.from_user.first_name
    user_id = message.from_user.id
    texto = message.text
    
    # Detectar si es registro de entrega
    if any(word in texto.lower() for word in ['entregado', 'entregada', 'recibido']) and len(texto.split()) > 2:
        # Probablemente es "Entregado a [Nombre]"
        partes = texto.split()
        persona_entregada = texto
        
        # Intentar extraer nombre después de "a" o "para"
        for i, palabra in enumerate(partes):
            if palabra.lower() in ['a', 'para', 'entregado', 'entregada'] and i + 1 < len(partes):
                persona_entregada = " ".join(partes[i+1:])
                break
        
        # Registrar en sistema si tiene ruta asignada
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
    
    # Detectar estatus automáticamente (lógica original)
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
    
    # Si no es estatus ni entrega, es reporte normal
    respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}! Registrado: \"{texto}\""
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📝 Reporte: {user} - {texto}")

# =============================================================================
# INICIALIZACIÓN Y EJECUCIÓN
# =============================================================================

def inicializar_sistema():
    """Inicializar el sistema al arrancar"""
    print("🔄 Inicializando sistema de rutas automáticas...")
    cargar_rutas_disponibles()
    print(f"✅ Sistema listo. Rutas disponibles: {len(RUTAS_DISPONIBLES)}")
    print("🤖 Bot listo para recibir solicitudes de rutas")

# =============================================================================
# API PARA RECIBIR RUTAS DEL PROGRAMA GENERADOR
# =============================================================================
from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "service": "bot_rutas_pjcdmx"})

@app.route('/api/rutas', methods=['POST'])
def recibir_rutas_desde_programa():
    """Endpoint para que el programa generador envíe rutas reales"""
    try:
        datos_ruta = request.json
        
        if not datos_ruta:
            return jsonify({"error": "Datos vacíos"}), 400
        
        ruta_id = datos_ruta.get('ruta_id', 1)
        zona = datos_ruta.get('zona', 'GENERAL')
        
        # Guardar la ruta en el sistema
        archivo_ruta = f"rutas_telegram/Ruta_{ruta_id}_{zona}.json"
        
        with open(archivo_ruta, 'w', encoding='utf-8') as f:
            json.dump(datos_ruta, f, indent=2, ensure_ascii=False)
        
        # Recargar rutas disponibles
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

def ejecutar_api():
    """Ejecutar Flask en segundo plano"""
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

# Iniciar API en segundo plano al arrancar el bot
threading.Thread(target=ejecutar_api, daemon=True).start()
print("🌐 API Flask iniciada en puerto 8000")

if __name__ == "__main__":
    print("\n🎯 SISTEMA AUTOMÁTICO DE RUTAS PJCDMX - 100% OPERATIVO")
    print("📱 Comandos: /solicitar_ruta, /miruta, /entregar, /estado_rutas")
    print("🚀 Inicializando en Railway...")
    
    inicializar_sistema()
    
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"❌ Error: {e}")
