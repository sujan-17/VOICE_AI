class MemoryManager:
    def __init__(self):
        # Dictionary structure: { "session_id": [messages] }
        self.sessions = {}

    def get_history(self, session_id):
        return self.sessions.get(session_id, [])

    def add_message(self, session_id, role, content):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append({"role": role, "content": content})
        
        # Keep only the last 10 messages to save tokens/memory
        if len(self.sessions[session_id]) > 10:
            self.sessions[session_id] = self.sessions[session_id][-10:]