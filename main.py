
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
from discord import TextChannel, Role
import os, json, asyncio, random, re
from datetime import timedelta
from dotenv import load_dotenv
from datetime import datetime

# Load token from .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Bot token not found in .env")

# ---------- Define intents ----------
intents = discord.Intents.all()  # you can customize, e.g., intents.members = True

# ---------- Create bot ----------
PREFIX = "."  # Define your bot prefix here
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ---------- Persistent storage ----------
WELCOME_FILE = "welcome.json"
REACTION_ROLES_FILE = "reaction_roles.json"
GIVEAWAYS_FILE = "giveaways.json"
CUSTOM_CMDS_FILE = "custom_cmds.json"
for f in [WELCOME_FILE, REACTION_ROLES_FILE, GIVEAWAYS_FILE, CUSTOM_CMDS_FILE]:
    if not os.path.exists(f):
        with open(f, "w") as file:
            json.dump({}, file)


# ---------- Helper Functions ----------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def parse_duration(duration: str) -> int:
    match = re.match(r"(\d+)([smhd])", duration.lower())
    if not match:
        return None
    amount, unit = match.groups()
    return int(amount) * {"s":1,"m":60,"h":3600,"d":86400}[unit]

async def check_perm(ctx, perm_name, friendly_name=None):
    if friendly_name is None:
        friendly_name = perm_name.replace('_',' ').title()
    if not getattr(ctx.author.guild_permissions, perm_name, False):
        await ctx.send(f"❌ Missing **{friendly_name}** permission.")
        return False
    return True
@bot.command(name="auction")
async def auction(ctx, *, args: str = None):
    """
    Start an auction for one or multiple targets.
    Usage: .auction <item> | <minimum_bid> | <@user/@role ...>
    Example: .auction Nitro Account | 5$ | @Members @VIP @User123
    """
    await ctx.message.delete()

    if not args:
        return await ctx.send("❌ Usage: `.auction <item> | <minimum_bid> | <@user/@role ...>`")

    # Split by separator "|"
    parts = [p.strip() for p in args.split("|")]
    if len(parts) != 3:
        return await ctx.send("❌ Please use the format: `item | minimum_bid | @user/@role ...`")

    item, min_bid, target_str = parts

    # --- Detect targets (users or roles) ---
    target_objs = []

    # Add mentioned users
    target_objs.extend(ctx.message.mentions)

    # Add mentioned roles
    target_objs.extend(ctx.message.role_mentions)

    # If no mentions, try to find roles/users by name (comma-separated)
    if not target_objs:
        names = [n.strip() for n in re.split(r",|\s+", target_str)]
        for name in names:
            # Check role first
            role = discord.utils.find(lambda r: r.name.lower() == name.lower(), ctx.guild.roles)
            if role and role not in target_objs:
                target_objs.append(role)
            else:
                # Check user by name
                member = discord.utils.find(lambda m: m.name.lower() == name.lower(), ctx.guild.members)
                if member and member not in target_objs:
                    target_objs.append(member)

    if not target_objs:
        return await ctx.send("❌ Could not find any valid targets (users or roles).")

    # --- Embed for auction ---
    embed = discord.Embed(
        title="🪙 Auction Started!",
        description=(
            f"**Item:** {item}\n"
            f"**Minimum Bid:** {min_bid}\n"
            f"**Hosted by:** {ctx.author.mention}"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
   

    # Build target text outside embed
    target_texts = []
    for obj in target_objs:
        if isinstance(obj, discord.Role):
            target_texts.append(f"{obj.mention}")
        else:
            target_texts.append(f"**User:** {obj.mention}")

    await ctx.send("\n".join(target_texts), embed=embed)

@bot.command(name="stock")
async def stock(ctx, *, args: str = None):
    """
    Post a stock item for sale.
    Usage: .stock <item> | <price> | <@user/@role ...>
    Example: .stock Nitro Account | 5$ | @Members @VIP
    """
    await ctx.message.delete()

    if not args:
        return await ctx.send("❌ Usage: `.stock <item> | <price> | <@user/@role ...>`")

    # Split by separator "|"
    parts = [p.strip() for p in args.split("|")]
    if len(parts) != 3:
        return await ctx.send("❌ Please use the format: `item | price | @user/@role ...`")

    item, price, target_str = parts

    # --- Detect targets (users or roles) ---
    target_objs = []

    # Add mentioned users
    target_objs.extend(ctx.message.mentions)

    # Add mentioned roles
    target_objs.extend(ctx.message.role_mentions)

    # If no mentions, try to find roles/users by name (comma or space separated)
    if not target_objs:
        names = [n.strip() for n in re.split(r",|\s+", target_str)]
        for name in names:
            # Check role first
            role = discord.utils.find(lambda r: r.name.lower() == name.lower(), ctx.guild.roles)
            if role and role not in target_objs:
                target_objs.append(role)
            else:
                # Check user by name
                member = discord.utils.find(lambda m: m.name.lower() == name.lower(), ctx.guild.members)
                if member and member not in target_objs:
                    target_objs.append(member)

    if not target_objs:
        return await ctx.send("❌ Could not find any valid targets (users or roles).")

    # --- Embed for stock ---
    embed = discord.Embed(
        title="📦 Stock Item Available!",
        description=(
            f"**Item:** {item}\n"
            f"**Price:** {price}\n"
            f"**Posted by:** {ctx.author.mention}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
   

    # Build target text outside embed
    target_texts = []
    for obj in target_objs:
        if isinstance(obj, discord.Role):
            target_texts.append(f"{obj.mention}")
        else:
            target_texts.append(f"**User:** {obj.mention}")

    await ctx.send("\n".join(target_texts), embed=embed)



# ---------- Welcome System with Auto-role ----------
@bot.command(name="setwelcomechannel")
@commands.has_permissions(administrator=True)
async def set_welcome_channel(ctx, channel: discord.TextChannel):
    data = load_json(WELCOME_FILE)
    data[str(ctx.guild.id)] = {'channel_id': channel.id, 'message': 'Welcome {user} to {guild}!', 'autorole': None}
    save_json(WELCOME_FILE, data)
    await ctx.send(f"✅ Welcome channel set to {channel.mention}", delete_after=5)

@bot.command(name="setwelcomemsg")
@commands.has_permissions(administrator=True)
async def set_welcome_msg(ctx, *, msg):
    data = load_json(WELCOME_FILE)
    guild_data = data.get(str(ctx.guild.id))
    if not guild_data:
        await ctx.send("❌ Set a welcome channel first.")
        return
    guild_data['message'] = msg
    data[str(ctx.guild.id)] = guild_data
    save_json(WELCOME_FILE, data)
    await ctx.send(f"✅ Welcome message updated!", delete_after=5)

@bot.command(name="setautorole")
@commands.has_permissions(administrator=True)
async def set_autorole(ctx, role: discord.Role):
    data = load_json(WELCOME_FILE)
    guild_data = data.get(str(ctx.guild.id))
    if not guild_data:
        await ctx.send("❌ Set a welcome channel first.")
        return
    guild_data['autorole'] = role.id
    data[str(ctx.guild.id)] = guild_data
    save_json(WELCOME_FILE, data)
    await ctx.send(f"✅ Auto-role set to {role.mention}", delete_after=5)

@bot.event
async def on_member_join(member):
    data = load_json(WELCOME_FILE)
    guild_data = data.get(str(member.guild.id))
    if guild_data:
        channel = member.guild.get_channel(guild_data['channel_id'])
        if channel:
            msg = guild_data['message'].replace('{user}', member.mention).replace('{guild}', member.guild.name)
            await channel.send(msg)
        role_id = guild_data.get('autorole')
        if role_id:
            role = member.guild.get_role(role_id)
            if role:
                await member.add_roles(role)

# ---------- Moderation ----------
@bot.command(name="kick")
async def kick(ctx, member: discord.Member, *, reason=None):
    if not await check_perm(ctx, "kick_members"): return
    await member.kick(reason=reason)
    await ctx.send(f"✅ {member} has been kicked.")

@bot.command(name="ban")
async def ban(ctx, member: discord.Member, *, reason=None):
    if not await check_perm(ctx, "ban_members"): return
    await member.ban(reason=reason)
    await ctx.send(f"✅ {member} has been banned.")

@bot.command(name="purge")
async def purge(ctx, amount: int):
    if not await check_perm(ctx, "manage_messages"): return
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"✅ Deleted {len(deleted)} messages.", delete_after=5)

@bot.command(name="to")
async def timeout(ctx, member: discord.Member, duration: str):
    if not await check_perm(ctx, "moderate_members"): return
    seconds = parse_duration(duration)
    if not seconds:
        await ctx.send("❌ Invalid duration format.")
        return
    try:
        await member.timeout(discord.utils.utcnow() + timedelta(seconds=seconds))
        await ctx.send(f"✅ {member.mention} timed out for {duration}.", delete_after=5)
    except:
        await ctx.send("❌ Could not timeout member.")

@bot.command(name="nick")
async def nick(ctx, member: discord.Member, *, new_nick: str):
    if not await check_perm(ctx, "manage_nicknames"): return
    await member.edit(nick=new_nick)
    await ctx.send(f"✅ {member}'s nickname changed to {new_nick}.")

@bot.command(name="role_add")
async def role_add(ctx, member: discord.Member, *, role_name: str):
    if not await check_perm(ctx, "manage_roles"): return
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"❌ Role '{role_name}' not found.")
        return
    await member.add_roles(role)
    await ctx.send(f"✅ {role.mention} added to {member}.")

@bot.command(name="autorole")
@commands.has_permissions(administrator=True)
async def set_autorole(ctx, role: discord.Role):
    """
    Set an auto-role for new members.
    Usage: .setautorole @Role
    """
    # Load existing welcome data
    data = load_json(WELCOME_FILE)
    guild_data = data.get(str(ctx.guild.id))

    if not guild_data:
        return await ctx.send("❌ Please set a welcome channel first using `.setwelcomechannel`.")

    # Set the autorole
    guild_data['autorole'] = role.id
    data[str(ctx.guild.id)] = guild_data
    save_json(WELCOME_FILE, data)

    await ctx.send(f"✅ Auto-role has been set to {role.mention} for new members.", delete_after=5)


DATA_FILE = "storages.json"


def _ensure_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

async def load_data():
    _ensure_file()
    async with _lock:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

async def save_data(data):
    _ensure_file()
    async with _lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# --- STORE COMMAND ---
@bot.command(name="store")
async def store(ctx, *, content: str = None):
    if not content:
        return await ctx.reply("❗ Usage: `.store <text>`", mention_author=False)
    guild_id = str(ctx.guild.id) if ctx.guild else f"dm-{ctx.author.id}"
    data = await load_data()

    entry = {
        "text": content.strip(),
        "author": str(ctx.author),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    data.setdefault(guild_id, []).append(entry)

    if len(data[guild_id]) > 500:
        data[guild_id] = data[guild_id][-500:]
    await save_data(data)
    await ctx.reply("✅ Stored successfully!", mention_author=False)

# --- DISPLAY STORAGE ---
@bot.command(name="storage")
async def storssge(ctx, amount: int = 10):
    guild_id = str(ctx.guild.id) if ctx.guild else f"dm-{ctx.author.id}"
    data = await load_data()
    items = data.get(guild_id, [])

    if not items:
        return await ctx.reply("ℹ️ No stored info found.", mention_author=False)

    to_show = items[-amount:]
    to_show.reverse()

    lines = []
    for i, e in enumerate(to_show, start=1):
        t = e["timestamp"][:19].replace("T", " ")
        lines.append(f"**{i}.** `{t}` • *{e['author']}* — {e['text'][:150]}")

    embed = discord.Embed(
        title=f"🗂️ Stored items (last {len(to_show)})",
        description="\n".join(lines),
        color=0x2F3136
    )
    await ctx.reply(embed=embed, mention_author=False)

# --- UNSTORE COMMAND ---
@bot.command(name="unstore")
async def unstore(ctx, *, arg: str = None):
    """
    .unstore <index> — removes a stored item
    .unstore all — clears all (admin only)
    """
    if not arg:
        return await ctx.reply("❗ Usage: `.unstore <index>` or `.unstore all`", mention_author=False)

    guild_id = str(ctx.guild.id) if ctx.guild else f"dm-{ctx.author.id}"
    data = await load_data()

    if guild_id not in data or not data[guild_id]:
        return await ctx.reply("ℹ️ No stored info found.", mention_author=False)

    if arg.lower() == "all":
        # only admins can clear all
        if not ctx.author.guild_permissions.administrator:
            return await ctx.reply("🚫 Only admins can use `.unstore all`.", mention_author=False)
        del data[guild_id]
        await save_data(data)
        return await ctx.reply("🧹 Cleared all stored info for this server.", mention_author=False)

    # try to parse index
    try:
        index = int(arg)
    except ValueError:
        return await ctx.reply("⚠️ Please provide a valid number or `all`.", mention_author=False)

    items = data[guild_id]
    if index < 1 or index > len(items):
        return await ctx.reply(f"❌ Invalid index. Use `.storssge` to see item numbers.", mention_author=False)

    # items are stored oldest→newest, but `.storssge` shows reversed.
    # so if user says `.unstore 1`, they mean the newest one.
    real_index = -(index)
    removed = items.pop(real_index)
    await save_data(data)

    await ctx.reply(
        f"🗑️ Removed item #{index}: `{removed['text'][:80]}...`",
        mention_author=False
    )

# ---------- Reaction Roles ----------
class ReactionRoleView(View):
    def __init__(self, role_id):
        super().__init__(timeout=None)
        self.role_id = role_id

    @discord.ui.button(label="Toggle Role", style=discord.ButtonStyle.green)
    async def toggle_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"Removed {role.name}", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"Added {role.name}", ephemeral=True)

@bot.command(name="reactionrole")
async def reaction_role(ctx, role: discord.Role):
    view = ReactionRoleView(role.id)
    await ctx.send(f"Click to toggle {role.name}", view=view)
    bot.add_view(view)

@bot.command(name="role")
async def role(ctx, member: discord.Member, *, role_name: str):
    """Toggle a role by searching for a case-insensitive substring in the role name."""
    if not await check_perm(ctx, "manage_roles"):
        return

    role_name_clean = role_name.strip().lower()

    # Match role where role_name_clean is in the role's name
    role = discord.utils.find(lambda r: role_name_clean in r.name.lower(), ctx.guild.roles)
    
    if not role:
        await ctx.send(f"❌ Role containing '{role_name}' not found.")
        return

    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed role {role.name} from {member.mention}.")
    else:
        await member.add_roles(role)
        await ctx.send(f"✅ Added role {role.name} to {member.mention}.")

@bot.command(name="nickall")
@commands.has_permissions(manage_nicknames=True)
async def nickall(ctx, *, newnick: str = None):
    """Change nickname of everyone in the server"""
    if not newnick:
        return await ctx.send("❌ Please provide a new nickname: `.nickall <newnick>`")

    changed = 0
    failed = 0
    await ctx.send(f"🔄 Changing all nicknames to **{newnick}**...")

    for member in ctx.guild.members:
        if member == ctx.author or member.bot:
            continue
        try:
            await member.edit(nick=newnick)
            changed += 1
        except discord.Forbidden:
            failed += 1
        except Exception as e:
            print(f"Error changing nickname for {member}: {e}")
            failed += 1

    await ctx.send(f"✅ Changed nicknames for **{changed}** members.\n⚠️ Failed for **{failed}** members.")


# ---------- Giveaways ----------
class GiveawayModal(Modal):
    def __init__(self, view_obj, user_id):
        super().__init__(title="Setup Giveaway")
        self.view_obj = view_obj
        self.user_id = user_id
        self.prize = TextInput(label="Prize")
        self.duration = TextInput(label="Duration e.g., 10s,5m,1h")
        self.winners = TextInput(label="Number of winners")
        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.winners)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Not allowed", ephemeral=True)
            return
        self.view_obj.prize = self.prize.value.strip()
        self.view_obj.duration = self.duration.value.strip()
        try:
            self.view_obj.num_winners = int(self.winners.value.strip())
        except:
            await interaction.response.send_message("❌ Invalid number", ephemeral=True)
            return
        await interaction.response.send_message("✅ Giveaway setup saved.", ephemeral=True)
        await self.view_obj.update_embed()

class GiveawayView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.prize = ''
        self.duration = ''
        self.num_winners = 1
        self.giveaway_msg = None

    async def update_embed(self):
        if self.giveaway_msg:
            embed = discord.Embed(title=f"🎉 GIVEAWAY: {self.prize}", color=discord.Color.gold())
            embed.add_field(name="Duration", value=self.duration, inline=False)
            embed.add_field(name="Winners", value=str(self.num_winners), inline=False)
            await self.giveaway_msg.edit(embed=embed, view=self)

    @discord.ui.button(label="Setup Giveaway", style=discord.ButtonStyle.green)
    async def setup_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GiveawayModal(self, self.user_id))

    @discord.ui.button(label="Start Giveaway", style=discord.ButtonStyle.blurple)
    async def start_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        seconds = parse_duration(self.duration)
        if not self.prize or not seconds:
            await interaction.response.send_message("❌ Prize or duration invalid", ephemeral=True)
            return
        end_time = int(discord.utils.utcnow().timestamp() + seconds)
        embed = discord.Embed(title=f"🎉 GIVEAWAY: {self.prize}", color=discord.Color.gold())
        embed.add_field(name="Ends in", value=f"<t:{end_time}:R>")
        embed.set_footer(text=f"{self.num_winners} winner(s) • React 🎉")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎉")
        await interaction.response.send_message("✅ Giveaway started!", ephemeral=True)
        await asyncio.sleep(seconds)
        msg = await interaction.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in reaction.users() if not u.bot] if reaction else []
        if not users:
            await interaction.channel.send("❌ No participants.")
            return
        winners = random.sample(users, min(self.num_winners, len(users)))
        await interaction.channel.send(f"🏆 Congratulations {', '.join([w.mention for w in winners])}! You won **{self.prize}**!")

@bot.command(name="giveaway")
async def giveaway(ctx):
    view = GiveawayView(ctx.author.id)
    msg = await ctx.send(embed=discord.Embed(title="🎉 Giveaway Setup", description="Use buttons below"), view=view)
    view.giveaway_msg = msg
    bot.add_view(view)

@bot.command(name="greroll")
@commands.has_permissions(administrator=True)
async def greroll(ctx, message_id: int):
    """Reroll a giveaway, choosing new winners"""
    try:
        msg = await ctx.channel.fetch_message(message_id)
    except:
        await ctx.send("❌ Could not find message with that ID.")
        return

    # Get 🎉 reaction
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if not reaction:
        await ctx.send("❌ No 🎉 reaction found on that message.")
        return

    users = [u async for u in reaction.users() if not u.bot]
    if not users:
        await ctx.send("❌ No participants found.")
        return

    # Try to get number of winners from embed footer
    if msg.embeds and msg.embeds[0].footer.text:
        footer_text = msg.embeds[0].footer.text
        match = re.search(r"(\d+)\s*winner", footer_text)
        num_winners = int(match.group(1)) if match else 1
    else:
        num_winners = 1

    winners = random.sample(users, min(num_winners, len(users)))
    await ctx.send(f"🎉 **New winner(s):** {', '.join([w.mention for w in winners])}!")


@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    """Lock a channel (default: current one)."""
    await ctx.message.delete()
    channel = channel or ctx.channel

    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

    embed = discord.Embed(
        title="🔒 Channel Locked",
        description=f"{channel.mention} has been locked.\nMembers can no longer send messages.",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Locked by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    """Unlock a channel (default: current one)."""
    await ctx.message.delete()
    channel = channel or ctx.channel

    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

    embed = discord.Embed(
        title="🔓 Channel Unlocked",
        description=f"{channel.mention} is now open.\nMembers can chat again!",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Unlocked by {ctx.author}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="cmds")
async def cmds(ctx):
    """Show all bot commands, automatically categorized."""
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description=f"Prefix: `.`\nHere’s a list of all available commands:",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )

    # Create a dictionary to categorize commands
    categories = {
        "Welcome System": [],
        "Moderation": [],
        "Reaction Roles": [],
        "Giveaways": [],
        "Utility": []
    }

    # Loop through all commands
    for command in bot.commands:
        if command.hidden:
            continue  # skip hidden commands
        name = command.name
        desc = command.help if command.help else "No description."

        # Assign to categories based on command name
        if name in ["setwelcomechannel", "setwelcomemsg", "setautorole"]:
            categories["Welcome System"].append(f"`.{name}` → {desc}")
        elif name in ["kick", "ban", "purge", "to", "nick", "role", "role_add", "nickall"]:
            categories["Moderation"].append(f"`.{name}` → {desc}")
        elif name in ["reactionrole"]:
            categories["Reaction Roles"].append(f"`.{name}` → {desc}")
        elif name in ["giveaway", "greroll"]:
            categories["Giveaways"].append(f"`.{name}` → {desc}")
        else:
            categories["Utility"].append(f"`.{name}` → {desc}")

    # Add fields to embed dynamically
    for cat_name, cmds_list in categories.items():
        if cmds_list:
            embed.add_field(name=f"📌 {cat_name}", value="\n".join(cmds_list), inline=False)

    await ctx.send(embed=embed)


   

# ---------- Ready Event ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
