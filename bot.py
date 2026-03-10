import discord
from discord import app_commands
import anthropic
import os
from collections import defaultdict

SYSTEM_PROMPT = """You are a helpful personal assistant in a Discord server.
Be concise, friendly, and helpful. You remember the context of the conversation."""

MAX_HISTORY = 20

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

conversation_history = defaultdict(list)


def get_ai_response(user_id: int, user_message: str) -> str:
    history = conversation_history[user_id]
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY:
        conversation_history[user_id] = history[-MAX_HISTORY:]

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=conversation_history[user_id],
    )

    reply = response.content[0].text
    conversation_history[user_id].append({"role": "assistant", "content": reply})
    return reply


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {client.user} — slash commands synced.")


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if message.content.startswith("/"):
        return

    async with message.channel.typing():
        try:
            reply = get_ai_response(message.author.id, message.content)
            if len(reply) <= 2000:
                await message.reply(reply)
            else:
                chunks = [reply[i:i+1990] for i in range(0, len(reply), 1990)]
                for chunk in chunks:
                    await message.channel.send(chunk)
        except Exception as e:
            await message.reply(f"⚠️ Something went wrong: {e}")


@tree.command(name="ask", description="Ask your assistant a question")
@app_commands.describe(question="What do you want to ask?")
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    try:
        reply = get_ai_response(interaction.user.id, question)
        await interaction.followup.send(reply)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error: {e}")


@tree.command(name="clear", description="Clear your conversation history with the assistant")
async def clear(interaction: discord.Interaction):
    conversation_history[interaction.user.id] = []
    await interaction.response.send_message("🧹 Your conversation history has been cleared!", ephemeral=True)


@tree.command(name="history", description="See how many messages are in your conversation history")
async def history(interaction: discord.Interaction):
    count = len(conversation_history[interaction.user.id])
    await interaction.response.send_message(
        f"📝 You have **{count}/{MAX_HISTORY}** messages in your history.",
        ephemeral=True
    )


client.run(os.environ["DISCORD_TOKEN"])
