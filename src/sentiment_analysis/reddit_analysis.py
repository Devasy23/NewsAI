import asyncio
import os
import sys

from textblob import TextBlob

from src.ingestion.prawapi import fetch_reddit_posts_by_keyword
from src.utils.dbconnector import append_to_document, find_documents

sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..")))


def extract_post_content(posts):
    """
    First it concate the content of each post
    then it reduces the redunduncy from the content

    Args:
        posts (list): A list of posts
    """
    content = ""
    for post in posts:
        content += post["content"].strip()
        content += " "

    return content


def sentiment_analysis(text):
    """
    Analyzes the sentiment of the given text.

    Args:
        text (str): The text to analyze

    Returns:
        str: The sentiment of the text, either "positive", "neutral", or "negative"
    """

    analysis = TextBlob(text)
    print(analysis.sentiment.polarity)
    if analysis.sentiment.polarity > 0.25:
        return "positive"
        print("positive")
    elif analysis.sentiment.polarity < -0.25:
        return "negative"
        print("negative")
    else:
        return "neutral"
        print("neutral")


async def fetch_sentiment_analysis(content):
    """
    Asynchronously performs sentiment analysis.

    Args:
        content (str): The content to analyze.

    Returns:
        float: Sentiment score.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sentiment_analysis, content)


async def process_post(post):
    """
    Processes a single post by updating its sentiment and top comments.

    Args:
        post (dict): The post to process.

    Returns:
        dict: The updated post.
    """
    # Update post sentiment
    sentiment = await fetch_sentiment_analysis(post["content"])
    update_data = {"sentiment": sentiment}
    append_to_document("reddit_posts", {"id": post["id"]}, update_data)

    # Process top comments
    tasks = []
    for comment in post["top_comments"]:
        task = fetch_sentiment_analysis(comment["comment_content"])
        tasks.append(task)

    comment_sentiments = await asyncio.gather(*tasks)

    # Update comments with sentiment
    for comment, sentiment in zip(post["top_comments"], comment_sentiments):
        comment["comment_sentiment"] = sentiment

    update_data = {"top_comments": post["top_comments"]}
    append_to_document("reddit_posts", {"id": post["id"]}, update_data)

    return post


async def fetch_required_reddit_posts(keyword, limit):
    """
    Fetches the records from the database for the given keyword, processes them, and updates the sentiments.

    Args:
        keyword (str): The keyword to search for.
        limit (int): The number of posts to fetch.

    Returns:
        list: A list of processed documents.
    """
    # Fetch posts (assuming this is already asynchronous)
    posts = fetch_reddit_posts_by_keyword(
        keyword=keyword, limit=limit, to_json=True)

    # Process posts concurrently
    tasks = [process_post(post) for post in posts]
    processed_posts = await asyncio.gather(*tasks)
    post_ids = [post["id"] for post in processed_posts]

    return post_ids
    # return processed_posts

if __name__ == "__main__":
    posts = fetch_required_reddit_posts(
        keyword="kolkata murder case", limit=10)
    # content = extract_post_content(posts)
    # sentiment_analysis(content)
    # for post in posts:
    #     print(post["title"])
