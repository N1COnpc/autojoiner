import asyncio
import json
import logging
import websockets
import platform
import threading
import winsound
import os
from datetime import datetime
from websockets import WebSocketServerProtocol

# ==================== CONFIGURACIÓN ====================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
TARGET_CHANNEL_ID = os.environ.get("TARGET_CHANNEL_ID", "1082008662408712305")
DISCORD_WS_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
WEBSOCKET_PORT = int(os.environ.get("PORT", 8080))

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
        async with websockets.serve(self.handler, "0.0.0.0", WEBSOCKET_PORT):
            logger.info(f"> WebSocket server started: ws://0.0.0.0:{WEBSOCKET_PORT}")
            await asyncio.Future()

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

# ==================== DISCORD ====================
async def identify(ws):
    """Envía la identificación al gateway de Discord"""
    identify_payload = {
        "op": 2,
        "d": {
            "token": DISCORD_TOKEN,
            "properties": {
                "os": "Windows", 
                "browser": "Chrome", 
                "device": "", 
                "system_locale": "en-US",
                "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "referrer": "https://discord.com/", 
                "referring_domain": "discord.com"
            }
        }
    }

    await ws.send(json.dumps(identify_payload))
    logger.info("Sent client identification")

async def message_check(event):
    """Verifica si el mensaje es del canal objetivo y extrae el script"""
    try:
        channel_id = event['d']['channel_id']
        
        if channel_id != TARGET_CHANNEL_ID:
            return

        logger.info(f"[MESSAGE] Nuevo mensaje en canal {channel_id}")
        
        play_notification_sound()
        
        script = extract_join_script(event)
        
        if script:
            logger.info(f"[FOUND] Join script encontrado!")
            logger.info(f"[SCRIPT] Longitud: {len(script)} caracteres")
            
            play_script_found_sound()
            
            if execute_script(script):
                logger.info(f"[SUCCESS] Script ejecutado correctamente")
            else:
                logger.error(f"[ERROR] Fallo al ejecutar script")
        else:
            logger.debug(f"[DEBUG] No se encontró join script en el mensaje")

    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")

async def message_listener(ws):
    """Escucha mensajes del WebSocket de Discord"""
    logger.info("Listening for new messages...")
    
    while True:
        try:
            event = json.loads(await ws.recv())
            op_code = event.get("op", None)

            if op_code == 10:  # Hello
                logger.info("Received Hello from Discord")
                heartbeat = {"op": 1, "d": None}
                await ws.send(json.dumps(heartbeat))

            elif op_code == 11:  # Heartbeat ACK
                logger.debug("Heartbeat ACK received")

            elif op_code == 0:  # Dispatch
                event_type = event.get("t")
                if event_type == "MESSAGE_CREATE":
                    asyncio.create_task(message_check(event))

            elif op_code == 9:  # Invalid Session
                logger.warning("Invalid session, reconnecting...")
                await identify(ws)

        except websockets.exceptions.ConnectionClosed:
            logger.error("WebSocket connection closed")
            break
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            break

async def listener():
    """Función principal que maneja la conexión a Discord"""
    while True:
        try:
            logger.info(f"[CONNECT] Conectando a Discord...")
            async with websockets.connect(DISCORD_WS_URL, max_size=None) as ws:
                await identify(ws)
                await message_listener(ws)

        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"WebSocket closed: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
            continue

# ==================== MAIN ====================
if __name__ == "__main__":
    try:
        print(f"[{get_time()}] [INFO] Discord Script Finder - Railway")
        print(f"[{get_time()}] [INFO] Canal objetivo: {TARGET_CHANNEL_ID}")
        print(f"[{get_time()}] [INFO] WebSocket server: ws://0.0.0.0:{WEBSOCKET_PORT}")
        print(f"[{get_time()}] [INFO] Sonidos: {'Habilitados' if ENABLE_SOUND else 'Deshabilitados'}")
        print(f"[{get_time()}] [INFO] Iniciando servidores...")
        print()

        # Iniciar el servidor WebSocket en un hilo separado
        websocket_thread = threading.Thread(target=websocket_main, daemon=True)
        websocket_thread.start()
        
        # Esperar un poco para que el servidor WebSocket se inicie
        import time
        time.sleep(1)
        
        # Iniciar el listener de Discord
        asyncio.run(listener())
        
    except KeyboardInterrupt:
        logger.info("Application closed by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
