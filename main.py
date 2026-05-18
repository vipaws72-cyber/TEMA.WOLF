import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import time
import json
import asyncio
import traceback
import aiohttp
from datetime import date, timedelta

# =========================
# TOKEN
# =========================
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise ValueError("❌ TOKEN غير موجود")

# =========================
# IDs
# =========================
LOGIN_CHANNEL = 1473015218211651706
GAMES_CHANNEL_ID = 1473015187668861196
LOG_CHANNEL_ID = 1483891442920456263

ADMIN_ROLE = 1473015044643094643

# =========================
# العقوبات
# =========================
roles = {
    "warn1": 1475095531389714604,
    "warn2": 1475097777104097545,
    "warn3": 1475098153421377567,
    "disc1": 1473015121906368715,
    "disc2": 1473015122753749012,
    "timeout": 1473015129019908232,
}

protected_roles = [
    1473015044643094643,
    1473015048443269160,
    1473015062800367618,
]

# =========================
# المدد
# =========================
durations = {
    "warn1": 5 * 24 * 60 * 60,
    "warn2": 7 * 24 * 60 * 60,
    "warn3": 14 * 24 * 60 * 60,
    "disc1": 7 * 24 * 60 * 60,
    "disc2": 14 * 24 * 60 * 60,
}

# =========================
# API الألعاب
# =========================
API_URL = "https://www.gamerpower.com/api/giveaways"

# =========================
# INTENTS
# =========================
intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# DATA
# =========================
sessions = {}
points = {}
leave_timers = {}
sent_games = set()

current_day = date.today()
daily_count = 0

# =========================
# تحميل النقاط
# =========================
if os.path.exists("points.json"):
    try:
        with open("points.json", "r", encoding="utf-8") as f:
            points = json.load(f)
    except Exception:
        points = {}

# =========================
# حفظ النقاط
# =========================
def save_points():
    with open("points.json", "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=4)

# =========================
# تنسيق الوقت
# =========================
def format_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# =========================
# صلاحيات
# =========================
def is_admin(member):
    return any(role.id == ADMIN_ROLE for role in member.roles)

# =========================
# حماية
# =========================
def is_protected(member):
    return any(role.id in protected_roles for role in member.roles)

# =========================
# إزالة رتبة لاحقاً
# =========================
async def remove_role_later(member, role, delay):
    await asyncio.sleep(delay)

    try:
        if role in member.roles:
            await member.remove_roles(role)
    except Exception:
        pass

# =========================
# لوق
# =========================
async def send_log(guild, msg):
    ch = guild.get_channel(LOG_CHANNEL_ID)

    if ch:
        try:
            await ch.send(msg)
        except Exception:
            pass

# =========================
# READY
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(e)

    if not fetch_games.is_running():
        fetch_games.start()

# =========================
# تغيير الأسماء
# =========================
@bot.event
async def on_member_join(member):
    try:
        base_name = member.display_name

        if "👑" in base_name:
            return

        new_name = f"👑 | {base_name} | 👑"

        if len(new_name) > 32:
            allowed_length = 32 - len("👑 |  | 👑")
            base_name = base_name[:allowed_length]
            new_name = f"👑 | {base_name} | 👑"

        await member.edit(nick=new_name)

    except Exception:
        pass

# =========================
# أوامر النقاط
# =========================
@bot.tree.command(name="نقاط")
@app_commands.describe(member="العضو")
async def points_command(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(
        f"📊 | نقاط {member.mention}: {points.get(str(member.id), 0)}"
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
        f"🎁 تم إعطاء {amount} نقطة لـ {member.mention}"
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
        f"🗑️ تم سحب {amount} نقطة من {member.mention}"
    )

@bot.tree.command(name="صفر")
@app_commands.describe(member="العضو")
async def reset_user(interaction: discord.Interaction, member: discord.Member):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)

    points[str(member.id)] = 0

    save_points()

    await interaction.response.send_message(
        f"🧹 تم تصفير {member.mention}"
    )

@bot.tree.command(name="تصفير")
async def reset_all(interaction: discord.Interaction):

    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ ليس لديك صلاحية", ephemeral=True)

    points.clear()

    save_points()

    await interaction.response.send_message("🧹 تم تصفير الجميع")

# =========================
# منع روابط الديسكورد
# =========================
DISCORD_INVITE_PATTERNS = [
    "discord.gg/",
    "discord.com/invite/",
    "discordapp.com/invite/"
]

# =========================
# الرسائل
# =========================
@bot.event
async def on_message(message):
    try:
        if message.author.bot:
            return

        if any(link in message.content.lower() for link in DISCORD_INVITE_PATTERNS):

            if not is_admin(message.author):

                try:
                    await message.delete()
                except Exception:
                    pass

                try:
                    await message.author.timeout(
                        discord.utils.utcnow() + timedelta(hours=2),
                        reason="نشر رابط سيرفر ديسكورد"
                    )
                except Exception:
                    pass

                try:
                    await message.channel.send(
                        f"⛔ {message.author.mention} تم حذف الرابط وإعطاؤك تايم أوت ساعتين",
                        delete_after=10
                    )
                except Exception:
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

                try:
                    await member.send(
                        "🟢 تم تسجيل دخولك\n🎧 يتم احتساب الوقت الآن\n⭐ 30 نقطة لكل ساعة"
                    )
                except Exception:
                    pass

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
🏆 مجموع نقاطك: {points[str(member.id)]}

🎧 شكراً لنشاطك داخل السيرفر
💙 ننتظرك ترجع قريب"""
                )

        await bot.process_commands(message)

    except Exception:
        print(traceback.format_exc())

# =========================
# مراقبة الصوتي
# =========================
@bot.event
async def on_voice_state_update(member, before, after):
    try:
        if before.channel == after.channel:
            return

        if member.id not in sessions:
            return

        if before.channel and not after.channel:

            if member.id in leave_timers:
                leave_timers[member.id].cancel()

            async def leave_timer():
                await asyncio.sleep(300)

                if member.id in sessions and (
                    not member.voice or not member.voice.channel
                ):

                    start = sessions[member.id]
                    duration = int(time.time() - start)
                    earned = int((duration / 3600) * 30)

                    del sessions[member.id]

                    points[str(member.id)] = points.get(str(member.id), 0) + earned

                    save_points()

                    try:
                        await member.send(
                            f"⏰ انتهت المهلة\n⏳ الوقت: {format_time(duration)}\n⭐ النقاط: {earned}"
                        )
                    except Exception:
                        pass

            leave_timers[member.id] = asyncio.create_task(leave_timer())

            try:
                await member.send("🚪 خرجت من الصوتي، لديك 5 دقائق للعودة")
            except Exception:
                pass

        if after.channel:

            if member.id in leave_timers:
                leave_timers[member.id].cancel()
                del leave_timers[member.id]

                try:
                    await member.send("✅ تم إلغاء المهلة واستمرار تسجيلك")
                except Exception:
                    pass

    except Exception:
        print(traceback.format_exc())

# =========================
# الألعاب المجانية
# =========================
@tasks.loop(minutes=5)
async def fetch_games():
    global daily_count, current_day

    await bot.wait_until_ready()

    if date.today() != current_day:
        daily_count = 0
        current_day = date.today()
        print("🔄 تم تصفير العداد اليومي")

    if daily_count >= 4:
        return

    channel = bot.get_channel(GAMES_CHANNEL_ID)

    if channel is None:
        print("❌ روم الألعاب غير موجود")
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
                        description=f"📍 {platforms}\n[اضغط لتحميل اللعبة]({url})",
                        color=discord.Color.green()
                    )

                    if image:
                        embed.set_image(url=image)

                    await channel.send(embed=embed)

        except Exception as e:
            print(f"❌ Error: {e}")

# =========================
# العقوبات
# =========================
class PunishSelect(discord.ui.Select):
    def __init__(self, member):
        self.member = member

        options = [
            discord.SelectOption(label="قذف", description="انذار + تايم اوت"),
            discord.SelectOption(label="سب", description="تحذير"),
            discord.SelectOption(label="تسحيب", description="باند نهائي"),
            discord.SelectOption(label="تسحيب متكرر", description="ديسك"),
            discord.SelectOption(label="استعمال ادارة", description="إزالة رتبة الإدارة"),
        ]

        super().__init__(
            placeholder="اختر العقوبة",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        member = self.member
        guild = interaction.guild

        if is_protected(member):
            return await interaction.response.send_message(
                "❌ هذا العضو محمي",
                ephemeral=True
            )

        try:
            if self.values[0] == "قذف":

                r1 = guild.get_role(roles["disc1"])
                r2 = guild.get_role(roles["disc2"])
                t = guild.get_role(roles["timeout"])

                await member.add_roles(r1, r2, t)

                await member.timeout(
                    discord.utils.utcnow() + timedelta(days=7)
                )

                bot.loop.create_task(remove_role_later(member, r1, durations["disc1"]))
                bot.loop.create_task(remove_role_later(member, r2, durations["disc2"]))
                bot.loop.create_task(remove_role_later(member, t, 7 * 24 * 60 * 60))

            elif self.values[0] == "سب":

                r1 = guild.get_role(roles["warn1"])
                r2 = guild.get_role(roles["warn2"])

                await member.add_roles(r1, r2)

                bot.loop.create_task(remove_role_later(member, r1, durations["warn1"]))
                bot.loop.create_task(remove_role_later(member, r2, durations["warn2"]))

            elif self.values[0] == "تسحيب":
                await member.ban(reason="تسحيب")

            elif self.values[0] == "تسحيب متكرر":

                r1 = guild.get_role(roles["disc1"])
                r2 = guild.get_role(roles["disc2"])

                await member.add_roles(r1, r2)

            elif self.values[0] == "استعمال ادارة":

                for role in member.roles:
                    if role.permissions.administrator:
                        await member.remove_roles(role)

            await interaction.response.send_message(
                "✅ تم تنفيذ العقوبة",
                ephemeral=True
            )

            await send_log(
                guild,
                f"📢 تم معاقبة {member.mention} بواسطة {interaction.user.mention}"
            )

        except Exception:
            print(traceback.format_exc())

class PunishView(discord.ui.View):
    def __init__(self, member):
        super().__init__()
        self.add_item(PunishSelect(member))

@bot.tree.command(name="عقوبة")
async def punish(interaction: discord.Interaction, member: discord.Member):

    await interaction.response.send_message(
        "اختر العقوبة:",
        view=PunishView(member),
        ephemeral=True
    )

# =========================
# تشغيل البوت
# =========================
bot.run(TOKEN)
