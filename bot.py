import os
import telebot
import sqlite3
import time
import requests
import json
from telebot import types

print("🚀 INICIANDO BOT COMPLETO PJCDMX CON SISTEMA DE RUTAS...")

# CONFIGURACIÓN SEGURA - TOKEN SOLO EN VARIABLES DE ENTORNO
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ ERROR: BOT_TOKEN no configurado en Railway")
    print("💡 Ve a Railway → Variables → Agrega BOT_TOKEN")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# BASE DE DATOS (SQLite funciona en Railway)
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
print("🗃️ Base de datos lista en /tmp/")

# CREAR CARPETAS PARA SISTEMA DE RUTAS
for carpeta in ['rutas_telegram', 'avances_ruta', 'incidencias_trafico', 'fotos_acuses']:
    os.makedirs(carpeta, exist_ok=True)
print("📁 Carpetas del sistema de rutas creadas")

# FUNCIÓN NOTIFICACIÓN ADMIN
def notificar_admin(mensaje):
    print(f"📢 ADMIN: {mensaje}")

# FUNCIONES PARA SISTEMA DE RUTAS
def obtener_rutas_usuario(user_id):
    """Obtener rutas asignadas a un usuario"""
    try:
        rutas_asignadas = []
        if os.path.exists('rutas_telegram'):
            for archivo in os.listdir('rutas_telegram'):
                if archivo.endswith('.json'):
                    with open(f'rutas_telegram/{archivo}', 'r', encoding='utf-8') as f:
                        ruta = json.load(f)
                        # Asignar por user_id o por nombre de repartidor
                        repartidor_asignado = ruta.get('repartidor_asignado')
                        if (repartidor_asignado == f"user_{user_id}" or 
                            repartidor_asignado == str(user_id)):
                            rutas_asignadas.append(ruta)
        return rutas_asignadas
    except Exception as e:
        print(f"❌ Error obteniendo rutas: {e}")
        return []

def formatear_ruta_telegram(ruta):
    """Formatear información de ruta para Telegram"""
    texto = f"*🗺️ RUTA {ruta['ruta_id']} - {ruta['zona']}*\n\n"
    texto += f"*Paradas:* {len(ruta['paradas'])}\n"
    texto += f"*Distancia:* {ruta['estadisticas']['distancia_km']} km\n"
    texto += f"*Tiempo estimado:* {ruta['estadisticas']['tiempo_min']} min\n\n"
    
    # Mostrar progreso
    entregadas = len([p for p in ruta['paradas'] if p.get('estado') == 'entregado'])
    texto += f"*Progreso:* {entregadas}/{len(ruta['paradas'])} entregadas\n\n"
    
    # Botón para abrir en Google Maps
    texto += f"[📍 Abrir en Google Maps]({ruta['google_maps_url']})\n\n"
    
    texto += "*Próximas paradas:*\n"
    for parada in ruta['paradas'][:3]:  # Mostrar solo 3 próximas
        if parada.get('estado') != 'entregado':
            texto += f"📍 {parada['nombre']}\n"
            texto += f"   🏢 {parada['dependencia']}\n"
            texto += f"   🏠 {parada['direccion'][:30]}...\n\n"
    
    if len(ruta['paradas']) > 3:
        texto += f"... y {len(ruta['paradas']) - 3} paradas más"
    
    return texto

def registrar_entrega_sistema(ruta_id, user_name, user_id, persona_entregada, foto_id=None):
    """Registrar entrega en el sistema de archivos"""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        datos_entrega = {
            'ruta_id': ruta_id,
            'repartidor': user_name,
            'repartidor_id': user_id,
            'persona_entregada': persona_entregada,
            'foto_acuse': f"fotos_acuses/{foto_id}.jpg" if foto_id else None,
            'timestamp': timestamp,
            'coords_entrega': 'Por definir'  # Se puede obtener de ubicación
        }
        
        # Guardar en avances_ruta
        archivo_avance = f"avances_ruta/entrega_{ruta_id}_{int(time.time())}.json"
        with open(archivo_avance, 'w', encoding='utf-8') as f:
            json.dump(datos_entrega, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Entrega registrada: {user_name} → {persona_entregada} (Ruta {ruta_id})")
        return True
    except Exception as e:
        print(f"❌ Error registrando entrega: {e}")
        return False

# --- COMANDOS ACTUALIZADOS ---

# 1. COMANDO START MEJORADO
@bot.message_handler(commands=['start', 'hola'])
def enviar_bienvenida(message):
    welcome_text = f"""
🤖 *BOT DE RUTAS - PJCDMX* 🚚

¡Hola {message.from_user.first_name}! Soy MoniBot

*Comandos disponibles:*
/start - Mostrar esta ayuda
/rutas - 🗺️ Ver mis rutas asignadas
/incidente - 📝 Reportar incidente  
/ubicacion - 📍 Enviar ubicación actual
/foto - 📸 Enviar foto del incidente
/atencionH - 👨‍💼 Comunicarse con persona
/estatus - 📊 Actualizar estatus (con foto opcional)
/entregar - 📦 Registrar entrega completada

¡Reporta en tiempo real!
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    print(f"📨 Start: {message.from_user.first_name}")

# 2. NUEVO COMANDO: RUTAS
@bot.message_handler(commands=['rutas'])
def mostrar_rutas(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    rutas = obtener_rutas_usuario(user_id)
    
    if not rutas:
        bot.reply_to(message, 
                    "📭 *No tienes rutas asignadas en este momento.*\n\n"
                    "Las rutas se asignan desde el sistema central. "
                    "Contacta a tu supervisor si crees que hay un error.",
                    parse_mode='Markdown')
        print(f"📭 Rutas: {user_name} - Sin rutas asignadas")
        return
    
    bot.reply_to(message, 
                f"🗺️ *TUS RUTAS ASIGNADAS*\n\n"
                f"Tienes *{len(rutas)}* ruta(s) asignada(s).",
                parse_mode='Markdown')
    
    # Enviar cada ruta en un mensaje separado
    for ruta in rutas:
        texto_ruta = formatear_ruta_telegram(ruta)
        bot.send_message(message.chat.id, texto_ruta, parse_mode='Markdown')
    
    print(f"🗺️ Rutas mostradas: {user_name} - {len(rutas)} rutas")

# 3. NUEVO COMANDO: ENTREGAR
@bot.message_handler(commands=['entregar'])
def iniciar_entrega(message):
    texto = """
📦 *REGISTRAR ENTREGA COMPLETADA*

Para registrar una entrega:

1. *Selecciona la ruta* (usa /rutas para verlas)
2. *Envía el nombre completo* de la persona que recibió
3. *Opcional:* Envía foto del acuse

*Ejemplo:*
`Carlos Rodríguez Hernández`

💡 *Consejo:* Si envías foto, asegúrate de incluir el nombre en el pie de foto.
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📦 Entregar: {message.from_user.first_name}")

# 4. COMANDO INCIDENTE (CON SERVICIO AL CLIENTE MEJORADO)
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

# 5. COMANDO UBICACIÓN (MANTENIDO)
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

# 6. MANEJADOR DE UBICACIONES (MEJORADO)
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
    
    # También guardar para sistema de rutas si hay rutas activas
    rutas = obtener_rutas_usuario(user_id)
    if rutas:
        # Podríamos asociar la ubicación con la ruta activa
        pass
    
    respuesta = (f"📍 *UBICACIÓN RECIBIDA* ¡Gracias {user}!\n\n"
                f"*Coordenadas:* `{lat:.6f}, {lon:.6f}`\n"
                f"*Guardado para:* Reportes y seguimiento de rutas")
    
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📍 Ubicación recibida: {user} - {lat},{lon}")
    notificar_admin(f"📍 {user} envió ubicación: {lat},{lon}")

# 7. COMANDO FOTO (MEJORADO PARA ACUSES)
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

# 8. MANEJADOR DE FOTOS (MEJORADO)
@bot.message_handler(content_types=['photo'])
def manejar_foto(message):
    user = message.from_user.first_name
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id
    caption = message.caption if message.caption else "Sin descripción"
    
    # Determinar tipo de foto
    if any(word in caption.lower() for word in ['entregado', 'entregada', '✅', 'recibido']):
        tipo = 'foto_acuse'
        # Intentar extraer nombre de persona
        persona_entregada = "Por determinar"
        for word in caption.split():
            if word.istitle() and len(word) > 3:
                persona_entregada = word
                break
                
        # Registrar en sistema de rutas
        rutas = obtener_rutas_usuario(user_id)
        if rutas:
            registrar_entrega_sistema(rutas[0]['ruta_id'], user, user_id, persona_entregada, file_id)
            respuesta = f"📦 *ACUSE CON FOTO REGISTRADO* ¡Gracias {user}!\nEntrega a *{persona_entregada}* registrada en el sistema."
        else:
            respuesta = f"📸 *FOTO DE ACUSE RECIBIDA* ¡Gracias {user}!\n*Nota:* No tienes rutas activas asignadas."
            
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
    notificar_admin(f"📸 {user} envió foto ({tipo}): {caption}")

# 9. COMANDO ATENCIÓN HUMANA (MANTENIDO)
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
    notificar_admin(f"🚨 {user} (ID: {user_id}) solicitó ATENCIÓN HUMANA")

# 10. COMANDO ESTATUS MEJORADO
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

# 11. MANEJADOR GENERAL DE TEXTO MEJORADO
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
        if 'a' in partes or 'a:' in [p.lower() for p in partes]:
            # Es un registro de entrega
            rutas = obtener_rutas_usuario(user_id)
            if rutas:
                persona_entregada = " ".join(partes[partes.index('a')+1:]) if 'a' in partes else texto
                registrar_entrega_sistema(rutas[0]['ruta_id'], user, user_id, persona_entregada)
                respuesta = f"📦 *ENTREGA REGISTRADA* ¡Gracias {user}!\nEntrega a *{persona_entregada}* registrada en el sistema."
            else:
                respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}!\n*Nota:* No tienes rutas activas asignadas."
            
            bot.reply_to(message, respuesta, parse_mode='Markdown')
            print(f"📦 Entrega registrada: {user} - {persona_entregada}")
            notificar_admin(f"📦 {user} registró entrega a: {persona_entregada}")
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
            notificar_admin(f"📊 {user} actualizó estatus a: {estatus}")
            return
    
    # Si no es estatus ni entrega, es reporte normal
    respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}! Registrado: \"{texto}\""
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📝 Reporte: {user} - {texto}")
    notificar_admin(f"📝 {user} reportó: {texto}")

# --- INICIAR BOT ---
if __name__ == "__main__":
    print("\n🎯 MONIBOT PJCDMX CON SISTEMA DE RUTAS - LISTO AL 100%")
    print("📱 Comandos: /start, /rutas, /incidente, /ubicacion, /foto, /atencionH, /estatus, /entregar")
    print("📁 Sistema de rutas integrado")
    print("🚀 Iniciando bot en Railway...")
    
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"❌ Error: {e}")
