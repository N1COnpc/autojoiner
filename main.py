import asyncio
import json
import logging
import websockets
import platform
import threading
import winsound
import os
import aiohttp
import base64
import random
import time
from datetime import datetime
from websockets import WebSocketServerProtocol
from aiohttp import ClientTimeout, web

# ==================== CONFIGURACIÓN ====================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = os.environ.get("TARGET_CHANNEL_ID", "1082008662408712305")
DISCORD_API_URL = "https://discord.com/api/v9"
HTTP_PORT = int(os.environ.get("PORT", 8080))
WEBSOCKET_PORT = 8081

# Validar que el token esté configurado
if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN no está configurado en las variables de entorno")
    exit(1)

# Configuración de sonidos
ENABLE_SOUND = True
SOUND_FREQUENCY = 1000
SOUND_DURATION = 500

# ==================== LOGGER ====================
def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    class CustomFormatter(logging.Formatter):
        def format(self, record):
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            return f'[{timestamp}] [{record.levelname}]: {record.getMessage()}'

    cn_handler = logging.StreamHandler()
    cn_handler.setLevel(logging.INFO)
    cn_handler.setFormatter(CustomFormatter())
    logger.addHandler(cn_handler)

    return logger

logger = setup_logger()

# ==================== UTILS ====================
def get_time():
    return datetime.now().strftime("%H:%M:%S")

def play_notification_sound():
    """Reproduce un sonido de notificación"""
    if not ENABLE_SOUND:
        return
    
    try:
        if platform.system() == "Windows":
            winsound.Beep(SOUND_FREQUENCY, SOUND_DURATION)
        else:
            os.system(f"echo -e '\a'")
    except Exception as e:
        logger.debug(f"Error reproduciendo sonido: {e}")

def play_script_found_sound():
    """Reproduce un sonido especial cuando se encuentra un script"""
    if not ENABLE_SOUND:
        return
    
    try:
        if platform.system() == "Windows":
            winsound.Beep(800, 200)
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 300)
        else:
            for i in range(3):
                os.system(f"echo -e '\a'")
                os.system("sleep 0.2")
    except Exception as e:
        logger.debug(f"Error reproduciendo sonido de script: {e}")

def extract_join_script(event: dict):
    """Extrae el join script de los embeds del mensaje"""
    try:
        embeds = event["d"].get("embeds", [])
        if not embeds:
            return None

        fields = embeds[0].get("fields", [])
        for field in fields:
            name = field.get("name", "").strip()
            value = field.get("value", "").strip()

            if "join script" in name.lower() or "script" in name.lower():
                script = value.strip("`")
                return script

    except Exception as e:
        logger.debug(f"Error extrayendo script: {e}")

    return None

# ==================== WEBSOCKET SERVER ====================
class ScriptWebSocketServer:
    def __init__(self):
        self.connected_clients = set()
        self._paused = False
        self._lock = threading.Lock()

    @property
    def paused(self):
        with self._lock:
            return self._paused

    async def handler(self, websocket: WebSocketServerProtocol):
        logger.info(f"> New client connected: {websocket.remote_address}")
        self.connected_clients.add(websocket)

        try:
            await asyncio.Future()
        finally:
            self.connected_clients.remove(websocket)
            logger.info(f"> Client disconnected: {websocket.remote_address}")

    async def broadcast_script(self, script: str):
        """Envía el script a todos los clientes conectados"""
        if self.paused:
            logger.info("> Script sending paused")
            return

        if not self.connected_clients:
            logger.warning("> No clients connected to receive script")
            return

        dead_clients = set()
        sent_count = 0

        for client in self.connected_clients:
            try:
                await client.send(script)
                sent_count += 1
            except websockets.ConnectionClosed:
                dead_clients.add(client)

        if dead_clients:
            self.connected_clients.difference_update(dead_clients)

        logger.info(f"> Script sent to {sent_count} client(s)")

    async def run(self):
        """Inicia el servidor WebSocket"""
        try:
            async with websockets.serve(self.handler, "0.0.0.0", WEBSOCKET_PORT):
                logger.info(f"> WebSocket server started: ws://0.0.0.0:{WEBSOCKET_PORT}")
                await asyncio.Future()
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")

def execute_script(script: str):
    """Envía el script por WebSocket a los clientes conectados"""
    try:
        logger.info(f"[SCRIPT] Enviando script por WebSocket:")
        logger.info(f"[SCRIPT] {script[:100]}...")
        
        asyncio.create_task(server.broadcast_script(script))
        
        return True
    except Exception as e:
        logger.error(f"Error enviando script: {e}")
        return False

# Crear instancia del servidor
server = ScriptWebSocketServer()

def websocket_main():
    """Función para ejecutar el servidor WebSocket en un hilo separado"""
    asyncio.run(server.run())

# ==================== DISCORD HTTP API ====================
class DiscordMonitor:
    def __init__(self):
        self.base_url = DISCORD_API_URL
        self.session = None
        self.timeout = ClientTimeout(total=30)
        self.known_messages = set()
        
    def get_headers(self):
        buildNum = random.randint(160000, 170000)
        return {
            "Authorization": DISCORD_TOKEN,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Super-Properties": base64.b64encode(json.dumps({
                "os": "Windows",
                "browser": "Chrome",
                "device": "",
                "system_locale": "es-ES",
                "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "browser_version": "120.0.0.0",
                "os_version": "10",
                "referrer": "",
                "referring_domain": "",
                "referrer_current": "",
                "referring_domain_current": "",
                "release_channel": "stable",
                "client_build_number": buildNum,
                "client_event_source": None
            }).encode()).decode(),
            "X-Discord-Locale": "es-ES",
            "X-Debug-Options": "bugReporterEnabled",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/channels/@me",
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "*/*",
            "TE": "trailers"
        }

    async def get_session(self):
        try:
            if self.session is None or self.session.closed:
                connector = aiohttp.TCPConnector(
                    ssl=False,
                    force_close=True,
                    limit=50,
                    ttl_dns_cache=300
                )
                
                self.session = aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=connector
                )
            return self.session
        except Exception as e:
            logger.error(f"Error creando sesión: {str(e)}")
            connector = aiohttp.TCPConnector(ssl=False, force_close=True, limit=50)
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector
            )
            return self.session

    async def safe_request(self, method, url, **kwargs):
        max_retries = 3
        current_try = 0
        
        while current_try < max_retries:
            try:
                session = await self.get_session()
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 429:  # Rate limit
                        data = await response.json()
                        retry_after = data.get('retry_after', 5)
                        logger.info(f"Rate limit, esperando {retry_after}s...")
                        await asyncio.sleep(retry_after + random.uniform(0.1, 1))
                        continue
                    
                    if response.status in [200, 201, 204]:
                        try:
                            return await response.json()
                        except:
                            return True
                    else:
                        logger.error(f"Error HTTP {response.status}")
                        return None
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"Error en intento {current_try + 1}: {str(e)}")
                current_try += 1
                if current_try < max_retries:
                    await asyncio.sleep(random.uniform(1, 3))
                continue
            except Exception as e:
                logger.error(f"Error fatal: {str(e)}")
                return None
        return None

    async def get_channel_messages(self, limit: int = 10):
        """Obtiene los últimos mensajes del canal objetivo"""
        try:
            url = f"{self.base_url}/channels/{TARGET_CHANNEL_ID}/messages"
            headers = self.get_headers()
            params = {"limit": limit}
            
            result = await self.safe_request('GET', url, headers=headers, params=params)
            if result:
                return result
            return []
        except Exception as e:
            logger.error(f"Error obteniendo mensajes: {e}")
            return []

    async def check_new_messages(self):
        """Verifica si hay mensajes nuevos en el canal"""
        try:
            messages = await self.get_channel_messages(5)
            if not messages:
                logger.debug("No se pudieron obtener mensajes")
                return

            new_messages = 0
            
            for message in messages:
                message_id = message.get('id')
                
                if message_id not in self.known_messages:
                    logger.info(f"[MESSAGE] Nuevo mensaje detectado: {message_id}")
                    
                    # Agregar a mensajes conocidos
                    self.known_messages.add(message_id)
                    new_messages += 1
                    
                    # Reproducir sonido de notificación
                    play_notification_sound()
                    
                    # Extraer join script
                    script = extract_join_script(message)
                    
                    if script:
                        logger.info(f"[FOUND] Join script encontrado!")
                        logger.info(f"[SCRIPT] Longitud: {len(script)} caracteres")
                        
                        # Reproducir sonido especial para script encontrado
                        play_script_found_sound()
                        
                        # Ejecutar el script
                        if execute_script(script):
                            logger.info(f"[SUCCESS] Script ejecutado correctamente")
                        else:
                            logger.error(f"[ERROR] Fallo al ejecutar script")
                    else:
                        logger.debug(f"[DEBUG] No se encontró join script en el mensaje")
            
            if new_messages == 0:
                logger.debug("No hay mensajes nuevos")
            else:
                logger.info(f"✅ {new_messages} mensaje(s) nuevo(s) procesado(s)")
                
        except Exception as e:
            logger.error(f"Error verificando mensajes: {e}")

    async def start_monitoring(self):
        """Inicia el monitoreo de mensajes"""
        logger.info("Iniciando monitoreo de mensajes...")
        
        # Cargar mensajes existentes para evitar procesar mensajes viejos
        logger.info("Cargando mensajes existentes...")
        existing_messages = await self.get_channel_messages(10)
        for message in existing_messages:
            self.known_messages.add(message.get('id'))
        logger.info(f"Cargados {len(self.known_messages)} mensajes existentes")
        
        logger.info("🚀 Iniciando monitoreo... Solo detectará mensajes NUEVOS")
        
        while True:
            try:
                await self.check_new_messages()
                await asyncio.sleep(2)  # Verificar cada 2 segundos
            except KeyboardInterrupt:
                logger.info("Monitoreo detenido por el usuario")
                break
            except Exception as e:
                logger.error(f"Error en monitoreo: {e}")
                await asyncio.sleep(5)

    async def cleanup(self):
        """Limpia recursos"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

# ==================== HTTP SERVER ====================
async def health_check(request):
    """Health check endpoint para Railway"""
    return web.Response(text="OK", status=200)

async def start_http_server():
    """Inicia el servidor HTTP con health check"""
    try:
        app = web.Application()
        app.router.add_get('/health', health_check)
        app.router.add_get('/', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        # Usar puerto principal para HTTP (Railway espera esto)
        site = web.TCPSite(runner, '0.0.0.0', HTTP_PORT)
        await site.start()
        logger.info(f"HTTP server started on port {HTTP_PORT} with health check")
        return runner
    except Exception as e:
        logger.error(f"Error starting HTTP server: {e}")
        return None

# ==================== MAIN ====================
async def main():
    monitor = DiscordMonitor()
    http_runner = None
    
    try:
        print(f"[{get_time()}] [INFO] Discord Script Finder - Railway")
        print(f"[{get_time()}] [INFO] Canal objetivo: {TARGET_CHANNEL_ID}")
        print(f"[{get_time()}] [INFO] HTTP server: http://0.0.0.0:{HTTP_PORT}/health")
        print(f"[{get_time()}] [INFO] WebSocket server: ws://0.0.0.0:{WEBSOCKET_PORT}")
        print(f"[{get_time()}] [INFO] Sonidos: {'Habilitados' if ENABLE_SOUND else 'Deshabilitados'}")
        print(f"[{get_time()}] [INFO] Iniciando servidores...")
        print()

        # Iniciar el servidor HTTP con health check PRIMERO
        http_runner = await start_http_server()
        if not http_runner:
            logger.error("Failed to start HTTP server, exiting...")
            return
        
        logger.info("HTTP server started successfully!")
        
        # Iniciar el servidor WebSocket en un hilo separado
        websocket_thread = threading.Thread(target=websocket_main, daemon=True)
        websocket_thread.start()
        
        # Esperar para que Railway pueda hacer health check
        logger.info("Waiting for Railway health check...")
        await asyncio.sleep(5)
        
        # Iniciar el monitoreo de Discord
        await monitor.start_monitoring()
        
    except KeyboardInterrupt:
        logger.info("Application closed by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        if http_runner:
            await http_runner.cleanup()
        await monitor.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
