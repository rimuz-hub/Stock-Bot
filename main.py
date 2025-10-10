import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from discord import TextChannel, Role
from dotenv import load_dotenv
from datetime import timedelta
import asyncio
import random
import re
import json
import os

# Load .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Bot token not found! Please check your .env file.")

# ---------- Helper Functions ----------
def generate_stock_embed(stock_data: dict, title="📦 Current Stock"):
    embed = discord.Embed(title=title, color=discord.Color.green())
    if not stock_data:
        embed.description = "Stock is empty!"
    else:
        for item, amount in stock_data.items():
            embed.add_field(name=item, value=str(amount), inline=False)
    return embed

# ---------- Bot Setup ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # needed for welcome messages
bot = commands.Bot(command_prefix=".", intents=intents)

# Store welcome settings in memory
welcome_channel: TextChannel | None = None
welcome_msg: str = "Welcome to the server, {user}!"

# ---------- Modals ----------
class StockModal(Modal):
    def __init__(self, action: str, user_id: int, stock_message: discord.Message, view_obj):
        super().__init__(title=f"{action} Item")
        self.action = action
        self.user_id = user_id
        self.stock_message = stock_message
        self.view_obj = view_obj

        self.item_name = TextInput(label="Item Name", placeholder="Enter the item name")
        self.amount = TextInput(label="Amount", placeholder="Enter the amount", max_length=10)

        self.add_item(self.item_name)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't interact with this modal.", ephemeral=True)
            return

        item = self.item_name.value.strip()
        try:
            amount = int(self.amount.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Amount must be a number.", ephemeral=True)
            return

        stock_data = self.view_obj.stock_data

        if self.action == "Add":
            stock_data[item] = stock_data.get(item, 0) + amount
        elif self.action == "Remove":
            if item not in stock_data:
                await interaction.response.send_message(f"❌ Item **{item}** not in stock.", ephemeral=True)
                return
            stock_data[item] -= amount
            if stock_data[item] <= 0:
                stock_data.pop(item, None)

        await self.stock_message.edit(embed=generate_stock_embed(stock_data, self.view_obj.title), view=self.view_obj)
        await interaction.response.send_message(f"✅ {self.action}ed **{amount}** of **{item}**!", ephemeral=True)

class ChangeTitleModal(Modal):
    def __init__(self, user_id: int, stock_message: discord.Message, view_obj):
        super().__init__(title="Change Stock Embed Title")
        self.user_id = user_id
        self.stock_message = stock_message
        self.view_obj = view_obj

        self.new_title = TextInput(label="New Title", placeholder="Enter the new embed title")
        self.add_item(self.new_title)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't interact with this modal.", ephemeral=True)
            return

        self.view_obj.title = self.new_title.value.strip()
        await self.stock_message.edit(embed=generate_stock_embed(self.view_obj.stock_data, self.view_obj.title), view=self.view_obj)
        await interaction.response.send_message(f"✅ Title changed to **{self.view_obj.title}**", ephemeral=True)

# ---------- Persistent Stock Setup View ----------
class StockSetupView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.stock_message: discord.Message | None = None
        self.stock_data: dict = {}  # per-setup stock
        self.target_channel: TextChannel | None = None
        self.ping_role: Role | None = None
        self.title = "📦 Current Stock"  # default title

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't interact with this setup.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Add Item", style=discord.ButtonStyle.green, custom_id="stock_add")
    async def add_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StockModal("Add", self.user_id, self.stock_message, self))

    @discord.ui.button(label="Remove Item", style=discord.ButtonStyle.red, custom_id="stock_remove")
    async def remove_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StockModal("Remove", self.user_id, self.stock_message, self))

    @discord.ui.button(label="View Stock", style=discord.ButtonStyle.blurple, custom_id="stock_view")
    async def view_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = generate_stock_embed(self.stock_data, self.title)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Add Channel", style=discord.ButtonStyle.gray, custom_id="stock_channel")
    async def add_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please mention the channel to send the stock embed (e.g., #general).", ephemeral=True)

        def check(msg):
            return msg.author.id == self.user_id and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            if len(msg.channel_mentions) == 0:
                await interaction.followup.send("❌ No channel mentioned.", ephemeral=True)
                return
            self.target_channel = msg.channel_mentions[0]
            await msg.delete()  # delete user's message
            await interaction.followup.send(f"✅ Channel set to {self.target_channel.mention}", ephemeral=True)
        except:
            await interaction.followup.send("❌ Timeout. Please click 'Add Channel' again.", ephemeral=True)

    @discord.ui.button(label="Ping Role", style=discord.ButtonStyle.gray, custom_id="stock_role")
    async def ping_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please mention the role you want to ping (e.g., @StockRole).", ephemeral=True)

        def check(msg):
            return msg.author.id == self.user_id and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            if len(msg.role_mentions) == 0:
                await interaction.followup.send("❌ No role mentioned.", ephemeral=True)
                return
            self.ping_role = msg.role_mentions[0]
            await msg.delete()  # delete user's message
            await interaction.followup.send(f"✅ Role set to {self.ping_role.mention}", ephemeral=True)
        except:
            await interaction.followup.send("❌ Timeout. Please click 'Ping Role' again.", ephemeral=True)

    @discord.ui.button(label="Change Title", style=discord.ButtonStyle.blurple, custom_id="stock_title")
    async def change_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChangeTitleModal(self.user_id, self.stock_message, self))

    @discord.ui.button(label="Send Embed", style=discord.ButtonStyle.green, custom_id="stock_send")
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.target_channel is None:
            await interaction.response.send_message("❌ Please add a channel first.", ephemeral=True)
            return
        content = self.ping_role.mention if self.ping_role else None
        await self.target_channel.send(content=content, embed=generate_stock_embed(self.stock_data, self.title))
        await interaction.response.send_message(f"✅ Stock embed sent to {self.target_channel.mention}", ephemeral=True)

# ---------- Stock Command ----------
@bot.command(name="stock")
async def stock(ctx):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    embed = generate_stock_embed({})
    view = StockSetupView(ctx.author.id)
    message = await ctx.send(embed=embed, view=view)
    view.stock_message = message
    bot.add_view(view)



@bot.command(name="welcome")
async def welcome_test(ctx):
    """Test welcome message in the set welcome channel"""
    # Load channel from JSON
    channel_id = load_welcome_data(ctx.guild.id)
    if not channel_id:
        await ctx.send("❌ No welcome channel set. Use `.setwelcomechannel #channel` first.")
        return

    channel = ctx.guild.get_channel(channel_id)
    if not channel:
        await ctx.send("❌ Welcome channel not found.")
        return

    await channel.send(f"👋 This is a test welcome message for {ctx.author.mention}!")
    await ctx.message.delete()


# ---------- Duration Parsing ----------
def parse_duration(duration: str) -> int:
    match = re.match(r"(\d+)([smhd])", duration.lower())
    if not match:
        return None
    amount, unit = match.groups()
    return int(amount) * {"s":1, "m":60, "h":3600, "d":86400}[unit]

# ---------- Giveaway Modal ----------
class GiveawayModal(Modal):
    def __init__(self, user_id: int, view_obj):
        super().__init__(title="Set Prize/Duration/Winners")
        self.user_id = user_id
        self.view_obj = view_obj

        self.prize = TextInput(label="Prize", placeholder="Enter the giveaway prize")
        self.duration = TextInput(label="Duration", placeholder="e.g., 10s, 5m, 1h, 2d")
        self.winners = TextInput(label="Number of Winners", placeholder="Enter number of winners", max_length=3)

        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.winners)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't use this modal.", ephemeral=True)
            return

        self.view_obj.prize = self.prize.value.strip()
        self.view_obj.duration = self.duration.value.strip()
        try:
            self.view_obj.num_winners = int(self.winners.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Number of winners must be a number.", ephemeral=True)
            return

        await interaction.response.send_message(
            "✅ Giveaway setup saved! Use buttons to add requirements or send the embed.", ephemeral=True
        )
        await self.view_obj.update_embed()

# ---------- Giveaway Setup View ----------
class GiveawaySetupView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.giveaway_message: discord.Message | None = None
        self.prize: str = ""
        self.duration: str = ""
        self.num_winners: int = 1
        self.requirements: list = []  # role IDs
        self.title = "🎉 Giveaway Setup"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't interact with this giveaway setup.", ephemeral=True)
            return False
        return True

    async def update_embed(self):
        if self.giveaway_message:
            embed = discord.Embed(title=self.title, color=discord.Color.gold())
            embed.add_field(name="Prize", value=self.prize or "Not set", inline=False)
            embed.add_field(name="Duration", value=self.duration or "Not set", inline=False)
            embed.add_field(name="Number of Winners", value=str(self.num_winners), inline=False)
            if self.requirements:
                role_mentions = ", ".join(f"<@&{r}>" for r in self.requirements)
                embed.add_field(name="Requirements", value=role_mentions, inline=False)
            await self.giveaway_message.edit(embed=embed, view=self)

    @discord.ui.button(label="Set Prize/Duration/Winners", style=discord.ButtonStyle.green, custom_id="giveaway_set")
    async def set_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GiveawayModal(self.user_id, self))

    @discord.ui.button(label="Add Requirement", style=discord.ButtonStyle.gray, custom_id="giveaway_req")
    async def add_requirement(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please mention the role required to participate:", ephemeral=True)

        def check(msg):
            return msg.author.id == self.user_id and msg.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=60)
            if not msg.role_mentions:
                await interaction.followup.send("❌ No role mentioned.", ephemeral=True)
                return
            self.requirements.append(msg.role_mentions[0].id)
            await msg.delete()
            await self.update_embed()
            await interaction.followup.send(f"✅ Requirement {msg.role_mentions[0].mention} added.", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("❌ Timeout. Click 'Add Requirement' again.", ephemeral=True)

    @discord.ui.button(label="Send Giveaway", style=discord.ButtonStyle.blurple, custom_id="giveaway_send")
    async def send_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        seconds = parse_duration(self.duration)
        if not self.prize or not seconds:
            await interaction.response.send_message("❌ Prize or duration not set / invalid!", ephemeral=True)
            return

        # Discord timestamp for "Ends in"
        end_time = int(discord.utils.utcnow().timestamp() + seconds)

        embed = discord.Embed(title=f"🎉 GIVEAWAY: {self.prize}", color=discord.Color.gold())
        embed.add_field(name="Hosted by", value=interaction.user.mention)
        embed.add_field(name="Ends in", value=f"<t:{end_time}:R>")
        if self.requirements:
            role_mentions = ", ".join(f"<@&{r}>" for r in self.requirements)
            embed.add_field(name="Requirements", value=role_mentions, inline=False)
        embed.set_footer(text=f"{self.num_winners} winner(s) • Participants: 0 • React with 🎉 to enter!")
        giveaway_msg = await interaction.channel.send(embed=embed)
        await giveaway_msg.add_reaction("🎉")
        await interaction.response.send_message("✅ Giveaway started! React to enter.", ephemeral=True)

        # Update participants dynamically until end
        interval = 5
        while True:
            giveaway_msg = await interaction.channel.fetch_message(giveaway_msg.id)
            reaction = discord.utils.get(giveaway_msg.reactions, emoji="🎉")
            if reaction:
                users = [u async for u in reaction.users() if not u.bot]
                num_participants = len(users)
            else:
                num_participants = 0

            # Update footer only
            embed = giveaway_msg.embeds[0]
            embed.set_footer(text=f"{self.num_winners} winner(s) • Participants: {num_participants} • React with 🎉 to enter!")
            await giveaway_msg.edit(embed=embed)

            remaining = end_time - int(discord.utils.utcnow().timestamp())
            if remaining <= 0:
                break
            await asyncio.sleep(interval)

        # Fetch final participants and pick winners
        giveaway_msg = await interaction.channel.fetch_message(giveaway_msg.id)
        reaction = discord.utils.get(giveaway_msg.reactions, emoji="🎉")
        if not reaction:
            await interaction.channel.send("❌ No participants entered.")
            return

        users = [u async for u in reaction.users() if not u.bot]
        if self.requirements:
            users = [u for u in users if any(r.id in self.requirements for r in u.roles)]

        if not users:
            await interaction.channel.send("❌ No participants met the requirements.")
            return

        winners = random.sample(users, min(self.num_winners, len(users)))
        winner_mentions = ", ".join(w.mention for w in winners)
        await interaction.channel.send(f"🏆 Congratulations {winner_mentions}! You won **{self.prize}**!")

# ---------- Giveaway Command ----------
@bot.command(name="giveaway")
async def giveaway(ctx, action: str = None):
    if action is None or action.lower() != "create":
        await ctx.send("❌ Use `.giveaway create` to start a giveaway.", delete_after=5)
        return

    view = GiveawaySetupView(ctx.author.id)
    embed = discord.Embed(title="🎉 Giveaway Setup", description="Use the buttons to configure your giveaway.", color=discord.Color.gold())
    msg = await ctx.send(embed=embed, view=view)
    view.giveaway_message = msg
    bot.add_view(view)

@discord.ui.button(label="Send Giveaway", style=discord.ButtonStyle.blurple)
async def send_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
    giveaway_msg = await interaction.channel.send(embed=embed)
    await giveaway_msg.add_reaction("🎉")

    # Disable setup buttons
    for child in self.children:
        child.disabled = True
    await self.giveaway_message.edit(view=self)

@bot.command(name="greroll")
@commands.has_permissions(administrator=True)
async def greroll(ctx, message_id: int):
    """Reroll a giveaway. Usage: .greroll <giveaway_message_id>"""
    try:
        giveaway_msg = await ctx.channel.fetch_message(message_id)
    except discord.NotFound:
        await ctx.send("❌ Giveaway message not found!")
        return

    # Find the 🎉 reaction
    reaction = discord.utils.get(giveaway_msg.reactions, emoji="🎉")
    if not reaction:
        await ctx.send("❌ No 🎉 reaction found on this message.")
        return

    users = [u async for u in reaction.users() if not u.bot]

    if not users:
        await ctx.send("❌ No participants to reroll.")
        return

    # Optional: filter by roles if you stored requirements
    # users = [u for u in users if any(r.id in requirements for r in u.roles)]

    # You can set number of winners from footer or assume 1
    num_winners = 1
    winners = random.sample(users, min(num_winners, len(users)))
    winner_mentions = ", ".join(w.mention for w in winners)
    await ctx.send(f"🏆 Congratulations {winner_mentions}! You won the reroll!")

    # Optional: Edit embed to show new winner
    if giveaway_msg.embeds:
        embed = giveaway_msg.embeds[0]
        embed.add_field(name="Reroll Winner", value=winner_mentions, inline=False)
        await giveaway_msg.edit(embed=embed)

WELCOME_FILE = "welcome.json"

# Ensure welcome.json exists
if not os.path.exists(WELCOME_FILE):
    with open(WELCOME_FILE, "w") as f:
        json.dump({}, f)

def save_welcome_data(guild_id, channel_id):
    with open(WELCOME_FILE, "r") as f:
        data = json.load(f)
    data[str(guild_id)] = channel_id
    with open(WELCOME_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_welcome_data(guild_id):
    if not os.path.exists(WELCOME_FILE):
        return None
    with open(WELCOME_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id))

@bot.command(name="setwelcomechannel")
@commands.has_permissions(administrator=True)
async def setwelcomechannel(ctx, channel: discord.TextChannel):
    save_welcome_data(ctx.guild.id, channel.id)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(f"✅ Welcome channel set to {channel.mention}", delete_after=5)

# Event to welcome new members
@bot.event
async def on_member_join(member):
    channel_id = load_welcome_data(member.guild.id)
    if channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"👋 Welcome {member.mention} to {member.guild.name}!")





@bot.command(name="setwelcomemsg")
async def set_welcome_msg(ctx, *, msg):
    global welcome_msg
    welcome_msg = msg
    try:
        await ctx.message.delete()
    except:
        pass
    await ctx.send(f"✅ Welcome message updated!", delete_after=5)

@bot.event
async def on_member_join(member: discord.Member):
    if welcome_channel:
        msg = welcome_msg.replace("{user}", member.mention)
        await welcome_channel.send(msg)


@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    """
    Deletes <amount> messages from the channel.
    """
    if amount < 1:
        await ctx.send("❌ Amount must be at least 1.", delete_after=5)
        return

    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"✅ Deleted {len(deleted)} messages.", delete_after=5)

import re
from datetime import timedelta

@bot.command(name="to")
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, duration: str):
    """
    Timeouts a member. Duration format: 10s, 10m, 10h, 10d
    """
    match = re.match(r"(\d+)([smhd])", duration.lower())
    if not match:
        await ctx.send("❌ Invalid duration format. Example: 10s, 5m, 1h, 2d", delete_after=5)
        return

    amount, unit = match.groups()
    amount = int(amount)
    seconds = 0
    if unit == "s":
        seconds = amount
    elif unit == "m":
        seconds = amount * 60
    elif unit == "h":
        seconds = amount * 3600
    elif unit == "d":
        seconds = amount * 86400

    try:
        await member.timeout(discord.utils.utcnow() + timedelta(seconds=seconds))
        await ctx.send(f"✅ {member.mention} has been timed out for {duration}.", delete_after=5)
    except:
        await ctx.send("❌ Could not timeout the member.", delete_after=5)

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    """
    Kicks a member from the server.
    """
    try:
        await member.kick(reason=reason)
        await ctx.send(f"✅ {member.mention} has been kicked. Reason: {reason}", delete_after=5)
    except:
        await ctx.send("❌ Could not kick the member.", delete_after=5)

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    """
    Bans a member from the server.
    """
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ {member.mention} has been banned. Reason: {reason}", delete_after=5)
    except:
        await ctx.send("❌ Could not ban the member.", delete_after=5)

@bot.command(name="nick")
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, new_nick: str):
    """
    Change the nickname of a mentioned member.
    """
    try:
        await member.edit(nick=new_nick)
        await ctx.send(f"✅ Changed nickname of {member.mention} to **{new_nick}**.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to change this member's nickname.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Could not change nickname. Error: {e}", delete_after=5)

@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
async def role(ctx, action: str, member: discord.Member, *, role_name: str):
    """
    Add or remove a role from a member.
    Usage: 
    .role add @user RoleName
    .role remove @user RoleName
    """
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role is None:
        await ctx.send(f"❌ Role **{role_name}** not found.", delete_after=5)
        return

    try:
        if action.lower() == "add":
            await member.add_roles(role)
            await ctx.send(f"✅ Added role **{role.name}** to {member.mention}.", delete_after=5)
        elif action.lower() == "remove":
            await member.remove_roles(role)
            await ctx.send(f"✅ Removed role **{role.name}** from {member.mention}.", delete_after=5)
        else:
            await ctx.send("❌ Invalid action! Use `add` or `remove`.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage that role.", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Could not modify role. Error: {e}", delete_after=5)

# ---------- Commands List ----------
@bot.command(name="cmds")
async def cmds(ctx):
    embed = discord.Embed(
        title="🤖 Bot Commands",
        color=discord.Color.blurple(),
        description="Here’s a list of all available commands:"
    )

    # Group commands by category based on name or custom attribute
    categories = {
        "Stock Management": [],
        "Welcome System": [],
        "Moderation": [],
        "Utility": []
    }

    for command in bot.commands:
        if command.hidden:
            continue  # skip hidden commands
        name = command.name
        desc = command.help if command.help else "No description."
        
        # Assign categories dynamically (you can adjust rules)
        if name in ["stock"]:
            categories["Stock Management"].append(f"`.{name}` → {desc}")
        elif name in ["setwelcomchannel", "setwelcomemsg", "welcome"]:
            categories["Welcome System"].append(f"`.{name}` → {desc}")
        elif name in ["purge", "to", "kick", "ban", "nick", "role"]:
            categories["Moderation"].append(f"`.{name}` → {desc}")
        else:
            categories["Utility"].append(f"`.{name}` → {desc}")

    for cat_name, cmds_list in categories.items():
        if cmds_list:
            embed.add_field(name=f"📌 {cat_name}", value="\n".join(cmds_list), inline=False)

    await ctx.send(embed=embed, delete_after=60)

# ---------- Ready Event ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")

bot.run(TOKEN)
