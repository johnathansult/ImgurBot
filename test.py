import ImgurBot
import os

name = "ImgurBot"

# Create bot.
bot = ImgurBot.ImgurBot(name)

# Check that the correct directories and files exist.
assert os.path.exists(os.path.normpath(os.getcwd() + "/log")) == True
assert os.path.exists(os.path.normpath(os.getcwd() + "/ini")) == True
assert os.path.exists(os.path.normpath(os.getcwd() + "/db")) == True
assert os.path.isfile(os.path.normpath(os.getcwd() + "/log/" + name + ".log")) == True
assert os.path.isfile(os.path.normpath(os.getcwd() + "/ini/" + name + ".ini")) == True
assert os.path.isfile(os.path.normpath(os.getcwd() + "/db/" + name + ".db")) == True

# Test seen functionality.
bot.reset_seen()
bot.mark_seen("1")
assert bot.has_seen("0") == False
assert bot.has_seen("1") == True

# Finalize bot.
del bot