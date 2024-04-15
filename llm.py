import logging
import os
import shlex
import requests
from dotenv import load_dotenv
#from openai import OpenAI
#import bittensor as bt
from typing import List, Optional
import asyncio 
import pprint
import json
import re
from datetime import date
from langchain_community.utilities import GoogleSerperAPIWrapper


load_dotenv()
os.environ["SERPER_API_KEY"] = "2cc36227196e0737cee7e369042275db14f184bc" # roguetensors

logging.basicConfig(level=logging.DEBUG)
search = GoogleSerperAPIWrapper()


def call_subnet(message_content, history):
    prompt = message_content
    datas = []

    for i in history:
        datas.append({'source':i.author.name,'context':i.content})

    output = asyncio.run(run(prompt, datas))
    logging.debug([r.to_dict()["response"] for r in output])
    
    responses = []
    count = 1

    for i in output:
        if i.response and i.response["response"]:
            response_str = f"Response {count}: {i.response['response']}"
            responses.append(response_str)
            count += 1

    final_output = "\n".join(responses)
    logging.debug("Subnet Response: " + final_output)
   
    return final_output


def search_with_sources(query):
    search_data = search._google_serper_api_results(
                query,
                gl="us",
                hl="en",
                num=10,
                tbs=None,
                search_type="search"
            )
    result = search._parse_results(search_data)
    sources = ""
    for item in search_data["organic"]:
        sources += f"{item['link']}\n"
    return result, sources



def extract_queries(queries):
    return [line.split('. ', 1)[-1].strip('"') for line in queries.strip().split('\n') if line]

def get_google_questions(ticket_data):
    prompt = f"""
    """
    query_prompt = f"""
    SYSTEM:
    You are an IT assistant. You will be receiving questions from a tech support IT Specialist. Your job is to determine up to 5 google queries that could be performed by either the client or IT Specialist that could help provide information to solve the clients needs. ALWAYS provide the queries in a numbered list. DO NOT provide any additional information besides the Google queries. The Title is more important than the Body, but there might be necessary details in the body. Ignore things like "I am sending this from my phone".
    --------------------------------------
    {ticket_data}

    Google queries:
    """
    logging.debug(f"prompt: {query_prompt}")
    result = query_llm(query_prompt)

    logging.debug(f"result: {result}")
    return extract_queries(result['responses'])

def get_responses_to_google_questions(google_questions):
    context = ""
    for question in google_questions:
        logging.debug(f"question: {question}")
        context += search.run(question) + "\n"
    return context

def get_responses_to_google_questions_with_sources(google_questions):
    context = ""
    sources = set()  # Use a set directly for unique sources
    for question in google_questions:
        logging.debug(f"question: {question}")
        result, source = search_with_sources(question)
        sources.add(source)
        context += result + "\n"
    return context, list(sources)  # Convert sources back to a list if needed


def google_needed(prompt):
    query_prompt = f"""
    SYSTEM:
    You are an IT assistant. You will be receiving questions from a tech support IT Specialist. Your job is to determine if you require additional information by searching google to answer the question. Reply 'yes', if doing a google search is necessary and 'no' if doing a google search is not necessary. ALWAYS provide either 'yes' or 'no'. DO NOT provide any additional information besides 'yes' or 'no'.
    --------------------------------------
    {prompt}

    Response:
    """
    response = query_llm(query_prompt)
    response = response['responses']
    logging.debug(f"google questions required: {response}")

    if "yes" in response.lower():
        return True
    elif "no" in response.lower():
        return False
    else:
        return None

def google_needed_with_questions(prompt):
    query_prompt = f"""
    SYSTEM:
    You are an IT assistant. You will be receiving questions from a tech support IT Specialist. Your job is to determine if you require additional information by searching google to answer the question. You do not need to google everything. Try to come up with the minimum required google queries to get the information you need. Today's date is {date.today()}. Check your current date and if you need up to date information then you SHOULD perform a google query. If the user is having any sort of technical issues with their computer, phone, internet, email, etc, ALWAYS perform a search. If the question is referencing any software or device, assume that it is something related to the IT specialist. REMEMBER, you DO NOT have up to date information, so be sure to search if you need to. For example, if someone asks you for the LATEST information on a topic or place, ALWAYS search it. General (non-technical) questions may need a google search is the question requires live or up to date information.
    If doing a google search is necessary then return 'yes' as 'Google required:' and determine as few google queries as possible that could be performed by either the client or IT specialist that could help provide information to solve the client's needs. Never produce more than 5 google queries. ALWAYS provide the queries in a numbered list. DO NOT provide any additional information besides the Google queries. Google searching is expensive, so NEVER perform a google search for generic conversation such as 'hey are you there?'.
    If a google search is not needed then ONLY return 'no'.
    Your answer should conform to the provided ANSWER TEMPLATE.
    --------------------------------------
    ANSWER TEMPLATE:
    Google required: 'yes' or 'no'

    Google queries: if google required then numbered list of queries
    --------------------------------------
    {prompt}
    """
    logging.debug(f"google question prompt: {query_prompt}")
    response = query_llm(query_prompt)
    response = response['responses']
    logging.debug(f"google questions required: {response}")

    questions = []
    if re.search(r"google.*?required:\s*'?no", response, re.IGNORECASE | re.DOTALL):
        needed = False
    else:
        logging.debug("YOU GOT HERE!!!")
        needed = True
        matches = re.search(r"google.*?queries:\s*(.*)?", response, re.IGNORECASE | re.DOTALL)
        logging.debug(f"matches: {matches}")
        if matches:
            questions = extract_queries(matches.group(0))
        else:
            questions = extract_queries(response)

        logging.debug(f"questions: {questions}")

    return [needed, questions]


def query_llm(prompt, data=[]):
    data = {'prompt': prompt, 'datas': []}
    response = requests.post("https://roguetensor.com/bitagent/v1/api", json=data)
    response_data = json.loads(response.text)

    return response_data


def call(user_text):
    message = re.sub(r"<@\w+>", "", user_text)
    full_message = f'User: {message}'
    prompt = f"""
SYSTEM:
You are a helpful technical assistant. Answer the users questions thoroughly and succintly.
Your job is to converse with the IT specialist to help them solve the problem. Keep in mind that the IT specialist has expertise in this field, so speak with them at the appropriate level. Try to maintain conversation that makes sense.
--------------------------------------
User: Hello, is anyone there?
Assistant: Hello, yeah I am here and ready to assist.
User: {message}
Assistant:
    """
    #response = call_subnet(prompt, [])
    goog_needed, questions = google_needed_with_questions(full_message)
    #if google_needed(prompt):
        #logging.debug("We must google")
        #questions = get_google_questions(prompt)
    sources = []
    if goog_needed:
        logging.debug(f"google questions: {questions}")
        google_context = get_responses_to_google_questions(questions)
        # google_context, sources = get_responses_to_google_questions_with_sources(questions)
        prompt = f"""
        SYSTEM:
        You are an IT assistant. Your job is to converse with the IT specialist to help them solve the problem. Keep in mind that the IT specialist has expertise in this field, so speak with them at the appropriate level. You will be given helpful context that you can use if you need to. Try to maintain conversation that makes sense.
        --------------------------------------
        HELPFUL CONTEXT - Use if needed
        {google_context}
        --------------------------------------
        {user_text}

        Answer:
        """
        
    logging.debug(f"final_prompt: {prompt}")
    response = query_llm(prompt)
    response_text = response['responses']
    logging.debug(response)
    logging.debug(f"response: {response_text}")

    if sources:
        response_text += "\nSources:\n"
        for source in sources:
            response_text += f"{source}\n"
        
    return response_text