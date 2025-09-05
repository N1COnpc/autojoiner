# Discord Script Finder - Railway

Bot de Discord que detecta join scripts y los envía por WebSocket.

## Funcionalidades

- 🔍 Monitorea canal específico de Discord
- 📡 Extrae join scripts de embeds
- �� Servidor WebSocket para enviar scripts
- 🔊 Notificaciones de sonido
- 🚀 Deploy automático en Railway

## Uso

1. Conecta tu repo a Railway
2. Configura las variables de entorno
3. El bot se conecta automáticamente
4. Conecta tu cliente Lua al WebSocket

## Variables de Entorno

- `DISCORD_TOKEN`: Token del bot de Discord
- `TARGET_CHANNEL_ID`: ID del canal a monitorear
- `PORT`: Puerto del WebSocket (por defecto 8080)