import discord, os, json
from discord.ext import commands
from dotenv import load_dotenv

DATA_FILE = "/app/data/db.json"
load_dotenv()
TOKEN = os.getenv("TOKEN")
PREFIX = '!'

intents = discord.Intents.default()
intents.members = True 
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

@bot.tree.command(name="top", description="Показывает человека который отправил больше всего стикеров и гиф")
async def stats(interaction: discord.Interaction):
    chat = str(interaction.guild_id)
    with open(DATA_FILE, "r", encoding='utf-8') as file:
        data = json.load(file)
    users = data[chat]["users"]
    first_user = list(users.keys())[0]
    best_user, best_score = first_user, sum(users[first_user])
    for id, lst in users.items():
        score = sum(lst)
        if score > best_score:
            best_user = id
            best_score = score
    
    user = bot.get_user(int(best_user))
    user_name = user.display_name if user else f"Пользователь [{best_user}]"
    sticks = users[best_user][0]
    gifs = users[best_user][1]

    if sticks+gifs != 0:  return await interaction.response.send_message(f"🏆 **Чемпион чата:** {user_name}\nОн отправил `{sticks}` стикеров и `{gifs}` гиф!")
    return await interaction.response.send_message("В чат не было отправлено ни одного стикера или гиф")

@bot.tree.command(name='get_sticker', description='Показать самый популярный стикер в этом чате')
async def stick(interaction: discord.Interaction):
    chat = str(interaction.guild_id)
    with open(DATA_FILE, "r", encoding='utf-8') as file:
        data = json.load(file)

    sticks = data.get(chat, {}).get("stickers")
    if sticks:
        max_key = max(sticks, key=sticks.get)
        try:
            #используем bot.fetch_sticker и передаем туда ИМЕННО КЛЮЧ (max_key)
            sticker = await bot.fetch_sticker(int(max_key))
        except discord.NotFound:
            # Защита на случай, если стикер удалили с сервера, чтобы бот не упал
            return await interaction.response.send_message(f"Самый популярный стикер имел ID `{max_key}`, но его удалили из Дискорда.")
        
        await interaction.response.send_message("Самый популярный стикер в этом чате: ")
        await interaction.channel.send(stickers=[sticker])
    else: return await interaction.response.send_message("Стикеров в чате не было")

@bot.tree.command(name='get_gif', description='Показать самый популярный гиф в этом чате')
async def giff(interaction: discord.Interaction):
    chat = str(interaction.guild_id)
    with open(DATA_FILE, "r", encoding='utf-8') as file:
        data = json.load(file)
    gifs = data.get(chat, {}).get("gif")
    if gifs:
        max_key = max(gifs, key=gifs.get)
        await interaction.response.send_message("Самая популярная GIF в этом чате: ")
        
        # Проверяем, что сохранено в max_key: ссылка или ID файла
        if max_key.startswith("http"):
            # ВАРИАНТ 1: Это ссылка на Tenor/Giphy. Просто отправляем её текстом.
            # Discord сам автоматически превратит её в красивую живую гифку.
            await interaction.channel.send(max_key)
        else:
            # ВАРИАНТ 2: Это ID файла. По нему нельзя восстановить старый файл напрямую.
            # Поэтому пишем заглушку или отправляем уведомление.
            await interaction.channel.send(f"*(Эта GIF была загружена файлом, её ID: `{max_key}`)*")
    else:
        return await interaction.response.send_message("GIF-анимаций в чате еще не было.")

@bot.listen("on_guild_join")
async def jonas_joined_guild(guild: discord.Guild):
    with open(DATA_FILE, "r", encoding='utf-8') as file:
        data = json.load(file)
    data[str(guild.id)] = {
        "name": guild.name,
        "stickers": {},                #тип id_стикера: кол-во использований
        "gif": {},                     #тип id_гиф: кол-во использований
        "users": {}                    #тип id_юзера: [кол-во стикеров, кол-во гиф]
    }
    for member in guild.members:
        if member.bot: continue
        data[str(guild.id)]["users"][str(member.id)] = [0,0]
    with open(DATA_FILE, "w", encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    # Опционально: Найти первый доступный текстовый канал и отправить приветствие
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(
                f"👋 Привет, **{guild.name}**! Я бот для подсчета стикеров и GIF.\n"
                f"Я уже начал собирать статистику. Используйте `/stats` для просмотра!"
            )
            break


@bot.listen("on_message")
async def stick_handler(message: discord.Message):
    if message.guild is None or message.author.bot: return
    if not message.stickers: return 

    member = str(message.author.id)
    chat = str(message.guild.id)
    stick = message.stickers[0]
    stick = str(stick.id)
    with open(DATA_FILE, "r", encoding='utf-8') as file:
        data = json.load(file)
    
    if member not in data[chat]["users"]:
        data[chat]["users"][member] = [0, 0]
    data[chat]["users"][member][0] += 1

    sticks = data.get(chat, {}).get("stickers")

    if stick in sticks: data[chat]["stickers"][stick] += 1
    else: data[chat]["stickers"][stick] = 1

    with open(DATA_FILE, "w", encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

@bot.listen("on_message")
async def gif_handler(message: discord.Message):
    if message.author.bot or message.guild is None: return

    is_gif = False
    gif_id = None

    if "://tenor.com" in message.content or "://giphy.com" in message.content:
        is_gif = True
        gif_id = message.content.strip() 
    elif message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and "image/gif" in attachment.content_type:
                is_gif = True
                gif_id = str(attachment.id)
                break

    if is_gif and gif_id:
        member = str(message.author.id)
        chat = str(message.guild.id)

        with open(DATA_FILE, "r", encoding='utf-8') as file:
            data = json.load(file)

        if member not in data[chat]["users"]:
            data[chat]["users"][member] = [0, 0]
        data[chat]["users"][member][1] += 1

        if "gif" not in data[chat]: data[chat]["gif"] = {}
        gifs_dict = data[chat]["gif"]

        if gif_id in gifs_dict:
            data[chat]["gif"][gif_id] += 1
        else:
            data[chat]["gif"][gif_id] = 1

        with open(DATA_FILE, "w", encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            
        #print(f"Засчитана GIF от пользователя {member}")

@bot.event
async def on_ready():
    #print(f"Робот {bot.user} успешно авторизован.")
    try:
        # Эта строчка отправляет все созданные в коде слэш-команды на сервера Discord
        synced = await bot.tree.sync()
        print(f"Успешно зарегистрировано слэш-команд: {len(synced)}")
    except Exception as e:
        print(f"Ошибка при регистрации команд: {e}")

@bot.command
async def commands(ctx):
    pass


if __name__ == "__main__":
    bot.run(TOKEN)