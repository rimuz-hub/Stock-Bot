
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
from discord import TextChannel, Role
import os, json, asyncio, random, re
from datetime import timedelta
from dotenv import load_dotenv

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


@bot.command(name="cmds")
async def cmds(ctx):
    """Show a categorized list of all bot commands."""
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description=f"Prefix: `.`\nHere’s a list of all available commands:",
        color=discord.Color.blurple()
    )

    # Categories dictionary
    categories = {
        "Welcome System": [],
        "Moderation": [],
        "Reaction Roles": [],
        "Giveaways": [],
        "Utility": []
    }

    for command in bot.commands:
        if command.hidden:
            continue
        name = command.name
        desc = command.help if command.help else "No description."

        # Assign to categories
        if name in ["setwelcomechannel", "setwelcomemsg", "setautorole"]:
            categories["Welcome System"].append(f"`.{name}` → {desc}")
        elif name in ["kick", "ban", "purge", "to", "nick", "role"]:
            categories["Moderation"].append(f"`.{name}` → {desc}")
        elif name in ["reactionrole"]:
            categories["Reaction Roles"].append(f"`.{name}` → {desc}")
        elif name in ["giveaway"]:
            categories["Giveaways"].append(f"`.{name}` → {desc}")
        else:
            categories["Utility"].append(f"`.{name}` → {desc}")

    # Add fields to embed
    for cat_name, cmds_list in categories.items():
        if cmds_list:
            embed.add_field(name=f"📌 {cat_name}", value="\n".join(cmds_list), inline=False)

    await ctx.send(embed=embed)

   

# ---------- Ready Event ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
