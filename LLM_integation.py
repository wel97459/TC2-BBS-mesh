import time
from groq import Groq
import requests
import re
from meshtastic import BROADCAST_NUM
import configparser
import logging

from command_handlers import handle_help_command
from utils import send_message, update_user_state, get_node_id_from_num, get_node_long_name

config_file = 'config.ini'

class llm_config:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.API_key = self.config.get('groq_llm', 'api', fallback=None),

class NodeChatLLMHistory:
    def __init__(self):
        self.node_history = {}

    def send(self, message, sender_node_id):
        if sender_node_id not in self.node_history:
            self.node_history[sender_node_id] = []
        self.node_history[sender_node_id].append(message)

    def get_history(self, sender_node_id):
        return self.node_history.get(sender_node_id, [])

    def delete_history(self, sender_node_id):
        if sender_node_id in self.node_history:
            del self.node_history[sender_node_id]

node_llm_chat_history = NodeChatLLMHistory()
config = llm_config()

client = Groq(api_key=config.API_key)


def send_LLM_reply(interface, user_message, sender_node_id):
    destid = get_node_id_from_num(sender_node_id, interface)
    longName = get_node_long_name(destid, interface)
    msg=[
        {"role": "system", "content": "You are a helpful assistant, bandwidth is limited so keep the replys short. The users handel is {longName}."}
    ]

    node_llm_chat_history.send({"role": "user", "content": user_message}, sender_node_id)
    conversation_history = node_llm_chat_history.get_history(sender_node_id)
    msg.extend(conversation_history)

    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=msg,
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
        )
    
    node_llm_chat_history.send({"role": "assistant", "content": completion.choices[0].message.content}, sender_node_id)
    send_message(completion.choices[0].message.content, sender_node_id, interface)

def handle_LLM_command(sender_id, interface):
    response = "LLM Chat\nUse the word END to end the chat.\nAnd the word clear to start a new chat history."
    send_message(response, sender_id, interface)
    send_LLM_reply(interface, "*User has enter chat.", sender_id)
    update_user_state(sender_id, {'command': 'LLM_CHAT', 'step': 1})

def handle_LLM_steps(sender_id, message, step, interface):
    if step == 1:
        if message.lower() == "end":
            send_LLM_reply(interface, "*User is leaving chat.", sender_id)
            node_llm_chat_history.delete_history(sender_id)
            handle_help_command(sender_id, interface, 'utilities')
        elif message.lower() == "clear":
            send_LLM_reply(interface, "*User is clearing chat history.", sender_id)
            node_llm_chat_history.delete_history(sender_id)
        else:
            send_LLM_reply(interface, message, sender_id)