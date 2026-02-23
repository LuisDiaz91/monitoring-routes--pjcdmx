"""
BOT TELEGRAM OPTIMIZADO - PJCDMX ENTREGAS
Versión: 2.0
Características:
- 50% menos código
- Integración perfecta con sistema de rutas
- Manejo de errores mejorado
- URLs de Google Maps más confiables
"""

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
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from functools import lru_cache

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    logger.error("❌ BOT_TOKEN no configurado")
    exit(1)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Configuración
class Config:
    ORIGEN_FIJO = "TSJCDMX - Niños Héroes 150, Doctores, Ciudad de México"
    CARPETA_RUTAS = "rutas_telegram"
    CARPETA_FOTOS = "carpeta_fotos_central"
    DB_PATH = '/tmp/incidentes.db'
    TIMEOUT_API = 10
    MAX_DIRECCIONES_URL = 8  # Google Maps tiene límite de waypoints

CONFIG = Config()

# =============================================================================
# BASE DE DATOS
# =============================================================================

class Database:
    """Manejador de base de datos SQLite"""
    
    def __init__(self):
        self.conn = sqlite3.connect(CONFIG.DB_PATH, check_same_thread=False)
        self._crear_tablas()
    
    def _crear_tablas(self):
        cursor = self.conn.cursor()
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
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rutas_asignadas (
            user_id INTEGER PRIMARY KEY,
            ruta_id INTEGER,
            fecha_asignacion DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ubicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            latitud REAL,
            longitud REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.conn.commit()
    
    def guardar_foto(self, file_id: str, user_id: int, user_name: str, 
                     caption: str, tipo: str, ruta_local: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO fotos (file_id, user_id, user_name, caption, tipo, ruta_local) VALUES (?, ?, ?, ?, ?, ?)",
                (file_id, user_id, user_name, caption, tipo, ruta_local)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error guardando foto: {e}")
            return False
    
    def guardar_ubicacion(self, user_id: int, latitud: float, longitud: float) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO ubicaciones (user_id, latitud, longitud) VALUES (?, ?, ?)",
                (user_id, latitud, longitud)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error guardando ubicación: {e}")
            return False
    
    def obtener_estadisticas(self) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fotos")
        total_fotos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM ubicaciones")
        total_ubicaciones = cursor.fetchone()[0]
        
        return {
            "fotos": total_fotos,
            "ubicaciones": total_ubicaciones
        }

# =============================================================================
# GESTOR DE RUTAS
# =============================================================================

@dataclass
class Ruta:
    """Modelo de ruta"""
    id: int
    zona: str
    origen: str
    paradas: List[Dict]
    google_maps_url: Optional[str] = None
    
    @property
    def total_paradas(self) -> int:
        return len(self.paradas)
    
    @property
    def total_personas(self) -> int:
        return sum(p.get('total_personas', 1) for p in self.paradas)

class RouteManager:
    """Gestor de rutas - Carga y procesamiento"""
    
    def __init__(self):
        self.rutas_disponibles: List[Ruta] = []
        self.rutas_asignadas: Dict[int, int] = {}  # user_id -> ruta_id
        self.db = Database()
        self._cargar_rutas()
    
    def _cargar_rutas(self):
        """Carga rutas desde archivos JSON"""
        self.rutas_disponibles = []
        
        if not os.path.exists(CONFIG.CARPETA_RUTAS):
            os.makedirs(CONFIG.CARPETA_RUTAS)
            self._crear_ruta_ejemplo()
            return
        
        for archivo in os.listdir(CONFIG.CARPETA_RUTAS):
            if not archivo.endswith('.json'):
                continue
            
            try:
                with open(f"{CONFIG.CARPETA_RUTAS}/{archivo}", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Validar datos mínimos
                if not data.get('paradas'):
                    logger.warning(f"Ruta sin paradas: {archivo}")
                    continue
                
                ruta = Ruta(
                    id=data.get('ruta_id', 0),
                    zona=data.get('zona', 'SIN ZONA'),
                    origen=data.get('origen', CONFIG.ORIGEN_FIJO),
                    paradas=data.get('paradas', []),
                    google_maps_url=data.get('google_maps_url')
                )
                
                # Generar URL si no existe
                if not ruta.google_maps_url:
                    ruta.google_maps_url = self._generar_url_maps(ruta)
                    if ruta.google_maps_url:
                        self._guardar_url_en_archivo(archivo, ruta.google_maps_url)
                
                self.rutas_disponibles.append(ruta)
                logger.info(f"✅ Ruta {ruta.id} cargada: {ruta.total_paradas} paradas")
                
            except Exception as e:
                logger.error(f"Error cargando {archivo}: {e}")
        
        if not self.rutas_disponibles:
            logger.warning("No hay rutas disponibles, creando ejemplo")
            self._crear_ruta_ejemplo()
    
    def _crear_ruta_ejemplo(self):
        """Crea una ruta de ejemplo para pruebas"""
        ruta_ejemplo = {
            "ruta_id": 1,
            "zona": "CENTRO",
            "origen": CONFIG.ORIGEN_FIJO,
            "paradas": [
                {
                    "orden": 1,
                    "nombre": "PALACIO NACIONAL",
                    "dependencia": "GOBIERNO FEDERAL",
                    "direccion": "Plaza de la Constitución S/N, Centro Histórico, Ciudad de México",
                    "total_personas": 3,
                    "personas": [
                        {"nombre": "JUAN PÉREZ"},
                        {"nombre": "MARÍA GARCÍA"},
                        {"nombre": "CARLOS LÓPEZ"}
                    ]
                },
                {
                    "orden": 2,
                    "nombre": "SUPREMA CORTE",
                    "dependencia": "PODER JUDICIAL",
                    "direccion": "Pino Suárez 2, Centro, Ciudad de México",
                    "total_personas": 2,
                    "personas": [
                        {"nombre": "ANA MARTÍNEZ"},
                        {"nombre": "LUIS HERNÁNDEZ"}
                    ]
                }
            ]
        }
        
        url = self._generar_url_maps(Ruta(**ruta_ejemplo))
        if url:
            ruta_ejemplo['google_maps_url'] = url
        
        archivo = f"{CONFIG.CARPETA_RUTAS}/Ruta_1_CENTRO.json"
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(ruta_ejemplo, f, indent=2, ensure_ascii=False)
        
        self.rutas_disponibles.append(Ruta(**ruta_ejemplo))
        logger.info("✅ Ruta de ejemplo creada")
    
    def _guardar_url_en_archivo(self, archivo: str, url: str):
        """Guarda URL en archivo JSON"""
        try:
            with open(f"{CONFIG.CARPETA_RUTAS}/{archivo}", 'r+', encoding='utf-8') as f:
                data = json.load(f)
                data['google_maps_url'] = url
                f.seek(0)
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.truncate()
        except Exception as e:
            logger.error(f"Error guardando URL: {e}")
    
    def _limpiar_direccion(self, direccion: str) -> str:
        """Limpia y normaliza una dirección"""
        if not direccion:
            return CONFIG.ORIGEN_FIJO
        
        d = str(direccion)
        # Limpiar HTML y saltos de línea
        d = re.sub(r'<br\s*/?>', ' ', d)
        d = re.sub(r'[\n\r]', ' ', d)
        d = re.sub(r'\s+', ' ', d)
        d = d.strip()
        
        # Agregar Ciudad de México si es necesario
        if not any(term in d.lower() for term in ['ciudad de méxico', 'cdmx', 'mexico']):
            d += ", Ciudad de México"
        
        return d
    
    def _extraer_direccion_parada(self, parada: Dict) -> str:
        """Extrae la mejor dirección disponible de una parada"""
        # Intentar con dirección directa
        direccion = parada.get('direccion', '')
        if direccion and direccion not in ['', 'Sin dirección', 'N/A']:
            return direccion
        
        # Intentar con coordenadas
        coords = parada.get('coords', '')
        if coords and ',' in coords:
            return coords
        
        # Intentar con primera persona
        personas = parada.get('personas', [])
        if personas:
            dir_persona = personas[0].get('direccion', '')
            if dir_persona and dir_persona not in ['', 'Sin dirección']:
                return dir_persona
        
        # Usar nombre del edificio como último recurso
        nombre = parada.get('nombre', f"Edificio {parada.get('orden', '')}")
        return f"{nombre}, Ciudad de México"
    
    def _generar_url_maps(self, ruta: Ruta) -> Optional[str]:
        """Genera URL de Google Maps para la ruta"""
        try:
            logger.info(f"Generando URL Maps para ruta {ruta.id}...")
            
            if not ruta.paradas:
                return None
            
            # Extraer direcciones válidas
            direcciones = []
            for parada in ruta.paradas[:CONFIG.MAX_DIRECCIONES_URL]:  # Límite de Google
                dir_raw = self._extraer_direccion_parada(parada)
                dir_limpia = self._limpiar_direccion(dir_raw)
                direcciones.append(dir_limpia)
            
            if len(direcciones) < 1:
                return None
            
            # Codificar para URL
            direcciones_codificadas = [urllib.parse.quote(d) for d in direcciones]
            
            # Construir URL
            base = "https://www.google.com/maps/dir/"
            origen = urllib.parse.quote(CONFIG.ORIGEN_FIJO)
            
            if len(direcciones) == 1:
                url = f"{base}{origen}/{direcciones_codificadas[0]}/data=!4m2!4m1!3e0"
            else:
                waypoints = "/".join(direcciones_codificadas[:-1])
                destino = direcciones_codificadas[-1]
                url = f"{base}{origen}/{waypoints}/{destino}/data=!4m2!4m1!3e0"
            
            logger.info(f"✅ URL Maps generada: {url[:100]}...")
            return url
            
        except Exception as e:
            logger.error(f"Error generando URL Maps: {e}")
            return None
    
    def obtener_ruta_para_usuario(self, user_id: int, user_name: str) -> Optional[Ruta]:
        """Obtiene o asigna una ruta para un usuario"""
        # Si ya tiene ruta asignada
        if user_id in self.rutas_asignadas:
            ruta_id = self.rutas_asignadas[user_id]
            for ruta in self.rutas_disponibles:
                if ruta.id == ruta_id:
                    return ruta
            # Si la ruta ya no existe, eliminar asignación
            del self.rutas_asignadas[user_id]
        
        # Asignar nueva ruta (round-robin simple)
        if not self.rutas_disponibles:
            return None
        
        # Buscar ruta no asignada o tomar la primera
        rutas_asignadas_ids = set(self.rutas_asignadas.values())
        for ruta in self.rutas_disponibles:
            if ruta.id not in rutas_asignadas_ids:
                self.rutas_asignadas[user_id] = ruta.id
                logger.info(f"Ruta {ruta.id} asignada a {user_name}")
                return ruta
        
        # Todas están asignadas, tomar la primera
        ruta = self.rutas_disponibles[0]
        self.rutas_asignadas[user_id] = ruta.id
        logger.info(f"Ruta {ruta.id} (reutilizada) asignada a {user_name}")
        return ruta
    
    def liberar_ruta(self, user_id: int):
        """Libera la ruta asignada a un usuario"""
        if user_id in self.rutas_asignadas:
            del self.rutas_asignadas[user_id]
            logger.info(f"Ruta liberada para usuario {user_id}")

# =============================================================================
# INTERFAZ DE TELEGRAM - MENÚS Y HANDLERS
# =============================================================================

class TelegramBot:
    """Manejador principal del bot de Telegram"""
    
    def __init__(self):
        self.route_manager = RouteManager()
        self._registrar_handlers()
    
    def _registrar_handlers(self):
        """Registra todos los handlers del bot"""
        
        @bot.message_handler(commands=['start', 'inicio', 'menu'])
        def cmd_start(message):
            self._menu_principal(message)
        
        @bot.message_handler(commands=['ruta', 'solicitar'])
        def cmd_ruta(message):
            self._solicitar_ruta(message)
        
        @bot.message_handler(commands=['mi_ruta', 'ver_ruta'])
        def cmd_mi_ruta(message):
            self._ver_ruta_actual(message)
        
        @bot.message_handler(commands=['ayuda', 'help'])
        def cmd_ayuda(message):
            self._mostrar_ayuda(message)
        
        @bot.message_handler(commands=['liberar'])
        def cmd_liberar(message):
            self._liberar_ruta(message)
        
        @bot.callback_query_handler(func=lambda call: True)
        def callback_handler(call):
            self._manejar_callback(call)
        
        @bot.message_handler(content_types=['location'])
        def handle_location(message):
            self._procesar_ubicacion(message)
    
    def _menu_principal(self, message):
        """Muestra el menú principal"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta"),
            types.InlineKeyboardButton("🗺️ VER MI RUTA", callback_data="ver_ruta"),
            types.InlineKeyboardButton("📍 COMPARTIR UBICACIÓN", callback_data="compartir_ubicacion"),
            types.InlineKeyboardButton("📞 CONTACTAR SUPERVISOR", callback_data="supervisor"),
            types.InlineKeyboardButton("📋 ESTADO", callback_data="estado"),
            types.InlineKeyboardButton("❓ AYUDA", callback_data="ayuda")
        )
        
        texto = (
            "🤖 **BOT DE ENTREGAS PJCDMX**\n\n"
            "🚀 **¿Qué deseas hacer?**\n\n"
            "• **🚗 SOLICITAR RUTA** - Obtén tu ruta de entregas\n"
            "• **🗺️ VER MI RUTA** - Muestra tu ruta actual\n"
            "• **📍 COMPARTIR UBICACIÓN** - Envía tu ubicación en tiempo real\n"
            "• **📞 CONTACTAR SUPERVISOR** - Habla con tu supervisor\n"
            "• **📋 ESTADO** - Ver estado de tus entregas\n"
            "• **❓ AYUDA** - Instrucciones de uso"
        )
        
        bot.send_message(
            message.chat.id,
            texto,
            parse_mode='Markdown',
            reply_markup=markup
        )
    
    def _solicitar_ruta(self, message):
        """Solicita y asigna una ruta"""
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        # Mostrar "escribiendo..."
        bot.send_chat_action(message.chat.id, 'typing')
        
        ruta = self.route_manager.obtener_ruta_para_usuario(user_id, user_name)
        
        if not ruta:
            bot.reply_to(
                message,
                "❌ **NO HAY RUTAS DISPONIBLES**\n\n"
                "El sistema está generando nuevas rutas. Intenta más tarde."
            )
            return
        
        # Crear mensaje de respuesta
        texto = (
            f"✅ **RUTA ASIGNADA EXITOSAMENTE**\n\n"
            f"👤 **Repartidor:** {user_name}\n"
            f"📊 **Ruta ID:** {ruta.id} - {ruta.zona}\n"
            f"🏢 **Edificios:** {ruta.total_paradas}\n"
            f"👥 **Personas:** {ruta.total_personas}\n\n"
        )
        
        # Botones
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if ruta.google_maps_url:
            markup.add(
                types.InlineKeyboardButton("📍 ABRIR EN GOOGLE MAPS", url=ruta.google_maps_url)
            )
        
        markup.add(
            types.InlineKeyboardButton("📋 LISTA DE EDIFICIOS", callback_data=f"lista_{ruta.id}"),
            types.InlineKeyboardButton("📍 COMPARTIR UBICACIÓN", callback_data="compartir_ubicacion"),
            types.InlineKeyboardButton("📞 SUPERVISOR", callback_data="supervisor"),
            types.InlineKeyboardButton("⬅️ VOLVER AL MENÚ", callback_data="menu")
        )
        
        # Mostrar primeras paradas
        if ruta.paradas:
            texto += "**PRÓXIMOS EDIFICIOS:**\n"
            for i, parada in enumerate(ruta.paradas[:3], 1):
                nombre = parada.get('nombre', f'Edificio {i}')
                personas = parada.get('total_personas', 1)
                texto += f"\n{i}. **{nombre}** - 👥 {personas} personas"
        
        bot.reply_to(message, texto, parse_mode='Markdown', reply_markup=markup)
    
    def _ver_ruta_actual(self, message):
        """Muestra la ruta actual del usuario"""
        user_id = message.from_user.id
        
        if user_id not in self.route_manager.rutas_asignadas:
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🚗 SOLICITAR RUTA", callback_data="solicitar_ruta")
            )
            bot.reply_to(
                message,
                "⚠️ **NO TIENES UNA RUTA ASIGNADA**\n\nUsa /ruta para solicitar una.",
                reply_markup=markup
            )
            return
        
        ruta_id = self.route_manager.rutas_asignadas[user_id]
        ruta = next((r for r in self.route_manager.rutas_disponibles if r.id == ruta_id), None)
        
        if not ruta:
            self.route_manager.liberar_ruta(user_id)
            bot.reply_to(message, "❌ Tu ruta ya no está disponible. Solicita una nueva con /ruta")
            return
        
        texto = (
            f"🗺️ **TU RUTA ACTUAL**\n\n"
            f"**ID:** {ruta.id} - {ruta.zona}\n"
            f"**Edificios:** {ruta.total_paradas}\n"
            f"**Personas:** {ruta.total_personas}\n\n"
            f"**ORIGEN:**\n{ruta.origen}\n\n"
        )
        
        if ruta.paradas:
            texto += "**EDIFICIOS:**\n"
            for i, parada in enumerate(ruta.paradas[:5], 1):
                nombre = parada.get('nombre', f'Edificio {i}')
                direccion = parada.get('direccion', '')
                personas = parada.get('total_personas', 1)
                
                texto += f"\n{i}. **{nombre}**\n"
                texto += f"   📍 {direccion[:60]}...\n"
                texto += f"   👥 {personas} persona{'s' if personas > 1 else ''}\n"
        
        if len(ruta.paradas) > 5:
            texto += f"\n... y {len(ruta.paradas) - 5} edificios más"
        
        markup = types.InlineKeyboardMarkup()
        if ruta.google_maps_url:
            markup.add(types.InlineKeyboardButton("📍 VER EN GOOGLE MAPS", url=ruta.google_maps_url))
        markup.add(types.InlineKeyboardButton("⬅️ VOLVER", callback_data="menu"))
        
        bot.reply_to(message, texto, parse_mode='Markdown', reply_markup=markup)
    
    def _liberar_ruta(self, message):
        """Libera la ruta actual del usuario"""
        user_id = message.from_user.id
        if user_id in self.route_manager.rutas_asignadas:
            self.route_manager.liberar_ruta(user_id)
            bot.reply_to(message, "✅ Ruta liberada. Puedes solicitar una nueva con /ruta")
        else:
            bot.reply_to(message, "⚠️ No tienes una ruta asignada")
    
    def _mostrar_ayuda(self, message):
        """Muestra mensaje de ayuda"""
        ayuda = (
            "❓ **AYUDA - COMANDOS DISPONIBLES**\n\n"
            "**/start** - Menú principal\n"
            "**/ruta** - Solicitar nueva ruta\n"
            "**/mi_ruta** - Ver ruta actual\n"
            "**/liberar** - Liberar ruta actual\n"
            "**/ayuda** - Mostrar esta ayuda\n\n"
            "**📱 USO DEL BOT:**\n"
            "1. Solicita una ruta con /ruta\n"
            "2. Usa el botón de Google Maps para navegar\n"
            "3. Comparte tu ubicación en tiempo real\n"
            "4. Contacta a supervisor si hay problemas"
        )
        bot.reply_to(message, ayuda, parse_mode='Markdown')
    
    def _procesar_ubicacion(self, message):
        """Procesa ubicación compartida"""
        try:
            lat = message.location.latitude
            lon = message.location.longitude
            user_id = message.from_user.id
            
            # Guardar en DB
            self.route_manager.db.guardar_ubicacion(user_id, lat, lon)
            
            maps_url = f"https://www.google.com/maps?q={lat},{lon}"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🗺️ VER EN MAPAS", url=maps_url),
                types.InlineKeyboardButton("⬅️ VOLVER", callback_data="menu")
            )
            
            bot.reply_to(
                message,
                f"📍 **UBICACIÓN REGISTRADA**\n\n"
                f"Latitud: `{lat}`\n"
                f"Longitud: `{lon}`\n"
                f"Hora: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"✅ Ubicación guardada correctamente",
                parse_mode='Markdown',
                reply_markup=markup
            )
            
        except Exception as e:
            logger.error(f"Error procesando ubicación: {e}")
            bot.reply_to(message, "❌ Error procesando tu ubicación")
    
    def _manejar_callback(self, call):
        """Maneja todos los callbacks de botones inline"""
        try:
            data = call.data
            
            if data == "menu":
                self._menu_principal(call.message)
                bot.answer_callback_query(call.id)
                
            elif data == "solicitar_ruta":
                # Crear mensaje falso para reusar función
                class FakeMessage:
                    def __init__(self, chat_id, from_user):
                        self.chat = type('obj', (object,), {'id': chat_id})()
                        self.from_user = from_user
                
                fake_msg = FakeMessage(call.message.chat.id, call.from_user)
                self._solicitar_ruta(fake_msg)
                bot.answer_callback_query(call.id, "🔄 Procesando solicitud...")
                
            elif data == "ver_ruta":
                fake_msg = type('obj', (object,), {
                    'chat': type('obj', (object,), {'id': call.message.chat.id})(),
                    'from_user': call.from_user
                })
                self._ver_ruta_actual(fake_msg)
                bot.answer_callback_query(call.id)
                
            elif data == "compartir_ubicacion":
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📍 Compartir ubicación", request_location=True))
                
                bot.send_message(
                    call.message.chat.id,
                    "📍 Presiona el botón para compartir tu ubicación:",
                    reply_markup=markup
                )
                bot.answer_callback_query(call.id)
                
            elif data == "supervisor":
                self._mostrar_supervisor(call.message)
                bot.answer_callback_query(call.id)
                
            elif data == "estado":
                self._mostrar_estado(call.message)
                bot.answer_callback_query(call.id)
                
            elif data == "ayuda":
                self._mostrar_ayuda(call.message)
                bot.answer_callback_query(call.id)
                
            elif data.startswith("lista_"):
                ruta_id = int(data.split("_")[1])
                self._mostrar_lista_edificios(call.message, ruta_id)
                bot.answer_callback_query(call.id)
                
            else:
                bot.answer_callback_query(call.id, "Opción no disponible")
                
        except Exception as e:
            logger.error(f"Error en callback {call.data}: {e}")
            bot.answer_callback_query(call.id, "❌ Error")
    
    def _mostrar_supervisor(self, message):
        """Muestra información del supervisor"""
        texto = (
            "📞 **CONTACTO CON SUPERVISOR**\n\n"
            "**Nombre:** Pedro Javier Hernández\n"
            "**Teléfono:** `+525512345678`\n"
            "**Correo:** `supervisor@pjcdmx.gob.mx`\n\n"
            "**Horario:** Lunes a Viernes 8:00-18:00\n\n"
            "**Emergencias:** +525576543210"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📞 LLAMAR", url="tel:+525512345678"),
            types.InlineKeyboardButton("📧 CORREO", url="mailto:supervisor@pjcdmx.gob.mx"),
            types.InlineKeyboardButton("📱 WHATSAPP", url="https://wa.me/525512345678"),
            types.InlineKeyboardButton("⬅️ VOLVER", callback_data="menu")
        )
        
        bot.send_message(message.chat.id, texto, parse_mode='Markdown', reply_markup=markup)
    
    def _mostrar_estado(self, message):
        """Muestra estado del sistema"""
        stats = self.route_manager.db.obtener_estadisticas()
        
        texto = (
            "📊 **ESTADO DEL SISTEMA**\n\n"
            f"**Rutas disponibles:** {len(self.route_manager.rutas_disponibles)}\n"
            f"**Repartidores activos:** {len(self.route_manager.rutas_asignadas)}\n"
            f"**Fotos registradas:** {stats['fotos']}\n"
            f"**Ubicaciones guardadas:** {stats['ubicaciones']}\n\n"
            f"**Estado:** ✅ Operando normalmente"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ VOLVER", callback_data="menu"))
        
        bot.send_message(message.chat.id, texto, parse_mode='Markdown', reply_markup=markup)
    
    def _mostrar_lista_edificios(self, message, ruta_id: int):
        """Muestra lista completa de edificios de una ruta"""
        ruta = next((r for r in self.route_manager.rutas_disponibles if r.id == ruta_id), None)
        
        if not ruta:
            bot.send_message(message.chat.id, "❌ Ruta no encontrada")
            return
        
        texto = f"📋 **RUTA {ruta.id} - {ruta.zona}**\n\n"
        
        for i, parada in enumerate(ruta.paradas, 1):
            nombre = parada.get('nombre', f'Edificio {i}')
            direccion = parada.get('direccion', 'Sin dirección')
            personas = parada.get('total_personas', 1)
            
            texto += f"**{i}. {nombre}**\n"
            texto += f"📍 {direccion[:80]}\n"
            texto += f"👥 {personas} personas\n\n"
            
            if len(texto) > 3500:  # Límite de Telegram
                texto += f"... y {len(ruta.paradas) - i} edificios más"
                break
        
        markup = types.InlineKeyboardMarkup()
        if ruta.google_maps_url:
            markup.add(types.InlineKeyboardButton("📍 VER RUTA EN MAPAS", url=ruta.google_maps_url))
        markup.add(types.InlineKeyboardButton("⬅️ VOLVER", callback_data="menu"))
        
        bot.send_message(message.chat.id, texto, parse_mode='Markdown', reply_markup=markup)
    
    def run(self):
        """Inicia el bot"""
        logger.info("🚀 Bot iniciado - Esperando mensajes...")
        bot.infinity_polling()

# =============================================================================
# FLASK API ENDPOINTS
# =============================================================================

# Inicializar bot (pero no iniciar polling aquí)
telegram_bot = TelegramBot()

@app.route('/')
def home():
    return f"""
    <html>
        <head><title>🤖 Bot PJCDMX - Sistema de Entregas</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h1>🤖 Bot PJCDMX - Sistema de Entregas</h1>
            <p><strong>Estado:</strong> ✅ ACTIVO</p>
            <p><strong>Rutas cargadas:</strong> {len(telegram_bot.route_manager.rutas_disponibles)}</p>
            <p><strong>Usuarios activos:</strong> {len(telegram_bot.route_manager.rutas_asignadas)}</p>
            <hr>
            <p>🔗 <a href="/api/status">Ver estado completo</a></p>
            <p>🔗 <a href="/api/health">Ver salud del sistema</a></p>
        </body>
    </html>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook para recibir updates de Telegram"""
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200

@app.route('/api/status')
def api_status():
    """Endpoint de estado detallado"""
    stats = telegram_bot.route_manager.db.obtener_estadisticas()
    
    return jsonify({
        "status": "ok",
        "rutas": {
            "disponibles": len(telegram_bot.route_manager.rutas_disponibles),
            "asignadas": len(telegram_bot.route_manager.rutas_asignadas)
        },
        "usuarios_activos": len(telegram_bot.route_manager.rutas_asignadas),
        "fotos": stats['fotos'],
        "ubicaciones": stats['ubicaciones'],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health')
def api_health():
    """Endpoint de health check"""
    return jsonify({
        "status": "healthy",
        "bot_token": bool(TOKEN),
        "rutas_cargadas": len(telegram_bot.route_manager.rutas_disponibles) > 0,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/rutas', methods=['POST'])
def api_recibir_ruta():
    """Endpoint para recibir rutas del sistema generador"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Datos vacíos"}), 400
        
        ruta_id = data.get('ruta_id', 1)
        zona = data.get('zona', 'GENERAL')
        
        logger.info(f"📥 Recibiendo ruta {ruta_id} - {zona}")
        
        # Guardar archivo
        archivo = f"{CONFIG.CARPETA_RUTAS}/Ruta_{ruta_id}_{zona}.json"
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Recargar rutas
        telegram_bot.route_manager._cargar_rutas()
        
        return jsonify({
            "status": "success",
            "ruta_id": ruta_id,
            "archivo": archivo,
            "rutas_disponibles": len(telegram_bot.route_manager.rutas_disponibles)
        })
        
    except Exception as e:
        logger.error(f"Error en API /rutas: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Crear carpetas necesarias
    os.makedirs(CONFIG.CARPETA_RUTAS, exist_ok=True)
    os.makedirs(f"{CONFIG.CARPETA_FOTOS}/entregas", exist_ok=True)
    os.makedirs(f"{CONFIG.CARPETA_FOTOS}/incidentes", exist_ok=True)
    
    # Configurar modo de ejecución
    use_webhook = os.environ.get('USE_WEBHOOK', 'false').lower() == 'true'
    
    if use_webhook:
        # Modo webhook para producción
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"🚀 Iniciando en modo WEBHOOK en puerto {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Modo polling para desarrollo
        logger.info("🚀 Iniciando en modo POLLING")
        telegram_bot.run()
