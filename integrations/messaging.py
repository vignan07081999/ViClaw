import logging
from core.config import is_platform_enabled, get_platform_token

# Note: In a full production implementation, these would use asyncio and the respective libraries
# (python-telegram-bot, discord.py, etc.) to listen for incoming messages and push them
# into an asyncio queue read by the core agent heartbeat.

class BaseConnector:
    def __init__(self, platform_name):
        self.platform_name = platform_name
        self.enabled = is_platform_enabled(platform_name)
        self.token = get_platform_token(platform_name)

    def start(self, message_callback):
        """
        Starts the listener. message_callback is the function to call when a message is received.
        Signature: message_callback(platform_name, user_id, message_text)
        """
        if not self.enabled:
            return
        logging.info(f"Starting {self.platform_name} connector...")
        self._start_listening(message_callback)

    def _start_listening(self, message_callback):
        raise NotImplementedError

    def send_message(self, user_id, message_text):
        """
        Sends a message back to the user on this platform.
        """
        raise NotImplementedError

class CLIConnector(BaseConnector):
    def __init__(self):
        super().__init__("cli")

    def _start_listening(self, message_callback):
        import threading
        
        def listen_loop():
            # Run in a separate thread so it doesn't block the asyncio event loop
            try:
                print("CLI Connector started. Type your message and press Enter. Type 'exit' to quit.")
                while True:
                    user_input = input("User: ")
                    if user_input.strip().lower() == "exit":
                        break
                    if user_input.strip():
                        # Push the message to the central agent queue
                        message_callback("cli", "local_user", user_input.strip())
            except EOFError:
                pass
            except KeyboardInterrupt:
                pass
            
        t = threading.Thread(target=listen_loop, daemon=True)
        t.start()

    def send_message(self, user_id, message_text):
        print(f"\nOpenClaw: {message_text}\nUser: ", end="", flush=True)

class TelegramConnector(BaseConnector):
    def __init__(self):
        super().__init__("telegram")
        self.app = None
        self.bot = None
        self.loop = None

    def _start_listening(self, message_callback):
        if not self.token:
            logging.error("Telegram token not configured.")
            return

        import threading
        import asyncio
        from telegram import Update
        from telegram.ext import Application, MessageHandler, filters, ContextTypes

        logging.info("Initializing Telegram bot...")

        def _run_bot():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self.app = Application.builder().token(self.token).build()
            self.bot = self.app.bot

            async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if not update.message or not update.message.text:
                    return
                user_id = str(update.effective_user.id)
                text = update.message.text
                message_callback("telegram", user_id, text)

            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
            # Also catch commands as text
            self.app.add_handler(MessageHandler(filters.COMMAND, handle_msg))

            logging.info("Telegram polling started.")
            self.app.run_polling(drop_pending_updates=True)

        t = threading.Thread(target=_run_bot, daemon=True)
        t.start()

    def send_message(self, user_id, message_text):
        if not self.bot or not self.loop:
            return
        
        import asyncio
        
        async def _send():
            try:
                await self.bot.send_message(chat_id=int(user_id), text=message_text)
            except Exception as e:
                logging.error(f"Failed to send Telegram message: {e}")
                
        # Fire and forget threadsafe
        asyncio.run_coroutine_threadsafe(_send(), self.loop)

class DiscordConnector(BaseConnector):
    def __init__(self):
        super().__init__("discord")

    def _start_listening(self, message_callback):
        if not self.token:
            logging.error("Discord token not configured.")
            return
        logging.info("Discord integration initialized. (Placeholder implementation for OpenClaw Clone)")
        # Actual implementation: bot.run(self.token) in an asyncio task

    def send_message(self, user_id, message_text):
        logging.info(f"[Discord] Sending to {user_id}: {message_text}")

class WhatsAppConnector(BaseConnector):
    def __init__(self):
        super().__init__("whatsapp")

    def _start_listening(self, message_callback):
        if not self.token:
            return
        logging.info("WhatsApp integration initialized. (Placeholder)")

    def send_message(self, user_id, message_text):
        logging.info(f"[WhatsApp] Sending to {user_id}: {message_text}")

# Central Platform Manager
class PlatformManager:
    def __init__(self, is_daemon=False):
        self.connectors = {
            "telegram": TelegramConnector(),
            "discord": DiscordConnector(),
            "whatsapp": WhatsAppConnector()
        }
        
        # Only attach interactive CLI connector if running attached to a terminal
        if not is_daemon:
            self.connectors["cli"] = CLIConnector()

    def start_all(self, message_callback):
        for name, connector in self.connectors.items():
            connector.start(message_callback)

    def send(self, platform_name, user_id, message_text):
        if platform_name in self.connectors:
            self.connectors[platform_name].send_message(user_id, message_text)
        else:
            logging.error(f"Cannot send message to unknown platform {platform_name}")
