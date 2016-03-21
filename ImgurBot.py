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

    def __init__(self, name="ImgurBot"):
        """Initialize the ImgurBot.

        :type name: str

        This constructor performs the following tasks:
            - Sets up the bot with the passed name, or ImgurBot by default
            - Prepares the logfile for writing (log/BOTNAME.txt)
            - Prepares the database for access (db/BOTNAME.db)
            - Checks for appropriate access credentials (cfg/BOTNAME.ini)
            - Walks user through obtaining access and refresh tokens if not supplied
            - Initializes the Imgur client (self.client)
        """

        # Set the bot's name (defaults to ImgurBot).
        # TODO: Sanitize so we don't get unexpected behavior when using this in filesystem paths.
        self.name = name

        # Create our directories and set up our paths.
        self.log_dir = ImgurBot.ensure_dir_in_cwd_exists("log")
        self.log_path = os.path.normpath(self.log_dir + "/" + self.name + ".log")

        self.ini_dir = ImgurBot.ensure_dir_in_cwd_exists("ini")
        self.ini_path = os.path.normpath(self.ini_dir + "/" + self.name + ".ini")

        self.db_dir = ImgurBot.ensure_dir_in_cwd_exists("db")
        self.db_path = os.path.normpath(self.db_dir + "/" + self.name + ".db")

        # Initialize the logfile for writing.
        self.logfile = open(self.log_path, 'a')
        self.log("Welcome to ImgurBot v" + self.version + ".")

        # Set up the SQLite database.
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
            exit(0)

        # Create our ConfigParser in preparation for reading or writing the .ini file.
        self.config = self.get_config_parser()
        self.config.read(self.ini_path)

        # Test if config file exists. If not, create a template .ini file and terminate.
        if not os.path.isfile(self.ini_path):
            self.create_new_ini()
            exit(0)

        # Initialize the client and perform authentication.
        try:
            self.client = ImgurClient(self.config.get('credentials', 'client_id'),
                                      self.config.get('credentials', 'client_secret'))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError) as e:
            self.log("Error when parsing config from " + self.ini_path + ": " + str(e) + ": " + str(e.args) +
                     ". Terminating.")
            exit(0)

        # Check to make sure we have access and refresh tokens; if not, have the user go through token creation.
        if not (self.config.has_option('credentials', 'access_token') and
                self.config.has_option('credentials', 'refresh_token')):
            self.get_new_auth_info()

        # Use the access and refresh tokens read from the file / imported through account authorization.
        self.client.set_user_auth(self.config.get('credentials', 'access_token'),
                                  self.config.get('credentials', 'refresh_token'))

        # TODO: Figure out how to verify that all the tokens here are valid.

    def __del__(self):
        """Deconstruct the ImgurBot."""

        # Disconnect from Imgur if necessary.
        # TODO: Figure out if this is actually necessary.

        # Clean up the SQLite database. Note: This does not perform a commit.
        self.db.close()

        # Close the logfile.
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
        print(message)
        self.logfile.write(prefix + message + '\n')

    def mark_seen(self, post_id):
        """Marks a post identified by post_id as seen.
        :type post_id: str
        """

        if self.has_seen(post_id):
            self.log("Error: Attempting to mark as seen a post that already exists in the Seen table.")
            return

        # TODO: Sanitize input into SQL.
        self.db.execute("INSERT INTO Seen(id) VALUES ('" + post_id + "')")
        self.db.commit()

    def has_seen(self, post_id):
        """Boolean check for if the bot has seen the post identified by post_id.
        :type post_id: str

        :return: True if post_id in DB, false otherwise.
        """

        # TODO: Sanitize input into SQL.
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM Seen WHERE id = '" + post_id + "'")
        for row in cursor:
            return True
        return False

    def reset_seen(self):
        """ Purge the 'seen' table.
        """
        # TODO: Should I add some sort of 'are you sure you want to do this' verification? Or a backup?
        self.log("Dropping 'Seen' table and recreating with no data.")
        cursor = self.db.cursor()
        cursor.execute("DROP TABLE IF EXISTS Seen")
        cursor.execute("CREATE TABLE Seen(id TEXT PRIMARY KEY NOT NULL)")
        self.db.commit()

    def create_new_ini(self):
        """ Creates a template config file for the user to fill out. """

        # TODO: Refactor this so instead of creating a blank file it interactively creates the correct file.

        self.log("Creating blank config file at " + self.ini_path + ".")
        self.log("Please fill this file with your credentials and try again.")

        self.config.add_section('credentials')
        self.config.set('credentials', 'client_id', 'YOUR_CLIENT_ID_HERE')
        self.config.set('credentials', 'client_secret', 'YOUR_CLIENT_SECRET_HERE')
        self.config.set('credentials', 'access_token', 'YOUR_ACCESS_TOKEN_HERE')
        self.config.set('credentials', 'refresh_token', 'YOUR_REFRESH_TOKEN_HERE')

        try:
            with open(self.ini_path, 'w') as ini_file:
                self.config.write(ini_file)
        except IOError as e:
            self.log("Error when writing file " + self.ini_path + ": " + str(e) + ": " + str(e.args))

    def get_new_auth_info(self):
        """ Interfaces with Imgur and the user to obtain access and refresh tokens.
        """
        # No access or refresh tokens. Send them to the auth workflow.
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
                    self.log("Your initial client credentials were invalid. Correct them in " + self.ini_path + ".")
                    self.log("Terminating program.")
                    exit(0)

        self.log("Access and refresh token obtained. Writing them to " + self.ini_path + ".")
        self.config.set('credentials', 'access_token', credentials['access_token'])
        self.config.set('credentials', 'refresh_token', credentials['refresh_token'])

        try:
            with open(self.ini_path, 'w') as ini_file:
                self.config.write(ini_file)
        except IOError as e:
            self.log("Error in writing access and refresh tokens to " + self.ini_path + ": " +
                     str(e) + ": " + str(e.args[0]))
            self.log("Please manually add these tokens to the .ini file:")
            self.log("access_token = " + credentials['access_token'])
            self.log("refresh_token = " + credentials['refresh_token'])
            self.log("Program will now terminate.")
            exit(0)

    # Static helper methods.
    @staticmethod
    def get_input(string):
        """ Get input from console regardless of python 2 or 3
        From ImgurPython's examples/helpers.py file. Imported to enable 2.x and 3.x Python compatibility.

        :type string: str
        :return: The user's inputted string.
        """
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
            import ConfigParser
            return ConfigParser.ConfigParser()
        except:
            import configparser
            return configparser.ConfigParser()

    @staticmethod
    def ensure_dir_in_cwd_exists(directory):
        """ Guarantees that the given directory exists by creating it if not extant. Exits on failure.

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
        return path
