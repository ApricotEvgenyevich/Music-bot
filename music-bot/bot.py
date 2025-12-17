from telebot import types
import os
import telebot
from dotenv import load_dotenv
import logging
import yt_dlp
import tempfile
import shutil
import sys
import sqlite3
from database import init_db, get_or_create_user, add_track, get_user_tracks, create_playlist, get_user_playlists, get_playlist_tracks, add_track_to_playlist, remove_track_from_playlist, is_track_in_playlist, get_track_by_id

init_db()

if sys.platform.startswith('win'):
    FFMPEG_PATH = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')
else:
    FFMPEG_PATH = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg')
if not os.path.exists(FFMPEG_PATH):
    raise FileNotFoundError(f"ffmpeg не найден по пути: {FFMPEG_PATH}")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot_errors.log", encoding='utf-8'), logging.StreamHandler()]
)
logger = logging.getLogger("SwagaGod")


load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.critical("❌ Токен не найден в .env!")
    exit(1)
bot = telebot.TeleBot(BOT_TOKEN)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
user_states = {}


def get_reply_keyboard():    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.add(types.KeyboardButton("/start"))
    return markup


def show_main_menu(chat_id, message_id=None):    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("Добавить трек", callback_data='add_music')
    markup.row(btn1)
    btn2 = types.InlineKeyboardButton("Моя музыка", callback_data='my_music')
    markup.row(btn2)
    btn3 = types.InlineKeyboardButton("Мои плейлисты", callback_data='my_playlists')
    markup.row(btn3)
    btn4 = types.InlineKeyboardButton("Создать плейлист", callback_data='create_playlist')
    markup.row(btn4)    
    if message_id:
        bot.edit_message_text(
            "Привет! Я твой телеграм-плеер SwagaGod, вот что я могу:", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id,"Привет! Я твой телеграм-плеер SwagaGod, вот что я могу:", reply_markup=markup)

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
        'ffmpeg_location': os.path.dirname(FFMPEG_PATH),  
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
        logger.info(f"✅ Аудио успешно скачано: {mp3_path}")
        return mp3_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании: {str(e)}")
        raise


@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):    
    show_main_menu(call.message.chat.id, call.message.message_id)    


@bot.callback_query_handler(func=lambda call: call.data == "add_music")
def add_music(call):
    user_states[call.from_user.id] = {'action': 'waiting_for_track'}    
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')
    markup.add(back_btn)  

    bot.edit_message_text("🎧 Отправь ссылку на YouTube:", call.message.chat.id, call.message.message_id, reply_markup=markup)    
    bot.send_message(call.message.chat.id, "📝 Ты можешь отправить ссылку здесь 👇", )


@bot.callback_query_handler(func=lambda call: call.data == "my_music")
def my_music(call):
    user_id = get_or_create_user(call.from_user.id, call.from_user.username)
    tracks = get_user_tracks(user_id, 20)    

    if not tracks:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')
        markup.add(back_btn)        
        bot.edit_message_text("📭 У тебя пока нет сохранённой музыки.", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return   
     
    response = "🎵 *Твоя музыка:* 🎵\n\n"
    markup = types.InlineKeyboardMarkup()  

    for i, track in enumerate(tracks, 1):
        track_id, title, artist, duration = track
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "??:??"
        response += f"{i}. *{title}*\n"

        if artist:
            response += f"   Исполнитель: {artist}\n"
        response += f"   Длительность: {duration_str}\n"  

        add_btn = types.InlineKeyboardButton(f"➕ Добавить '{title[:15]}...' в плейлист",  callback_data=f"add_track_{track_id}")
        play_btn = types.InlineKeyboardButton(f"🎵 Воспроизвести '{title[:15]}...'", callback_data=f"play_track_{track_id}")
        markup.add(add_btn, play_btn)    
    
    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')
    markup.add(back_btn)    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("play_track_"))
def play_track(call):
    track_id = int(call.data.split("_")[2])
    track_info = get_track_by_id(track_id)    

    if not track_info:
        bot.answer_callback_query(call.id, "❌ Трек не найден!")
        return  
      
    track_id, user_id, file_id, title, artist, duration = track_info
    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "??:??"   

    try:
        bot.send_audio(call.message.chat.id, file_id, caption=f"🎵 *{title}*\n🎤 {artist or 'Неизвестный исполнитель'}\n⏱ {duration_str}", parse_mode='Markdown')
        bot.answer_callback_query(call.id, f"🎶 Воспроизводится: {title}")

    except Exception as e:
        logger.error(f"Ошибка при отправке аудио: {str(e)}")
        bot.answer_callback_query(call.id, "❌ Ошибка при воспроизведении трека!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("play_all_"))
def play_all_playlist(call):
    playlist_id = int(call.data.split("_")[2])
    tracks = get_playlist_tracks(playlist_id)   

    if not tracks:
        bot.answer_callback_query(call.id, "📭 В плейлисте пока нет треков")
        return 
           
    first_track = tracks[0]
    track_id, title, artist, duration = first_track
    track_info = get_track_by_id(track_id)    

    if track_info:
        _, _, file_id, _, _, _ = track_info
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "??:??"        
        sent_msg = bot.send_audio(call.message.chat.id, file_id, caption=f"🎵 *{title}*\n🎤 {artist or 'Неизвестный исполнитель'}\n⏱ {duration_str}\n\n🎧 *Плейлист начался!*", parse_mode='Markdown') 
             
        if len(tracks) > 1:
            bot.send_message(call.message.chat.id, f"⏳ Загружаю остальные треки из плейлиста ({len(tracks)-1} шт.)...")     

            for i, track in enumerate(tracks[1:], 2):
                track_id, title, artist, duration = track
                track_info = get_track_by_id(track_id)   

                if track_info:
                    _, _, file_id, _, _, _ = track_info
                    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "??:??"               
                    import time
                    time.sleep(0.5)                    
                    bot.send_audio(call.message.chat.id, file_id, caption=f"🎵 *{title}*\n🎤 {artist or 'Неизвестный исполнитель'}\n⏱ {duration_str}\n📀 Трек {i}/{len(tracks)}", parse_mode='Markdown')        
        
        bot.answer_callback_query(call.id, f"✅ Плейлист воспроизводится ({len(tracks)} треков)")
    
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка при воспроизведении плейлиста!")


@bot.callback_query_handler(func=lambda call: call.data == "my_playlists")
def my_playlists(call):
    user_id = get_or_create_user(call.from_user.id, call.from_user.username)
    playlists = get_user_playlists(user_id)   

    if not playlists:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')
        markup.add(back_btn)        
        bot.edit_message_text("📭 У тебя пока нет плейлистов. Создай первый с помощью кнопки 'Создать плейлист", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return
    
    markup = types.InlineKeyboardMarkup()

    for playlist_id, name in playlists:
        btn = types.InlineKeyboardButton(f"🎧 {name}", callback_data=f"playlist_{playlist_id}")
        markup.add(btn)  

    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')
    markup.add(back_btn)    
    bot.edit_message_text("📁 *Твои плейлисты:*", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("playlist_"))
def show_playlist_tracks(call):
    playlist_id = int(call.data.split("_")[1])
    tracks = get_playlist_tracks(playlist_id)    
    
    if not tracks:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("⬅️ Назад к плейлистам", callback_data='my_playlists')
        markup.add(back_btn)        
        bot.edit_message_text("📭 В этом плейлисте пока нет треков.", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return  
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,))
    playlist_name = cursor.fetchone()[0]
    conn.close() 

    response = f"🎵 *Плейлист: {playlist_name}* 🎵\n\n"
    markup = types.InlineKeyboardMarkup()     
    play_all_btn = types.InlineKeyboardButton("🎶 Воспроизвести весь плейлист", callback_data=f"play_all_{playlist_id}")
    markup.add(play_all_btn)   

    for i, track in enumerate(tracks, 1):
        track_id, title, artist, duration = track
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "??:??"
        response += f"{i}. *{title}*\n"
        
        if artist:
            response += f"   Исполнитель: {artist}\n"

        response += f" Длительность: {duration_str}\n"      
        play_btn = types.InlineKeyboardButton(f"▶️ Воспроизвести '{title[:15]}...'", callback_data=f"play_track_{track_id}")
        remove_btn = types.InlineKeyboardButton(f"❌ Удалить '{title[:15]}...'",  callback_data=f"remove_from_playlist_{playlist_id}_{track_id}")

        markup.add(play_btn, remove_btn)  

    back_btn1 = types.InlineKeyboardButton("⬅️ Назад к плейлистам", callback_data='my_playlists')
    back_btn2 = types.InlineKeyboardButton("⬅️ В главное меню", callback_data='back_to_menu')
    markup.add(back_btn1, back_btn2)    
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("add_track_"))
def add_track_to_playlist_menu(call):
    track_id = int(call.data.split("_")[2])
    user_id = get_or_create_user(call.from_user.id, call.from_user.username)    
    user_states[call.from_user.id] = {'action': 'select_playlist_for_track', 'track_id': track_id}   
    playlists = get_user_playlists(user_id)    
    
    if not playlists:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='my_music')
        markup.add(back_btn)        
        bot.edit_message_text("📭 У тебя пока нет плейлистов, ты можешь создать новый ыплейлист", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return    

    markup = types.InlineKeyboardMarkup()

    for playlist_id, name in playlists:
        btn = types.InlineKeyboardButton(f"🎧 {name}", callback_data=f"select_playlist_{playlist_id}")
        markup.add(btn)    
    
    back_btn = types.InlineKeyboardButton("⬅️ Назад к музыке", callback_data='my_music')
    markup.add(back_btn)    
    bot.edit_message_text("📁 *Выбери плейлист для добавления трека:*", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_playlist_"))
def select_playlist_for_track(call):
    playlist_id = int(call.data.split("_")[2])
    user_id = get_or_create_user(call.from_user.id, call.from_user.username)    
    
    if call.from_user.id not in user_states or user_states[call.from_user.id].get('action') != 'select_playlist_for_track':
        bot.answer_callback_query(call.id, "❌ Сессия истекла. Начни заново.")
        return    
    
    track_id = user_states[call.from_user.id].get('track_id')        
    
    if is_track_in_playlist(playlist_id, track_id):
        bot.answer_callback_query(call.id, "❌ Этот трек уже есть в плейлисте!")
        return        
    
    success = add_track_to_playlist(playlist_id, track_id)    
    
    if success:
        bot.answer_callback_query(call.id, "✅ Трек успешно добавлен в плейлист!")       
        my_music(call)
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка при добавлении трека в плейлист!")


@bot.callback_query_handler(func=lambda call: call.data.startswith("remove_from_playlist_"))
def remove_track_from_playlist_handler(call):
    parts = call.data.split("_")
    playlist_id = int(parts[3])
    track_id = int(parts[4])     
    
    remove_track_from_playlist(playlist_id, track_id)   
    bot.answer_callback_query(call.id, "✅ Трек удалён из плейлиста!")     
    show_playlist_tracks(call)


@bot.callback_query_handler(func=lambda call: call.data == "create_playlist")
def create_playlist_start(call):
    user_states[call.from_user.id] = {'action': 'waiting_for_playlist_name'}    
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_to_menu')
    markup.add(back_btn)    
    
    bot.edit_message_text("✏️ Введите название для нового плейлиста:", call.message.chat.id, call.message.message_id, reply_markup=markup)    
    bot.send_message(call.message.chat.id, "📝 Напиши название плейлиста 👇")


@bot.message_handler(commands=['start'])
def start(message):
    show_main_menu(message.chat.id)    


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    logger.info(f"📨 Входящее: тип={message.content_type}, текст={getattr(message,'text','НЕТ')}, user_id={user_id}")
    
    if message.content_type == 'text' and message.text == '/start':
        show_main_menu(message.chat.id)
        bot.send_message(message.chat.id,"👋 Используй кнопку ниже для быстрого вызова меню!",reply_markup=get_reply_keyboard())
        if user_id in user_states: del user_states[user_id]
        return
    
    if user_id in user_states:
        state = user_states[user_id]['action']
        logger.info(f"Пользователь в состоянии: {state}")
        
        if state == 'waiting_for_playlist_name':
            db_user_id = get_or_create_user(user_id,message.from_user.username)
            playlist_id = create_playlist(db_user_id,message.text.strip())
            del user_states[user_id]
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("⬅️ В главное меню",callback_data='back_to_menu')
            markup.add(back_btn)
            bot.reply_to(message,f"✅ Плейлист '{message.text}' успешно создан!",reply_markup=markup)
            bot.send_message(message.chat.id,"🎉 Плейлист создан!",reply_markup=get_reply_keyboard())
            return
            
        elif state == 'waiting_for_track':
            logger.info("Обработка трека в состоянии waiting_for_track")
            db_user_id = get_or_create_user(user_id,message.from_user.username)
                
            if message.content_type == 'text' and ('youtube.com' in message.text or 'youtu.be' in message.text):
                logger.info(f"Получена YouTube ссылка: {message.text}")
                bot.reply_to(message,"⏳ Скачиваю аудио... Это может занять 1-2 минуты.")
                try:
                    mp3_path = download_youtube_audio(message.text.strip())
                    with open(mp3_path,'rb') as audio:
                        sent_message = bot.send_audio(message.chat.id,audio,caption="✅ Трек скачан! Теперь он сохранён в твоей коллекции.",title=os.path.basename(mp3_path).replace('.mp3',''),performer="SwagaGod")
                    file_id = sent_message.audio.file_id
                    title = os.path.basename(mp3_path).replace('.mp3','')
                    duration = None
                    track_id = add_track(db_user_id,file_id,title,duration=duration)
                    logger.info(f"YouTube трек сохранён с ID: {track_id}")
                    os.remove(mp3_path)
                    parent_dir = os.path.dirname(mp3_path)
                    shutil.rmtree(parent_dir,ignore_errors=True)
                    bot.send_message(message.chat.id,"🎵 Трек скачан!",reply_markup=get_reply_keyboard())
                except Exception as e:
                    logger.error(f"Ошибка при скачивании: {str(e)}")
                    bot.reply_to(message,"❌ Не удалось скачать аудио. Проверьте ссылку или попробуйте позже.")
                del user_states[user_id]
            else:
                bot.reply_to(message,"❌ Неподдерживаемый формат. Отправьте ссылку YouTube или аудиофайл.")
                del user_states[user_id]
            return
    
    elif message.content_type == 'text' and ('youtube.com' in message.text or 'youtu.be' in message.text):
        logger.info(f"YouTube ссылка получена вне состояния: {message.text}")
        bot.reply_to(message,"⏳ Скачиваю аудио... Это может занять 1-2 минуты.")
        try:
            mp3_path = download_youtube_audio(message.text.strip())
            with open(mp3_path,'rb') as audio:
                bot.send_audio(message.chat.id,audio,caption="✅ Готово! Наслаждайся музыкой!",reply_markup=get_reply_keyboard())
            os.remove(mp3_path)
            parent_dir = os.path.dirname(mp3_path)
            shutil.rmtree(parent_dir,ignore_errors=True)
        except Exception as e:
            logger.error(f"Ошибка при скачивании: {str(e)}")
            bot.reply_to(message,"❌ Не удалось скачать аудио. Проверьте ссылку или попробуйте позже.")
    
    elif message.content_type == 'text':
        logger.info(f"Получен текст вне команд: {message.text}")


if __name__ == '__main__':
    logger.info("🚀 SwagaGod запущен!")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)