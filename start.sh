#!/bin/bash

echo "================================================"
echo "🤖 BOT PJCDMX - INICIANDO EN MODO PRODUCCIÓN"
echo "================================================"

# Verificar variables de entorno críticas
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN no está configurado"
    exit 1
fi

echo "✅ BOT_TOKEN configurado"
echo "🔧 Puerto: $PORT"
echo "🌍 Entorno: $RAILWAY_ENVIRONMENT"

# Crear carpetas necesarias si no existen
mkdir -p carpeta_fotos_central/entregas
mkdir -p carpeta_fotos_central/incidentes
mkdir -p carpeta_fotos_central/estatus
mkdir -p carpeta_fotos_central/general
mkdir -p rutas_telegram
mkdir -p avances_ruta
mkdir -p incidencias_trafico

echo "📁 Carpetas del sistema verificadas"

# Configurar webhook antes de iniciar
echo "🔄 Configurando webhook para Telegram..."
python -c "
import os
import time
import telebot

TOKEN = os.environ.get('BOT_TOKEN')
if TOKEN:
    bot = telebot.TeleBot(TOKEN)
    
    # Obtener URL de Railway
    railway_url = os.environ.get('RAILWAY_STATIC_URL', 'https://monitoring-routes-pjcdmx-production.up.railway.app')
    webhook_url = f'{railway_url}/webhook'
    
    print(f'🌐 Configurando webhook: {webhook_url}')
    
    try:
        bot.remove_webhook()
        time.sleep(2)
        success = bot.set_webhook(url=webhook_url)
        if success:
            print('✅ Webhook configurado exitosamente')
        else:
            print('❌ Error configurando webhook')
    except Exception as e:
        print(f'⚠️ Error en webhook: {e}')
else:
    print('❌ No se pudo configurar webhook: BOT_TOKEN no disponible')
"

# Iniciar la aplicación con Gunicorn
echo "🚀 Iniciando servidor con Gunicorn..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile - wsgi:app
