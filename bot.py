import os
import telebot
import sqlite3
import json
import requests
from telebot import types
from datetime import datetime
from flask import Flask, request, jsonify, Response, send_file

print("🚀 INICIANDO BOT COMPLETO - CON FOTOS...")

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
                {"nombre": "JUAN PÉREZ", "dependencia": "OFICINA CENTRAL", "direccion": "Av Principal 123"},
                {"nombre": "MARÍA GARCÍA", "dependencia": "DEPTO LEGAL", "direccion": "Calle 456"},
                {"nombre": "CARLOS LÓPEZ", "dependencia": "RECURSOS HUMANOS", "direccion": "Plaza 789"}
            ]
        }
        with open('rutas_telegram/ruta_1.json', 'w') as f:
            json.dump(ruta_prueba, f)
        RUTAS_DISPONIBLES.append(ruta_prueba)
        print("✅ Ruta de prueba creada")
    
    print(f"📦 Rutas listas: {len(RUTAS_DISPONIBLES)}")
    return len(RUTAS_DISPONIBLES)

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
# HANDLERS DE TELEGRAM
# =============================================================================

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "🤖 Bot PJCDMX ACTIVO\n\n"
        "📸 **Sistema de Fotos ACTIVADO**\n\n"
        "🚀 **Comandos:**\n"
        "/ruta - Obtener una ruta\n"
        "/miruta - Ver tu ruta\n"
        "/fotos - Ver tus fotos\n"
        "/debug - Info técnica\n\n"
        "📸 **Envía una foto con:**\n"
        "'ENTREGADO A [nombre]' para entregas\n"
        "Cualquier texto para reportes")

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
    
    # Mensaje con información completa
    mensaje = f"🗺️ RUTA {ruta['ruta_id']} - {ruta['zona']}\n\n"
    
    for i, parada in enumerate(ruta['paradas'][:5], 1):
        nombre = parada.get('nombre', f'Persona {i}')
        dependencia = parada.get('dependencia', 'Sin dep')
        direccion = parada.get('direccion', 'Sin dir')
        
        mensaje += f"{i}. {nombre}\n"
        mensaje += f"   🏢 {dependencia}\n"
        mensaje += f"   📍 {direccion}\n\n"
    
    if len(ruta['paradas']) > 5:
        mensaje += f"... y {len(ruta['paradas']) - 5} más\n"
    
    mensaje += "\n📸 **Para registrar entrega:**\nEnvía foto con 'ENTREGADO A [nombre]'"
    
    bot.reply_to(message, mensaje)

@bot.message_handler(commands=['miruta'])
def ver_ruta(message):
    user_id = message.from_user.id
    
    if user_id not in RUTAS_ASIGNADAS:
        bot.reply_to(message, "❌ No tienes ruta. Usa /ruta")
        return
    
    ruta_id = RUTAS_ASIGNADAS[user_id]
    
    for ruta in RUTAS_DISPONIBLES:
        if ruta['ruta_id'] == ruta_id:
            mensaje = f"🗺️ TU RUTA: {ruta['zona']}\n\n"
            
            for i, parada in enumerate(ruta['paradas'], 1):
                nombre = parada.get('nombre', f'Persona {i}')
                dependencia = parada.get('dependencia', 'Sin dep')
                direccion = parada.get('direccion', 'Sin dir')
                
                mensaje += f"{i}. {nombre}\n"
                mensaje += f"   🏢 {dependencia}\n"
                mensaje += f"   📍 {direccion}\n\n"
            
            mensaje += "📸 **Envía foto con 'ENTREGADO A [nombre]'**"
            bot.reply_to(message, mensaje)
            return
    
    bot.reply_to(message, "❌ Ruta no encontrada")

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
    
    mensaje = f"🔧 DEBUG INFO:\n"
    mensaje += f"Rutas en memoria: {len(RUTAS_DISPONIBLES)}\n"
    mensaje += f"Tus fotos: {total_fotos}\n"
    mensaje += f"Tienes ruta: {'SÍ' if user_id in RUTAS_ASIGNADAS else 'NO'}\n"
    
    if user_id in RUTAS_ASIGNADAS:
        mensaje += f"Tu ruta_id: {RUTAS_ASIGNADAS[user_id]}\n"
    
    bot.reply_to(message, mensaje)

@bot.message_handler(commands=['recargar'])
def recargar(message):
    cargar_rutas_simple()
    bot.reply_to(message, f"✅ Rutas recargadas: {len(RUTAS_DISPONIBLES)}")

# =============================================================================
# MANEJO DE FOTOS - SISTEMA COMPLETO
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
                respuesta += f"\n\nRuta: {RUTAS_ASIGNADAS[user_id]}\nTexto: {caption}"
            
            bot.reply_to(message, respuesta, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Error al guardar la foto")
        
    except Exception as e:
        print(f"❌ Error con foto: {e}")
        bot.reply_to(message, "❌ Error procesando foto")

# =============================================================================
# ENDPOINTS FLASK
# =============================================================================

@app.route('/')
def home():
    return "🤖 Bot ACTIVO - Sistema de Fotos funcionando"

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
            "rutas_disponibles": len(RUTAS_DISPONIBLES)
        })
        
    except Exception as e:
        print(f"❌ Error en API /api/rutas: {e}")
        return jsonify({"error": str(e)}), 500

# Endpoint para ver fotos via web
@app.route('/api/fotos_usuario/<int:user_id>')
def fotos_usuario(user_id):
    """Ver fotos de un usuario específico"""
    try:
        cursor.execute('''
            SELECT file_id, caption, tipo, ruta_local, timestamp 
            FROM fotos 
            WHERE user_id = ? 
            ORDER BY timestamp DESC
        ''', (user_id,))
        
        fotos = cursor.fetchall()
        
        resultado = {
            "user_id": user_id,
            "total_fotos": len(fotos),
            "fotos": []
        }
        
        for foto in fotos:
            file_id, caption, tipo, ruta_local, timestamp = foto
            resultado["fotos"].append({
                "file_id": file_id,
                "caption": caption,
                "tipo": tipo,
                "timestamp": timestamp,
                "tiene_archivo": os.path.exists(ruta_local) if ruta_local else False
            })
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =============================================================================
# INICIALIZACIÓN
# =============================================================================

print("🎯 CARGANDO SISTEMA COMPLETO...")
cargar_rutas_simple()
print("✅ BOT LISTO - SISTEMA DE FOTOS ACTIVADO")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
