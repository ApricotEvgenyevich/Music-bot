import os
import telebot
from dotenv import load_dotenv
import logging
import traceback
import yt_dlp
import tempfile
import shutil
import sys

# Определяем путь к ffmpeg в проекте
if sys.platform.startswith('win'):
    FFMPEG_PATH = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')
else:
    FFMPEG_PATH = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg')

# Проверяем, что ffmpeg существует
if not os.path.exists(FFMPEG_PATH):
    raise FileNotFoundError(f"ffmpeg не найден по пути: {FFMPEG_PATH}")
# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_errors.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MusicBot")

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    logger.critical("❌ Токен не найден в .env!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
DOWNLOAD_DIR = "downloads"

# Создаём папку для загрузок
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_youtube_audio(url: str) -> str:
    logger.info(f"📥 Начинаю скачивание: {url}")
    
    temp_dir = tempfile.mkdtemp(dir=DOWNLOAD_DIR)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'postprocessor_args': ['-ar', '48000'],
        'ffmpeg_location': os.path.dirname(FFMPEG_PATH),  # ← Ключевая строка!
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_path = filename.rsplit('.', 1)[0] + '.mp3'
        return mp3_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании: {str(e)}")
        raise

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_path = filename.rsplit('.', 1)[0] + '.mp3'
            
        logger.info(f"✅ Аудио успешно скачано: {mp3_path}")
        return mp3_path
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании: {str(e)}")
        raise

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        bot.reply_to(message, "🎵 Привет! Отправь ссылку на YouTube, и я пришлю MP3!")
    except Exception as e:
        logger.error(f"Ошибка в /start: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        text = message.text.strip()
        user_id = message.from_user.id
        
        # Проверка ссылки
        if not ("youtube.com" in text or "youtu.be" in text):
            bot.reply_to(message, "❌ Пожалуйста, отправь ссылку на YouTube видео.")
            return

        bot.reply_to(message, "⏳ Скачиваю аудио... Это может занять 1-2 минуты.")
        logger.info(f"📥 Запрос на скачивание от {user_id}: {text}")

        # Скачиваем аудио
        mp3_path = download_youtube_audio(text)
        
        # Проверяем размер (Telegram ограничивает 50 МБ)
        file_size = os.path.getsize(mp3_path) / (1024 * 1024)  # в МБ
        if file_size > 50:
            os.remove(mp3_path)
            bot.reply_to(message, f"❌ Файл слишком большой ({file_size:.1f} МБ). Максимум 50 МБ.")
            return

        # Отправляем файл
        with open(mp3_path, 'rb') as audio:
            bot.send_audio(message.chat.id, audio, caption="✅ Готово! Наслаждайся музыкой!")
        
        logger.info(f"📤 Отправлен MP3 пользователю {user_id}")
        
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Ошибка YouTube-DL: {str(e)}")
        bot.reply_to(message, "❌ Не удалось скачать аудио. Проверьте ссылку или попробуйте позже.")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        logger.error(f"Детали:\n{traceback.format_exc()}")
        bot.reply_to(message, "⚠️ Произошла ошибка при обработке запроса.")
        
    finally:
        # Очищаем временные файлы
        try:
            if 'mp3_path' in locals() and os.path.exists(mp3_path):
                parent_dir = os.path.dirname(mp3_path)
                shutil.rmtree(parent_dir, ignore_errors=True)
                logger.info(f"🧹 Удалены временные файлы: {parent_dir}")
        except Exception as e:
            logger.warning(f"Не удалось удалить временные файлы: {str(e)}")

if __name__ == '__main__':
    logger.info("🚀 Бот с функцией скачивания запущен!")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)