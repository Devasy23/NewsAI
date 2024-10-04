import json
import os
import re
import sys
from datetime import datetime

import praw
from dotenv import load_dotenv

from src.utils.dbconnector import (find_documents, find_one_document,
                                   insert_document)
from src.utils.logger import setup_logger

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))

# Import setup_logger from utils

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
REDDIT_CACHE_COLLECTION = "reddit_cache"  # MongoDB collection for cache
REDDIT_POSTS_COLLECTION = "reddit_posts"


def remove_emoji(string):
    """
    Removes all emojis from the given string.

    The emojis are removed using a regular expression. The regular expression is
    based on the Unicode ranges for emojis.

    Args:
        string (str): The string to remove emojis from.

    Returns:
        str: The string with all emojis removed.
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002500-\U00002BEF"  # chinese char
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", string)


def clean_content(text):
    # Remove @mentions replace with blank
    """
    This function takes in a string and removes @mentions, #, RT, hyperlinks, and the : character.
    It also removes emojis from the string.
    """
    text = re.sub(r"@[A-Za-z0–9]+", "", text)
    text = re.sub(r"#", "", text)  # Remove the '#' symbol, replace with blank
    text = re.sub(r"RT[\s]+", "", text)  # Removing RT, replace with blank
    text = re.sub(r"https?:\/\/\S+", "", text)  # Remove the hyperlinks
    text = re.sub(r":", "", text)  # Remove :
    return remove_emoji(text)


def fetch_cached_posts(keyword):
    """
    Fetches cached posts from the database for a given keyword.

    Args:
        keyword (str): The keyword to search for.

    Returns:
        list: A list of posts if cached posts are found, otherwise None.
    """
    cache_entry = find_one_document(
        REDDIT_CACHE_COLLECTION, {"keyword": keyword})
    if cache_entry and "post_ids" in cache_entry:
        post_ids = cache_entry["post_ids"]
        # Retrieve the posts using the list of post IDs
        return list(find_documents(REDDIT_POSTS_COLLECTION, {"id": {"$in": post_ids}}))
    return None


def update_cache(keyword, post_ids):
    """
    Updates the cache with the given list of post IDs for the given keyword.

    Args:
        keyword (str): The keyword to update the cache for.
        post_ids (list): List of post IDs to update the cache with.
    """
    insert_document(REDDIT_CACHE_COLLECTION, {
                    "keyword": keyword, "post_ids": post_ids})


def fetch_reddit_posts_by_keyword(keyword, limit=10, to_json=True):
    """
    Fetches Reddit posts containing the given keyword.

    Args:
        keyword (str): The keyword to search for in Reddit posts.
        limit (int, optional): The number of posts to fetch. Defaults to 10.
        to_json (bool, optional): Whether to store the results in a JSON file. Defaults to True.

    Returns:
        List[Dict]: A list of dictionaries containing the post data.
    """
    cached_posts = fetch_cached_posts(keyword)
    if cached_posts:
        logger.info(
            f"Cache hit for keyword: {keyword}. Returning cached data.")
        return cached_posts[:limit]


def clean_content(content: str) -> str:
    """
    Clean a string by replacing carriage returns and newlines with spaces and then removing excessive spaces.

    Args:
        content (str): The string to clean.

    Returns:
        str: The cleaned string.
    """
    if not isinstance(content, str):
        raise ValueError("Input must be a string.")
    cleaned_content = content.replace("\r", " ").replace("\n", " ")
    # Remove excessive spaces (multiple spaces turned into a single space)
    cleaned_content = " ".join(cleaned_content.split())
    return cleaned_content


def fetch_reddit_posts_by_keyword(keyword, limit=10, to_json=True):
    """
    Fetches Reddit posts containing the given keyword.

    Args:
        keyword (str): The keyword to search for in Reddit posts.
        limit (int, optional): The number of posts to fetch. Defaults to 10.
        to_json (bool, optional): Whether to store the results in a JSON file. Defaults to True.

    Returns:
        List[Dict]: A list of dictionaries containing the post data.
    """
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
                logger.error(
                    f"Error inserting post ID {post.id} into MongoDB: {str(e)}"
                )

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
