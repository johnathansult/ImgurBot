import ImgurBot
import os
import shutil

name = "ImgurTestBot"

# TODO: It may be necessary to refactor the ImgurBot class (or the testing regimen) so that we don't exhaust our...
# TODO  ...rate limit / available requests.

ImgurBot.ImgurBot.get_input("WARNING: This will delete all files in the ini, log, and db directories. "
                            "Press 'enter' to proceed with the test.")


# Directory destruction and creation methods, used in the following tests.
def delete_dir(directory):
    if os.path.exists(os.path.normpath(os.getcwd() + "/" + directory)):
        shutil.rmtree(os.path.normpath(os.getcwd() + "/" + directory))
    assert os.path.exists(os.path.normpath(os.getcwd() + "/" + directory)) == False

def verify_dir_exists(directory):
    assert os.path.exists(os.path.normpath(os.getcwd() + "/" + directory)) == True

tindex = 1
def test_msg(message):
    global tindex
    print("Test case " + tindex + ": " + message)
    tindex += 1


# Test case setup: No bot directories exist.
test_msg("Create directories when nonexistent.")
delete_dir("log")
delete_dir("ini")
delete_dir("db")

bot = ImgurBot.ImgurBot(name)

verify_dir_exists("log")
verify_dir_exists("ini")
verify_dir_exists("db")
# End no-bot-directories test case (but carry over the live bot for further tests).

# Test case: Adding to empty Seen table.
test_msg("Adding entry to empty Seen table.")
bot.reset_seen()
bot.mark_seen("1")
assert bot.has_seen("1") == True
bot.mark_seen("2")
assert bot.has_seen("2") == True
assert bot.has_seen("0") == False

# Test case: Adding conflicting entries to Seen table.
test_msg("Adding conflicting entry to Seen table.")
bot.mark_seen("1")
assert bot.has_seen("1") == True
assert bot.has_seen("0") == False

del bot

# Test case: Directories already exist.
test_msg("Create directories when already extant.")
bot = ImgurBot.ImgurBot(name)
verify_dir_exists("log")
verify_dir_exists("ini")
verify_dir_exists("db")

del bot

# TODO: Test for malformed ini, bad db, etc