import ConfigParser
import sqlite3
import datetime
import os

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError


class ImgurBot:
    """
    A class to implement a simple bot for interfacing with Imgur.
    """
    version = "0.1"

    def __init__(self, name="ImgurBot", testing_mode=False):
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

        # Set the bot's name (defaults to ImgurBot).
        # TODO: Sanitize so we don't get unexpected behavior when using this in filesystem paths.
        self.name = name

        self.testing_mode = testing_mode

        if self.testing_mode:
            print("Testing mode enabled; performing early termination of __init__.")
            return

        # Initialize the logfile for writing.
        self.initialize_logging()

        # Set up the SQLite database.
        self.initialize_database()

        # Set up for ConfigParser.
        self.initialize_config()

        # Initialize the client and perform authentication.
        self.initialize_client()

    def __del__(self):
        """Deconstruct the ImgurBot."""

        # Disconnect from Imgur if necessary.
        # TODO: Figure out if this is actually necessary.

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
        Also prints the message to stdout.

        :param prefix: A string to prepend to the passed string. Defaults to the current date and time.
        :type message: str
        :type prefix: str
        """
        assert self.logfile is not None, "Out-of-order call: initialize_logging must be called before log."

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
        """ Purge the 'seen' table.

        :param force: True to skip verification message.
        :type force: bool
        """
        assert self.db is not None, "Out-of-order call: initialize_database must be called before reset_seen."

        if not force:
            response = self.get_input("Are you sure you want to delete the contents of the Seen table? (y/N): ")
            if response != 'y':
                print("Canceling reset_seen.")
                return

        self.log("Dropping 'Seen' table and recreating with no data.")
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
                    # TODO: Interactive credential correction.
                    self.log("Your initial client credentials were invalid. Correct them in " + self.ini_path + ".")
                    raise

        self.log("Access and refresh token obtained.")
        # noinspection PyTypeChecker
        self.config.set('credentials', 'access_token', credentials['access_token'])
        # noinspection PyTypeChecker
        self.config.set('credentials', 'refresh_token', credentials['refresh_token'])

        if no_file_write:
            return

        self.log("Writing tokens to " + self.ini_path + ".")

        try:
            with open(self.ini_path, 'w') as ini_file:
                self.config.write(ini_file)
        except IOError as e:
            self.log("Error in writing access and refresh tokens to " + self.ini_path + ": " +
                     str(e) + ": " + str(e.args[0]))
            self.log("Please manually add these tokens to the .ini file:")
            # noinspection PyTypeChecker
            self.log("access_token = " + credentials['access_token'])
            # noinspection PyTypeChecker
            self.log("refresh_token = " + credentials['refresh_token'])
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
                self.log("Creating database at " + self.db_path + ".")

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
            # TODO: Refactor this so instead of creating a blank file it interactively creates the correct file.
            self.config.add_section('credentials')

            self.log("No .ini file was found. Beginning interactive creation.")
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

            self.log("Writing new config to " + self.ini_path + ".")

            try:
                with open(self.ini_path, 'w') as ini_file:
                    self.config.write(ini_file)
            except IOError as e:
                self.log("Error when writing file " + self.ini_path + ": " + str(e) + ": " + str(e.args))
                self.log("For your reference, your tokens are: ")
                self.log("client_id = " + client_id)
                self.log("client_secret = " + client_secret)
                self.log("access_token = " + access_token)
                self.log("refresh_token = " + refresh_token)
                raise

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

        # Check to make sure we have access and refresh tokens; if not, have the user go through token creation.
        if not (self.config.has_option('credentials', 'access_token') and
                self.config.has_option('credentials', 'refresh_token')):
            self.get_new_auth_info()

        # Use the access and refresh tokens read from the file / imported through account authorization.
        self.client.set_user_auth(self.config.get('credentials', 'access_token'),
                                  self.config.get('credentials', 'refresh_token'))

        # TODO: Figure out how to verify that all the tokens here are valid.

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

        :return: The output of ConfigParser.ConfigParser() or configparser.ConfigParser() depending on Python version.
        """
        # noinspection PyBroadException
        try:
            # noinspection PyUnresolvedReferences
            import ConfigParser
            return ConfigParser.ConfigParser()
        except:
            # noinspection PyUnresolvedReferences
            import configparser
            return configparser.ConfigParser()

    @staticmethod
    def ensure_dir_in_cwd_exists(directory):
        """ Guarantees that the given directory exists by creating it if not extant. Exits on failure.
        Note that this removes all slashes from the passed-in directory parameter, and as such will only ever create
        directories in the current working directory.

        :param directory: str
        :return: The full OS-normalized path to the directory with no trailing slash.
        """
        path = os.path.normpath(os.getcwd() + "/" + directory.translate(None, "/\\"))
        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                print("Error creating directory " + path + ": " + str(e) + ":" + str(e.args[0]))
                print("Terminating program.")
                exit(0)

        assert os.path.exists(path), "ensure_dir_in_cwd_exists: Directory %s not found even after creation" % path
        return path
