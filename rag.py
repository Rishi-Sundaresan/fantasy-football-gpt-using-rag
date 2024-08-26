#!/usr/bin/env python
# coding: utf-8

# ### Create RAG App

# In[227]:
OPENAI_API_KEY = "HIDDEN"
HUGGINGFACE_API_TOKEN = "HIDDEN"


import requests
import praw
from datetime import datetime
import numpy
import jax.numpy as jnp
from openai import OpenAI
import re
import ast
import json
import Levenshtein
from huggingface_hub import login, InferenceApi

def parse_info_from_string(input_string):
    # Define regex patterns for matching the list and the sentence
    list_pattern = r'1\)\s*(\[\s*[^]]+\s*\])'
    sentence_pattern = r'2\)\s*(.*)'

    # Search for the list part using regex
    list_match = re.search(list_pattern, input_string)
    if list_match:
        list_str = list_match.group(1)
        # Convert the list string to a Python list
        try:
            parsed_list = ast.literal_eval(list_str)
        except:
            print("Could not parse player names in input string.")
            return []
            
    else:
        parsed_list = []

    # Search for the sentence part using regex
    sentence_match = re.search(sentence_pattern, input_string)
    if sentence_match:
        sentence_part = sentence_match.group(1).strip()
    else:
        sentence_part = ""

    return parsed_list, sentence_part

def is_near_match(a, b, max_distance_ratio=0.2):
    """
    Checks if string 'a' exists in string 'b' within a scaled allowed edit distance.
    
    :param a: The string to search for.
    :param b: The text in which to search.
    :param max_distance_ratio: The maximum allowed Levenshtein distance as a ratio of the length of 'a'.
    :return: True if a match is found, otherwise False.
    """
    a,b = a.lower(), b.lower()
    len_a = len(a)
    max_distance = int(max_distance_ratio * len_a)
    
    # Loop through the text in sliding windows of the length of string 'a'
    for i in range(len(b) - len_a + 1):
        substring = b[i:i+len_a]
        # Calculate the Levenshtein distance between the substring and 'a'
        if Levenshtein.distance(a, substring) <= max_distance:
            return True
    
    return False


# In[228]:


client = OpenAI(api_key=OPENAI_API_KEY)
print("------")
print("HuggingFace Authentication.")
login(HUGGINGFACE_API_TOKEN)
sentence_similarity = InferenceApi(repo_id='sentence-transformers/paraphrase-MiniLM-L3-v2')
print("------")


# In[229]:


class FantasyRAG:
    def reformat_query_using_gpt(self, input_text, task = ""):
        # Define the prompt to guide the OpenAI model
        _DEFAULT_TASK = """Format this query into the following 2 part answer: 
        
       1)  [list of football players names in the query (if any), each in quotation marks]: news or injury information. 
       2)  Summarize the query more succintly. 


    *Note that in your response, use the official name of each player online in ESPN, even though the query may have them abbreviated or mispelled.
    """ 
        
        if not task:
            task = _DEFAULT_TASK
            
        prompt = (
            f"{task}\n\n"
            f"Detailed Query: {input_text}\n\n"
        )
        
        # Request completion from OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return parse_info_from_string(response.choices[0].message.content.strip('"'))

    def get_top_n_most_similar_texts(self, cosine_similarities, retrieved_texts, n, min_similarity):
        # Cosine similarities and retrieved texts must be aligned.
        sorted_similar_indices = jnp.argsort(cosine_similarities)[::-1] # sorted in descending order
        sorted_similarities = cosine_similarities[sorted_similar_indices]

        if min_similarity != None:
            valid_mask = sorted_similarities >= min_similarity
            sorted_similar_indices = sorted_similar_indices[valid_mask]
        top_n_indices = sorted_similar_indices[:n]
        return [retrieved_texts[i] for i in top_n_indices]
        
    
    def get_n_most_similar_texts_using_similarity_transformer(self, query, retrieved_texts, n, min_similarity=None):
        print("Call to Sentence Similarity")
        cosine_similarities = jnp.array(sentence_similarity(inputs={"sentences": retrieved_texts, "source_sentence":query}))
        print("Response")
        return self.get_top_n_most_similar_texts(cosine_similarities, retrieved_texts, n, min_similarity)

    
    def get_n_most_similar_texts_using_embedding_model(self, query, retrieved_texts, n, embeddings_fn, min_similarity=None):
        if not retrieved_texts:
            print("No Retrieved Texts")
            return []
        if n > len(retrieved_texts):
            print("Not enough retrieved texts")
            return []

        embeddings = self.embeddings_fn([query] + retrieved_texts)
        embeddings_cpu = [embedding.cpu().numpy() for embedding in embeddings]
        query_embedding = jnp.array(embeddings_cpu[0])
        texts_embedding = jnp.array(embeddings_cpu[1:])

        # Cosine Similarity Calculations
        norm_query, norm_texts = jnp.linalg.norm(query_embedding), jnp.linalg.norm(texts_embedding, axis=1)
        
        dot_product = jnp.dot(texts_embedding, query_embedding.T)
        cosine_similarities = dot_product / (norm_texts * norm_query)
        return self.get_top_n_most_similar_texts(cosine_similarities, retrieved_texts, n, min_similarity)

rag = FantasyRAG()


# In[230]:


def retrieve_relevant_reddit_comments(clean_query):
    with open('reddit_posts.json', 'r') as file:
        _reddit_posts = json.load(file)
    title_list = [title for title in _reddit_posts]
    most_similar_titles = rag.get_n_most_similar_texts_using_similarity_transformer(clean_query, title_list, 20)
    all_comments_from_similar_titles = []
    for title in most_similar_titles:
        all_comments_from_similar_titles.extend(_reddit_posts[title])
    print("Retrieved reddit comments.")
    return rag.get_n_most_similar_texts_using_similarity_transformer(clean_query, all_comments_from_similar_titles, 20)


# In[231]:


def retrieve_relevant_player_news(clean_query, player_list):
    with open('player_news.json', 'r') as file:
        _player_news = json.load(file)
    # First check if there are name matches:
    news_info = []
    for article in _player_news['player_news']:
        for player_name in player_list:
            if is_near_match(player_name, article):
                news_info.append(article)
    # Then check for semantic similarity.
    news_info.extend(rag.get_n_most_similar_texts_using_similarity_transformer(clean_query, _player_news['player_news'], 5, min_similarity = 0.55))
    print("Retrieved player news.")
    return news_info


# In[232]:


def send_gpt_request_with_context(reddit_comments, player_news_info, prompt, conversation_history):
    reddit_context = "\n\n".join(reddit_comments)
    news_context = "\n\n".join(player_news_info)

    messages = []
    # Add conversation history to the messages list
    for message in conversation_history:
        messages.append({
            "role": message['role'],
            "content": message['content']
        })
    
    gpt_input_prompt = f"""
    You are secretly Given the following context:\n\n{reddit_context}\n and player news: {news_context}: 
    \n\n, {prompt}.
    Provide a short, concise (usually <= 3 sentences), opinionated answer, and be slightly assertive. The answer should directly answer the prompt.
    Your answer should be up to date as of today's date, which is {datetime.now().date()}. Keep in mind the following:
    1) Assume the league is a redraft league (not a dynasty league) unless otherwise stated. 
    2) Usually the question will be about a specific timeframe, by default this season, which is the season with the date {datetime.now().date()},
    but the user could specify a specific week, etc:
    3) For every player mentioned in the prompt, use the context and player news to see if they are healthy or dealing with an injury.
    Remember to weight injuries heavily, as a player who is injured and/or not projected to play will not provide fantasy value until he is fully healthy.
    4) For players mentioned in the prompt, take into account their performance last season."""

    # Request to OpenAI API
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages + [{
            "role": "user",
            "content": gpt_input_prompt
        }])
        
    return response.choices[0].message.content


# In[233]:


def reply(prompt, conversation_history):
    print("--------")
    print("Prompt:", prompt)
    player_list, clean_query = rag.reformat_query_using_gpt(prompt)
    relevant_reddit_comments = retrieve_relevant_reddit_comments(clean_query)
    player_news = retrieve_relevant_player_news(clean_query, player_list)
    answer = send_gpt_request_with_context(relevant_reddit_comments, player_news, prompt, conversation_history)
    print("Answer:", answer)
    print("---------")
    return answer

# In[ ]:




