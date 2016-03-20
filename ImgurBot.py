import ConfigParser
import sqlite3
import datetime

from imgurpython import ImgurClient


# Ideas: When splitting comments, add in dashes at syllable breaks (or break around words).
# Optionally, add a 1/x 2/x etc counter to the comments.


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
        self.logfile = open(self.name + ".txt", 'a')
        self.log("Welcome to ImgurBot v" + self.version + ". Initializing bot '" + self.name + "'.")

        # Set up the SQLite database.
        try:
            self.db = sqlite3.connect(self.name + '.db')
            self.db.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY NOT NULL)")

        except sqlite3.Error, e:
            self.log("Error in DB setup: " + e.args[0] + ". Terminating.")
            if self.db:
                self.db.close()
            exit(0)

        # Import data from the config_file (BOTNAME.ini).
        self.config = ConfigParser.ConfigParser()
        self.config.read(self.name + ".ini")

        # Initialize the client and perform authentication.
        self.client = ImgurClient(self.config.get('credentials', 'client_id'),
                                  self.config.get('credentials', 'client_secret'),
                                  self.config.get('credentials', 'access_token'),
                                  self.config.get('credentials', 'refresh_token'))

        # Close the config_file.
        self.config.close()

        self.log("Initialization complete.")

    def __del__(self):
        """Deconstruct the ImgurBot."""
        self.log("Finalizing bot '" + self.name + "'.")

        # Disconnect from Imgur if necessary.

        # Clean up the SQLite database.
        self.db.close()

        # Close the logfile.
        self.log("Finalization complete.")
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
        """Writes the given message to $name.txt, prefixed with current date and time.
        :param prefix: A string to prepend to the passed string. Defaults to the current date and time.
        :type message: str
        """
        self.logfile.write(prefix + message)

    def mark_seen(self, post_id):
        """Marks a post identified by post_id as seen.
        :type post_id: str
        """

    def has_seen(self, post_id):
        """Boolean check for if the bot has seen the post identified by post_id.
        :type post_id: str

        :returns: true if post_id in DB, false otherwise.
        """
