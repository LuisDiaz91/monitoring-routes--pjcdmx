import os
import telebot
import sqlite3
import time
import requests
from telebot import types

print("🚀 INICIANDO BOT COMPLETO PJCDMX EN NUBE...")

# CONFIGURACIÓN OPTIMIZADA PARA RAILWAY
TOKEN = os.environ.get("BOT_TOKEN", "7913463398:AAHA_h9zD9WN_tc3fVv8b81Mdtk9gMGPe5E")
bot = telebot.TeleBot(TOKEN)

# BASE DE DATOS (SQLite funciona en Railway)
conn = sqlite3.connect('/tmp/incidentes.db', check_same_thread=False)  # Cambiado a /tmp para Railway
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

# FUNCIÓN NOTIFICACIÓN ADMIN
def notificar_admin(mensaje):
    print(f"📢 ADMIN: {mensaje}")

# --- TODOS LOS COMANDOS EN ORDEN ---

# 1. COMANDO START
@bot.message_handler(commands=['start', 'hola'])
def enviar_bienvenida(message):
    welcome_text = f"""
🤖 *BOT DE RUTAS - PJCDMX* 🚚

¡Hola {message.from_user.first_name}! Soy MoniBot

*Comandos disponibles:*
/start - Mostrar esta ayuda
/incidente - 📝 Reportar incidente  
/ubicacion - 📍 Enviar ubicación actual
/foto - 📸 Enviar foto del incidente
/atencionH - 👨‍💼 Comunicarse con persona
/estatus - 📊 Actualizar estatus (con foto opcional)

¡Reporta en tiempo real!
    """
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    print(f"📨 Start: {message.from_user.first_name}")

# 2. COMANDO INCIDENTE
@bot.message_handler(commands=['incidente'])
def reportar_incidente(message):
    texto = """
🚨 *REPORTAR INCIDENTE*

Describe el incidente. Ejemplos:
- "Tráfico pesado en Periférico" 
- "No se encuentra a la persona"
- "Vehículo sobrecalentado"

Escribe tu reporte:
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"🚨 Incidente: {message.from_user.first_name}")

# 3. COMANDO UBICACIÓN
@bot.message_handler(commands=['ubicacion'])
def solicitar_ubicacion(message):
    texto = """
📍 *UBICACIÓN EN TIEMPO REAL*

Envía tu ubicación actual:
1. Toca el clip 📎 
2. Selecciona "Ubicación"
3. "Enviar mi ubicación actual"
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📍 Ubicación: {message.from_user.first_name}")

# 4. MANEJADOR DE UBICACIONES
@bot.message_handler(content_types=['location'])
def manejar_ubicacion(message):
    user = message.from_user.first_name
    lat = message.location.latitude
    lon = message.location.longitude
    
    cursor.execute('INSERT INTO incidentes (user_id, user_name, tipo, ubicacion) VALUES (?, ?, ?, ?)',
                  (message.from_user.id, user, 'ubicacion', f"{lat},{lon}"))
    conn.commit()
    
    respuesta = f"📍 *UBICACIÓN RECIBIDA* ¡Gracias {user}! Coordenadas guardadas."
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📍 Ubicación recibida: {user} - {lat},{lon}")
    notificar_admin(f"📍 {user} envió ubicación: {lat},{lon}")

# 5. COMANDO FOTO
@bot.message_handler(commands=['foto'])
def solicitar_foto(message):
    texto = """
📸 *ENVIAR FOTO*

Envía foto del incidente:
1. Toca el clip 📎 
2. "Galería" o "Cámara"
3. Toma/selecciona foto
4. Agrega descripción opcional
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📸 Foto: {message.from_user.first_name}")

# 6. MANEJADOR DE FOTOS
@bot.message_handler(content_types=['photo'])
def manejar_foto(message):
    user = message.from_user.first_name
    file_id = message.photo[-1].file_id
    caption = message.caption if message.caption else "Sin descripción"
    
    # Determinar si es foto de estatus o incidente normal
    tipo = 'foto_estatus' if any(word in caption.lower() for word in 
                               ['entregado', 'retrasado', 'problema', 'terminado', '✅', '⏳', '🚨', '🏁']) else 'foto'
    
    cursor.execute('INSERT INTO incidentes (user_id, user_name, tipo, descripcion, foto_id) VALUES (?, ?, ?, ?, ?)',
                  (message.from_user.id, user, tipo, caption, file_id))
    conn.commit()
    
    if tipo == 'foto_estatus':
        respuesta = f"📊 *ESTATUS CON FOTO ACTUALIZADO* ¡Gracias {user}! Foto de evidencia guardada."
    else:
        respuesta = f"📸 *FOTO RECIBIDA* ¡Gracias {user}! Foto guardada: {caption}"
    
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📸 Foto recibida: {user} - {caption} - Tipo: {tipo}")
    notificar_admin(f"📸 {user} envió foto ({tipo}): {caption}")

# 7. COMANDO ATENCIÓN HUMANA
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

# 8. COMANDO ESTATUS MEJORADO (CON FOTO OPCIONAL)
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

*Ejemplo con foto:* Envía foto con "✅ entregado" en la descripción
    """
    bot.reply_to(message, texto, parse_mode='Markdown')
    print(f"📊 Estatus: {message.from_user.first_name}")

# 9. MANEJADOR GENERAL DE TEXTO
@bot.message_handler(func=lambda message: True, content_types=['text'])
def manejar_texto_general(message):
    if message.text.startswith('/'):
        return
    
    user = message.from_user.first_name
    texto = message.text
    
    # Detectar estatus automáticamente
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
    
    # Si no es estatus, es reporte normal
    respuesta = f"✅ *REPORTE RECIBIDO* ¡Gracias {user}! Registrado: \"{texto}\""
    bot.reply_to(message, respuesta, parse_mode='Markdown')
    print(f"📝 Reporte: {user} - {texto}")
    notificar_admin(f"📝 {user} reportó: {texto}")

# --- INICIAR BOT ---
if __name__ == "__main__":
    print("\n🎯 MONIBOT PJCDMX OPTIMIZADO PARA NUBE - LISTO AL 100%")
    print("📱 Comandos: /start, /incidente, /ubicacion, /foto, /atencionH, /estatus")
    print("🚀 Iniciando bot en Railway...")
    
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"❌ Error: {e}")
