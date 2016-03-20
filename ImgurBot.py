import ConfigParser
import sqlite3
import datetime
import os

from imgurpython import ImgurClient


class ImgurBot:
    """A class to implement a simple bot for interfacing with Imgur."""
    version = "0.1"

    def __init__(self, name="ImgurBot"):
        """Initialize the ImgurBot.
        :type name: str
        """

        # Set the bot's name (defaults to ImgurBot).
        self.name = name

        # Initialize the logfile for writing.
        self.logfile = open(os.path.normpath(os.getcwd() + "/log/" + self.name + ".log"), 'a')
        self.log("Welcome to ImgurBot v" + self.version + ". Initializing bot '" + self.name + "'.")

        # Set up the SQLite database.
        try:
            # Inform the user that a new .db file is being created (if not previously extant).
            db_path = os.path.normpath(os.getcwd() + "/db/" + self.name + ".db")
            if not os.path.isfile(db_path):
                self.log("- Creating database at " + db_path + ".")
            else:
                self.log("- Connecting to database at " + db_path + ".")

            self.db = sqlite3.connect(db_path)
            self.db.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY NOT NULL)")

        except sqlite3.Error as e:
            self.log("Error in DB setup: " + str(e) + ": " + str(e.args) + ". Terminating.")
            if self.db:
                self.db.close()
            exit(0)

        # Create our ConfigParser in preparation for reading or writing the .ini file.
        self.config = ConfigParser.ConfigParser()

        cfg_path = os.path.normpath(os.getcwd() + "/cfg/" + self.name + ".ini")
        self.config.read(cfg_path)

        # Test if config file exists. If not, create a template .ini file and terminate.
        if not os.path.isfile(cfg_path):
            print '\n'
            self.log("Creating blank config file at " + cfg_path + ".")
            self.log("Please fill this file with your credentials and try again.")

            self.config.add_section('credentials')
            self.config.set('credentials', 'client_id', 'YOUR_CLIENT_ID_HERE')
            self.config.set('credentials', 'client_secret', 'YOUR_CLIENT_SECRET_HERE')
            self.config.set('credentials', 'access_token', 'YOUR_ACCESS_TOKEN_HERE')
            self.config.set('credentials', 'refresh_token', 'YOUR_REFRESH_TOKEN_HERE')

            try:
                with open(cfg_path, 'w') as inifile:
                    self.config.write(inifile)
            except IOError as e:
                self.log("Error when writing file " + cfg_path + ": " + str(e) + ": " + str(e.args))
            exit(0)

        # Initialize the client and perform authentication.
        self.log("- Reading config information from " + cfg_path + ".")
        try:
            self.client = ImgurClient(self.config.get('credentials', 'client_id'),
                                      self.config.get('credentials', 'client_secret'),
                                      self.config.get('credentials', 'access_token'),
                                      self.config.get('credentials', 'refresh_token'))
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError) as e:
            self.log("Error when parsing config from " + cfg_path + ": " + str(e) + ": " + str(e.args) +
                     ". Terminating.")
            exit(0)

        self.log("Initialization complete.\n")

    def __del__(self):
        """Deconstruct the ImgurBot."""
        self.log("Finalizing bot '" + self.name + "'.")

        # Disconnect from Imgur if necessary.

        # Clean up the SQLite database.
        self.db.close()

        # Close the logfile.
        self.log("Finalization complete.\n")
        self.logfile.close()

    # External / Imgur-facing methods
    def post_comment(self, gallery_id, comment_text):
        """Posts the given string as a comment to the passed gallery id. If the string is too long for a single comment,
        it is automatically split at the 180-character boundary.

        TODO: Intelligent splitting on whitespace, indexing split comments with numbers.
        :type gallery_id: str
        :type comment_text: str
        """

    # Internal / non Imgur-facing methods
    def log(self, message, prefix='['+datetime.datetime.now().strftime("%c")+']: '):
        """Writes the given message to $name.log, prefixed with current date and time. Ends with a newline.
        Also prints the message to stdout.

        :param prefix: A string to prepend to the passed string. Defaults to the current date and time.
        :type message: str
        :type prefix: str
        """
        print message
        self.logfile.write(prefix + message + '\n')

    def mark_seen(self, post_id):
        """Marks a post identified by post_id as seen.
        :type post_id: str
        """

    def has_seen(self, post_id):
        """Boolean check for if the bot has seen the post identified by post_id.
        :type post_id: str

        :returns: true if post_id in DB, false otherwise.
        """
