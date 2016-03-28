import ImgurBot

name = "Example Bot"
bot = ImgurBot.ImgurBot(name)

print(str(bot.client.get_account('me').id))

del bot