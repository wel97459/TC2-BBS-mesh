import logging
import time

user_states = {}


def update_user_state(user_id, state):
    user_states[user_id] = state


def get_user_state(user_id):
    return user_states.get(user_id, None)


def send_message(message, destination, interface):

    chunks = split_into_chunks(message)
    for i, chunk in enumerate(chunks):
        try:
            d = interface.sendText(
                text=chunk,
                destinationId=destination,
                wantAck=True,
                wantResponse=False
            )
            destid = get_node_id_from_num(destination, interface)
            chunk = chunk.replace('\n', '\\n')
            logging.info(f"Sending message to user '{get_node_short_name(destid, interface)}' ({destid}) with sendID {d.id}: \"{chunk}\"")
        except Exception as e:
            logging.info(f"REPLY SEND ERROR {e.message}")
        time.sleep(2)


def get_node_info(interface, short_name):
    nodes = [{'num': node_id, 'shortName': node['user']['shortName'], 'longName': node['user']['longName']}
             for node_id, node in interface.nodes.items()
             if node['user']['shortName'].lower() == short_name]
    return nodes


def get_node_id_from_num(node_num, interface):
    for node_id, node in interface.nodes.items():
        if node['num'] == node_num:
            return node_id
    return None


def get_node_short_name(node_id, interface):
    node_info = interface.nodes.get(node_id)
    if node_info:
        return node_info['user']['shortName']
    return None

def get_node_long_name(node_id, interface):
    node_info = interface.nodes.get(node_id)
    if node_info:
        return node_info['user']['longName']
    return None


def send_bulletin_to_bbs_nodes(board, sender_short_name, subject, content, unique_id, bbs_nodes, interface):
    message = f"BULLETIN|{board}|{sender_short_name}|{subject}|{content}|{unique_id}"
    for node_id in bbs_nodes:
        send_message(message, node_id, interface)


def send_mail_to_bbs_nodes(sender_id, sender_short_name, recipient_id, subject, content, unique_id, bbs_nodes,
                           interface):
    message = f"MAIL|{sender_id}|{sender_short_name}|{recipient_id}|{subject}|{content}|{unique_id}"
    logging.info(f"SERVER SYNC: Syncing new mail message {subject} sent from {sender_short_name} to other BBS systems.")
    for node_id in bbs_nodes:
        send_message(message, node_id, interface)


def send_delete_bulletin_to_bbs_nodes(bulletin_id, bbs_nodes, interface):
    message = f"DELETE_BULLETIN|{bulletin_id}"
    for node_id in bbs_nodes:
        send_message(message, node_id, interface)


def send_delete_mail_to_bbs_nodes(unique_id, bbs_nodes, interface):
    message = f"DELETE_MAIL|{unique_id}"
    logging.info(f"SERVER SYNC: Sending delete mail sync message with unique_id: {unique_id}")
    for node_id in bbs_nodes:
        send_message(message, node_id, interface)


def send_channel_to_bbs_nodes(name, url, bbs_nodes, interface):
    message = f"CHANNEL|{name}|{url}"
    for node_id in bbs_nodes:
        send_message(message, node_id, interface)

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