import sqlite3
import datetime
import os
import shutil
import math

import ConfigParser

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError

# TODO: Implement rate limiting on non-OAuth calls.
# TODO: Figure out some kind of fail-safe that stops the client cold when ImgurClientRateLimitError is thrown.
# ..... Hitting that 5x in a month bans the bot for the rest of the month.


# TODO: Mid-process: Convert log and debug_log statements to unified logs with log levels.

# TODO: Look into making this truly Python 2/3 compatible (currently 2-exclusive with 3 compat thrown in).


class ImgurBot:
    """
    A class that implements a bot for interfacing with Imgur.
    """
    version = "0.2a"

    # From https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words.
    # Space not included since it's safe in these use cases. Other characters are probably safe too, but YMMV.
    # TODO: Figure out if any other characters can be pruned from this list for enhanced user-friendliness.
    restricted_filesystem_chars = "/\\?*%:|\"<>."
    log_levels = {"Debug": 5, "Information": 4, "Warning": 3, "Error": 2, "Fatal": 1}

    def __init__(self, name="ImgurBot", print_at_log_level="Warning", testing_mode=False):
        """Initialize the ImgurBot.

        :type name: str

        This constructor has a testing_mode option which sets the name and then exits. This is designed to enable unit
        testing of other initialization measures (database, config). Please make sure you understand the flow of the
        program and what must be initialized in what order before you invoke this option; limited protection against
        out-of-order initialization has been added, but they are by no means comprehensive.
        """

        # Table of instance variables: These are pre-defined here so that the initialize_x() methods can be used to
        #    init the bot without loss of readability.

        # TODO: Comments.
        self.log_path = None
        self.db_path = None
        self.ini_path = None

        self.db = None
        self.logfile = None
        self.config = None

        self.client = None
        self.testing_mode = testing_mode

        # Set the bot's name (defaults to ImgurBot). Remove restricted filesystem characters while we're at it.
        self.name = name.translate(None, ImgurBot.restricted_filesystem_chars)

        # Set the bot's log level (defaults to Warning).
        if print_at_log_level not in ImgurBot.log_levels:
            print("Log level {0} is not a valid log level. Defaulting to 'Warning'.".format(str(print_at_log_level)))
            self.print_at_log_level = "Warning"
        else:
            self.print_at_log_level = print_at_log_level

        # Testing mode check: If we're in testing mode, stop here. Print the disallowed characters debug statement too.
        if self.testing_mode:
            print("Testing mode enabled; performing early termination of __init__.")
            if name != self.name:
                print("Disallowed characters removed from bot name; now '{0}'.".format(self.name))
            return

        # Initialize the logfile at log/NAME.log for writing.
        self.initialize_logging()
        self.log("Initializing ImgurBot version {0}...".format(self.version), "Debug")
        if name != self.name:
            self.log("Disallowed characters removed from bot name; now '{0}'.".format(self.name), "Information")

        # Set up the SQLite database at db/NAME.db.
        self.initialize_database()

        # Set up the ConfigParser and load from ini/NAME.ini.
        self.initialize_config()

        # Initialize the client and perform authentication.
        self.initialize_client()
        self.log("Initialization of bot '{0}' complete.".format(self.name), "Debug")

    def __del__(self):
        """Deconstruct the ImgurBot."""

        # Record our most up-to-date auth token.
        if self.config is not None and self.client is not None and self.client.auth is not None:
            self.config.set('credentials', 'access_token', self.client.auth.get_current_access_token())
            self.write_ini_file()

        # Clean up the SQLite database. Note: This does not perform a commit.
        if self.db is not None:
            self.db.close()

        # Close the logfile.
        if self.logfile is not None:
            self.log("Successful termination of ImgurBot.", "Debug")
            self.logfile.close()

    # External / Imgur-facing methods
    def get_new_auth_info(self, no_file_write=False):
        """ Interfaces with Imgur and the user to obtain access and refresh tokens, then writes them to the .ini file.
        """
        # No access or refresh tokens. Send them to the auth workflow.
        assert self.config is not None, "Out-of-order call: initialize_config must be called before get_new_auth_info."
        assert self.client is not None, "Out-of-order call: initialize_client must be called before get_new_auth_info."

        print("")
        print("You need to supply your PIN to obtain access and refresh tokens.")
        print("Go to the following URL: {0}".format(self.client.get_auth_url('pin')))

        credentials = []

        # Loop and obtain the correct PIN.
        while True:
            try:
                pin = self.get_input("Enter the PIN code from the above URL: ")
                credentials = self.client.authorize(pin, 'pin')
                print("")
                break
            except ImgurClientError as e:
                if str(e) == "(400) Invalid Pin":
                    print("\nYou have entered an invalid pin. Try again.")
                elif str(e) == "(400) The client credentials are invalid":
                    # offer choice: delete credentials and recreate?
                    result = self.get_input("Your client credentials were incorrect. " +
                                            "Would you like to go through interactive bot registration? (y/N): ")
                    if result == 'y':
                        self.log("Moving {0} to {0}.old.".format(self.ini_path), "Information")
                        shutil.copy(self.ini_path, "{0}.old".format(self.ini_path))
                        os.remove(self.ini_path)
                        self.initialize_config()
                        self.initialize_client()
                        return
                    else:
                        self.log("Your client credentials were invalid. Correct them in {0}.".format(self.ini_path),
                                 "Error")
                        raise

        self.log("Access and refresh token successfully obtained.", "Debug")
        # noinspection PyTypeChecker
        self.config.set('credentials', 'access_token', credentials['access_token'])
        # noinspection PyTypeChecker
        self.config.set('credentials', 'refresh_token', credentials['refresh_token'])

        if no_file_write:
            return

        self.write_ini_file()

    # Internal / non Imgur-facing methods
    def log(self, message, log_level):
        """Writes the given message to NAME.log, prefixed with current date and time. Ends with a newline.
        Also prints the message to the screen.

        :param log_level: A string to indicate the level of the log message.
        :type message: str
        :type log_level: str
        """
        assert self.logfile is not None, "Out-of-order call: initialize_logging must be called before log."

        self.logfile.write("[{0}-{1}]: ".format(datetime.datetime.now().strftime("%c"), log_level) + message + '\n')
        if ImgurBot.log_levels[log_level] <= ImgurBot.log_levels[self.print_at_log_level]:
            print(message)

    def mark_seen(self, post_id):
        """Marks a post identified by post_id as seen.

        Possible exception: sqlite.IntegrityError if the post was already marked as seen.

        :type post_id: str
        """
        assert self.db is not None, "Out-of-order call: initialize_database must be called before mark_seen."

        self.db.execute("INSERT INTO Seen(id) VALUES (?)", [post_id])
        self.db.commit()

    def has_seen(self, post_id):
        """Boolean check for if the bot has seen the post identified by post_id.
        :type post_id: str

        :return: True if post_id in DB, false otherwise.
        """
        assert self.db is not None, "Out-of-order call: initialize_database must be called before has_seen."

        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM Seen WHERE id = ?", [post_id])
        return cursor.fetchone() is not None

    def reset_seen(self, force=False):
        """ Delete all entries from 'Seen' table in the database. Due to the extremely destructive nature of this
        method, this first prints a verification message and requires user input if the 'force' variable is not set.

        :param force: True to skip verification message.
        :type force: bool
        """

        assert self.db is not None, "Out-of-order call: initialize_database must be called before reset_seen."

        if not force:
            response = self.get_input("Are you sure you want to delete all entries from the Seen table? (y/N): ")
            if response != 'y':
                print("Canceling reset_seen.")
                return

        self.log("Deleting all entries from 'Seen' table.", "Debug")
        self.db.execute("DELETE FROM Seen")
        self.db.commit()

    def write_ini_file(self):
        self.log("Writing config file at {0}.".format(self.ini_path), "Debug")
        try:
            with open(self.ini_path, 'w') as ini_file:
                self.config.write(ini_file)
        except IOError as e:
            self.log("Error when writing config file at {0}: {1}: {2}\n".format(self.ini_path, str(e), str(e.args)) +
                     "Please manually create the file with the following contents: \n" +
                     "\n" +
                     "[credentials]\n" +
                     "client_id = {0}\n".format(self.config.get('credentials', 'client_id')) +
                     "client_secret = {0}\n".format(self.config.get('credentials', 'client_secret')) +
                     "access_token = {0}\n".format(self.config.get('credentials', 'access_token')) +
                     "refresh_token = {0}\n".format(self.config.get('credentials', 'refresh_token')), "Error")
            raise

    # Methods used to initialize the bot.
    def initialize_logging(self):
        """Forces the creation of the log directory, then creates/opens the logfile there. Also initializes the (self.)
        log_path and logfile variables."""

        # Broken out from __init__ to aid in testing.
        log_dir = ImgurBot.ensure_dir_in_cwd_exists("log")
        self.log_path = os.path.join(log_dir, "{0}.log".format(self.name))

        self.logfile = open(self.log_path, 'a')

    def initialize_database(self):
        db_dir = ImgurBot.ensure_dir_in_cwd_exists("db")
        self.db_path = os.path.join(db_dir, "{0}.db".format(self.name))

        try:
            # Inform the user that a new .db file is being created (if not previously extant).
            if not os.path.isfile(self.db_path):
                self.log("Creating database at {0}.".format(self.db_path), "Debug")

            # Connect and ensure that the database is set up properly.
            self.db = sqlite3.connect(self.db_path)
            cursor = self.db.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS Seen(id TEXT PRIMARY KEY NOT NULL)")

        except sqlite3.Error as e:
            self.log("Error in DB setup: {0}: {1}.".format(str(e), str(e.args)), "Error")
            if self.db:
                self.db.close()
            raise

    def initialize_config(self):
        ini_dir = ImgurBot.ensure_dir_in_cwd_exists("ini")
        self.ini_path = os.path.join(ini_dir, "{0}.ini".format(self.name))

        # Generate our config parser.
        self.config = self.get_raw_config_parser()

        # Test if config file exists. If not, create a template .ini file and terminate.
        if not os.path.isfile(self.ini_path):
            self.config.add_section('credentials')

            self.log("No .ini file was found. Beginning interactive creation.", "Debug")
            print("")
            print("To proceed, you will need a client_id and client_secret tokens, which can be obtained from Imgur at")
            print("the following website: https://api.imgur.com/oauth2/addclient")
            print("")

            while True:
                client_id = self.get_input("Enter your client_id: ")
                client_secret = self.get_input("Enter your client_secret: ")
                print("")
                reply = self.get_input("You entered client_id {0} and _secret {1}".format(client_id, client_secret) +
                                       ". Are these correct? (y/N): ")
                if reply == "y":
                    self.config.set('credentials', 'client_id', client_id)
                    self.config.set('credentials', 'client_secret', client_secret)
                    break

            reply = self.get_input("Do you have an access and refresh token available? (y/N): ")
            if reply == "y":
                while True:
                    access_token = self.get_input("Enter your access token: ")
                    refresh_token = self.get_input("Enter your refresh token: ")
                    reply = self.get_input(
                        "You entered access token {0} and refresh token {1}".format(access_token, refresh_token) +
                        ". Are these correct? (y/N): ")
                    if reply == "y":
                        self.config.set('credentials', 'access_token', access_token)
                        self.config.set('credentials', 'refresh_token', refresh_token)
                        break

            self.write_ini_file()

        # Point our config parser at the ini file.
        self.config.read(self.ini_path)

    def initialize_client(self):
        assert self.config is not None, "Out-of-order initialization: initialize_config must precede initialize_client."

        try:
            self.client = ImgurClient(self.config.get('credentials', 'client_id'),
                                      self.config.get('credentials', 'client_secret'))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError) as e:
            self.log("Error when parsing config from {0}: {1}: {2}.".format(self.ini_path, str(e), str(e.args)),
                     "Error")
            raise

        # Auth verification loop.
        while True:
            # Check to make sure we have access and refresh tokens; if not, have the user go through token creation.
            if not (self.config.has_option('credentials', 'access_token') and
                    self.config.has_option('credentials', 'refresh_token')):
                        self.get_new_auth_info()  # Automatically checks client credential validity.

            # Use the access and refresh tokens read from the file / imported through account authorization.
            self.client.set_user_auth(self.config.get('credentials', 'access_token'),
                                      self.config.get('credentials', 'refresh_token'))

            # Verify that the access/refresh tokens we were supplied with are valid.
            try:
                self.client.get_account('me')
            except ImgurClientError as e:
                if str(e) == "(400) Error refreshing access token!":
                    self.log("The supplied access and refresh tokens were invalid.", "Error")
                    self.config.remove_option('credentials', 'access_token')
                    self.config.remove_option('credentials', 'refresh_token')
            else:
                break

    # Static helper methods.
    @staticmethod
    def get_input(string):
        """ Get input from console regardless of python 2 or 3
        From ImgurPython's examples/helpers.py file. Imported to enable 2.x and 3.x Python compatibility.

        :type string: str
        :return: The user's inputted string.
        """
        # noinspection PyBroadException
        try:
            return raw_input(string)
        except:
            return input(string)

    @staticmethod
    def get_raw_config_parser():
        """ Create a config parser for reading INI files
        From ImgurPython's examples/helpers.py file. Imported to enable 2.x and 3.x Python compatibility.
        Modified to return a RawConfigParser to enable remove_option.

        :return: The output of ConfigParser.ConfigParser() or configparser.ConfigParser() depending on Python version.
        """
        # noinspection PyBroadException
        try:
            # noinspection PyUnresolvedReferences
            import ConfigParser
            return ConfigParser.RawConfigParser()
        except:
            # noinspection PyUnresolvedReferences
            import configparser
            return configparser.RawConfigParser()

    @staticmethod
    def ensure_dir_in_cwd_exists(directory):
        """ Guarantees that the given directory exists by creating it if not extant.
        Note that this removes all slashes and other filesystem-used characters from the passed-in directory parameter,
        and as such will only ever create directories in the current working directory.

        :param directory: str
        :return: The full OS-normalized path to the directory with no trailing slash.
        """

        # TODO: Is stripping out sensitive characters the best way to handle it, or should we assume the user knows
        # ..... what they're doing?

        path = os.path.join(os.getcwd(), directory.translate(None, ImgurBot.restricted_filesystem_chars))
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                print("Error creating directory {0}: {1}: {2}.".format(path, str(e), str(e.args[0])))
                raise

        assert os.path.exists(path), "ensure_dir_in_cwd_exists: Directory {0} not found after creation.".format(path)
        return path

    @staticmethod
    def process_comment(comment):
        """Takes a string of arbitrary length and processes it into comment chunks that meet Imgur's 180-character
        requirement.

        If the string is <= 180 characters in length, it is returned as-is.
        If it is greater, it is broken up into a list of substrings such that each substring plus an indexing suffix
        totals no more than 180 characters in length.

        :param comment: A string of arbitrary length.
        :type comment: str
        :return: A list of strings.
        """

        # TODO: Break at syllable boundary. If no valid syllable immediately before 180, break at whitespace. If no
        # ..... valid whitespace within X characters of 180-character boundary, break at 180-character boundary.
        # TeX has a useful hyphenation algorithm that we might be able to incorporate here.

        comment_list = []

        # If the comment fits within one comment block, return as-is.
        if len(comment) <= 180:
            comment_list.append(comment)
            return comment_list

        # Calculate out the total number of comment blocks needed.
        suffix = ImgurBot.calculate_number_of_comment_chunks(comment)
        suffix_length = len(str(suffix))

        # Append each comment (with " index/total" appended to it) to the comment_list.
        iterations = 0
        while len(comment) > 0:
            iterations += 1
            # Magic number explanation: 180 characters - (len(" ") + len("/")) = 178 characters
            max_len = int((180 - len(" /")) - math.ceil(math.log10(iterations + 1)) - suffix_length)
            comment_list.append(comment[0:max_len] + " " + str(iterations) + "/" + str(suffix))
            comment = comment[max_len:]

        # Sanity check: We're not doing something like 4/3 or 2/3
        assert iterations == suffix

        return comment_list

    @staticmethod
    def calculate_number_of_comment_chunks(comment):
        """Calculate the number of substrings generated from spitting the given comment string into Imgur-length strings
        of length <= 180. Includes calculation to allow each string to have a suffix that indicates its index and the
        total number of substrings calculated.

        Accelerated pre-calculation available for strings <= 171936 characters in length. For the sake of
        completeness, brute-force calculation is performed on strings greater than that length.

        Note: Explanations for pre-calculated magic numbers are provided in comments preceding the number's use.
        """

        # Obtain the length of the comment, pre-formatted as a float to avoid truncation errors later.
        length = float(len(comment))

        # 1584 = 9 chunks * (180 characters - len(" 1/9"))
        if length <= 1584:
            return int(math.ceil(length / 176))

        # 17235 = 9 * (180 - len(" 1/99")) + (99 - 9) * (180 - len(" 10/99"))
        if length <= 17235:
            # 1575 = 9 * (180 - len(" 1/99"))
            # 174 = 180 - len(" 10/99")
            return int(9 + math.ceil((length - 1575) / 174))

        # 171936 = 9 * (180-len(" 1/999")) + (99-9) * (180-len(" 10/999")) + (999-99) * (180-len(" 100/999"))
        if length <= 171936:
            # 17136 = 9 * (180-len(" 1/999")) + (99-9) * (180-len(" 10/999"))
            # 172 = 180 - len(" 100/999")
            return int(9 + 90 + math.ceil((length - 17136) / 172))

        # Someone's given us a string that needs to be broken up into 1000 or more substrings...
        # Reserve 4 characters for the total and begin brute-force calculating how many substrings we'll need to hold
        #  the entirety of the comment. If we have more than 9999 substrings required, reserve 5 characters and start
        #  over, etc.

        # TODO: This was written for the sake of completeness, but is it even desirable to have this happen?
        # ..... maybe we should raise an exception instead.

        iterations = 0
        reserved = 4
        while True:
            iterations += 1

            # Calculate the maximum allowable length for this comment chunk.
            # Magic number explanation: 180 - (len(" ") + len("/")) = 178
            max_len = int(178 - math.ceil(math.log10(iterations + 1)) - reserved)

            # Ending case: The remaining text is less than or equal to our maximum length.
            if length <= max_len:
                return iterations

            # Edge case: We require more space to write the count of the substrings than is reserved.
            if math.ceil(math.log10(iterations + 1)) > reserved:
                reserved += 1  # Increment our reservation.
                iterations = 0
                length = len(comment)  # Start over.
            else:
                length -= max_len
