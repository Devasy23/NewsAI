import json
import os
import re
import sys
from datetime import datetime

import praw
from dotenv import load_dotenv

from src.utils.logger import setup_logger

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))

# Import setup_logger from utils
from src.utils.logger import setup_logger
from src.utils.dbconnector import insert_document, find_documents, find_one_document

load_dotenv()

reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENTID"),
    client_secret=os.getenv("REDDIT_SECRETKEY"),
    user_agent="{0} by u/{1}".format(
        os.getenv("REDDIT_APPNAME"), os.getenv("REDDIT_USERNAME")
    ),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
)

logger = setup_logger()

# constants
COMMENT_COUNT = 10
TIME_SLOT = "all"  # Time filter can be 'all', 'day', 'week', 'month', 'year'
REDDIT_CACHE_COLLECTION = 'reddit_cache'  # MongoDB collection for cache
REDDIT_POSTS_COLLECTION = 'reddit_posts'

def remove_emoji(string):
    emoji_pattern = re.compile("["
    u"\U0001F600-\U0001F64F" # emoticons
    u"\U0001F300-\U0001F5FF" # symbols & pictographs
    u"\U0001F680-\U0001F6FF" # transport & map symbols
    u"\U0001F1E0-\U0001F1FF" # flags (iOS)
    u"\U00002500-\U00002BEF" # chinese char
    u"\U00002702-\U000027B0"
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    u"\U0001f926-\U0001f937"
    u"\U00010000-\U0010ffff"
    u"\u2640-\u2642"
    u"\u2600-\u2B55"
    u"\u200d"
    u"\u23cf"
    u"\u23e9"
    u"\u231a"
    u"\ufe0f" # dingbats
    u"\u3030"
    "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', string)
def clean_content(text):
    text = re.sub(r'@[A-Za-z0–9]+', '', text) #Remove @mentions replace with blank
    text = re.sub(r'#', '', text) #Remove the '#' symbol, replace with blank
    text = re.sub(r'RT[\s]+', '', text) #Removing RT, replace with blank
    text = re.sub(r'https?:\/\/\S+', '', text) #Remove the hyperlinks
    text = re.sub(r':', '', text) # Remove :
    return remove_emoji(text)

def fetch_cached_posts(keyword):
    """Retrieve cached posts for a keyword using the cache collection."""
    cache_entry = find_one_document(REDDIT_CACHE_COLLECTION, {"keyword": keyword})
    if cache_entry and "post_ids" in cache_entry:
        post_ids = cache_entry["post_ids"]
        # Retrieve the posts using the list of post IDs
        return list(find_documents(REDDIT_POSTS_COLLECTION, {"id": {"$in": post_ids}}))
    return None

def update_cache(keyword, post_ids):
    """Update the cache with new post IDs for a keyword."""
    insert_document(REDDIT_CACHE_COLLECTION, {"keyword": keyword, "post_ids": post_ids})

def fetch_reddit_posts_by_keyword(keyword, limit=10, to_json=True):
    cached_posts = fetch_cached_posts(keyword)
    if cached_posts:
        logger.info(f"Cache hit for keyword: {keyword}. Returning cached data.")
        return cached_posts

    try:
        # Search for posts containing the keyword
        search_results = reddit.subreddit("all").search(
            query=keyword,
            sort="relevance",  # Sort results by relevance
            time_filter=TIME_SLOT,
            limit=limit,
        )

        posts = []
        post_ids = []
        for post in search_results:
            if not post or post.stickied:  # Skip if post is None or stickied
                continue

            post_data = {
                "title": post.title,
                "id": post.id,
                "content": clean_content(post.selftext),
                "url": post.url,
                "created_utc": datetime.utcfromtimestamp(post.created_utc).isoformat(),
                "discussion_topic": keyword,
                "top_comments": [],
            }

            # Fetch and process top comments
            try:
                comments = post.comments.list()  # Get all comments
                sorted_comments = sorted(
                    comments,
                    key=lambda c: c.score if hasattr(c, "score") else 0,
                    reverse=True,
                )
                top_comments = sorted_comments[:COMMENT_COUNT]

                post_data["top_comments"] = [
                    {
                        "comment_id": comment.id,
                        "comment_content": clean_content(comment.body),
                        "comment_score": comment.score,
                        "comment_created_utc": datetime.utcfromtimestamp(
                            comment.created_utc
                        ).isoformat(),
                    }
                    for comment in top_comments
                    if hasattr(comment, "body")
                ]
            except Exception as e:
                logger.error(
                    f"Error fetching comments for post ID {post.id}: {str(e)}")

            try:
                insert_document(REDDIT_POSTS_COLLECTION, post_data)
                logger.info(f"Inserted post ID {post.id} into MongoDB")
                post_ids.append(post.id)
            except Exception as e:
                logger.error(f"Error inserting post ID {post.id} into MongoDB: {str(e)}")

            posts.append(post_data)
            logger.debug(f"Post Title: {post.title} Saved to MongoDB")

        # Update the cache with the new post IDs
        update_cache(keyword, post_ids)

        return posts

    except Exception as e:
        logger.error(f"Error fetching posts: {type(e).__name__} - {str(e)}")
        return []


if __name__ == "__main__":
    # Example usage: searching for posts about "python"
    fetch_reddit_posts_by_keyword(keyword="python", limit=5)
