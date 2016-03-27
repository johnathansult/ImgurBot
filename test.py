import ImgurBot
import os
import shutil
import sqlite3

name = "ImgurTestBot"

ImgurBot.ImgurBot.get_input("WARNING: This will delete all files in the ini, log, and db directories. "
                            "Press 'enter' to proceed with the test.")


# Directory destruction and creation methods, used in the following tests.
def delete_dir(directory):
    if os.path.exists(os.path.normpath(os.getcwd() + "/" + directory)):
        shutil.rmtree(os.path.normpath(os.getcwd() + "/" + directory))
    assert os.path.exists(os.path.normpath(os.getcwd() + "/" + directory)) == False


def verify_dir_exists(directory):
    assert os.path.exists(os.path.normpath(os.getcwd() + "/" + directory)) == True


def verify_file_exists(my_file):
    assert os.path.isfile(os.path.normpath(os.getcwd() + "/" + my_file)) == True


def new_test_set(message):
    global test_set
    if test_set >= 0:
        print("\n* Successful completion of Test Set " + str(test_set + 1) + ".")
    test_set += 1
    print("* Beginning Test Set " + str(test_set + 1) + ": " + message)  # Displays as 1 on first call, then 2, 3...
test_set = -1  # Starts at -1 so that it becomes 0 on the first new_test_set call.


def test_msg(message):
    global test_index, test_set
    if len(test_index) <= test_set:
        test_index.append(1)

    print("\n* Test case " + str(test_set + 1) + "-" + str(test_index[test_set]) + ": " + message)
    test_index[test_set] += 1
test_index = []


def finished_testing():
    global test_set
    print("\n* Successful completion of Test Set " + str(test_set + 1) + ". All tests complete.")
    exit(0)


# Test case setup: Initialize logging when no directories exist.
new_test_set("Initialization of bot with no directories or files.")

delete_dir("log")
delete_dir("db")
delete_dir("ini")
bot = ImgurBot.ImgurBot(name, True)

test_msg("Initialize logging when no log directory exists.")
bot.initialize_logging()
verify_dir_exists("log")
verify_file_exists("log/" + name + ".log")

test_msg("Initialize database when no db directory exists.")
bot.initialize_database()
verify_dir_exists("db")
verify_file_exists("db/" + name + ".db")

test_msg("Initialize config when no ini directory exists.")
bot.initialize_config()
verify_dir_exists("ini")
verify_file_exists("ini/" + name + ".ini")

# TODO: Test client initialization.
# test_msg("Initialize client.")
# bot.initialize_client()

new_test_set("Deletion of fully-initialized bot.")
test_msg("Delete fully-initialized bot.")
del bot

# TODO: Test for behavior with already-extant log, ini, db, etc

# TODO: Test for behavior with malformed ini, bad db, etc

new_test_set("Database tests.")
# Test case: Adding to empty Seen table.
bot = ImgurBot.ImgurBot(name, True)
bot.initialize_logging()
bot.initialize_database()

test_msg("Adding entry to empty Seen table.")
bot.reset_seen()
bot.mark_seen("1")
assert bot.has_seen("1") == True
bot.mark_seen("2")
assert bot.has_seen("2") == True
assert bot.has_seen("0") == False

# Test case: Adding conflicting entries to Seen table.
test_msg("Adding conflicting entry to Seen table.")

error_encountered = False
try:
    bot.mark_seen("1")
except sqlite3.IntegrityError as e:
    pass
else:
    print("Test failure: mark_seen of previously seen post did not produce an error.")

assert bot.has_seen("1") == True
assert bot.has_seen("0") == False

del bot

finished_testing()
