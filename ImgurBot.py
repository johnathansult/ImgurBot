import ConfigParser
import sqlite3
import datetime
import os
import shutil

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError


class ImgurBot:
    """
    A class to implement a simple bot for interfacing with Imgur.
    """
    version = "0.1"

    # From https://en.wikipedia.org/wiki/Filename#Reserved_characters_and_words.
    # Space not included since it's safe in these use cases. Other characters are probably safe too, but YMMV.
    # TODO: Figure out if any other characters can be pruned from this list for enhanced user-friendliness.
    restricted_filesystem_chars = "/\\?*%:|\"<>."

    def __init__(self, name="ImgurBot", testing_mode=False, debug_mode=False):
        """Initialize the ImgurBot.

        :type name: str

        This constructor performs the following tasks:
            - Sets up the bot with the passed name, or ImgurBot by default
            - Prepares the logfile for writing (log/BOTNAME.txt)
            - Prepares the database for access (db/BOTNAME.db)
            - Checks for appropriate access credentials (cfg/BOTNAME.ini)
            - Walks user through obtaining access and refresh tokens if not supplied
            - Initializes the Imgur client (self.client)

        This constructor has a testing_mode option which sets the name and then exits. This is designed to enable unit
        testing of other initialization measures (database, config). Please make sure you understand the flow of the
        program and what must be initialized in what order before you invoke this option; limited protection against
        out-of-order initialization has been added, but they are by no means comprehensive.
        """

        # Table of instance variables: These are pre-defined here so that the initialize_x() methods can be used to
        #    init the bot without loss of clarity.
        self.log_dir = None
        self.log_path = None
        self.logfile = None
        self.db_dir = None
        self.db_path = None
        self.db = None
        self.ini_dir = None
        self.ini_path = None
        self.config = None
        self.client = None

        # Set the bot's name (defaults to ImgurBot). Remove restricted filesystem characters while we're at it.
        self.name = name.translate(None, ImgurBot.restricted_filesystem_chars)

        self.testing_mode = testing_mode
        self.debug_mode = debug_mode

        if self.testing_mode:
            print("Testing mode enabled; forcing debug_mode and performing early termination of __init__.")
            self.debug_mode = True
            return

        # Initialize the logfile for writing.
        self.initialize_logging()
        if name != self.name:
            self.debug_log("Disallowed characters removed from bot name ('" + name + "' > '" + self.name + "').")

        # Set up the SQLite database.
        self.initialize_database()

        # Set up for ConfigParser.
        self.initialize_config()

        # Initialize the client and perform authentication.
        self.initialize_client()

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
            self.log("Successful termination of ImgurBot.")
            self.logfile.close()

    # External / Imgur-facing methods
    def post_comment(self, gallery_id, comment_text):
        """Posts the given string as a comment to the passed gallery id. If the string is too long for a single comment,
        it is automatically split at the 180-character boundary.

        TODO: Intelligent splitting on whitespace, indexing split comments with numbers.
        :type gallery_id: str
        :type comment_text: str
        """
        # TODO: Create.

    # Internal / non Imgur-facing methods
    def log(self, message, prefix='['+datetime.datetime.now().strftime("%c")+']: '):
        """Writes the given message to $name.log, prefixed with current date and time. Ends with a newline.
        Also prints the message to the screen.

        :param prefix: A string to prepend to the passed string. Defaults to the current date and time.
        :type message: str
        :type prefix: str
        """
        assert self.logfile is not None, "Out-of-order call: initialize_logging must be called before log."

        print(message)
        self.logfile.write(prefix + message + '\n')

    def debug_log(self, message, prefix='[' + datetime.datetime.now().strftime("%c") + ']: DEBUG: '):
        """If self.debug_mode is True: Writes the given message to $name.log, prefixed with current date and time.
        Ends with a newline. Also prints the message to the screen.

        :param prefix: A string to prepend to the passed string. Defaults to the current date and time.
        :type message: str
        :type prefix: str
        """
        if self.debug_mode:
            assert self.logfile is not None, "Out-of-order call: initialize_logging must be called before debug_log."

            print(message)
            self.logfile.write(prefix + message + '\n')

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
        """ Delete and re-create the 'seen' table in the database.

        :param force: True to skip verification message.
        :type force: bool
        """
        # TODO: Should this method be repurposed to only delete all rows and not remake the table? User may wish to
        # ..... have a customized 'seen' table, in which case remaking it with default config is sub-optimal.

        assert self.db is not None, "Out-of-order call: initialize_database must be called before reset_seen."

        if not force:
            response = self.get_input("Are you sure you want to delete and recreate the Seen table? (y/N): ")
            if response != 'y':
                print("Canceling reset_seen.")
                return

        self.debug_log("Dropping 'Seen' table and recreating with no data.")
        cursor = self.db.cursor()
        cursor.execute("DROP TABLE IF EXISTS Seen")
        cursor.execute("CREATE TABLE Seen(id TEXT PRIMARY KEY NOT NULL)")
        self.db.commit()

    def get_new_auth_info(self, no_file_write=False):
        """ Interfaces with Imgur and the user to obtain access and refresh tokens, then writes them to the .ini file.
        """
        # No access or refresh tokens. Send them to the auth workflow.
        assert self.config is not None, "Out-of-order call: initialize_config must be called before get_new_auth_info."
        assert self.client is not None, "Out-of-order call: initialize_client must be called before get_new_auth_info."

        print("")
        self.log("You need to supply your PIN to obtain access and refresh tokens.")
        self.log("Go to the following URL: " + format(self.client.get_auth_url('pin')))

        credentials = []

        # Loop and obtain the correct PIN.
        while True:
            try:
                pin = self.get_input("Enter the PIN code from the above URL: ")
                credentials = self.client.authorize(pin, 'pin')
                break
            except ImgurClientError as e:
                if str(e) == "(400) Invalid Pin":
                    print("\nYou have entered an invalid pin. Try again.")
                elif str(e) == "(400) The client credentials are invalid":
                    # offer choice: delete credentials and recreate?
                    result = self.get_input("Your client credentials were incorrect. " +
                                            "Would you like to go through interactive bot registration? (y/N): ")
                    if result == 'y':
                        self.log("Moving " + self.ini_path + " to " + self.ini_path + ".old.")
                        shutil.copy(self.ini_path, self.ini_path + ".old")
                        os.remove(self.ini_path)
                        self.initialize_config()
                        self.initialize_client()
                        return
                    else:
                        self.log("Your initial client credentials were invalid. Correct them in " + self.ini_path + ".")
                        raise

        self.log("Access and refresh token successfully obtained.")
        # noinspection PyTypeChecker
        self.config.set('credentials', 'access_token', credentials['access_token'])
        # noinspection PyTypeChecker
        self.config.set('credentials', 'refresh_token', credentials['refresh_token'])

        if no_file_write:
            return

        self.write_ini_file()

    def write_ini_file(self):
        self.debug_log("Writing config file at " + self.ini_path + ".")
        try:
            with open(self.ini_path, 'w') as ini_file:
                self.config.write(ini_file)
        except IOError as e:
            self.log("Error when writing config file at " + self.ini_path + ": " + str(e) + ": " + str(e.args))
            self.log("Please manually create the file with the following contents: \n")
            self.log("[credentials]")
            self.log("client_id = " + self.config.get('credentials', 'client_id'))
            self.log("client_secret = " + self.config.get('credentials', 'client_secret'))
            self.log("access_token = " + self.config.get('credentials', 'access_token'))
            self.log("refresh_token = " + self.config.get('credentials', 'refresh_token'))
            raise

    # Methods used to initialize the bot.
    def initialize_logging(self):
        """Forces the creation of the log directory, then creates/opens the logfile there. Also initializes the (self.)
        log_dir, log_path and logfile variables."""

        # Broken out from __init__ to aid in testing.
        self.log_dir = ImgurBot.ensure_dir_in_cwd_exists("log")
        self.log_path = os.path.normpath(self.log_dir + "/" + self.name + ".log")

        self.logfile = open(self.log_path, 'a')

        self.log("Welcome to ImgurBot v" + self.version + ".")

    def initialize_database(self):
        self.db_dir = ImgurBot.ensure_dir_in_cwd_exists("db")
        self.db_path = os.path.normpath(self.db_dir + "/" + self.name + ".db")

        try:
            # Inform the user that a new .db file is being created (if not previously extant).
            if not os.path.isfile(self.db_path):
                self.debug_log("Creating database at " + self.db_path + ".")

            # Connect and ensure that the database is set up properly.
            self.db = sqlite3.connect(self.db_path)
            cursor = self.db.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS Seen(id TEXT PRIMARY KEY NOT NULL)")

        except sqlite3.Error as e:
            self.log("Error in DB setup: " + str(e) + ": " + str(e.args) + ". Terminating.")
            if self.db:
                self.db.close()
            raise

    def initialize_config(self):
        self.ini_dir = ImgurBot.ensure_dir_in_cwd_exists("ini")
        self.ini_path = os.path.normpath(self.ini_dir + "/" + self.name + ".ini")

        # Generate our config parser.
        self.config = self.get_config_parser()

        # Test if config file exists. If not, create a template .ini file and terminate.
        if not os.path.isfile(self.ini_path):
            self.config.add_section('credentials')

            self.debug_log("No .ini file was found. Beginning interactive creation.")
            print("To proceed, you will need a client_id and client_secret tokens, which can be obtained from Imgur at")
            print("the following website: https://api.imgur.com/oauth2/addclient")
            print("")

            client_id = None
            client_secret = None
            access_token = None
            refresh_token = None

            while True:
                client_id = self.get_input("Enter your client_id: ")
                client_secret = self.get_input("Enter your client_secret: ")
                reply = self.get_input("You entered client_id " + client_id + " and client_secret " + client_secret +
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
                        "You entered access token " + access_token + " and refresh token " + refresh_token +
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
            self.log("Error when parsing config from " + self.ini_path + ": " + str(e) + ": " + str(e.args) +
                     ". Terminating.")
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
                    self.log("The supplied access and refresh tokens were invalid. Try again.")
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
    def get_config_parser():
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
        """ Guarantees that the given directory exists by creating it if not extant. Exits on failure.
        Note that this removes all slashes from the passed-in directory parameter, and as such will only ever create
        directories in the current working directory.

        :param directory: str
        :return: The full OS-normalized path to the directory with no trailing slash.
        """
        path = os.path.normpath(os.getcwd() + "/" + directory.translate(None, ImgurBot.restricted_filesystem_chars))
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                print("Error creating directory " + path + ": " + str(e) + ":" + str(e.args[0]))
                print("Terminating program.")
                exit(0)

        assert os.path.exists(path), "ensure_dir_in_cwd_exists: Directory %s not found even after creation" % path
        return path
