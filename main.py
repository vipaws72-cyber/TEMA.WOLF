TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("TOKEN غير موجود")

LOGIN_CHANNEL = 1473015218211651706
GAMES_CHANNEL_ID = 1473015187668861196
LOG_CHANNEL_ID = 1483891442920456263

ADMIN_ROLES = [
    1473015044643094643,
    1473015048443269160,
]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

sessions = {}
points = {}
leave_timers = {}
sent_games = set()

API_URL = "https://www.gamerpower.com/api/giveaways"

current_day = date.today()
daily_count = 0

if os.path.exists("points.json"):
    try:
        with open("points.json", "r", encoding="utf-8") as f:
            points = json.load(f)
    except:
        points = {}

def save_points():
    with open("points.json", "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=4)

def format_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

def is_admin(member):
    return any(role.id in ADMIN_ROLES for role in member.roles)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

    if not fetch_games.is_running():
        fetch_games.start()

@bot.tree.command(name="نقاط")
@app_commands.describe(member="العضو")
async def points_command(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(
        f"📊 | نقاط {member.mention}: {points.get(str(member.id), 0)}"
    )

@bot.tree.command(name="تصفير")
async def reset_all(interaction: discord.Interaction):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)

    points.clear()
    save_points()

    await interaction.response.send_message("✅ تم تصفير جميع النقاط")

@bot.tree.command(name="صفر")
@app_commands.describe(member="العضو")
async def reset_user(interaction: discord.Interaction, member: discord.Member):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)

    points[str(member.id)] = 0
    save_points()

    await interaction.response.send_message(
        f"✅ تم تصفير نقاط {member.mention}"
    )

@bot.tree.command(name="سحب_نقاط")
@app_commands.describe(member="العضو", amount="عدد النقاط")
async def remove_points(interaction: discord.Interaction, member: discord.Member, amount: int):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)

    current = points.get(str(member.id), 0)

    if amount <= 0 or current < amount:
        return await interaction.response.send_message("❌ رقم غير صحيح", ephemeral=True)

    points[str(member.id)] = current - amount

    save_points()

    await interaction.response.send_message(
        f"➖ تم سحب {amount} نقطة من {member.mention}"
    )

@bot.tree.command(name="اعطاء_نقاط")
@app_commands.describe(member="العضو", amount="عدد النقاط")
async def give_points(interaction: discord.Interaction, member: discord.Member, amount: int):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)

    if amount <= 0:
        return await interaction.response.send_message("❌ رقم غير صحيح", ephemeral=True)

    points[str(member.id)] = points.get(str(member.id), 0) + amount

    save_points()

    await interaction.response.send_message(
        f"➕ تم إعطاء {amount} نقطة لـ {member.mention}"
    )

DISCORD_INVITE_PATTERNS = [
    "discord.gg/",
    "discord.com/invite/",
    "discordapp.com/invite/"
]

@bot.event
async def on_message(message):
    try:
        if message.author.bot:
            return

        if any(link in message.content.lower() for link in DISCORD_INVITE_PATTERNS):

            if not is_admin(message.author):

                try:
                    await message.delete()
                except:
                    pass

                try:
                    await message.author.timeout(
                        discord.utils.utcnow() + timedelta(hours=2),
                        reason="نشر رابط ديسكورد"
                    )
                except:
                    pass

                return

        if message.channel.id == LOGIN_CHANNEL:

            member = message.author
            content = message.content.strip()

            if content == "تسجيل دخول":

                if not member.voice or not member.voice.channel:
                    return await message.reply("❌ لازم تكون داخل روم صوتي")

                if member.id in sessions:
                    return await message.reply("⚠️ أنت مسجل بالفعل")

                sessions[member.id] = time.time()

                await message.reply("🟢 تم تسجيل دخولك")

            elif content == "تسجيل خروج":

                if member.id not in sessions:
                    return await message.reply("❌ أنت غير مسجل")

                start = sessions[member.id]
                duration = int(time.time() - start)
                earned = int((duration / 3600) * 30)

                del sessions[member.id]

                points[str(member.id)] = points.get(str(member.id), 0) + earned

                save_points()

                await message.reply(
                    f"""✨ تم تسجيل خروجك بنجاح ✨

⏳ الوقت الذي قضيته: {format_time(duration)}
⭐ النقاط المكتسبة: {earned}
🏆 مجموع نقاطك: {points[str(member.id)]}"""
                )

                try:
                    await member.send(
                        f"""🎧 شكراً لنشاطك داخل السيرفر

⏳ الوقت الذي قضيته: {format_time(duration)}
⭐ النقاط المكتسبة: {earned}
🏆 مجموع نقاطك: {points[str(member.id)]}

💙 ننتظرك ترجع قريب"""
                    )
                except:
                    pass

        await bot.process_commands(message)

    except:
        print(traceback.format_exc())

@tasks.loop(minutes=5)
async def fetch_games():
    global daily_count, current_day

    await bot.wait_until_ready()

    if date.today() != current_day:
        daily_count = 0
        current_day = date.today()

    if daily_count >= 4:
        return

    channel = bot.get_channel(GAMES_CHANNEL_ID)

    if channel is None:
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL) as resp:
                data = await resp.json()

                for game in data:

                    if daily_count >= 4:
                        break

                    game_id = game.get("id")
                    title = game.get("title")
                    url = game.get("open_giveaway_url")
                    image = game.get("image")
                    platforms = game.get("platforms", "")

                    if not game_id or not title or not url:
                        continue

                    if "Epic" not in platforms and "Steam" not in platforms:
                        continue

                    if game_id in sent_games:
                        continue

                    sent_games.add(game_id)
                    daily_count += 1

                    embed = discord.Embed(
                        title=f"🎮 {title}",
                        description=f"📍 {platforms}\n[تحميل اللعبة]({url})",
                        color=discord.Color.green()
                    )

                    if image:
                        embed.set_image(url=image)

                    await channel.send(embed=embed)

        except Exception as e:
            print(e)

bot.run(TOKEN)
