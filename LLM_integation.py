import time
from groq import Groq
import requests
import re
from meshtastic import BROADCAST_NUM

from command_handlers import handle_help_command
from utils import send_message, update_user_state

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

api_key = "";
client = Groq(api_key=api_key)

def split_into_chunks(
    s: str,
    max_bytes: int = 200,
    split_chars: list = None
) -> list:
    """
    Splits a string into chunks of up to max_bytes, trying to split at contextually
    appropriate points (spaces, punctuation). Maintains valid UTF-8 encoding.
    """
    if split_chars is None:
        split_chars = [' ', '\n', '.', ',', '!', '?', ';', ':', '\t', '(', ')', '[', ']', '{', '}']

    split_bytes = [ord(c) for c in split_chars if len(c.encode('utf-8')) == 1]
    encoded = s.encode('utf-8')
    chunks = []
    start = 0
    total_bytes = len(encoded)

    while start < total_bytes:
        end = min(start + max_bytes, total_bytes)
        
        # Ensure we don't check beyond the byte array
        safe_end = min(end, total_bytes - 1)
        
        # Backtrack to avoid splitting multi-byte characters
        while safe_end > start and (encoded[safe_end] & 0b11000000) == 0b10000000:
            safe_end -= 1

        # Find last valid split character
        split_pos = -1
        for i in range(min(safe_end, total_bytes-1), start-1, -1):
            if encoded[i] in split_bytes:
                split_pos = i
                break

        # Determine actual chunk end
        if split_pos != -1:
            actual_end = split_pos + 1
        else:
            actual_end = safe_end

        # Final validation to prevent empty/infinite loops
        if actual_end <= start:
            actual_end = min(start + max_bytes, total_bytes)
            while actual_end > start and actual_end < total_bytes and (encoded[actual_end] & 0b11000000) == 0b10000000:
                actual_end -= 1
            actual_end = max(actual_end, start + 1)

        chunks.append(encoded[start:actual_end].decode('utf-8'))
        start = actual_end

    return chunks


def send_LLM_reply(interface, user_message, sender_node_id):
    msg=[
        {"role": "system", "content": "You are a helpful assistant, bandwidth is limited so keep the replys short."}
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

    chunks = split_into_chunks(completion.choices[0].message.content)
    for i, chunk in enumerate(chunks):
        send_message(chunk, sender_node_id, interface)

def handle_LLM_command(sender_id, interface):
    response = "LLM Chat\nUse the word END to end the chat."
    send_message(response, sender_id, interface)
    update_user_state(sender_id, {'command': 'LLM_CHAT', 'step': 1})

def handle_LLM_steps(sender_id, message, step, interface):
    if step == 1:
        if message.lower() == "end":
            send_LLM_reply(interface, "*User is leaving chat.", sender_id)
            node_llm_chat_history.delete_history(sender_id)
            handle_help_command(sender_id, interface, 'utilities')
        elif message.lower() == "clear":
            send_LLM_reply(interface, "*user is clearing chat history.", sender_id)
            node_llm_chat_history.delete_history(sender_id)
        else:
            send_LLM_reply(interface, message, sender_id)