import os

import pandas as pd
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from src.utils.logger import setup_logger

logger = setup_logger()

# Load environment variables
load_dotenv()


def get_mongo_client():
    """
    Connects to MongoDB and returns the database object.

    Uses environment variables for connection:
        MONGO_USERNAME: username for MongoDB authentication
        MONGO_PASSWORD: password for MongoDB authentication
        MONGO_DB_NAME: name of the database to connect to

    Returns:
        pymongo.database.Database: the connected database object

    Raises:
        Exception: if connection fails
    """
    try:
        mongo_uri = f"mongodb+srv://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@devasy23.a8hxla5.mongodb.net/?retryWrites=true&w=majority&appName=Devasy23"
        db_name = os.getenv("DB_NAME")
        client = MongoClient(
            mongo_uri, socketTimeoutMS=60000, connectTimeoutMS=60000)
        db = client[db_name]
        logger.info("Successfully connected to MongoDB.")
        return db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


def content_manager(article_id, required_fields):
    """
    Checks if the specified fields are present in the database for the given article_id.

    Args:
        article_id (str): The ID of the article to check.
        required_fields (list): A list of fields to check for presence (e.g., ["content", "summary", "keywords", "sentiment"]).

    Returns:
        dict: A dictionary with the status of each field (True if present, False if not).
    """
    # Connect to the MongoDB
    db = get_mongo_client()
    collection = db["News_Articles"]

    # Query the document by article_id
    article = collection.find_one({"id": article_id})

    # Check for the required fields
    field_status = {
        field: field in article and bool(article[field]) for field in required_fields
    }

    return field_status


def insert_document(collection_name, document):
    """
    Inserts a document into the given collection.

    Args:
        collection_name (str): The name of the collection.
        document (dict): The document to be inserted.

    Returns:
        str: The ID of the inserted document.

    Raises:
        Exception: If there is an error inserting the document.
    """
    db = get_mongo_client()
    collection = db[collection_name]
    try:
        result = collection.insert_one(document)
        logger.info(f"Document inserted with ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        logger.error(f"Failed to insert document: {e}")
        raise


def find_one_document(collection_name, query):
    """
    Finds a single document in the given MongoDB collection using the given query.

    Args:
        collection_name (str): The name of the collection.
        query (dict): The query to select documents.

    Returns:
        dict: The selected document.

    Raises:
        Exception: If there is an error finding the document.
    """
    db = get_mongo_client()
    collection = db[collection_name]
    try:
        result = collection.find_one(query)
        return result
    except Exception as e:
        logger.error(f"Failed to find document: {e}")
        raise


def append_to_document(collection_name, query, update_data):
    """
    Appends new data to an existing document in the MongoDB collection.

    Args:
        collection_name (str): The name of the MongoDB collection.
        query (dict): The query to select the document to update.
        update_data (dict): The new data to be appended to the document.

    Returns:
        int: The number of documents updated.
    """
    db = get_mongo_client()
    collection = db[collection_name]
    try:
        result = collection.update_one(query, {"$set": update_data})
        if result.modified_count > 0:
            logger.info(f"Document updated successfully.")
        else:
            logger.warning(
                f"No document matched the query. No update performed.")
        return result.modified_count
    except Exception as e:
        logger.error(f"Failed to update document: {e}")
        raise


def find_documents(collection_name, query):
    """
    Finds documents in the given MongoDB collection using the given query.

    Args:
        collection_name (str): The name of the MongoDB collection.
        query (dict): The query to select documents.

    Returns:
        list: A list of documents found by the query.

    Raises:
        Exception: If there is an error finding documents.
    """
    db = get_mongo_client()
    collection = db[collection_name]
    try:
        documents = collection.find(query)
        return documents
    except Exception as e:
        logger.error(f"Failed to find documents: {e}")
        raise


def fetch_and_combine_articles(collection_name, article_ids):
    """
    Fetches documents from the given MongoDB collection using the given IDs and combines them into a Pandas DataFrame.

    Args:
        collection_name (str): The name of the MongoDB collection.
        article_ids (List[str]): List of IDs of the articles to fetch and combine.

    Returns:
        pd.DataFrame: A Pandas DataFrame containing the combined documents.

    Raises:
        Exception: If there is an error fetching and combining the documents.
    """
    db = get_mongo_client()
    collection = db[collection_name]

    # Debug log to check what is being passed to the function
    logger.debug(f"Received article_ids: {article_ids}")

    try:
        # Ensure article_ids is a list and not None

        # Query MongoDB to find documents by their IDs
        query = {"id": {"$in": article_ids}}
        documents = collection.find(query)
        logger.info(f"Fetched {documents} documents for the given IDs.")

        # Prepare a list of documents
        docs = []
        for doc in documents:
            doc["_id"] = str(
                doc["_id"]
            )  # Convert ObjectId to string for easier handling
            docs.append(doc)

        # Convert the list of documents to a DataFrame
        df = pd.DataFrame(docs)
        print(df.drop(columns=["_id", "id"], inplace=True))
        if df.empty:
            logger.warning("No documents found for the provided article IDs.")
        else:
            logger.info("Successfully converted documents to DataFrame.")
            logger.debug(df.columns)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch and combine articles: {e}")
        raise

def fetch_and_combine_reddit_posts_and_comments(post_ids):
    """
    Fetches Reddit posts and their comments from the MongoDB database using the given post IDs and combines them into a Pandas DataFrame.

    Args:
        post_ids (List[str]): List of post IDs to fetch and combine.

    Returns:
        pd.DataFrame: A Pandas DataFrame containing the combined posts and comments.

    Raises:
        Exception: If there is an error fetching and combining the documents.
    """
    db = get_mongo_client()
    posts_collection = db["reddit_posts"]

    try:
        # Fetch posts by their IDs
        query = {"id": {"$in": post_ids}}
        posts_cursor = posts_collection.find(query)
        
        posts = []
        for post in posts_cursor:
            post["_id"] = str(post["_id"])
            posts.append(post)
        return posts

    except Exception as e:
        logger.error(f"Failed to fetch and combine Reddit posts and comments: {e}")
        raise
