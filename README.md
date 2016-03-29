# ImgurBot
This is an experiment in creating a bot framework for Imgur in Python. It is built off of the imgurpython module, and is designed to handle the background / administrative tasks involved in bot creation to accelerate bot deployment.

Current Features:
-----------------
-	Interactive bot registration and authentication workflow.
-	SQLite DB that tracks seen posts.
-	Splitting and indexing of over-length comment strings.

Planned Features:
-----------------
-	Rate-limited posting of comments.
-	Ability to queue up actions with delays to prevent exceeding of rate limit.